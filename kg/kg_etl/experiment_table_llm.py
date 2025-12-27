# rag/etl/experiment_table_llm.py
"""
sections.csv를 기반으로

pmid(논문아이디), experiment_id(고유 실험 ID), experiment_index(논문 내 실험 번호),
method(방법), condition(조건),
category_parent(상위 카테고리), category_leaf(하위 카테고리),
materials(재료 문자열), equipment(장비 문자열)

형태의 실험 테이블을 생성하는 스크립트.
각 논문의 실험 정보를 OpenAI LLM으로 추출한다.

추가로:
- paper_experiments_materials.csv
    pmid, experiment_id, experiment_index, method, category_parent, category_leaf, material
- paper_experiments_equipment.csv
    pmid, experiment_id, experiment_index, method, category_parent, category_leaf, equipment

두 개의 세부 테이블도 생성한다.
"""
import argparse
from pathlib import Path
import os
import sys
import time
import json
import re

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# ─────────────────────────────────────
# 0) 경로 및 OpenAI 클라이언트 설정
# ─────────────────────────────────────

# 프로젝트 루트 추론
ROOT_DIR = Path(__file__).resolve().parents[2]

# common_experiment_categories 모듈 import 가능하도록 sys.path에 추가
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from common_experiment_categories import (
    CATEGORY_TREE,
    LEAF_TO_PARENT,
    PARENT_DEFAULT_LEAF,
    CATEGORIES_BLOCK,
)

DEBUG = False

# sections.csv / 출력 경로
SECTIONS_PATH = ROOT_DIR / "data" / "pmc_1000" / "t_sections_filtered.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "pmc_1000" / "ts_paper_experiments_table.csv"

# .env 로드
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("OPENAI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY가 .env에서 로드되지 않았습니다. .env 파일을 확인해주세요.")

client = OpenAI(api_key=api_key)

# ─────────────────────────────────────
# 1) sections.csv 로드 & 실험 섹션 필터링
# ─────────────────────────────────────
def chunk_df(df: pd.DataFrame, batch_size: int):
    """DataFrame을 batch_size 단위로 나누어 yield."""
    n = len(df)
    for i in range(0, n, batch_size):
        yield df.iloc[i : i + batch_size]


def load_sections() -> pd.DataFrame:
    if not SECTIONS_PATH.exists():
        raise FileNotFoundError(f"{SECTIONS_PATH} 가 존재하지 않습니다.")
    df = pd.read_csv(SECTIONS_PATH)
    print(f"[INFO] 전체 섹션 수: {len(df)}")
    return df


def filter_experiment_sections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Methods / Experiments / Results / Main 섹션을
    '실험 관련 섹션'으로 간주해서 필터링.
    """
    sec_cat = df["section_category"].fillna("").str.lower()
    sec_title = df["section_title"].fillna("").str.lower()

    target_cats = ["method", "methods", "experiment", "experiments"]

    mask = (
        sec_cat.isin(target_cats)
        | sec_title.str.contains("method")
        | sec_title.str.contains("experiment")
    )

    exp_df = df[mask].copy()
    print(f"[INFO] 실험 관련 섹션 수: {len(exp_df)}")
    print(f"[INFO] 실험 관련 섹션이 있는 논문 수: {exp_df['pmid'].nunique()}")
    return exp_df


def build_paper_texts(exp_df: pd.DataFrame) -> pd.DataFrame:
    """
    같은 pmid에 속한 실험 관련 섹션들의 텍스트를
    한 논문당 하나의 긴 문자열로 합친다.
    """
    exp_df = exp_df.sort_values(["pmid", "path", "section_id"])
    exp_df["section_text"] = exp_df["section_text"].fillna("").astype(str)

    grouped = (
        exp_df.groupby("pmid")["section_text"]
        .apply(lambda xs: "\n\n".join([t for t in xs if t.strip() != ""]))
        .reset_index()
        .rename(columns={"section_text": "experiment_text"})
    )

    print(f"[INFO] 실험 텍스트가 만들어진 논문 수: {len(grouped)}")
    return grouped


# ─────────────────────────────────────
# 2) LLM 프롬프트 & 호출 함수
# ─────────────────────────────────────


def build_prompt_for_table(text: str) -> str:
    return f"""
너는 생명과학/화학/바이오 논문의 실험 설계를 정리하는 전문가야.

아래 텍스트는 한 논문의 Methods/Experiments/Results 부분에서 뽑은 내용이다.
이 텍스트를 보고, 이 논문에서 수행한 "실험들"을
다음 5개 항목으로 나누어 여러 행(row)으로 정리해줘.

중요 규칙:
- 출력은 반드시 순수한 JSON 배열만 포함해야 한다.
- JSON 배열 앞뒤에 어떤 설명 문장도 붙이지 마.
- ``` 또는 ```json 같은 마크다운 코드 블록을 절대 사용하지 마.
- method, condition, category, materials, equipment 값은 모두 영어로 작성해. 한국어를 절대 사용하지 마.
- 입력 텍스트가 한국어이든 영어이든, 출력은 항상 영어로만 작성해.
- 가능한 한 실험 설정을 최대한 많이 추출하되, 서로 완전히 동일한 설정은 하나로 합쳐라.
- 실험이 명시적으로 잘 안 보이더라도, 문맥을 바탕으로 합리적으로 추론해서 작성해라.
- 정말로 실험/방법에 대한 내용이 전혀 없을 때만 빈 배열 [] 을 반환해라. 애매하면 최소 1개 이상의 실험을 만들어라.

각 행은 하나의 실험 설정을 의미하며 다음 정보를 포함해야 한다:

- method: 어떤 실험 방법/기법/모델을 사용했는지
          (예: "ELISA", "Western blot", "dose–response viability assay", "molecular docking")
- condition: 그 방법을 어떤 조건/설정/데이터 범위에서 사용했는지
             (예: "HEK293T cells treated with 0.01–100 µM compound for 48 h",
                  "C57BL/6 mice dosed at 1–50 mg/kg and monitored for 21 days")
- category: 아래 "가능한 category 라벨" 중에서
           **항상 하위 카테고리(leaf) 라벨 하나만** 선택해야 한다.

  중요:
  - 상위 카테고리(group) 이름(예: "cell_based_assays", "in_vivo_models")은 절대 사용하지 마라.
  - 반드시 들여쓰기된 하위 라벨(예: "dose_response_viability_assay") 중 하나만 선택해라.

가능한 category 라벨 (트리 구조, 예시는 다음과 같음)
- 맨 앞이 '-' 로 시작하는 줄은 상위 카테고리 이름이고,
- 그 아래 '  -' 로 시작하는 줄이 실제로 선택해야 하는 하위 카테고리 이름이다.

{CATEGORIES_BLOCK}

- materials: 주요 재료/시료/시약/데이터셋 등을 영어로 요약
             (예: "HEK293T cells, compound X, C57BL/6 mice")
- equipment: 실험에 핵심적으로 사용된 장비/플랫폼/하드웨어
             (예: "CO2 incubator, plate reader, flow cytometer, Cryo-EM")

반드시 JSON 배열(JSON array) 형태로만 답해줘.
JSON 배열 외에 어떤 텍스트도 출력하지 마.
각 원소는 다음과 같은 형태의 JSON 객체여야 한다 (예시는 영어로):

[
  {{
    "method": "dose-response viability assay",
    "condition": "HEK293T cells treated with 0.01–100 µM compound X for 48 h; EC50 estimated by nonlinear regression",
    "category": "dose_response_viability_assay",
    "materials": "HEK293T cells, compound X, culture medium",
    "equipment": "CO2 incubator, plate reader"
  }},
  {{
    "method": "molecular docking",
    "condition": "Docking performed on 500 protein–ligand complexes from the PDBbind v2019 dataset",
    "category": "molecular_docking",
    "materials": "protein–ligand structures from PDBbind v2019",
    "equipment": "docking software, GPU server"
  }}
]

아무 실험도 파악하기 어려우면 빈 배열 [] 을 반환해.

--- 텍스트 시작 ---
{text}
--- 텍스트 끝 ---
""".strip()


def _extract_json_array(content: str) -> str:
    """
    LLM이 ```json ... ``` 처럼 코드블록으로 감싸거나,
    앞뒤에 설명 텍스트를 붙여도, JSON 배열 부분만 뽑아서 반환.
    """
    if not isinstance(content, str):
        content = str(content)

    # 1) 코드블록 마크다운 제거
    content = re.sub(r"```json", "", content, flags=re.IGNORECASE)
    content = re.sub(r"```", "", content)
    content = content.strip()

    # 2) 문자열 안에서 첫 '[' 와 마지막 ']' 사이만 취함
    start = content.find("[")
    end = content.rfind("]")

    if start != -1 and end != -1 and start < end:
        content = content[start: end + 1]

    return content.strip()


def split_items(s: str) -> list[str]:
    """
    materials / equipment 같이 여러 개가 한 문자열에 들어있을 때
    콤마, 세미콜론, ' and ' 등을 기준으로 잘라서 리스트로 변환.
    """
    if not s:
        return []
    if not isinstance(s, str):
        s = str(s)

    # 쉼표, 세미콜론, ' and ' 로 분할
    parts = re.split(r"[;,]| and ", s)
    return [p.strip() for p in parts if p.strip()]


def call_llm_for_table(text: str) -> list[dict]:
    """
    experiment_text를 LLM에 보내서
    [{method, condition, category_parent, category_leaf, materials, equipment}, ...] 리스트를 받는다.
    """
    if text and len(text) > 8000:
        text = text[:8000]

    prompt = build_prompt_for_table(text)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_content = resp.choices[0].message.content
    if not isinstance(raw_content, str):
        raw_content = str(raw_content)

    if DEBUG:
        print("=== RAW LLM OUTPUT (snippet) ===")
        print(raw_content[:500])
        print("================================")

    cleaned_str = _extract_json_array(raw_content)

    try:
        data = json.loads(cleaned_str)
    except Exception as e:
        print("[WARN] JSON 파싱 실패, 원본문자열 일부:", raw_content[:200])
        print("[WARN] 정제된 문자열 일부:", cleaned_str[:200])
        raise e

    if not isinstance(data, list):
        print("[WARN] JSON 최상위가 list가 아님, 강제로 리스트로 감쌈")
        data = [data]

    cleaned: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        method = (item.get("method") or "").strip()
        condition = (item.get("condition") or "").strip()

        leaf_category = (item.get("category") or "").strip()

        # ── parent/leaf 안전 처리 ──
        if not leaf_category:
            parent_category = "other_or_not_specified"
            leaf_category = "other"
        elif leaf_category in LEAF_TO_PARENT:
            parent_category = LEAF_TO_PARENT[leaf_category]
        elif leaf_category in CATEGORY_TREE:
            # parent 이름이 들어온 경우 → 해당 parent의 기본 leaf로 교체
            parent_category = leaf_category
            leaf_category = PARENT_DEFAULT_LEAF.get(parent_category, "other")
        else:
            parent_category = "other_or_not_specified"
            leaf_category = "other"
        # ──────────────────────────

        materials = (item.get("materials") or "").strip()
        equipment = (item.get("equipment") or "").strip()

        # method/condition 둘 다 비어 있으면 버림
        if not method and not condition:
            continue

        cleaned.append(
            {
                "method": method,
                "condition": condition,
                "category_parent": parent_category,
                "category_leaf": leaf_category,
                "materials": materials,
                "equipment": equipment,
            }
        )

    return cleaned


# ─────────────────────────────────────
# 3) 메인: 논문별로 호출해서 최종 테이블 생성
# ─────────────────────────────────────


import argparse  # 파일 상단 import 구역에 추가되어 있어야 함


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="한 번에 처리할 논문(pmid) 수 (기본값: 20)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="기존 output CSV를 무시하고 처음부터 다시 처리",
    )
    args = parser.parse_args()

    batch_size = args.batch_size
    resume = not args.no_resume

    sections_df = load_sections()
    exp_sections_df = filter_experiment_sections(sections_df)
    paper_texts_df = build_paper_texts(exp_sections_df)

    # ─────────────────────────────
    # 0) 이미 처리된 pmid (resume용)
    # ─────────────────────────────
    processed_pmids: set[str] = set()

    mat_path = ROOT_DIR / "data" / "pmc_1000" / "ts_paper_experiments_materials.csv"
    eq_path = ROOT_DIR / "data" / "pmc_1000" / "ts_paper_experiments_equipment.csv"

    if resume and OUTPUT_PATH.exists():
        try:
            prev = pd.read_csv(OUTPUT_PATH, usecols=["pmid"])
            processed_pmids = set(prev["pmid"].astype(str).unique())
            print(f"[INFO] 기존 결과에서 이미 처리된 pmid 수: {len(processed_pmids)}")
        except Exception as e:
            print("[WARN] 기존 OUTPUT_PATH 읽기 실패, resume 무시:", e)

    # ─────────────────────────────
    # 1) 배치 단위로 처리
    # ─────────────────────────────
    total_papers = len(paper_texts_df)
    print(f"[INFO] 전체 실험 텍스트 논문 수: {total_papers}")
    print(f"[INFO] batch_size={batch_size}, resume={resume}")

    first_write_main = not (resume and OUTPUT_PATH.exists())
    first_write_mat = not (resume and mat_path.exists())
    first_write_eq = not (resume and eq_path.exists())

    processed_count = 0

    for batch_idx, batch_df in enumerate(chunk_df(paper_texts_df, batch_size), start=1):
        # 이미 처리한 pmid는 건너뜀
        if processed_pmids:
            batch_df = batch_df[
                ~batch_df["pmid"].astype(str).isin(processed_pmids)
            ]

        if batch_df.empty:
            continue

        print(
            f"\n[INFO] ====== 배치 {batch_idx} 시작 (논문 수: {len(batch_df)}) ======"
        )

        batch_rows: list[dict] = []
        batch_material_rows: list[dict] = []
        batch_equipment_rows: list[dict] = []

        for _, row in batch_df.iterrows():
            pmid = row["pmid"]
            text = row["experiment_text"]

            if not isinstance(text, str) or not text.strip():
                print(f"[WARN] pmid {pmid}: experiment_text 비어 있음, 건너뜀")
                continue

            print(f"[INFO] pmid {pmid} -> LLM 호출 중.")

            try:
                exp_list = call_llm_for_table(text)
            except Exception as e:
                print(f"[ERROR] pmid {pmid}: LLM 호출/파싱 실패: {e}")
                continue

            if not exp_list:
                print(f"[INFO] pmid {pmid}: 추출된 실험 없음")
                continue

            # 논문 내 실험을 1,2,3,... 순서로 index 부여
            for exp_idx, exp in enumerate(exp_list, start=1):
                method = exp["method"]
                condition = exp["condition"]
                category_parent = exp["category_parent"]
                category_leaf = exp["category_leaf"]
                materials_str = exp["materials"]
                equipment_str = exp["equipment"]

                experiment_id = f"{pmid}_{exp_idx}"

                # 1) 메인 실험 테이블
                batch_rows.append(
                    {
                        "pmid": pmid,
                        "experiment_id": experiment_id,
                        "experiment_index": exp_idx,
                        "method": method,
                        "condition": condition,
                        "category_parent": category_parent,
                        "category_leaf": category_leaf,
                        "materials": materials_str,
                        "equipment": equipment_str,
                    }
                )

                # 2) materials 분리 테이블
                for m in split_items(materials_str):
                    batch_material_rows.append(
                        {
                            "pmid": pmid,
                            "experiment_id": experiment_id,
                            "experiment_index": exp_idx,
                            "method": method,
                            "category_parent": category_parent,
                            "category_leaf": category_leaf,
                            "material": m,
                        }
                    )

                # 3) equipment 분리 테이블
                for eq in split_items(equipment_str):
                    batch_equipment_rows.append(
                        {
                            "pmid": pmid,
                            "experiment_id": experiment_id,
                            "experiment_index": exp_idx,
                            "method": method,
                            "category_parent": category_parent,
                            "category_leaf": category_leaf,
                            "equipment": eq,
                        }
                    )

            processed_pmids.add(str(pmid))
            processed_count += 1

            # 과금/속도 조절용 텀 (원하면 줄이거나 없애도 됨)
            time.sleep(0.3)

        # ─────────────────────────────
        # 2) 배치 결과를 바로 CSV에 append
        # ─────────────────────────────
        if batch_rows:
            out_df = pd.DataFrame(batch_rows)
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(
                OUTPUT_PATH,
                index=False,
                mode="w" if first_write_main else "a",
                header=first_write_main,
            )
            first_write_main = False
            print(f"[INFO] 배치 {batch_idx} 메인 테이블 {len(out_df)}행 저장")

        if batch_material_rows:
            mat_df = pd.DataFrame(batch_material_rows)
            mat_df.to_csv(
                mat_path,
                index=False,
                mode="w" if first_write_mat else "a",
                header=first_write_mat,
            )
            first_write_mat = False
            print(f"[INFO] 배치 {batch_idx} 재료 테이블 {len(mat_df)}행 저장")

        if batch_equipment_rows:
            eq_df = pd.DataFrame(batch_equipment_rows)
            eq_df.to_csv(
                eq_path,
                index=False,
                mode="w" if first_write_eq else "a",
                header=first_write_eq,
            )
            first_write_eq = False
            print(f"[INFO] 배치 {batch_idx} 장비 테이블 {len(eq_df)}행 저장")

        print(
            f"[INFO] ====== 배치 {batch_idx} 종료, 누적 처리 논문 수: {processed_count} ======"
        )

    print(f"\n[INFO] 전체 처리 완료. 총 처리 논문 수: {processed_count}")



if __name__ == "__main__":
    main()
