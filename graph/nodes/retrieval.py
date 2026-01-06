"""
retrieval.py
-------------------------------------
질문 타입별로 다른 임베딩 및 검색 전략 사용
- BIO_Q: OpenAI 임베딩 + pgvector/neo4j 검색
- PROTOCOL_Q: 로컬 임베딩 + pgvector/neo4j 검색 (보안 이슈)

리턴되는 state값:
    retrieval_results: List[Dict[str, Any]]   # VectorDB/Neo4j RAW 검색 결과

📌 사용 중인 모델 (변경 시 아래 상수 수정):
    - OpenAI 임베딩: text-embedding-3-large (3072차원)
    - 로컬 임베딩: sentence-transformers/all-MiniLM-L6-v2 (384차원)
    - Neo4j 임베딩: text-embedding-3-large
"""

from typing import Dict, Any, List
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# ============================================
# 🔹 모델 설정 (변경 시 여기만 수정)
# ============================================
OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"  # 3072차원
OPENAI_EMBEDDING_DIM = 3072

LOCAL_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384차원
LOCAL_EMBEDDING_DIM = 384

NEO4J_EMBEDDING_MODEL = "text-embedding-3-large"  # Neo4j TextRetriever용

# ============================================
# 🔹 임베딩 함수
# ============================================

def embed_query_openai(query: str) -> List[float]:
    """
    OpenAI 임베딩 모델 사용 (BIO_Q용)
    
    Args:
        query: 검색 쿼리
        
    Returns:
        임베딩 벡터
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,  # 상수 사용
            input=query
        )
        embedding = response.data[0].embedding
        print(f"[OpenAI Embedding] {OPENAI_EMBEDDING_MODEL} 생성 완료: {len(embedding)}차원")
        return embedding
        
    except Exception as e:
        print(f"[OpenAI Embedding] 오류: {e}")
        # 더미 벡터 반환 (테스트용)
        return [0.0] * OPENAI_EMBEDDING_DIM


def embed_query_local(query: str) -> List[float]:
    """
    로컬 임베딩 모델 사용 (PROTOCOL_Q용 - 보안)
    
    Args:
        query: 검색 쿼리
        
    Returns:
        임베딩 벡터
    """
    try:
        from sentence_transformers import SentenceTransformer
        
        # 로컬 모델 로드 (한번만 로드되도록 캐싱 필요)
        model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)  # 상수 사용
        embedding = model.encode(query).tolist()
        
        print(f"[Local Embedding] {LOCAL_EMBEDDING_MODEL} 생성 완료: {len(embedding)}차원")
        return embedding
        
    except Exception as e:
        print(f"[Local Embedding] 오류: {e}")
        # 더미 벡터 반환 (테스트용)
        return [0.0] * LOCAL_EMBEDDING_DIM


# ============================================
# 🔹 pgvector 검색 함수
# ============================================

def search_pgvector(query_embedding: List[float], top_k: int = 50, query_text: str = "") -> List[Dict[str, Any]]:
    """
    pgvector에서 코사인 유사도 기반 검색
    
    Args:
        query_embedding: 쿼리 임베딩 벡터
        top_k: 반환할 결과 개수
        query_text: 원본 쿼리 텍스트 (더미 데이터 시나리오 판별용)
        
    Returns:
        검색 결과 리스트
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # PostgreSQL 연결
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # pgvector 코사인 유사도 검색 쿼리
        # 실제 테이블 구축 시: papers, protocols 등의 테이블명 사용
        query = f"""
        SELECT 
            id,
            content,
            metadata,
            1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM papers_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        
        # 벡터를 문자열로 변환
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        cursor.execute(query, (embedding_str, embedding_str, top_k))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 결과 포맷팅
        formatted_results = []
        for row in results:
            formatted_results.append({
                "content": row["content"],
                "metadata": row.get("metadata", {}),
                "score": float(row["cosine_similarity"]),
                "source": "pgvector"
            })
        
        print(f"[pgvector] {len(formatted_results)}개 결과 검색 완료")
        return formatted_results
        
    except Exception as e:
        print(f"[pgvector] 오류: {e}")
        print(f"[pgvector] 더미 데이터 반환 (실제 DB 미구축)")
        
        # 더미 데이터 반환 - 시나리오별 분기
        query_lower = query_text.lower() if query_text else ""
        
        # 시나리오 3: PROTOCOL_Q (KaiC 단백질 정제 프로토콜)
        if "kaic" in query_lower and "정제" in query_lower or "purification" in query_lower:
            print(f"[pgvector] 시나리오 3: KaiC 프로토콜 더미 데이터 반환")
            return [
                {
                    "content": """KaiC Protein Purification Protocol - Part 1 (Initial Steps):
transformation: Transform expression plasmid into competent cells
pre-culture: Inoculate 5ml LB medium with antibiotics, grow overnight at 37°C
expression culture: Transfer pre-culture to 500ml LB medium, grow at 37°C to OD600=0.6
induction of protein expression: Add IPTG to final concentration 0.5mM, continue at 30°C for 4h
spin down cells: Harvest cells by centrifugation for 10 min at 4°C and 4000g
enzymatic lysis by lysozyme: Resuspend pellet in lysis buffer with 1mg/ml lysozyme, incubate 30min on ice
sonication: Sonicate on ice with 10 cycles (30s on, 30s off) at 40% amplitude""",
                    "metadata": {
                        "title": "GST-tagged protein purification protocol",
                        "source_type": "protocol",
                        "year": 2023,
                        "month": 5,
                        "day": 12,
                        "journal": "Protocol",
                        "pmid": "",
                        "authors": "Laboratory Protocol Database",
                        "doi": "10.17504/protocols.io.kaic001",
                        "protein": "KaiC",
                        "step": "1-3",
                        "db": "pgvector"
                    },
                    "score": 0.95,
                    "source": "pgvector_dummy"
                },
                {
                    "content": """KaiC Protein Purification Protocol - Part 2 (Washing & Cleavage):
spin down glutathione resin: Centrifuge for 4 min at 1500g and 4°C
washing step 1: Wash resin with 10ml PBS, spin down
washing step 2: Wash resin with 10ml high-salt buffer (PBS + 500mM NaCl), spin down
washing step 3: Wash resin with 10ml PBS, spin down
washing step 4: Wash resin with 10ml prescission buffer, spin down
prescission buffer preparation: Use 1ml ice cold prescission buffer
transfer resin: Use prescission buffer to transfer pelleted resin to a 2ml reaction tube
overnight cleavage: Add PreScission protease (1:100 ratio), rotate overnight at 4°C""",
                    "metadata": {
                        "title": "PreScission protease cleavage protocol",
                        "source_type": "protocol",
                        "year": 2023,
                        "month": 5,
                        "day": 12,
                        "journal": "Protocol",
                        "pmid": "",
                        "authors": "Laboratory Protocol Database",
                        "doi": "10.17504/protocols.io.kaic002",
                        "protein": "KaiC",
                        "step": "4-6",
                        "db": "pgvector"
                    },
                    "score": 0.93,
                    "source": "pgvector_dummy"
                },
                {
                    "content": """KaiC Protein Purification Protocol - Part 3 (Final Purification):
qualitative analysis of elutate fractions: Run SDS-PAGE gel to check protein purity
buffer exchange: Pool fractions with highest purity, dialyze against storage buffer overnight
set-up of your liquid chromatography system: Prepare FPLC or HPLC system
equilibration of the column: Wash size-exclusion column (Superdex 200) with 2 column volumes of buffer
protein purification: Load concentrated sample onto column, collect fractions at flow rate 0.5ml/min
qualitative analysis of eluate fractions: Analyze peak fractions by SDS-PAGE, pool pure fractions
final quality control: Measure concentration by Bradford assay, check activity, aliquot and store at -80°C""",
                    "metadata": {
                        "title": "Size exclusion chromatography for protein purification",
                        "source_type": "protocol",
                        "year": 2023,
                        "month": 5,
                        "day": 12,
                        "journal": "Protocol",
                        "pmid": "",
                        "authors": "Laboratory Protocol Database",
                        "doi": "10.17504/protocols.io.kaic003",
                        "protein": "KaiC",
                        "step": "7-9",
                        "db": "pgvector"
                    },
                    "score": 0.91,
                    "source": "pgvector_dummy"
                }
            ]
        
        # 시나리오 2-2: BIO_Q 최근 2개월 (관련성 낮은 논문 → web_search 트리거)
        elif ("최근" in query_lower or "recent" in query_lower) and ("2개월" in query_lower or "개월" in query_lower):
            print(f"[pgvector] 시나리오 2-2: 관련성 낮은 더미 (web_search 트리거용)")
            return [
                {
                    "content": "[pgvector dummy] Agricultural crop yield optimization using CRISPR technology. This study focuses on plant genetics and has minimal relevance to protein mutation analysis. Published in Plant Biotechnology Journal, 2024.",
                    "metadata": {"source_type": "paper", "year": 2024, "db": "pgvector"},
                    "score": 0.35,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "[pgvector dummy] Marine biodiversity and ocean temperature correlations. An ecological study examining species distribution patterns in response to climate change. No protein research included.",
                    "metadata": {"source_type": "paper", "year": 2023, "db": "pgvector"},
                    "score": 0.32,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "[pgvector dummy] Economic impacts of renewable energy adoption in developing countries. This paper discusses policy implications and has no biological content.",
                    "metadata": {"source_type": "paper", "year": 2024, "db": "pgvector"},
                    "score": 0.28,
                    "source": "pgvector_dummy"
                }
            ]
        
        # 시나리오 2-1: BIO_Q 2025년 논문 (기본값)
        else:
            print(f"[pgvector] 시나리오 2-1: 2025년 단백질 변이 논문 더미")
            return [
                {
                    "content": "Protein mutation analysis in 2025: Recent advances in understanding missense variants and their effects on protein stability. This comprehensive study examines 1,247 protein mutations across various organisms, revealing novel insights into mutation patterns and structural impacts. The research utilized deep mutational scanning combined with computational modeling to predict stability changes.",
                    "metadata": {
                        "title": "The emerging view on the origin and early evolution of eukaryotic cells.",
                        "source_type": "paper",
                        "year": 2024,
                        "month": 9,
                        "day": 11,
                        "journal": "Journal",
                        "pmid": "39261613",
                        "authors": "Vosseberg J et al.",
                        "doi": "10.1038/s41594-025-00012",
                        "db": "pgvector"
                    },
                    "score": 0.92,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "Deep mutational scanning reveals functional constraints on protein evolution. This paper reports high-throughput analysis of 50,000+ variants in key proteins, identifying critical residues for function. The study provides unprecedented detail on mutation tolerance landscapes and evolutionary constraints. Mutations affecting protein-protein interactions showed the strongest negative selection.",
                    "metadata": {
                        "title": "High-level expression of recombinant proteins in Escherichia coli.",
                        "source_type": "paper",
                        "year": 2006,
                        "month": 6,
                        "day": 14,
                        "journal": "Journal",
                        "pmid": "16754848",
                        "authors": "Baneyx F et al.",
                        "doi": "10.1016/j.copbio.2006.04.002",
                        "db": "pgvector"
                    },
                    "score": 0.90,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "Computational prediction of pathogenic mutations using machine learning. Novel AI-based approaches achieve 94% accuracy in distinguishing pathogenic from benign variants. The model integrates structural information, evolutionary conservation, and functional annotations. Validated on clinical datasets with superior performance to existing tools.",
                    "metadata": {
                        "title": "Eukaryotic cells.",
                        "source_type": "paper",
                        "year": 2024,
                        "month": 3,
                        "day": 20,
                        "journal": "Journal",
                        "pmid": "21592757",
                        "authors": "Alberts B et al.",
                        "doi": "10.1038/nature12345",
                        "db": "pgvector"
                    },
                    "score": 0.88,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "Systematic characterization of protein variants in human disease. Large-scale study analyzing 10,000+ disease-associated mutations reveals common mechanisms of pathogenicity. Focus on loss-of-function variants in metabolic enzymes.",
                    "metadata": {
                        "title": "Protein folding and misfolding in human diseases.",
                        "source_type": "paper",
                        "year": 2023,
                        "month": 8,
                        "day": 5,
                        "journal": "Journal",
                        "pmid": "18234567",
                        "authors": "Dobson CM et al.",
                        "doi": "10.1126/science.abc1234",
                        "db": "pgvector"
                    },
                    "score": 0.86,
                    "source": "pgvector_dummy"
                },
                {
                    "content": "Machine learning approaches for predicting protein structure and function from sequence data. This review discusses recent advances in deep learning methods for protein analysis, including AlphaFold and related technologies.",
                    "metadata": {
                        "title": "AlphaFold and the future of structural biology.",
                        "source_type": "paper",
                        "year": 2022,
                        "month": 11,
                        "day": 30,
                        "journal": "Journal",
                        "pmid": "35123456",
                        "authors": "Jumper J, Hassabis D et al.",
                        "doi": "10.1038/s41586-021-03819-2",
                        "db": "pgvector"
                    },
                    "score": 0.84,
                    "source": "pgvector_dummy"
                }
            ]


# ============================================
# 🔹 Neo4j 검색 함수
# ============================================

def search_neo4j(query: str, top_k: int = 50) -> List[Dict[str, Any]]:
    """
    Neo4j Text-to-Retriever 사용 검색
    
    Args:
        query: 원본 쿼리 텍스트
        top_k: 반환할 결과 개수
        
    Returns:
        검색 결과 리스트
    """
    try:
        from neo4j import GraphDatabase
        from neo4j_graphrag.retrievers import TextRetriever
        import json
        
        # Neo4j 연결
        NEO4J_URI = os.getenv("NEO4J_URI")
        NEO4J_USER = os.getenv("NEO4J_USER")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # TextRetriever 설정
        retriever = TextRetriever(
            driver=driver,
            index_name="papers_vector",
            embedding_model=NEO4J_EMBEDDING_MODEL,  # 상수 사용
            top_k=top_k
        )
        
        # 검색 실행
        results = retriever.retrieve(query)
        
        # 🔍 DEBUG: TextRetriever가 반환하는 원본 데이터 구조 확인
        print(f"\n{'='*60}")
        print(f"[DEBUG Neo4j TextRetriever] 검색 결과 수: {len(results) if results else 0}")
        if results and len(results) > 0:
            print(f"[DEBUG Neo4j TextRetriever] 첫 번째 결과 타입: {type(results[0])}")
            print(f"[DEBUG Neo4j TextRetriever] 첫 번째 결과 keys: {list(results[0].keys()) if isinstance(results[0], dict) else 'Not a dict'}")
            
            # 첫 번째 결과의 전체 구조 출력 (JSON으로 직렬화 시도)
            first_result = results[0]
            try:
                # dict인 경우 JSON으로 직렬화
                if isinstance(first_result, dict):
                    print(f"[DEBUG Neo4j TextRetriever] 첫 번째 결과 전체 구조:")
                    print(json.dumps(first_result, indent=2, default=str, ensure_ascii=False))
                else:
                    print(f"[DEBUG Neo4j TextRetriever] 첫 번째 결과 (직렬화 불가): {first_result}")
            except Exception as json_err:
                print(f"[DEBUG Neo4j TextRetriever] JSON 직렬화 실패: {json_err}")
                print(f"[DEBUG Neo4j TextRetriever] 첫 번째 결과 (raw): {first_result}")
            
            # metadata 구조 상세 확인
            if isinstance(first_result, dict):
                metadata = first_result.get("metadata", {})
                print(f"[DEBUG Neo4j TextRetriever] metadata 타입: {type(metadata)}")
                print(f"[DEBUG Neo4j TextRetriever] metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
                if isinstance(metadata, dict):
                    print(f"[DEBUG Neo4j TextRetriever] metadata 내용:")
                    print(json.dumps(metadata, indent=2, default=str, ensure_ascii=False))
                
                # title 관련 필드 확인
                if isinstance(metadata, dict):
                    title_fields = [k for k in metadata.keys() if 'title' in k.lower() or 'Title' in k]
                    if title_fields:
                        print(f"[DEBUG Neo4j TextRetriever] title 관련 필드: {title_fields}")
                        for field in title_fields:
                            print(f"[DEBUG Neo4j TextRetriever]   {field}: {metadata.get(field)}")
                    else:
                        print(f"[DEBUG Neo4j TextRetriever] ⚠️ metadata에 title 관련 필드 없음")
        print(f"{'='*60}\n")
        
        driver.close()
        
        # 결과 포맷팅
        formatted_results = []
        for idx, item in enumerate(results):
            # 🔍 DEBUG: 각 항목의 구조 확인 (처음 3개만)
            if idx < 3:
                print(f"[DEBUG Neo4j Format] 항목 {idx} 타입: {type(item)}")
                if isinstance(item, dict):
                    print(f"[DEBUG Neo4j Format] 항목 {idx} keys: {list(item.keys())}")
            
            formatted_results.append({
                "content": item.get("text", ""),
                "metadata": item.get("metadata", {}),
                "score": item.get("score", 0.0),
                "source": "neo4j"
            })
        
        print(f"[Neo4j] {len(formatted_results)}개 결과 검색 완료")
        return formatted_results
        
    except Exception as e:
        print(f"[Neo4j] 오류: {e}")
        print(f"[Neo4j] 더미 데이터 반환 (실제 노드 미구축)")
        
        # 더미 데이터 반환 - 시나리오별 분기
        query_lower = query.lower() if query else ""
        
        # 시나리오 3: PROTOCOL_Q (KaiC 단백질)
        if "kaic" in query_lower:
            print(f"[Neo4j] 시나리오 3: KaiC 프로토콜 그래프 더미")
            return [
                {
                    "content": "[neo4j dummy] KaiC protein purification workflow graph: Connected nodes include [GST-tag] -BINDS_TO-> [Glutathione resin] -CLEAVED_BY-> [PreScission protease] -YIELDS-> [Pure KaiC]. The workflow shows optimal conditions for each step with temperature and buffer requirements.",
                    "metadata": {"source_type": "knowledge_graph", "protein": "KaiC", "db": "neo4j"},
                    "score": 0.94,
                    "source": "neo4j_dummy"
                },
                {
                    "content": "[neo4j dummy] KaiC protein interactions in circadian rhythm: Graph shows [KaiC] -PHOSPHORYLATES-> [KaiB] -INTERACTS_WITH-> [KaiA]. These interactions form the core oscillator of the cyanobacterial circadian clock.",
                    "metadata": {"source_type": "knowledge_graph", "pathway": "circadian", "db": "neo4j"},
                    "score": 0.90,
                    "source": "neo4j_dummy"
                }
            ]
        
        # 기본 더미 (BIO_Q)
        else:
            print(f"[Neo4j] 기본 더미: 단백질 상호작용 그래프")
            return [
                {
                    "content": "[neo4j dummy] Protein mutation impact network: Knowledge graph analysis reveals that mutations in conserved domains have cascading effects on protein-protein interactions. Nodes represent proteins, edges represent interaction changes upon mutation.",
                    "metadata": {"source_type": "knowledge_graph", "db": "neo4j"},
                    "score": 0.89,
                    "source": "neo4j_dummy"
                },
                {
                    "content": "[neo4j dummy] Disease-protein-mutation relationship graph: Connected pathways show how specific mutations lead to loss of protein function and disease phenotypes. Graph includes [Mutation] -AFFECTS-> [Protein] -CAUSES-> [Disease].",
                    "metadata": {"source_type": "knowledge_graph", "db": "neo4j"},
                    "score": 0.85,
                    "source": "neo4j_dummy"
                }
            ]


# ============================================
# 🔹 검색 전략 결정 함수
# ============================================

def decide_search_strategy(query: str, case_type: str) -> str:
    """
    LLM을 사용하여 pgvector vs neo4j 검색 전략 결정
    
    Args:
        query: 검색 쿼리
        case_type: 질문 타입
        
    Returns:
        "pgvector" 또는 "neo4j"
    """
    from graph.llm_config import retrieval_decide_search_strategy_llm
    
    prompt = f"""다음 질문에 답하기 위해 어떤 검색 전략이 더 적합한지 결정하세요.

질문: {query}
질문 타입: {case_type}

검색 전략:
1. pgvector: 논문 본문, 임상연구 데이터, 단백질 시퀀스 등 텍스트 기반 검색에 적합
2. neo4j: 단백질 상호작용, 경로 분석, 관계 기반 지식 그래프 검색에 적합

질문의 특성을 분석하여 더 적합한 전략을 선택하세요.

반드시 "pgvector" 또는 "neo4j" 중 하나만 출력하세요:"""

    from graph.llm_config import get_model_name
    
    try:
        model_name = get_model_name(retrieval_decide_search_strategy_llm)
        print(f"[Search Strategy] 사용 모델: {model_name}")
        
        response = retrieval_decide_search_strategy_llm(prompt).strip().lower()
        
        if "neo4j" in response:
            print(f"[Search Strategy] neo4j 선택")
            return "neo4j"
        else:
            print(f"[Search Strategy] pgvector 선택 (기본값)")
            return "pgvector"
            
    except Exception as e:
        print(f"[Search Strategy] 오류: {e}, pgvector 기본값 사용")
        return "pgvector"


# ============================================
# 🔹 BIO_Q 리트리버 노드
# ============================================

def retriever_bio_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q 타입 질문용 리트리버
    - OpenAI 임베딩 사용
    - LLM이 pgvector vs neo4j 결정
    - RAG 결과에서 엔티티 추출 (placeholder - 나중에 RAG 구축 시 구현)

    Input:
        - state["question"]: 원본 질문
        - state["rewritten_query"]: 재작성된 쿼리
        - state["case_type"]: "BIO_Q"

    Output:
        - state["retrieval_results"]: 검색 결과 리스트
        - state["used_search_db"]: 사용한 DB ("pgvector" 또는 "neo4j")
        - state["entities"]: RAG 결과에서 추출된 엔티티들
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[RETRIEVER_BIO NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    query = state.get("rewritten_query", state.get("question", ""))
    case_type = state.get("case_type", "BIO_Q")
    
    # 1. OpenAI 임베딩 생성
    print("[BIO Retriever] Step 1: OpenAI 임베딩 생성")
    query_embedding = embed_query_openai(query)
    
    # 2. 검색 전략 결정 (LLM 판단)
    print("[BIO Retriever] Step 2: 검색 전략 결정")
    search_strategy = decide_search_strategy(query, case_type)
    
    # 3. 선택된 전략으로 검색
    print(f"[BIO Retriever] Step 3: {search_strategy} 검색 실행")
    if search_strategy == "neo4j":
        results = search_neo4j(query, top_k=50)
    else:
        results = search_pgvector(query_embedding, top_k=50, query_text=query)
    
    # 4. RAG 결과에서 엔티티 추출 (placeholder)
    # TODO: 나중에 RAG 구축 시 실제 엔티티 추출 로직 구현
    print("[BIO Retriever] Step 4: 엔티티 추출 (placeholder)")
    entities = []

    # Placeholder: 검색 결과의 메타데이터나 내용에서 엔티티 추출
    # 실제 구현 시 RAG 모듈의 함수를 호출하여 추출
    # 예: entities = extract_entities_from_rag_results(results)

    # 임시로 빈 리스트 반환 (RAG 구축 전까지)
    state["entities"] = entities

    # State 업데이트
    state["retrieval_results"] = results
    state["used_search_db"] = search_strategy

    # 노드 종료 로그
    print(f"\n[RETRIEVER_BIO NODE] 종료")
    print(f"  retrieval_results: {len(results)}개")
    print(f"  used_search_db: {search_strategy}")
    print(f"  entities: {len(entities)}개 (placeholder)")
    print(f"{'='*60}\n")
    
    return state


# ============================================
# 🔹 PROTOCOL_Q 리트리버 노드
# ============================================

def retriever_protocol_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q 타입 질문용 리트리버
    - 로컬 임베딩 사용 (보안 이슈)
    - LLM이 pgvector vs neo4j 결정
    - RAG 결과에서 엔티티 추출 (placeholder - 나중에 RAG 구축 시 구현)

    Input:
        - state["question"]: 원본 질문
        - state["rewritten_query"]: 재작성된 쿼리
        - state["case_type"]: "PROTOCOL_Q"

    Output:
        - state["retrieval_results"]: 검색 결과 리스트
        - state["used_search_db"]: 사용한 DB ("pgvector" 또는 "neo4j")
        - state["entities"]: RAG 결과에서 추출된 엔티티들
    """

    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[RETRIEVER_PROTOCOL NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    query = state.get("rewritten_query", state.get("question", ""))
    case_type = state.get("case_type", "PROTOCOL_Q")
    
    # 1. 로컬 임베딩 생성 (보안)
    print("[PROTOCOL Retriever] Step 1: 로컬 임베딩 생성 (보안)")
    query_embedding = embed_query_local(query)
    
    # 2. 검색 전략 결정 (LLM 판단)
    print("[PROTOCOL Retriever] Step 2: 검색 전략 결정")
    search_strategy = decide_search_strategy(query, case_type)
    
    # 3. 선택된 전략으로 검색
    print(f"[PROTOCOL Retriever] Step 3: {search_strategy} 검색 실행")
    if search_strategy == "neo4j":
        results = search_neo4j(query, top_k=50)
    else:
        results = search_pgvector(query_embedding, top_k=50, query_text=query)
    
    # 4. RAG 결과에서 엔티티 추출 (placeholder)
    # TODO: 나중에 RAG 구축 시 실제 엔티티 추출 로직 구현
    print("[PROTOCOL Retriever] Step 4: 엔티티 추출 (placeholder)")
    entities = []

    # Placeholder: 검색 결과의 메타데이터나 내용에서 엔티티 추출
    # 실제 구현 시 RAG 모듈의 함수를 호출하여 추출
    # 예: entities = extract_entities_from_rag_results(results)

    # 임시로 빈 리스트 반환 (RAG 구축 전까지)
    state["entities"] = entities

    # State 업데이트
    state["retrieval_results"] = results
    state["used_search_db"] = search_strategy

    # 노드 종료 로그
    print(f"\n[RETRIEVER_PROTOCOL NODE] 종료")
    print(f"  retrieval_results: {len(results)}개")
    print(f"  used_search_db: {search_strategy}")
    print(f"  entities: {len(entities)}개 (placeholder)")
    print(f"{'='*60}\n")
    
    return state

