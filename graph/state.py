from typing import List, Dict, Any, TypedDict, Tuple, Literal, NotRequired


class BioRAGState(TypedDict, total=False):
    """
    Bio RAG + Simulation + Protocol + Semantic Inference 시스템 상태 관리용 State.
    모든 노드(keyword_extract → memory_read → classifier → rewrite → retrieval → evaluate → generate)
    사이에서 공유되는 단일 데이터 컨테이너.
    """

    # -----------------------------
    # 🔹 1. User Input
    # -----------------------------
    question: str                       # 사용자가 "방금" 입력한 실제 질문
    conversation_id: NotRequired[str]   # Django DB PK
    original_question: NotRequired[str] # 첫 질문(대화 기준점) = 이 대화의 첫 번째 “의도 기준점”. context 유지, 후속 질문 의미 disambiguation

    ''' question과 original_question 차이
    턴 1: question = "KaiC 단백질 정제 방법 알려줘"
       original_question = "KaiC 단백질 정제 방법 알려줘"

    턴 2: question = "그거 다시 요약해줘"
        original_question = 여전히 턴 1 질문

    턴 3: question = "실험 조건을 바꾸면 어떻게 돼?"
        original_question = 턴 1 질문
    '''


    # -----------------------------
    # 🔹 2. Memory (Slot Memory)
    # memory_read 노드에서 DB → State 로드
    # -----------------------------
    memory_slot: Dict[str, Any]         # DB Slot 통합 구조

    # CASE별 히스토리도 선택적으로 포함 가능 (디버깅용)
    no_relation_history: NotRequired[List[Dict[str, Any]]]
    simulation_q_history: NotRequired[List[Dict[str, Any]]]
    inference_q_history: NotRequired[List[Dict[str, Any]]]
    bio_q_history: NotRequired[List[Dict[str, Any]]]
    protocal_q_history: NotRequired[List[Dict[str, Any]]]


    # -----------------------------
    # 🔹 3. Keyword Extraction - 질문 + 메모리 기반으로 “검색용 토큰”을 뽑는다
    # -----------------------------
    extracted_keywords: List[str]       # 키워드 - 엔티티보다 의미적이고 추상적인것. pgvextor에 적합
    extracted_entities: List[str]       # NER/Entity 추출 결과 - 엔티티는 고유 명사 혹은 객체 이름. neo4j에 적합


    # -----------------------------
    # 🔹 4. Classifier Result (Main Routing)
    # -----------------------------
    is_follow_up: bool                  # 후속 질문 여부 - 메모리 + 질문 + original_question 종합고려하여 결정
    case_type: Literal[
        "NO_RELATION",
        "BIO_Q",                        # 논문, 임상 실험 결과, 근거 검색
        "SIMULATION_Q",                 # 단백질 실험 Tool 경로 안내
        "PROTOCOL_Q",
        "INFERENCE_Q"
    ]                                   # classifier가 반환하는 CASE


    # -----------------------------
    # 🔹 5. Query Rewrite
    # -----------------------------
    rewritten_query: str                # rewrite_query 결과

    # -----------------------------
    # 🔹 6. Retrieval Results
    # -----------------------------
    retrieval_results: List[Dict[str, Any]]   # VectorDB/Neo4j RAW 검색 결과
    reranked_results: List[Dict[str, Any]]    # rerank 이후 정렬된 문서
    selected_chunks: List[str]                # evaluate 단계에서 통과한 chunk
    retrieval_score: float                    # rerank 최상위 점수

    # -----------------------------
    # 🔹 7. Chunk Evaluation
    # -----------------------------
    chunk_is_relevant: bool              # evaluate_chunk 결과
    chunk_relevance_score: float         # LLM relevance score

    # -----------------------------
    # 🔹 8. Web Search Fallback
    # -----------------------------
    used_web_search: bool                # 검색 실패 시 fallback 여부
    web_results: NotRequired[List[Dict[str, Any]]]  # NotRequired: 명시적으로 "optional"임을 표현. 아무것도 없으면 암묵적으로 optional
    web_selected_chunks: NotRequired[List[str]] # evaluate_web 실행 -> 질문과 진짜 관련 있는 텍스트만 선별해서 final_context로 넣을 수 있도록 정제된 chunk 리스트를 만든다.”


    # -----------------------------
    # 🔹 9. Answer Generation
    # -----------------------------
    final_context: str                   # generate_answer prompt에 들어갈 context 전체
    final_answer: str                    # 최종 답변(평문)
    structured_answer: Dict[str, Any]    # JSON 구조화된 답변
    answer_sources: List[str]            # 출처 리스트 - rag, web 모두 누적 입력
    llm_confidence: float                # 모델 confidence

    # -----------------------------
    # 🔹 10. System Debug Log (선택)
    # -----------------------------
    system_log: List[str]

    '''
    syste`m_log는 “필수는 아니지만, 넣지 않으면 프로덕션에서 디버깅이 극단적으로 어려워짐.”
    실제 서비스에서는 99% 시스템이 이런 형태의 state-level debug log를 둔다.
    스위칭이 많고 fa`llback이 있는 시스템에서는 매우 강력한 기능이다
    '''
