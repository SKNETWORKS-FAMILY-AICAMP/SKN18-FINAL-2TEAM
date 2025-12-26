# neo4j/pmc_kg_etl/protocol_category_etl.py

import os
import sys
import time
import json
from pathlib import Path

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

"""
입력(기본):  neo4j/import/t_protocol_metadata_Cell.csv
      (컬럼: protocol_sid, url, title)

출력(라벨링): neo4j/import/t_protocol_metadata_Cell_labeled.csv
      (컬럼: protocol_sid, url, title, category_parent, category_leaf)

특징:
- 이미 t_protocol_metadata_Cell_labeled.csv 가 존재하면,
  거기 있는 category_parent / category_leaf 를 재사용하고,
  "아직 안 채워진 행"만 LLM으로 분류해서 이어서 수행.
- 중간에 Ctrl+C 등으로 중단되어도, 지금까지 진행된 내용은 CSV에 저장됨.
"""

# ─────────────────────────────────────
# 0) 프로젝트 루트(.env) 로드
# ─────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[4]  # SKN18-FINAL-2TEAM

# 공통 카테고리 모듈 import 위해 sys.path에 루트 추가
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from rag.etl.step03_extract.extract_for_kg.common_experiment_categories import (
    CATEGORY_TREE,
    LEAF_TO_PARENT,
    VALID_PARENTS,
    VALID_LEAVES,
    CATEGORIES_BLOCK,
    normalize_category,
    is_valid_category,
)

load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY 가 .env에서 로드되지 않았어요 😭")

client = OpenAI(api_key=api_key)  # 이 인스턴스 하나만 사용


# ─────────────────────────────────────
# 1) LLM 시스템 프롬프트
# ─────────────────────────────────────

SYSTEM_PROMPT = f"""
You are an expert in wet-lab, biological, in vivo, ex vivo, and computational experiments.

Your task:
Given a protocol title (and optionally URL), classify it into exactly TWO levels
based on the FIXED taxonomy below.

1) category_parent:
   - MUST be exactly one of the following parent labels (string):
     {", ".join(sorted(VALID_PARENTS))}

2) category_leaf:
   - MUST be exactly one of the leaf labels listed under its parent.
   - You are NOT allowed to invent new labels.
   - If the protocol does not clearly fit any specific leaf,
     choose a reasonable "other_*" style leaf under the chosen parent,
     or fall back to:
       parent  = "other_or_not_specified"
       leaf    = "other"

Taxonomy (parent → leaf list):

{CATEGORIES_BLOCK}

Return STRICTLY a JSON object with two keys, for example:
{{
  "category_parent": "cell_based_assays",
  "category_leaf": "dose_response_viability_assay"
}}

Rules:
- Use concise English for both category_parent and category_leaf.
- Do NOT output explanations or any extra text.
- Do NOT output markdown code fences.
- Output must be valid JSON only.
""".strip()


# ─────────────────────────────────────
# 2) LLM 호출 함수
# ─────────────────────────────────────

def classify_protocol(title: str, url: str | None = None) -> tuple[str, str]:
    """
    OpenAI LLM을 호출해서 (category_parent, category_leaf)를 리턴.
    타이틀이 비어 있거나 '<no data>' 인 경우 ("", "") 리턴.
    """
    if not isinstance(title, str) or title.strip() == "" or title.strip() == "<no data>":
        return "", ""

    user_content = f"Protocol title: {title}"
    if isinstance(url, str) and url.strip():
        user_content += f"\nURL: {url}"

    resp = client.chat.completions.create(
        # 실제 사용 가능한 모델로 바꿔서 쓰면 됨
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
        raw_parent = (data.get("category_parent") or "").strip()
        raw_leaf = (data.get("category_leaf") or "").strip()
    except json.JSONDecodeError:
        raw_parent = "other_or_not_specified"
        raw_leaf = "other"

    fixed_parent, fixed_leaf = normalize_category(raw_parent, raw_leaf)
    return fixed_parent, fixed_leaf


# ─────────────────────────────────────
# 3) 메인: 재시작 가능한 ETL
# ─────────────────────────────────────

def main():
    # 입력: data/processed/protocols/protocol_csv 안의 메타데이터 파일
    input_dir = BASE_DIR / "data" / "processed" / "protocols" / "protocol_csv"
    # 실제 파일명에 공백이 포함되어 있음에 주의 ("Cell .csv")
    input_path = input_dir / "t_protocol_metadata_Cell.csv"

    # 출력: data/entities/protocol 안에 라벨링된 파일 저장
    output_dir = BASE_DIR / "data" / "entities" / "protocol"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "t_protocol_metadata_Cell_labeled.csv"

    print(f"입력 파일 경로:   {input_path}")
    print(f"출력 파일 경로:   {output_path}")
    print(f"현재 작업 디렉토리: {Path.cwd()}")

    # 1) 기본 입력 CSV 읽기
    base_df = pd.read_csv(input_path)

    # 2) 이미 라벨링된 파일이 있으면 거기서 이어서 하기
    if output_path.exists():
        print("💾 기존 라벨링 파일 발견! (resume 모드)")
        labeled_df = pd.read_csv(output_path)

        if "protocol_sid" in labeled_df.columns and "protocol_sid" in base_df.columns:
            df = base_df.merge(
                labeled_df[["protocol_sid", "category_parent", "category_leaf"]],
                on="protocol_sid",
                how="left",
                suffixes=("", "_old"),
            )
        else:
            print("⚠️ protocol_sid 컬럼이 없어 index 기준으로 병합합니다.")
            df = base_df.copy()
            if "category_parent" in labeled_df.columns:
                df["category_parent"] = labeled_df["category_parent"]
            if "category_leaf" in labeled_df.columns:
                df["category_leaf"] = labeled_df["category_leaf"]
    else:
        print("🆕 라벨링 파일이 없어 새로 시작합니다.")
        df = base_df.copy()
        if "category_parent" not in df.columns:
            df["category_parent"] = ""
        if "category_leaf" not in df.columns:
            df["category_leaf"] = ""

    total_rows = len(df)
    print(f"총 행 개수: {total_rows}")

    try:
        for idx, row in df.iterrows():
            title = row.get("title", "")
            url = row.get("url", "")
            cur_parent = row.get("category_parent", "")
            cur_leaf = row.get("category_leaf", "")

            # 이미 유효한 카테고리면 건너뜀 (resume 포인트)
            if is_valid_category(cur_parent, cur_leaf):
                print(f"[{idx+1}/{total_rows}] 이미 분류됨, 스킵 - title: {str(title)[:60]}...")
                continue

            print(f"[{idx+1}/{total_rows}] 분류 중 - title: {str(title)[:60]}...")

            if isinstance(title, str) and title.strip() not in ("", "<no data>"):
                parent, leaf = classify_protocol(title, url)
                time.sleep(0.05)  # rate limit/과금 고려해서 조정 가능
            else:
                parent, leaf = "", ""

            df.at[idx, "category_parent"] = parent
            df.at[idx, "category_leaf"] = leaf

            # 안전을 위해 N행마다 중간 저장 (예: 20행마다)
            if (idx + 1) % 20 == 0:
                df.to_csv(output_path, index=False)
                print(f"💾 중간 저장 완료 (행 {idx+1}까지 처리)")

    except KeyboardInterrupt:
        print("\n⛔️ 사용자가 중단 (Ctrl+C 감지). 지금까지 진행된 내용 저장합니다...")
    finally:
        df.to_csv(output_path, index=False)
        print(f"\n✅ 최종(또는 중간) 저장 완료: {output_path}")


if __name__ == "__main__":
    main()
