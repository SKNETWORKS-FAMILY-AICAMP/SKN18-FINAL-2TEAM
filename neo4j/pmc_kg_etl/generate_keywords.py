"""
generate_keywords_llm_umls.py

목적: 
  1. 섹션별로 텍스트를 병합하여 LLM에게 전체 문맥을 제공
  2. 섹션 성격(Abstract, Results, Main 등)에 맞는 정교한 프롬프트로 엔티티 추출
  3. 추출된 엔티티를 scispaCy(UMLS)를 통해 정규화(Normalization)
  4. Knowledge Graph 구축용 CSV 2종 생성

입력: 
  - import/section_meta.csv
  - import/section_embedding.csv (파일명 주의: 공백이 있다면 수정 필요)

출력:
  - import/entities.csv
  - import/section_keywords.csv
"""

import pandas as pd
import spacy
import scispacy.linking  # 필수: 링커 파이프 등록용
from scispacy.linking import EntityLinker
from openai import OpenAI
import os
import json
from tqdm import tqdm

# ==============================================================================
# 1. 설정
# ==============================================================================

# OpenAI API 키 설정 (환경변수에 없다면 아래에 직접 입력)
# client = OpenAI(api_key="sk-...")
client = OpenAI() # API Key는 환경변수(OPENAI_API_KEY)에 설정되어 있다고 가정


# 분석할 섹션 카테고리 (사용자 데이터 기준)
TARGET_CATS = ['result', 'discussion', 'introduction', 'methods', 'abstract', 'main']

# UMLS 의미 타입 매핑 (T-Code -> Readable Type)
UMLS_SEMTYPE_TO_ENTITY_TYPE = {
    "T047": "disease", "T191": "neoplasm", "T116": "chemical", "T121": "drug",
    "T123": "protein", "T028": "gene_or_genome", "T046": "pathologic_function",
    "T059": "lab_procedure", "T061": "therapeutic_proc",
}

# ==============================================================================
# 2. 초기화 및 헬퍼 함수
# ==============================================================================

def init_umls_pipeline():
    """scispaCy + UMLS 링커 초기화"""
    print("⚙️ scispaCy 모델 로딩 중 (en_core_sci_lg)...")
    try:
        nlp = spacy.load("en_core_sci_lg")
    except OSError:
        print("❌ 모델이 없습니다. 설치 필요: pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_lg-0.5.1.tar.gz")
        exit(1)
        
    print("🔗 UMLS Entity Linker 연결 중...")
    # config 방식으로 링커 추가 (spaCy v3 호환)
    nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})
    linker = nlp.get_pipe("scispacy_linker")
    return nlp, linker

def extract_keywords_with_llm(text, section_type):
    """
    LLM을 사용하여 섹션 텍스트에서 '지식 그래프 노드'로 사용할 고품질 엔티티 추출
    (모든 섹션 타입 커버: result, discussion, introduction, methods, abstract, main)
    """
    if len(text) < 50: return []

    section_lower = str(section_type).lower()
    section_guide = ""

    # 섹션별 맞춤형 가이드 설정
    if "method" in section_lower:
        section_guide = "- **METHODS** section: Prioritize Specific assays, Cell lines (e.g., HeLa), Antibodies, Reagents, Equipment, Model organisms, and Software tools."
    elif "result" in section_lower:
        section_guide = "- **RESULTS** section: Prioritize Target molecules (Genes/Proteins), Observed Phenotypes, Statistical metrics (only critical ones), Chemicals tested, and quantitative findings."
    elif any(x in section_lower for x in ["intro", "discussion", "conclu"]):
        section_guide = "- **INTRO/DISCUSSION** section: Prioritize Diseases, Biological Pathways, Mechanisms of Action, Hypothesis, and Broader biological concepts."
    elif "abstract" in section_lower:
        section_guide = "- **ABSTRACT** section: Prioritize the Core Research Topic, Primary Target (Gene/Drug), Main Disease/Condition, and Key Methodological approach. Capture the 'Big Picture' entities."
    elif "main" in section_lower:
        section_guide = "- **MAIN BODY** (Review/General): Prioritize Broad Topics, Historical Concepts, classifications of Drugs/Diseases, and comparative mechanisms."
    else:
        section_guide = "- **GENERAL** section: Extract the most significant scientific entities mentioned."

    prompt = f"""
    You are a Senior Biocurator building a high-precision Biomedical Knowledge Graph. 
    Your task is to extract **Specific Named Entities** from the following research paper text.

    **Current Section Type:** {str(section_type).upper()}
    {section_guide}

    **[Extraction Rules]**
    1. **Target Categories:** Extract entities belonging strictly to:
       - **Genes/Proteins:** Use standard symbols (e.g., TP53, EGFR) or full names.
       - **Chemicals/Drugs:** Specific drug names, inhibitors, metabolites.
       - **Diseases/Phenotypes:** Specific conditions (e.g., Non-small cell lung cancer), symptoms.
       - **Species/Cell Lines:** e.g., Mus musculus, HEK293T.
       - **Methods/Techniques:** e.g., Western Blot, CRISPR-Cas9, RNA-seq.
       
    2. **Granularity:** - PREFER specific terms over general ones (e.g., "Lung Cancer" instead of "Cancer", "Cisplatin" instead of "Chemotherapy").
       - Extract **compound entities** if necessary (e.g., "EGFR mutation", "p53 signaling pathway").

    3. **[STRICT EXCLUSION LIST] - DO NOT EXTRACT:**
       - Generic nouns: "study", "data", "result", "analysis", "patient", "group", "level", "effect", "role", "evidence".
       - Vague biological terms: "cell", "tissue", "protein", "gene", "expression", "activity".
       - Units/Numbers alone: "mg/ml", "p<0.05", "24h".
       - Verbs/Adjectives: "increased", "significant", "inhibited", "associated".

    **Output Requirement:**
    - Extract between **5 to 15** most distinct and important entities.
    - Return ONLY a valid JSON object with a single key "keywords".
    
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

def normalize_with_umls(keyword_list, nlp, linker):
    """LLM이 뽑은 키워드를 UMLS로 정규화"""
    results = []
    
    for kw in keyword_list:
        doc = nlp(kw)
        
        # 가장 적합한 엔티티 찾기 (Best Match)
        best_cui, best_score, best_name, best_type = None, 0.0, kw, "other" # 기본값
        
        for ent in doc.ents:
            if not ent._.kb_ents: continue
            
            # scispacy는 점수순으로 정렬해서 줌. 첫 번째가 가장 유력.
            cui, score = ent._.kb_ents[0]
            
            if score > best_score:
                best_cui = cui
                best_score = score
                
                # 상세 정보 조회
                umls_ent = linker.kb.cui_to_entity[cui]
                best_name = umls_ent.canonical_name # 정규화된 이름
                
                # 타입 매핑
                for t in umls_ent.types:
                    if t in UMLS_SEMTYPE_TO_ENTITY_TYPE:
                        best_type = UMLS_SEMTYPE_TO_ENTITY_TYPE[t]
                        break
        
        # 정규화 성공 여부와 상관없이 저장 (실패하면 원문 그대로 Entity 생성)
        # 단, 점수가 너무 낮거나 매핑 안된 건 'other' 타입으로 저장되거나 필터링 가능
        if best_cui:
            results.append({
                "raw_keyword": kw,
                "normalized_entity": best_name,
                "entity_type": best_type,
                "umls_cui": best_cui,
                "score": best_score
            })
        else:
            # UMLS에 없지만 LLM이 중요하다고 뽑은 단어 -> 그대로 사용
            results.append({
                "raw_keyword": kw,
                "normalized_entity": kw.title(), # 첫글자 대문자화 정도만
                "entity_type": "custom",
                "umls_cui": "N/A",
                "score": 1.0 # LLM 신뢰
            })
            
    return results

# ==============================================================================
# 3. 메인 프로세스
# ==============================================================================

def run_pipeline(meta_csv, embedding_csv, out_entities, out_keywords):
    # 1. 데이터 로드 및 병합
    if not os.path.exists(meta_csv) or not os.path.exists(embedding_csv):
        print("❌ 입력 파일이 없습니다.")
        return

    print("📂 데이터 로딩 및 병합 중...")
    
    # A. 섹션 메타 (카테고리 필터링)
    df_meta = pd.read_csv(meta_csv)
    pat = '|'.join(TARGET_CATS)
    mask = df_meta['section_category'].astype(str).str.lower().str.contains(pat, na=False)
    target_sections = df_meta[mask][['section_id', 'section_category']]
    
    # B. 텍스트 청크 병합 (Chunk -> Full Section Text)
    # section_embedding.csv 읽기 (파일명 주의: 공백이 있으면 수정 필요)
    df_chunk = pd.read_csv(embedding_csv)
    
    # section_id별로 텍스트 합치기 (순서 보장)
    df_text = df_chunk.sort_values(['section_id', 'chunk_seq']).groupby('section_id')['text_chunk'].apply(lambda x: " ".join(x.astype(str))).reset_index()
    
    # C. 조인 (Target Section만 남김)
    df_process = pd.merge(target_sections, df_text, on='section_id', how='inner')
    
    print(f"🎯 분석 대상 섹션: {len(df_process)}개 (LLM 비용 고려하여 필요시 샘플링하세요)")
    
    # 2. 파이프라인 초기화
    nlp, linker = init_umls_pipeline()
    
    # 3. 실행 루프
    all_entities = []
    all_keywords = []
    
    print("🚀 Extraction & Normalization 시작...")
    for idx, row in tqdm(df_process.iterrows(), total=len(df_process)):
        sec_id = row['section_id']
        text = row['text_chunk']
        cat = row['section_category']
        
        # Step 1: LLM (Keyword Extraction)
        raw_keywords = extract_keywords_with_llm(text, cat)
        if not raw_keywords: continue
        
        # Step 2: UMLS (Normalization)
        normalized_data = normalize_with_umls(raw_keywords, nlp, linker)
        
        for item in normalized_data:
            # 관계 (Section -> Keyword -> Entity)
            all_keywords.append({
                "section_id": sec_id,
                "raw_keyword": item['raw_keyword'],
                "normalized_entity": item['normalized_entity'],
                "score": item['score']
            })
            
            # 노드 (Entity Definition)
            all_entities.append({
                "normalized_entity": item['normalized_entity'],
                "entity_type": item['entity_type'],
                "umls_cui": item['umls_cui']
            })

    # 4. 저장
    if all_entities:
        # 중복 제거 후 저장
        df_ent = pd.DataFrame(all_entities).drop_duplicates(subset=['normalized_entity'])
        df_ent.to_csv(out_entities, index=False)
        
        df_kw = pd.DataFrame(all_keywords).drop_duplicates()
        df_kw.to_csv(out_keywords, index=False)
        
        print(f"\n✅ 완료!")
        print(f"   - entities.csv: {len(df_ent)}개 엔티티")
        print(f"   - section_keywords.csv: {len(df_kw)}개 관계")
    else:
        print("⚠️ 데이터가 생성되지 않았습니다.")

if __name__ == "__main__":
    BASE = "import"
    if not os.path.exists(BASE): os.makedirs(BASE)
    
    # 파일명은 사용자 환경에 맞게 수정
    # section_embedding.csv 파일명이 실제로는 'section _embedding.csv'인지 확인 필요
    META_CSV = os.path.join(BASE, "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\data\\pmc_data\\meta_new.csv")
    CHUNK_CSV = os.path.join(BASE, "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\data\\pmc_data\\before_embedding.csv") 
    
    OUT_ENTITIES = os.path.join(BASE, "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\import\\entities.csv")
    OUT_KEYWORDS = os.path.join(BASE, "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\import\\section_keywords.csv")
    
    run_pipeline(META_CSV, CHUNK_CSV, OUT_ENTITIES, OUT_KEYWORDS)