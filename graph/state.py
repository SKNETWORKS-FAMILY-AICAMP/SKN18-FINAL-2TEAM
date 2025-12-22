from typing import List, Dict, Any, TypedDict, Tuple, Literal, NotRequired, Annotated
import operator


class BioRAGState(TypedDict, total=False):
    """
    Bio RAG + Simulation + Protocol + Semantic Inference 시스템 상태 관리용 State.
    
    워크플로우:
    classify_agent → memory_read → query_rewrite_agent → retrieval → rerank 
    → evaluate_chunk → (web_search) → generate_answer → memory_write
    
    모든 노드 사이에서 공유되는 단일 데이터 컨테이너.
    """

    # -----------------------------
    # 🔹 1. User Input
    # -----------------------------
    question: str                       # 사용자가 "방금" 입력한 실제 질문
    conversation_id: NotRequired[str]   # Django DB PK (chat_room_id)
    user_id: str                        # 사용자 ID

    # -----------------------------
    # 🔹 2. Guardrail (Safety Check)
    # guardrail_input 노드에서 유해성 검사
    # -----------------------------
    guardrail_passed: bool                      # 가드레일 통과 여부 (True: 안전, False: 차단)

    # -----------------------------
    # 🔹 3. Memory (Slot Memory)
    # memory_read 노드에서 DB → State 로드
    # -----------------------------
    memory_slot: Dict[str, Any]         # DB Slot 통합 구조 (last_case, last_summary)
    # 꼬리질문 판단 (classifier에서 설정)
    is_follow_up: bool                  # 이전 대화를 참조하는 꼬리질문 여부
    reference_case_type: NotRequired[str]  # 참조하는 이전 대화의 case_type
    # 관련 대화 히스토리 (memory_read에서 설정, 최대 5개)
    relevant_history: NotRequired[List[Dict[str, Any]]]  # 현재 질문과 관련된 과거 대화
    history_source: NotRequired[str]    # "CURRENT_TYPE" | "FOLLOW_UP_TYPE"

    # -----------------------------
    # 🔹 4. Classifier Result (Main Routing)
    # -----------------------------
    case_type: Literal[
        "NO_RELATION",
        "BIO_Q",                        # 논문, 임상 실험 결과, 근거 검색
        "SIMULATION_Q",                 # 단백질 실험 Tool 경로 안내
        "PROTOCOL_Q",
        "INFERENCE_Q",
        "USER_INFO"                     # 사용자 인적사항 (학생, 연구원, 대학원생, 교수 등)
    ]                                   # classifier가 반환하는 CASE

    # -----------------------------
    # 🔹 5. Entity Extraction - RAG 결과에서 추출된 엔티티
    # -----------------------------
    entities: List[str]       # NER/Entity 추출 결과 - 엔티티는 고유 명사 혹은 객체 이름. neo4j에 적합 (retriever 노드에서 RAG 결과로부터 추출)

    # -----------------------------
    # 🔹 6. Query Rewrite
    # -----------------------------
    rewritten_query: str                # rewrite_query 결과

    # -----------------------------
    # 🔹 7. Retrieval Results
    # -----------------------------
    retrieval_results: Annotated[List[Dict[str, Any]], operator.add]   # VectorDB/Neo4j RAW 검색 결과
    reranked_results: Annotated[List[Dict[str, Any]], operator.add]    # rerank 이후 정렬된 문서
    selected_chunks: Annotated[List[str], operator.add]                # evaluate 단계에서 통과한 chunk
    retrieval_score: float                                              # rerank 최상위 점수
    used_search_db: NotRequired[str]                                    # 사용된 검색 DB ("pgvector" 또는 "neo4j")

    # -----------------------------
    # 🔹 8. Chunk Evaluation
    # -----------------------------
    chunk_is_relevant: bool              # evaluate_chunk 결과
    chunk_relevance_score: float         # LLM relevance score

    # -----------------------------
    # 🔹 9. Web Search Fallback
    # -----------------------------
    used_web_search: bool                                                       # 검색 실패 시 fallback 여부
    web_results: NotRequired[Annotated[List[Dict[str, Any]], operator.add]]    # 웹 검색 결과 (optional)
    web_selected_chunks: NotRequired[Annotated[List[str], operator.add]]       # evaluate_web으로 선별된 chunk (optional)
    should_skip_generation: NotRequired[bool]                                   # BIO_Q에서 웹서치 실패 시 조기 종료 플래그


    # -----------------------------
    # 🔹 10. Answer Generation
    # -----------------------------
    final_context: str                                  # generate_answer prompt에 들어갈 context 전체
    final_answer: str                                   # 최종 답변(평문)
    answer_sources: Annotated[List[str], operator.add] # 출처 리스트 - rag, web 모두 누적 입력
    chat_title: NotRequired[str]                        # 채팅방 제목용 1줄 요약 (Django 전달용)

