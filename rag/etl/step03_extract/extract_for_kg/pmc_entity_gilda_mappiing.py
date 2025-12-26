# build_entity_master_with_gilda.py
import os
from pathlib import Path

import pandas as pd
import gilda
from tqdm import tqdm

# ==========================================
# [설정] 파일 경로
# ==========================================
ROOT_DIR = Path(__file__).resolve().parents[4]
ENT_DIR = ROOT_DIR / "data" / "entities" / "pubmed"

INPUT_FILE  = ENT_DIR / "ts_entities.csv"      # pmc_section_generate_keywords 에서 생성한 엔티티 파일
OUTPUT_FILE = ENT_DIR / "ts_entity_master.csv"  # Gilda 매핑 + entity_id까지 포함한 최종 엔티티 마스터

# ==========================================
# Gilda 호출 헬퍼: 이름 -> (label, db, id, score)
# ==========================================
def get_best_label(text):
    """
    text -> (primekg_label, source_db, source_id, score)
    - primekg_label: 나중에 PrimeKG 노드 이름과 조인할 canonical name
    """
    if not isinstance(text, str) or not text.strip():
        return None, None, None, None

    matches = gilda.ground(text)
    if not matches:
        return None, None, None, None

    best = matches[0]
    return (
        best.term.entry_name,  # canonical label (PrimeKG 이름이랑 맞추고 싶은 이름)
        best.term.db,          # MONDO, DRUGBANK, HGNC, ...
        best.term.id,          # 0005148, DB00001, 17635, ...
        best.score,
    )

def main():
    # 1) 입력 파일 확인 및 로드
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 입력 파일 없음: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)
    print(f"📂 entities.csv 로드: {len(df)} 행")

    # 2) 필수 컬럼 체크
    required_cols = ["normalized_entity", "entity_type", "umls_cui"]
    for c in required_cols:
        if c not in df.columns:
            raise ValueError(f"'{c}' 컬럼이 없습니다. entities.csv 구조를 확인하세요.")

    # 3) 진짜 유니크 엔티티만 남기기
    df = df.drop_duplicates(subset=required_cols).reset_index(drop=True)
    print(f"🧮 유니크 엔티티 수: {len(df)}")

    norm_col = "normalized_entity"
    cui_col  = "umls_cui"

    # 4) MUTATION_NODE는 그대로 유지, 나머지만 Gilda 매핑
    mask_mut = df[cui_col] == "MUTATION_NODE"
    non_mut_texts = df.loc[~mask_mut, norm_col].dropna().unique()
    print(f"🧬 MUTATION_NODE: {mask_mut.sum()} 개 (Gilda 스킵)")
    print(f"🔄 Gilda 매핑 대상: {len(non_mut_texts)} 개")

    # 5) Gilda 매핑 캐시 (normalized_entity 기준)
    mapping = {}
    for t in tqdm(non_mut_texts, desc="Gilda→label"):
        mapping[t] = get_best_label(t)

    primekg_label = []
    primekg_db = []
    primekg_id = []
    match_score = []

    # 6) row 별로 primekg_* 컬럼 채우기
    for _, row in df.iterrows():
        text = row[norm_col]
        cui  = row[cui_col]

        if cui == "MUTATION_NODE":
            # 변이는 그냥 normalized_entity를 label로 사용
            primekg_label.append(text)
            primekg_db.append("MUTATION")
            primekg_id.append("MUTATION_NODE")
            match_score.append(1.0)
        else:
            label, db, mid, score = mapping.get(text, (None, None, None, None))
            primekg_label.append(label)
            primekg_db.append(db)
            primekg_id.append(mid)
            match_score.append(score)

    df["primekg_label"]     = primekg_label   # 🔑 이름 기반 조인용
    df["primekg_source_db"] = primekg_db
    df["primekg_source_id"] = primekg_id
    df["match_score"]       = match_score

    # 7) entity_id 부여 (E000001 형식)
    df = df.reset_index(drop=True)
    df["entity_id"] = (df.index + 1).map(lambda i: f"E{i:06d}")

    # 8) 컬럼 순서 정리 (원하는 대로 조정 가능)
    cols_order = [
        "entity_id",
        "normalized_entity",
        "entity_type",
        "umls_cui",
        "primekg_label",
        "primekg_source_db",
        "primekg_source_id",
        "match_score",
    ]
    # 혹시 없는 컬럼은 자동 제거
    cols_order = [c for c in cols_order if c in df.columns]
    df = df[cols_order]

    # 9) 저장
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ 엔티티 마스터 저장 완료: {OUTPUT_FILE}")
    print(df.head())

if __name__ == "__main__":
    main()
