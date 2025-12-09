import pandas as pd
import spacy
import scispacy.linking
from scispacy.linking import EntityLinker
from openai import OpenAI
import os
import json
from tqdm import tqdm
from dotenv import load_dotenv  # [추가] .env 로드용

# ==============================================================================
# 1. 설정 및 상수 정의
# ==============================================================================

# [수정] .env 파일 로드 (현재 디렉토리의 .env 파일을 찾아 환경변수로 설정)
load_dotenv()

# API 키 확인 (디버깅용, 실제 키 출력은 보안상 주의)
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY가 .env 파일이나 환경변수에 없습니다.")
    exit(1)

client = OpenAI() # 환경변수 OPENAI_API_KEY 사용

# 분석할 섹션 카테고리
TARGET_CATS = ['result', 'discussion', 'introduction', 'methods', 'abstract', 'main']

# UMLS 의미 타입 매핑 (T-Code -> Readable Type)
UMLS_SEMTYPE_TO_ENTITY_TYPE = {
    "T047": "disease", "T191": "neoplasm", "T116": "chemical", "T121": "drug",
    "T123": "protein", "T028": "gene_or_genome", "T046": "pathologic_function",
    "T059": "lab_procedure", "T061": "therapeutic_proc",
}

# ==============================================================================
# 2. 핵심 기능 분리 (LLM 추출 / 엔티티 정규화)
# ==============================================================================

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

def extract_raw_entities_llm(text, section_type):
    """
    [기능 1] LLM을 사용하여 텍스트에서 원시 엔티티 정보를 구조화하여 추출
    - 역할: 텍스트 이해, 문맥 파악, 변이-단백질 연결, 축약어 풀기
    """
    if len(text) < 50: return []

    section_guide = get_section_guide(section_type)

    prompt = f"""
    You are a Senior Biocurator. Extract specific Named Entities from the text for a Knowledge Graph.

    **Current Section:** {str(section_type).upper()}
    {section_guide}

    **[CRITICAL RULES for Normalization]**
    1. **Mutations:** ALWAYS link a mutation to its target protein.
       - Bad: "H70", "L858R" (Ambiguous)
       - Good: "TP53 p.His70", "EGFR p.Leu858Arg" (Contextualized)
    2. **Amino Acids:** Convert 1-letter codes to 3-letter codes.
       - "H70" -> "p.His70", "V600E" -> "p.Val600Glu"
    3. **General:** Prefer specific names ("Gefitinib") over classes ("TKI").

    **[Output Format]**
    Return a JSON object with a key "keywords". Each item must have:
    - "entity": The standardized, full name (e.g., "EGFR p.Leu858Arg").
    - "type": One of ["mutation", "protein", "drug", "disease", "method", "other"].
    - "raw_text": The exact text found in the paper.

    Text:
    {text[:3500]}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": "You are a precise biomedical entity extractor."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1 
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("keywords", [])
    except Exception as e:
        print(f"⚠️ LLM Error: {e}")
        return []

def normalize_entity_generation(llm_results, nlp, linker):
    """
    [기능 2] LLM 추출 결과를 바탕으로 최종 엔티티 생성 및 UMLS ID 매핑
    - 역할: LLM이 준 정보 검증, UMLS CUI 찾기, 최종 데이터 포맷팅
    """
    results = []
    
    for item in llm_results:
        # LLM이 정제해준 표준 이름 사용
        query_text = item.get('entity', '')
        entity_type_llm = item.get('type', 'other')
        raw_text = item.get('raw_text', query_text)

        best_cui = None
        best_name = query_text 
        best_type = entity_type_llm
        score = 0.0

        # 전략: Mutation은 UMLS에 없을 확률이 높으므로 LLM을 전적으로 신뢰
        if entity_type_llm == 'mutation':
            best_cui = "MUTATION_NODE" # 혹은 None
            score = 1.0 # LLM 신뢰
        else:
            # 그 외(단백질, 약물 등)는 scispaCy로 UMLS ID 조회 시도
            doc = nlp(query_text)
            best_score = 0.0
            
            for ent in doc.ents:
                if not ent._.kb_ents: continue
                cui, sc = ent._.kb_ents[0]
                
                # 점수가 더 높으면 갱신
                if sc > best_score:
                    best_score = sc
                    best_cui = cui
                    
                    # UMLS 표준명으로 교체 (선택사항)
                    umls_ent = linker.kb.cui_to_entity[cui]
                    best_name = umls_ent.canonical_name 
                    
                    # 타입 매핑
                    for t in umls_ent.types:
                        if t in UMLS_SEMTYPE_TO_ENTITY_TYPE:
                            best_type = UMLS_SEMTYPE_TO_ENTITY_TYPE[t]
                            break
            score = best_score if best_score > 0 else 0.8 # 매칭 안돼도 LLM이 뽑았으니 기본 점수 부여

        results.append({
            "raw_keyword": raw_text,
            "normalized_entity": best_name,
            "entity_type": best_type,
            "umls_cui": best_cui if best_cui else "N/A",
            "score": score
        })
            
    return results

def get_section_guide(section_type):
    """섹션별 프롬프트 가이드 반환 헬퍼"""
    s = str(section_type).lower()
    if "result" in s: return "Focus on: Target molecules (Genes/Proteins), Observed Phenotypes, Chemicals."
    if "method" in s: return "Focus on: Assays, Cell lines, Reagents, Equipment."
    if "abstract" in s: return "Focus on: Core Research Topic, Primary Target, Main Disease."
    return "Extract the most significant scientific entities."

# ==============================================================================
# 3. 배치 실행 파이프라인
# ==============================================================================

def run_batch_pipeline(meta_csv, embedding_csv, out_entities, out_keywords, batch_size=10):
    # 1. 데이터 준비
    if not os.path.exists(meta_csv) or not os.path.exists(embedding_csv):
        print("❌ 입력 파일 확인 필요")
        return

    print("📂 데이터 병합 중...")
    df_meta = pd.read_csv(meta_csv)
    mask = df_meta['section_category'].astype(str).str.lower().str.contains('|'.join(TARGET_CATS), na=False)
    target_ids = df_meta[mask]['section_id'].unique()

    df_chunk = pd.read_csv(embedding_csv)
    # Target Section만 필터링 및 텍스트 병합
    df_chunk = df_chunk[df_chunk['section_id'].isin(target_ids)]
    df_process = df_chunk.sort_values(['section_id', 'chunk_seq']).groupby('section_id')['text_chunk'].apply(lambda x: " ".join(x.astype(str))).reset_index()
    
    # 카테고리 정보 다시 결합
    df_process = pd.merge(df_process, df_meta[['section_id', 'section_category']], on='section_id', how='left')

    # 2. 이어하기(Resume) 체크
    processed_ids = set()
    if os.path.exists(out_keywords):
        try:
            processed_ids = set(pd.read_csv(out_keywords, usecols=['section_id'])['section_id'].unique())
            print(f"⏭️  기존 완료된 {len(processed_ids)}개 섹션 건너뜀")
        except: pass

    df_remaining = df_process[~df_process['section_id'].isin(processed_ids)]
    if len(df_remaining) == 0:
        print("✅ 모든 작업이 완료되어 있습니다.")
        return

    print(f"🚀 {len(df_remaining)}개 섹션 처리 시작 (Batch: {batch_size})")

    # 3. 모델 로드
    nlp, linker = init_umls_pipeline()

    # 4. 배치 루프
    batch_kw = []
    batch_ent = []

    for idx, row in tqdm(df_remaining.iterrows(), total=len(df_remaining)):
        sec_id = row['section_id']
        text = row['text_chunk']
        cat = row['section_category']

        try:
            # [Step 1] LLM Extraction
            llm_results = extract_raw_entities_llm(text, cat)
            
            if llm_results:
                # [Step 2] Entity Normalization
                final_entities = normalize_entity_generation(llm_results, nlp, linker)

                # 결과 수집
                for item in final_entities:
                    batch_kw.append({
                        "section_id": sec_id,
                        **item # raw_keyword, normalized_entity, score 등 포함
                    })
                    batch_ent.append({
                        "normalized_entity": item['normalized_entity'],
                        "entity_type": item['entity_type'],
                        "umls_cui": item['umls_cui']
                    })
            else:
                # 결과가 없어도 처리했다는 표시를 남기려면 빈 값이라도 저장하거나 로그 필요
                # 여기서는 그냥 넘어감 (나중에 재시도 가능하게)
                pass

        except Exception as e:
            print(f"Error processing {sec_id}: {e}")
            continue

        # [Step 3] 중간 저장
        if len(batch_kw) >= batch_size or idx == df_remaining.index[-1]:
            if batch_kw:
                # 파일 저장 (Append 모드)
                mode = 'a'
                header_kw = not os.path.exists(out_keywords)
                header_ent = not os.path.exists(out_entities)

                pd.DataFrame(batch_kw).to_csv(out_keywords, mode=mode, header=header_kw, index=False)
                pd.DataFrame(batch_ent).to_csv(out_entities, mode=mode, header=header_ent, index=False)
                
                # 버퍼 초기화
                batch_kw = []
                batch_ent = []

    print("\n✅ 전체 작업 완료! (entities.csv의 중복 제거를 권장합니다)")


if __name__ == "__main__":
    BASE = "import"
    if not os.path.exists(BASE): os.makedirs(BASE)


    # 윈도우 경로 사용 시 r"..." 스트링을 쓰거나 / 슬래시 사용 권장
    META = r"C:\dev\study\skn18_fianl-2team\SKN18-FINAL-2TEAM\data\pmc_data\meta_new.csv"
    CHUNK = r"C:\dev\study\skn18_fianl-2team\SKN18-FINAL-2TEAM\data\pmc_data\before_embedding.csv"
    
    OUT_ENT = r"C:\dev\study\skn18_fianl-2team\SKN18-FINAL-2TEAM\import\entities_v2.csv"
    OUT_KW = r"C:\dev\study\skn18_fianl-2team\SKN18-FINAL-2TEAM\import\section_keywords_v2.csv"
    run_batch_pipeline(META, CHUNK, OUT_ENT, OUT_KW, batch_size=10)