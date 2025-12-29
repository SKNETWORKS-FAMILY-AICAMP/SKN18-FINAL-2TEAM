from pathlib import Path
import pandas as pd
import os

# ==========================================
# [설정] 파일 경로
# ==========================================
ROOT_DIR = Path(__file__).resolve().parents[4]
ENT_DIR = ROOT_DIR / "data" / "entities" / "pubmed"

SECTION_FILE = ENT_DIR / "ts_section_keywords.csv"
MAPPING_FILE = ENT_DIR / "ts_entity_master.csv"
OUTPUT_FILE  = ENT_DIR / "ts_section_keywords_primekg.csv"

# ==========================================
# [로직] ID 갈아끼우기
# ==========================================
def main():
    # 1. 파일 로드
    if not os.path.exists(SECTION_FILE) or not os.path.exists(MAPPING_FILE):
        print("❌ 필수 파일이 없습니다. 경로를 확인해주세요.")
        return

    df_sec = pd.read_csv(SECTION_FILE)
    df_map = pd.read_csv(MAPPING_FILE)

    print(f"1️⃣ 섹션 데이터: {len(df_sec)}행 로드")
    print(f"2️⃣ 매핑 데이터: {len(df_map)}행 로드")

    # 2. 병합 (Join) - 텍스트(normalized_entity)를 기준으로 합칩니다.
    # how='left': 섹션 데이터는 유지하고, 매핑 정보만 붙입니다.
    merged_df = pd.merge(df_sec, df_map, on='normalized_entity', how='left')

    # 3. 최종 KG ID 결정 로직 (Cascade Strategy)
        # 3. 최종 KG ID 결정 로직 (Cascade Strategy)
    def get_final_id(row):
        # [Priority 1] Mutation인 텍스트 (PrimeKG에 없음)
        if row.get("umls_cui_x") == "MUTATION_NODE":  # _x는 section 파일 쪽 컬럼
            return row["normalized_entity"]

        # [Priority 2] Gilda 매핑 + 점수 기준 -> PrimeKG ID 사용
        # pmc_entity_gilda_mappiing.py에서 생성한 컬럼 사용:
        #   - primekg_source_db, primekg_source_id, match_score
        if (
            "primekg_source_id" in row
            and "primekg_source_db" in row
            and "match_score" in row
            and pd.notnull(row["primekg_source_id"])
            and pd.notnull(row["primekg_source_db"])
            and row["match_score"] >= 0.65
        ):
            return f"{row['primekg_source_db']}:{row['primekg_source_id']}"

        # [Priority 3] UMLS CUI가 있으면 사용
        if "umls_cui_x" in row and pd.notnull(row["umls_cui_x"]) and row["umls_cui_x"] != "N/A":
            return f"UMLS:{row['umls_cui_x']}"

        # [Priority 4] 아무 것도 없으면 텍스트 자체 사용
        return row["normalized_entity"]

    print("🔄 KG ID 변환 중...")
    merged_df['kg_node_id'] = merged_df.apply(get_final_id, axis=1)

    # 4. 필요한 컬럼만 정리
    # 이제 'normalized_entity'는 단순 속성이 되고, 'kg_node_id'가 주인공이 됩니다.
    final_df = merged_df[[
        'section_id',    # 논문 섹션 ID
        'kg_node_id',    # PrimeKG와 연결될 ID (예: MONDO:0005070)
        'normalized_entity', # 사람이 볼 이름 (속성)
        'entity_type_x', # 타입 (Disease, Drug 등)
        'score'          # 추출 신뢰도
    ]].rename(columns={'entity_type_x': 'entity_type'})

    # 5. 저장
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ 변환 완료! 저장된 파일: {OUTPUT_FILE}")
    print(final_df.head())

if __name__ == "__main__":
    main()
