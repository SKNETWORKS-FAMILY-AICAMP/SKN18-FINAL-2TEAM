import pandas as pd
import gilda
from tqdm import tqdm
import os

# ==========================================
# [설정] 파일 경로 지정
# ==========================================
# 앞선 단계(generate_keywords.py)에서 생성된 파일 경로
INPUT_FILE = r"/content/drive/MyDrive/final_project/data/entities_v2.csv"
OUTPUT_FILE = r"/content/drive/MyDrive/final_project/data/entities_all_dbs.csv"

def get_best_id(text):
    """
    텍스트를 받아 Gilda로 Grounding
    Returns: (db_name, id_value, standardized_name, score)
    """
    if not isinstance(text, str):
        return None, None, None, None
    
    matches = gilda.ground(text)
    if not matches:
        return None, None, None, None

    best_match = matches[0]
    return (best_match.term.db, 
            best_match.term.id, 
            best_match.term.entry_name, 
            best_match.score)

def main():
    print(f"📂 파일 로딩 중: {INPUT_FILE} ...")
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 파일을 찾을 수 없습니다: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    # 1. 사용할 텍스트 컬럼과 기존 ID 컬럼 지정
    target_col = 'normalized_entity'  # LLM이 정제한 엔티티 이름
    id_col = 'umls_cui'               # 기존에 할당된 ID (MUTATION_NODE 포함)

    # 컬럼 확인
    if target_col not in df.columns:
        print(f"❌ '{target_col}' 컬럼이 없습니다. CSV를 확인해주세요.")
        return

    print("🔄 Gilda 매핑 시작 (MUTATION_NODE 보호)...")
    
    # 2. Gilda 매핑이 '필요한' 텍스트만 추출 (Mutation 제외)
    # 조건: umls_cui가 'MUTATION_NODE'가 아닌 것들만 골라냄
    mask_mutation = df[id_col] == 'MUTATION_NODE'
    non_mutation_texts = df.loc[~mask_mutation, target_col].dropna().unique()

    # 3. 중복 제거 후 딕셔너리 생성 (속도 최적화)
    mapping_dict = {}
    for text in tqdm(non_mutation_texts, desc="Mapping Entities"):
        mapping_dict[text] = get_best_id(text)

    # 4. 결과 병합 로직
    print("💾 데이터 병합 중...")
    
    db_list = []
    id_list = []
    name_list = []
    score_list = []

    for idx, row in df.iterrows():
        text = row.get(target_col)
        existing_id = row.get(id_col)
        
        # [핵심] MUTATION_NODE 보호 로직
        if existing_id == 'MUTATION_NODE':
            # Mutation은 Gilda를 거치지 않고 그대로 유지 (또는 수동 마킹)
            db_list.append("LLM_Mutation")   # DB 출처 표시
            id_list.append("MUTATION_NODE")  # ID 유지
            name_list.append(text)           # 이름 유지
            score_list.append(1.0)           # LLM 신뢰도 (1.0)
            
        # 그 외: Gilda 매핑 결과 적용
        elif text in mapping_dict:
            db, val, name, score = mapping_dict[text]
            db_list.append(db)
            id_list.append(val)
            name_list.append(name)
            score_list.append(score)
            
        # 매핑 실패 또는 데이터 없음
        else:
            db_list.append(None)
            id_list.append(None)
            name_list.append(None)
            score_list.append(None)

    # 5. 새로운 컬럼 추가
    df['mapped_db'] = db_list
    df['mapped_id'] = id_list
    df['standard_name'] = name_list
    df['match_score'] = score_list

    # 저장
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ 완료! 저장된 파일: {OUTPUT_FILE}")
    
    # 결과 통계
    mutation_count = (df['mapped_id'] == 'MUTATION_NODE').sum()
    gilda_count = df['mapped_id'].notnull().sum() - mutation_count
    
    print("-" * 30)
    print(f"   - 총 데이터: {len(df)}행")
    print(f"   - Mutation 보존: {mutation_count}행 (MUTATION_NODE 유지)")
    print(f"   - Gilda 신규 매핑: {gilda_count}행")
    print("-" * 30)

if __name__ == "__main__":
    main()