# neo4j/pmc_kg_etl/protocol_category_etl_batch.py

import os
import time
import json
import math
from pathlib import Path

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 0) 설정 및 로드
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY 가 .env에서 로드되지 않았어요 😭")

client = OpenAI(api_key=api_key)

BATCH_SIZE = 50  # 요청 한 번에 처리할 개수

# (CATEGORY_TREE, LEAF_TO_PARENT, CATEGORIES_BLOCK 등은 기존과 동일하다고 가정)
# ... [이전 코드의 CATEGORY_TREE ~ _build_categories_block 함수 부분 그대로 사용] ...

# 여기서부터가 중요합니다! (코드의 윗부분에 이 블록을 복사해 넣으세요)
CATEGORY_TREE: dict[str, list[str]] = {
    # ... (기존과 동일하게 작성되어 있다고 가정) ...
    # 코드가 너무 길어지니 위쪽 정의는 생략합니다. 
    # 기존 코드의 CATEGORY_TREE 내용을 그대로 쓰시면 됩니다.
    "other_or_not_specified": ["other", "insufficient_information_to_classify"] 
}
# (임시로 추가: 위에서 정의한 CATEGORY_TREE 변수가 있어야 아래 코드가 돕니다)
# 실제 실행 시에는 기존 코드의 1)번 섹션을 그대로 두세요.

def _build_categories_block() -> str:
    lines = []
    for group, labels in CATEGORY_TREE.items():
        lines.append(f"- {group}:")
        for label in labels:
            lines.append(f"  - {label}")
    return "\n".join(lines)

CATEGORIES_BLOCK = _build_categories_block()
LEAF_TO_PARENT = {} # (기존 로직대로 채워져야 함)
for p, leaves in CATEGORY_TREE.items():
    for l in leaves: LEAF_TO_PARENT[l] = p


# ─────────────────────────────────────────────
# 2) 배치용 시스템 프롬프트 (수정됨)
# ─────────────────────────────────────────────
SYSTEM_PROMPT_BATCH = f"""
You are an expert in wet-lab, biological and computational experiments.

Your task:
You will receive a list of protocols formatted as "ID | Title".
Classify EACH protocol into exactly TWO levels based on the FIXED taxonomy below.

Taxonomy:
{CATEGORIES_BLOCK}

Return STRICTLY a JSON object where the **Keys are the IDs** provided in the input, and the values are objects containing 'category_parent' and 'category_leaf'.

Example Input:
101 | Western blot for p53
102 | Molecular dynamics of protein A

Example Output:
{{
  "101": {{ "category_parent": "molecular_and_biochemical_assays", "category_leaf": "molecular_biology_assay_pcr_cloning_western_blot" }},
  "102": {{ "category_parent": "computational_and_in_silico_studies", "category_leaf": "molecular_dynamics_simulation" }}
}}

Rules:
- Return ONLY valid JSON.
- Do NOT output markdown code fences.
- If a title implies multiple methods, pick the most dominant one.
- If unsure, use "other_or_not_specified" / "other".
""".strip()

# ─────────────────────────────────────────────
# 3) 카테고리 보정 함수 (기존과 동일)
# ─────────────────────────────────────────────
def normalize_category(cat_parent: str, cat_leaf: str) -> tuple[str, str]:
    cat_parent = (cat_parent or "").strip()
    cat_leaf = (cat_leaf or "").strip()
    
    if cat_leaf in LEAF_TO_PARENT:
        return LEAF_TO_PARENT[cat_leaf], cat_leaf
    
    if cat_parent in CATEGORY_TREE:
        leaves = CATEGORY_TREE[cat_parent]
        if cat_leaf in leaves:
            return cat_parent, cat_leaf
        other_like = [l for l in leaves if "other" in l]
        return cat_parent, other_like[0] if other_like else leaves[-1]

    return "other_or_not_specified", "other"

def is_valid_category(cat_parent: str, cat_leaf: str) -> bool:
    if not cat_parent and not cat_leaf: return False
    if cat_leaf in LEAF_TO_PARENT: return True
    if cat_parent in CATEGORY_TREE and cat_leaf in CATEGORY_TREE[cat_parent]: return True
    return False

# ─────────────────────────────────────────────
# 4) 배치 API 호출 함수 (새로 작성됨)
# ─────────────────────────────────────────────
def classify_batch(batch_items: list[dict]) -> dict:
    """
    batch_items: [{'id': 10, 'title': '...', 'url': '...'}, ...]
    Return: { 10: ('parent', 'leaf'), ... }
    """
    if not batch_items:
        return {}

    # LLM에게 던질 입력 텍스트 구성
    input_lines = []
    for item in batch_items:
        clean_title = str(item['title']).replace('\n', ' ').strip()
        input_lines.append(f"{item['id']} | {clean_title}")
    
    user_content = "\n".join(input_lines)

    try:
        resp = client.chat.completions.create(
            model="gpt-5-nano",  # 혹은 gpt-4o-mini
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_BATCH},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"} # JSON 모드 강제 (모델 지원 시)
        )
        
        text = resp.choices[0].message.content.strip()
        data = json.loads(text) # { "ID": { "category_parent": ... } }

        results = {}
        for item in batch_items:
            # ID는 문자열로 옴
            str_id = str(item['id'])
            if str_id in data:
                raw = data[str_id]
                p, l = normalize_category(raw.get("category_parent"), raw.get("category_leaf"))
                results[item['id']] = (p, l)
            else:
                # LLM이 빼먹은 경우 -> 기타로 처리하거나 로그 남김
                print(f"⚠️ Warning: ID {str_id} missing in LLM response.")
                results[item['id']] = ("other_or_not_specified", "other")
        
        return results

    except Exception as e:
        print(f"🔥 Batch Error: {e}")
        # 에러 발생 시 해당 배치 전체를 '기타' 혹은 '빈값' 처리하여 진행 멈춤 방지
        fallback = {}
        for item in batch_items:
            fallback[item['id']] = ("error_in_batch", "error")
        return fallback

# ─────────────────────────────────────────────
# 5) 메인 실행
# ─────────────────────────────────────────────
def main():
    neo4j_dir = BASE_DIR / "neo4j"
    import_dir = neo4j_dir / "import"
    input_path = import_dir / "t_protocol_metadata_Cell.csv"
    output_path = import_dir / "t_protocol_metadata_Cell_labeled.csv"

    print(f"📂 입력: {input_path}")
    
    # 데이터 로드
    base_df = pd.read_csv(input_path)
    
    # Resume 로직
    if output_path.exists():
        print("resume 모드: 기존 파일 병합 중...")
        labeled_df = pd.read_csv(output_path)
        # 인덱스 기준으로 병합 (또는 protocol_sid가 있다면 그것 사용 권장)
        # 여기서는 간단히 기존 labeled_df의 값을 base_df에 덮어씌우는 방식 사용
        df = base_df.copy()
        
        # 컬럼 초기화
        if "category_parent" not in df.columns: df["category_parent"] = ""
        if "category_leaf" not in df.columns: df["category_leaf"] = ""

        # labeled_df에 있는 값 매핑 (protocol_sid 기준이 안전)
        if "protocol_sid" in df.columns and "protocol_sid" in labeled_df.columns:
            merged = df.merge(labeled_df[['protocol_sid', 'category_parent', 'category_leaf']], 
                              on='protocol_sid', how='left', suffixes=('', '_new'))
            # _new 값이 있으면 업데이트
            df['category_parent'] = merged['category_parent_new'].fillna(df['category_parent'])
            df['category_leaf'] = merged['category_leaf_new'].fillna(df['category_leaf'])
        else:
            # 단순 인덱스 매핑 (위험할 수 있음)
            df.update(labeled_df)
    else:
        print("새로 시작합니다.")
        df = base_df.copy()
        df["category_parent"] = ""
        df["category_leaf"] = ""

    # 작업 대상 선정 (아직 분류 안 된 행)
    # parent가 비어있거나 이상한 값인 행들의 인덱스 추출
    target_indices = []
    for idx, row in df.iterrows():
        p, l = str(row.get('category_parent', '')), str(row.get('category_leaf', ''))
        if not is_valid_category(p, l):
            target_indices.append(idx)
    
    total_target = len(target_indices)
    print(f"총 {len(df)}행 중 처리할 대상: {total_target}건")
    
    # 배치 처리 루프
    # range(start, stop, step) -> step만큼 건너뛰며 반복
    try:
        for i in range(0, total_target, BATCH_SIZE):
            # 1. 이번 배치의 인덱스들 가져오기
            batch_idxs = target_indices[i : i + BATCH_SIZE]
            
            # 2. API에 보낼 데이터 구성
            batch_data = []
            for idx in batch_idxs:
                title = df.at[idx, 'title']
                url = df.at[idx, 'url']
                # 제목 없는 건 스킵
                if pd.isna(title) or str(title).strip() in ["", "<no data>"]:
                    df.at[idx, 'category_parent'] = "other_or_not_specified"
                    df.at[idx, 'category_leaf'] = "insufficient_information_to_classify"
                    continue
                    
                batch_data.append({
                    "id": idx,    # DataFrame의 인덱스를 ID로 사용
                    "title": title,
                    "url": url
                })
            
            if not batch_data:
                continue

            print(f"🚀 Processing batch {i // BATCH_SIZE + 1} / {math.ceil(total_target / BATCH_SIZE)} "
                  f"(Rows {batch_idxs[0]}~{batch_idxs[-1]})")

            # 3. API 호출
            results = classify_batch(batch_data)

            # 4. 결과 DataFrame에 반영
            for idx, (p, l) in results.items():
                df.at[idx, 'category_parent'] = p
                df.at[idx, 'category_leaf'] = l

            # 5. 중간 저장 (매 배치마다 저장해도 부담 적음)
            df.to_csv(output_path, index=False)
            time.sleep(0.5) # Rate Limit 방지용 쿨타임

    except KeyboardInterrupt:
        print("\n⛔️ 중단됨! 데이터 저장 중...")
    
    finally:
        df.to_csv(output_path, index=False)
        print(f"✅ 저장 완료: {output_path}")

if __name__ == "__main__":
    main()