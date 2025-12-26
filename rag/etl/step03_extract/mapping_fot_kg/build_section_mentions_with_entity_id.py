# build_section_mentions_with_entity_id.py
import pandas as pd
import os
from pathlib import Path

# data/entities 기준 경로
ROOT_DIR = Path(__file__).resolve().parents[4]
ENT_DIR = ROOT_DIR / "data" / "entities"

ENTITY_MASTER = ENT_DIR / "pubmed" / "ts_entity_master.csv"
SECTION_FILE  = ENT_DIR / "pubmed" / "ts_section_keywords_primekg.csv"
OUTPUT_FILE   = ENT_DIR / "pubmed" / "ts_section_entity_mentions.csv"
#keyword(raw text) - entity(nomalized text) mapping file
def main():
    if not os.path.exists(ENTITY_MASTER):
        print(f"❌ 엔티티 마스터 파일 없음: {ENTITY_MASTER}")
        return
    if not os.path.exists(SECTION_FILE):
        print(f"❌ 섹션 키워드 파일 없음: {SECTION_FILE}")
        return

    ent = pd.read_csv(ENTITY_MASTER)
    sec = pd.read_csv(SECTION_FILE)

    # 조인 키: entity_type은 제외, normalized_entity만 사용
    key_cols = ["normalized_entity"]
    for c in key_cols:
        if c not in ent.columns or c not in sec.columns:
            raise ValueError(f"'{c}' 컬럼이 ent/sec 둘 다 있어야 합니다.")

    # mention(섹션 키워드)에 entity_id 및 primekg_label 붙이기
    merged = sec.merge(
        ent[key_cols + ["entity_id", "primekg_label"]],
        on=key_cols,
        how="left",
    )

    # (선택) mention_id 생성
    merged = merged.reset_index(drop=True)
    merged["mention_id"] = merged.index.map(lambda i: f"M{i+1:07d}")

    # 컬럼 순서 정리 (원하는 대로)
    cols_order = [
        "mention_id",
        "section_id",
        "raw_keyword",
        "normalized_entity",
        "entity_type",
        "umls_cui",
        "entity_id",
        "primekg_label",
        "score",
    ]
    cols_order = [c for c in cols_order if c in merged.columns]
    merged = merged[cols_order]

    print("📊 전체 mention 수:", len(merged))
    print("⚠ entity_id 없는 mention 수:", merged["entity_id"].isna().sum())

    ENT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ section_entity_mentions 저장 완료: {OUTPUT_FILE}")
    print(merged.head())

if __name__ == "__main__":
    main()
