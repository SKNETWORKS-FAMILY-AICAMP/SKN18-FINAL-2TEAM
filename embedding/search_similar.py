import psycopg2
from openai import OpenAI
import time
import os
import json
from dotenv import load_dotenv

# [설정 1] .env 파일 로드
load_dotenv()

# ==========================================
# [설정 2] DB 연결 및 테이블 매핑
# ==========================================
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD")
}

# 1. 청크 테이블
CHUNK_TABLE = os.getenv("DB_TABLE_NAME", "pmc_section_chunk") 
CHUNK_TEXT_COL = os.getenv("DB_TEXT_COL", "text_chunk")
CHUNK_EMBED_COL = os.getenv("DB_EMBEDDING_COL", "embedding")
CHUNK_ID_COL = "chunk_id"
CHUNK_SEC_ID_COL = "section_id" 

# 2. 메타데이터 테이블
META_TABLE = os.getenv("DB_META_TABLE_NAME", "pmc_section_meta") 
META_SEC_ID_COL = "section_id"
META_PMCID_COL = "pmcid"
META_CAT_COL = "section_category"

TOP_K = 5
client = OpenAI()

# ==========================================
# [데이터] 연구자 실전 질문 20선 (Broad & Insightful)
# ==========================================
# verify_rag_json.py의 test_cases 부분을 아래 코드로 교체하세요.

test_cases = [
    # =========================================================
    # 1. Protein Structure & Enzyme Engineering (단백질 구조/효소)
    # =========================================================
    {
        "id": "Enzyme_Q1",
        "category": "Catalytic Mechanism",
        "question": "베타-사이클로덱스트린(β-Cyclodextrin) 이량체가 비타민 D3의 이성질화 반응 속도를 40배 가속화시키는 물리화학적 원인은 무엇인가?",
        # 근거: PMC12529775 (Unraveling the Catalytic Mechanism...)
        "keywords": ["confinement", "flexibility", "isomerization", "catalytic"],
    },
    {
        "id": "Enzyme_Q2",
        "category": "Protein Stability",
        "question": "RBP-Albumin 융합 단백질(R31)의 생산성과 열안정성을 동시에 높이기 위해 도메인 IIIA에 어떤 구조적 변이를 도입했는가?",
        # 근거: PMC11720212 (Strategic Optimization...)
        "keywords": ["disulfide", "mutation", "stability", "productivity", "RBP"],
    },
    {
        "id": "Enzyme_Q3",
        "category": "Enzyme Efficiency",
        "question": "RNase J1과 J2 파라로그(Paralog) 사이에서 촉매 효율의 차이가 발생하는 구조적, 전자적 이유는 무엇이라고 설명되는가?",
        # 근거: PMC11815676 (A physicochemical rationale...)
        "keywords": ["RNase J", "catalytic efficiency", "active site", "metal ion"],
    },
    {
        "id": "Enzyme_Q4",
        "category": "Folding",
        "question": "거대 단백질의 접힘(Folding) 과정에서 오프-패스웨이(Off-pathway) 응집을 막고 올바른 접힘을 유도하는 '중간체(Intermediate)'의 역할은?",
        # 근거: PMC11761020 (Discovery of an on-pathway...), PMC12260327
        "keywords": ["folding", "intermediate", "aggregation", "off-pathway"],
    },

    # =========================================================
    # 2. Cancer Biology & Oncology (암 생물학/임상)
    # =========================================================
    {
        "id": "Cancer_Q1",
        "category": "Therapeutic Strategy",
        "question": "삼중 음성 유방암(TNBC) 치료에서 나노백신(Nanovaccine)과 면역관문억제제(예: anti-OX40)를 병용했을 때 어떤 시너지 효과가 나타나는가?",
        # 근거: PMC12581784 (Multifunctional Nanovaccine...)
        "keywords": ["nanovaccine", "TNBC", "immune checkpoint", "OX40", "synergy"],
    },
    {
        "id": "Cancer_Q2",
        "category": "Drug Resistance",
        "question": "비소세포폐암(NSCLC)에서 오시머티닙(Osimertinib) 내성을 극복하기 위해 안로티닙(Anlotinib)을 병용할 때, 억제되는 주요 기전은 무엇인가?",
        # 근거: PMC12481689 (Anlotinib reverses...)
        "keywords": ["resistance", "Anlotinib", "EMT", "angiogenesis", "Osimertinib"],
    },
    {
        "id": "Cancer_Q3",
        "category": "Clinical Outcome",
        "question": "폐선암 수술 중 흉막 전이가 발견된 환자에게 주 종양 절제(Main tumor resection)를 시행하는 것이 생존율 측면에서 어떤 이점이 있는가?",
        # 근거: PMC12527613 (Long-term Survival Outcomes...)
        "keywords": ["survival", "resection", "pleural metastasis", "prognosis"],
    },
    {
        "id": "Cancer_Q4",
        "category": "Metastasis Mechanism",
        "question": "LncRNA H19이 폐동맥 내피세포에서 혈관신생(Angiogenesis)을 촉진하는 신호 전달 경로와 기전은 무엇인가?",
        # 근거: PMC12602639 (LncRNA H19 Promotes...)
        "keywords": ["H19", "angiogenesis", "VEGF", "HIF-1", "pathway"],
    },

    # =========================================================
    # 3. AI-based Modeling & Drug Design (AI 신약개발)
    # =========================================================
    {
        "id": "AI_Q1",
        "category": "Model Methodology",
        "question": "구조 기반 약물 설계(SBDD) 모델인 'DiffInt'는 기존 모델들과 달리 단백질-리간드 간의 어떤 상호작용을 명시적으로 학습에 반영하는가?",
        # 근거: PMC11733934 (DiffInt: A Diffusion Model...)
        "keywords": ["DiffInt", "hydrogen bond", "interaction", "diffusion"],
    },
    {
        "id": "AI_Q2",
        "category": "Virtual Screening",
        "question": "전복(Haliotis discus hannai) 유래 펩타이드를 이용해 고지혈증 치료 타겟인 HMGCR 억제제를 발굴한 가상 스크리닝 과정은?",
        # 근거: PMC11730078 (Virtual screening and evaluation...)
        "keywords": ["HMGCR", "peptide", "virtual screening", "hyperlipidemia"],
    },
    {
        "id": "AI_Q3",
        "category": "Protein Design AI",
        "question": "효소의 열안정성 최적화를 위해 '단백질 언어 모델(Pro-PRIME)'을 사용했을 때, 다중 변이(Multiple mutations) 간의 어떤 효과를 예측하여 성공률을 높였는가?",
        # 근거: PMC11685841 (Optimizing enzyme thermostability...)
        "keywords": ["Pro-PRIME", "epistasis", "thermostability", "language model"],
    },
    {
        "id": "AI_Q4",
        "category": "Interface Prediction",
        "question": "단백질-단백질 상호작용(PPI) 인터페이스의 품질을 평가하는 'EquiRank' 모델은 어떤 딥러닝 아키텍처와 특징(Feature)을 결합하여 성능을 높였는가?",
        # 근거: PMC11755013 (EquiRank: Improved protein-protein...)
        "keywords": ["EquiRank", "graph neural network", "GNN", "interface", "ESM"],
    },

    # =========================================================
    # 4. Cross-disciplinary & Trends (융합 연구)
    # =========================================================
    {
        "id": "Trend_Q1",
        "category": "Natural Products",
        "question": "감초 추출물인 Isoliquiritigenin(ISL)이 유방암 세포의 폐 전이를 억제하는 구체적인 분자적 기전은 무엇인가?",
        # 근거: PMC12624662 (Isoliquiritigenin...)
        "keywords": ["Isoliquiritigenin", "metastasis", "breast cancer", "PI3K/Akt", "MMP"],
    },
    {
        "id": "Trend_Q2",
        "category": "Rare Case",
        "question": "자궁경부암이나 간암(HCC) 환자에게서 드물게 발생하는 위장관(Gastric) 또는 부신(Adrenal) 전이 사례의 임상적 특징과 진단 시 주의점은?",
        # 근거: PMC12478650, PMC12481543
        "keywords": ["metastasis", "gastric", "adrenal", "rare", "case report"],
    },
]

# ==========================================
# [기능 1] 번역 및 LLM 평가
# ==========================================
def translate_to_english(text):
    """ 질문 한영 번역 """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Translate the scientific question to English. Output ONLY the translated text."},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except:
        return text

def evaluate_context_with_llm(question, retrieved_chunks):
    """
    [종합 평가]
    여러 개의 검색된 청크들을 모두 모아서(Context Aggregation),
    질문에 대한 포괄적인 답변이 가능한지 평가합니다.
    """
    
    # 여러 청크를 하나의 텍스트로 합침
    combined_context = "\n\n".join([
        f"[Chunk {i+1}] {chunk_text}" 
        for i, chunk_text in enumerate(retrieved_chunks)
    ])

    prompt = f"""
    You are a strict evaluator for a RAG system aimed at scientific research.
    
    User Question: "{question}"
    
    Retrieved Contexts (from top {len(retrieved_chunks)} chunks):
    {combined_context}
    
    Task: 
    1. Read the retrieved contexts carefully.
    2. Determine if the COMBINED information is sufficient to construct a comprehensive answer to the user's question.
    3. If yes, briefly summarize the answer based ONLY on the context.
    4. If no, explain what specific information is missing.
    
    Output format:
    Status: [YES or NO]
    Summary: [Your summarized answer or the missing information in Korean]
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Status: ERROR\nSummary: {e}"

def get_embedding(text):
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

# ==========================================
# [기능 2] SQL 검색 (카테고리 포함)
# ==========================================
def search_pgvector_join(conn, query_text, k=5):
    query_vector = get_embedding(query_text)
    vector_str = str(query_vector)
    
    # [수정됨] section_category 추가 조회
    sql = f"""
    SELECT 
        c.{CHUNK_TEXT_COL} as text,
        c.{CHUNK_ID_COL} as chunk_id,
        m.{META_PMCID_COL} as pmcid,
        m.{META_CAT_COL} as category,
        1 - (c.{CHUNK_EMBED_COL} <=> %s) as similarity
    FROM {CHUNK_TABLE} c
    LEFT JOIN {META_TABLE} m ON c.{CHUNK_SEC_ID_COL} = m.{META_SEC_ID_COL}
    ORDER BY c.{CHUNK_EMBED_COL} <=> %s
    LIMIT %s;
    """
    
    with conn.cursor() as cur:
        cur.execute(sql, (vector_str, vector_str, k))
        # 결과: [(text, chunk_id, pmcid, category, similarity), ...]
        return cur.fetchall()

# ==========================================
# [메인] 실행 로직
# ==========================================
def run_verification():
    print("🔌 PostgreSQL 연결 중...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ 연결 성공!\n")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return

    print(f"🚀 총 {len(test_cases)}개의 질문 테스트 (JSON 저장 포함)...\n")
    
    total_score = 0
    all_results = [] # JSON 저장을 위한 리스트
    
    for case in test_cases:
        print("=" * 80)
        print(f"🔹 [{case['id']}] 질문(KR): {case['question']}")
        
        # 1. 번역
        eng_question = translate_to_english(case['question'])
        print(f"   🇺🇸 번역(EN): {eng_question}")
        
        # 결과 저장을 위한 딕셔너리
        case_log = {
            "id": case['id'],
            "question_kr": case['question'],
            "question_en": eng_question,
            "target_keywords": case['keywords'],
            "retrieved_chunks": [],
            "final_status": "FAIL",
            "llm_eval": "N/A"
        }

        try:
            # 2. 검색
            start_t = time.time()
            records = search_pgvector_join(conn, eng_question, k=TOP_K)
            elapsed = time.time() - start_t
            
            if not records:
                print(f"   ❌ 검색 결과 없음")
                all_results.append(case_log)
                continue

            # 3. 결과 분석 및 종합 (Aggregation)
            found_keywords = set()
            retrieved_texts = []
            
            print(f"   🔎 검색된 상위 {TOP_K}개 청크 요약:")
            
            for i, row in enumerate(records):
                # 데이터 언패킹 (5개 변수)
                text, chunk_id, pmcid, category, score = row
                retrieved_texts.append(text)
                
                # 키워드 누적 검사
                for k in case['keywords']:
                    if k.lower() in text.lower():
                        found_keywords.add(k)
                
                # 정보 저장
                chunk_info = {
                    "rank": i + 1,
                    "similarity": float(score),
                    "pmcid": pmcid,
                    "chunk_id": chunk_id,
                    "section_category": category,
                    "text_preview": text[:100] + "..."
                }
                case_log["retrieved_chunks"].append(chunk_info)

                # 간단 출력 (수정: f-string 에러 해결)
                cat_str = f"[{category}]" if category else ""
                # 줄바꿈 제거 후 출력용 변수 생성
                preview_safe = text[:60].replace('\n', ' ')
                print(f"    - Rank {i+1} ({score:.3f}): {cat_str} ...{preview_safe}...")

            # 4. LLM 종합 평가 (모든 청크를 합쳐서 판단)
            print(f"   🤖 LLM이 {TOP_K}개 청크를 종합하여 평가 중...")
            eval_res = evaluate_context_with_llm(eng_question, retrieved_texts)
            
            # 결과 파싱
            llm_status = "UNKNOWN"
            llm_summary = ""
            for line in eval_res.split('\n'):
                if line.startswith("Status:"):
                    llm_status = line.replace("Status:", "").strip()
                elif line.startswith("Summary:"):
                    llm_summary = line.replace("Summary:", "").strip()
            
            case_log["llm_eval"] = f"{llm_status} | {llm_summary}"
            
            # 5. 종합 판정 출력
            icon = "✅" if "YES" in llm_status.upper() else "⚠️"
            print(f"\n   👉 [LLM 종합 판정]: {icon} {llm_status}")
            print(f"      📝 요약/이유: {llm_summary}")
            
            # 키워드 매칭율 (보조 지표)
            missing = [k for k in case['keywords'] if k not in found_keywords]
            print(f"      🔍 키워드 매칭: {len(found_keywords)}/{len(case['keywords'])} 발견 (누락: {missing})")

            if "YES" in llm_status.upper():
                total_score += 1
                case_log["final_status"] = "PASS"
            else:
                case_log["final_status"] = "FAIL"
            
            all_results.append(case_log)

        except Exception as e:
            print(f"   ⚠️ 에러 발생: {e}")
            conn.rollback() 
            case_log["error"] = str(e)
            all_results.append(case_log)
            
        print("\n")

    # 6. JSON 파일 저장
    json_filename = "rag_verification_results.json"
    try:
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
        print(f"💾 검증 결과가 '{json_filename}' 파일로 저장되었습니다.")
    except Exception as e:
        print(f"❌ JSON 저장 실패: {e}")

    print(f"📊 최종 점수 (LLM 기준): {total_score}/{len(test_cases)} 통과")
    conn.close()

if __name__ == "__main__":
    run_verification()