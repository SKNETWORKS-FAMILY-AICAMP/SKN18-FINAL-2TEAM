# [중요] 충돌 방지를 위해 scispacy/torch 관련 모듈을 가장 먼저 import
import scispacy.linking 
from scispacy.linking import EntityLinker
import spacy
import torch  # 혹시 모르니 명시적으로 추가해도 좋음

import pandas as pd
import gilda  # <--- 나중에 import
import os
from pathlib import Path
from tqdm import tqdm
# ==========================================
# [설정] 파일 경로 및 배치 설정
# ==========================================
ROOT_DIR = Path(__file__).resolve().parents[4]
NIH_DIR = ROOT_DIR / "data" / "processed" / "nih" 
OUT_DIR = ROOT_DIR / "data" / "entities" / "nih"
OUT_DIR.mkdir(parents=True, exist_ok=True)

METADATA_FILE = NIH_DIR / "nih_metadata1208.csv"
CHUNK_FILE = "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\data\\chunks\\nih\\nih_chunks.csv"

# 최종 결과 파일
OUTPUT_METADATA_ENTITIES = OUT_DIR / "ts_mapped_metadata_entities.csv"
OUTPUT_CHUNK_ENTITIES = OUT_DIR / "ts_mapped_chunk_entities.csv"

# 한 번에 처리할 행 개수 (메모리 관리용)
BATCH_SIZE = 2000 

# ==========================================
# [준비] 모델 및 캐시 초기화
# ==========================================

def init_umls_pipeline():
    """scispaCy + UMLS 링커 초기화 (한 번만 로딩)"""
    print("⚙️ scispaCy 모델 로딩 중 (en_core_sci_lg)...")
    try:
        nlp = spacy.load("en_core_sci_lg")
    except OSError:
        print("❌ 모델 설치 필요: pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_lg-0.5.1.tar.gz")
        exit(1)
        
    print("🔗 UMLS Entity Linker 연결 중...")
    if "scispacy_linker" not in nlp.pipe_names:
        nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})
    return nlp, nlp.get_pipe("scispacy_linker")
# [핵심] 중복 연산 방지용 인메모리 캐시
id_cache = {}

def get_cached_id(text):
    """
    텍스트 -> Gilda ID 매핑 (캐시 사용으로 속도 최적화)
    """
    if not isinstance(text, str) or not text.strip():
        return None
    
    # 캐시 적중 (Cache Hit)
    if text in id_cache:
        return id_cache[text]
    
    # 캐시 미스 (Cache Miss) -> Gilda 호출
    matches = gilda.ground(text)
    if matches:
        best = matches[0]
        result = {
            "db": best.term.db,
            "id": best.term.id,
            "name": best.term.entry_name,
            "score": best.score
        }
    else:
        result = None 
    
    id_cache[text] = result
    return result

# ==========================================
# [1] Metadata 배치 처리 (Conditions + Interventions + Keywords)
# ==========================================
def process_metadata_batch():
    print(f"\n🚀 [1/2] Metadata 배치 처리 시작: {METADATA_FILE}")
    
    if os.path.exists(OUTPUT_METADATA_ENTITIES): os.remove(OUTPUT_METADATA_ENTITIES)
    
    try:
        total_rows = sum(1 for _ in open(METADATA_FILE, encoding='utf-8')) - 1
    except:
        total_rows = None

    chunk_iter = pd.read_csv(METADATA_FILE, chunksize=BATCH_SIZE)

    with tqdm(total=total_rows, unit='rows') as pbar:
        for i, df in enumerate(chunk_iter):
            batch_results = []
            
            # --- [1] Disease (Conditions) ---
            df_cond = df[['nctId', 'conditions']].dropna()
            df_cond['condition_name'] = df_cond['conditions'].str.split(r' \|\|\| ')
            df_cond = df_cond.explode('condition_name')
            
            for _, row in df_cond.iterrows():
                res = get_cached_id(row['condition_name'])
                if res and res['db'] == 'MONDO': # 질병은 주로 MONDO
                    batch_results.append({
                        'nctId': row['nctId'],
                        'sourceType': 'Metadata_Condition',
                        'entityId': f"{res['db']}:{res['id']}",
                        'entityName': res['name'],
                        'entityType': 'Disease',
                        'score': res['score']
                    })

            # --- [2] Drug (Interventions) ---
            df_int = df[['nctId', 'interventions']].dropna()
            df_int['drug_name'] = df_int['interventions'].str.split(r' \|\|\| ')
            df_int = df_int.explode('drug_name')
            df_int['drug_name'] = df_int['drug_name'].str.replace(r'^Drug: ', '', regex=True)

            for _, row in df_int.iterrows():
                res = get_cached_id(row['drug_name'])
                if res and res['db'] in ['DRUGBANK', 'CHEBI', 'GO']:
                    batch_results.append({
                        'nctId': row['nctId'],
                        'sourceType': 'Metadata_Intervention',
                        'entityId': f"{res['db']}:{res['id']}",
                        'entityName': res['name'],
                        'entityType': 'Drug',
                        'score': res['score']
                    })

            # --- [3] Keywords 처리 (추가됨!) ---
            if 'keywords' in df.columns:
                df_key = df[['nctId', 'keywords']].dropna()
                # "No Data" 필터링
                df_key = df_key[df_key['keywords'] != 'No Data']
                
                if not df_key.empty:
                    df_key['keyword_name'] = df_key['keywords'].str.split(r' \|\|\| ')
                    df_key = df_key.explode('keyword_name')

                    for _, row in df_key.iterrows():
                        res = get_cached_id(row['keyword_name'])
                        
                        # 키워드는 모든 DB 허용 (MESH, NCIT, HP 등 다양한 용어가 섞여있음)
                        if res:
                            batch_results.append({
                                'nctId': row['nctId'],
                                'sourceType': 'Metadata_Keyword',
                                'entityId': f"{res['db']}:{res['id']}",
                                'entityName': res['name'],
                                'entityType': res['db'], # DB명 그대로 사용 (예: NCIT, HP)
                                'score': res['score']
                            })

            # 배치 결과 저장 (Append Mode)
            if batch_results:
                mode = 'w' if i == 0 else 'a' 
                header = (i == 0)             
                pd.DataFrame(batch_results).to_csv(OUTPUT_METADATA_ENTITIES, mode=mode, index=False, header=header)
            
            pbar.update(len(df))

# ==========================================
# [2] Chunk 배치 처리 (NLP)
# ==========================================
def process_chunks_batch():
    print(f"\n🚀 [2/2] Chunk 배치 처리 시작: {CHUNK_FILE}")
    
    if os.path.exists(OUTPUT_CHUNK_ENTITIES): os.remove(OUTPUT_CHUNK_ENTITIES)
    
    try:
        total_rows = sum(1 for _ in open(CHUNK_FILE, encoding='utf-8')) - 1
    except:
        total_rows = None

    chunk_iter = pd.read_csv(CHUNK_FILE, chunksize=BATCH_SIZE)

    with tqdm(total=total_rows, unit='rows') as pbar:
        for i, df in enumerate(chunk_iter):
            batch_results = []
            
            texts = df['chunk'].fillna("").tolist()
            chunk_ids = df['chunk_id'].tolist()
            if 'nctid' in df.columns:
                nct_ids = df['nctid'].tolist()
            else:
                nct_ids = ["Unknown"] * len(texts)

            for doc, chunk_id, nct_id in zip(nlp.pipe(texts), chunk_ids, nct_ids):
                seen_entities = set()
                
                for ent in doc.ents:
                    res = get_cached_id(ent.text)
                    if res:
                        unique_key = (chunk_id, res['id'])
                        if unique_key not in seen_entities:
                            batch_results.append({
                                'nctId': nct_id,
                                'chunkId': chunk_id,
                                'sourceType': 'Chunk_Text',
                                'entityId': f"{res['db']}:{res['id']}",
                                'entityName': res['name'],
                                'entityType': res['db'],
                                'score': res['score'],
                                'originalText': ent.text
                            })
                            seen_entities.add(unique_key)
            
            if batch_results:
                mode = 'w' if i == 0 else 'a'
                header = (i == 0)
                pd.DataFrame(batch_results).to_csv(OUTPUT_CHUNK_ENTITIES, mode=mode, index=False, header=header)
            
            pbar.update(len(df))

# ==========================================
# [메인 실행]
# ==========================================
if __name__ == "__main__":
    process_metadata_batch() # Keywords 포함
    process_chunks_batch()
    
    print("\n✅ 모든 작업 완료!")
    print(f"1. {OUTPUT_METADATA_ENTITIES} (Conditions, Interventions, Keywords)")
    print(f"2. {OUTPUT_CHUNK_ENTITIES}")
    print(f"📊 캐시된 고유 단어 수: {len(id_cache)}개")
