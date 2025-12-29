from typing import List, Dict, Any, TypedDict, Literal, NotRequired, Annotated, Optional
import operator


# -------------------------------------------------------------------------
# RAG Pipeline 서브 구조
# - rag/retriver/rag_state_v2.py 와 동일한 TypedDict 구조를 LangGraph 쪽에 복사해 둔 것.
# - 실제 RAG 로직은 rag/retriver/*_v2.py 에 있으며, 여기서는 타입 정의만 담당한다.
# -------------------------------------------------------------------------


class RewriteOutput(TypedDict, total=False):
    """RAG용 LLM Rewrite 결과 구조 (rag_state_v2.RewriteOutput 복사본)"""
    # 리라이트 기본 정보
    intent: str
    domains: Optional[List[str]]       # ["paper","clinical","protocol"] 등 다수 가능
    question_type: str                 # "chunk" | "list" | "filter"
    need_kg: bool                      # PrimeKG / KG 필요 여부
    needs_chunks: bool                 # 청크 기반 evidence 필요 여부

    confidence: float
    reason_short: str
    normalized_question: str

    # 엔티티 / 키워드 / 필터 / 검색 파라미터
    entities: List[Dict[str, Any]]
    must: List[str]
    should: List[str]
    must_not: List[str]
    filters: Dict[str, Any]
    retrieval: Dict[str, Any]

    # Debug / 확장 키워드
    intent_debug: Dict[str, Any]
    must_terms_expanded: List[str]
    must_not_terms_expanded: List[str]


class RouteInfo(TypedDict, total=False):
    """RAG Query Routing 결과 (rag_state_v2.RouteInfo 복사본)"""
    intent: str
    domains: Optional[List[str]]
    question_type: str
    need_kg: bool
    needs_chunks: bool

    confidence: float
    reason_short: str
    intent_why: Optional[str]


class RetrievalPlanStep(TypedDict, total=False):
    """개별 Retrieval Plan Step (rag_state_v2.RetrievalPlanStep 복사본)"""
    domain: str             # paper | clinical | protocol | kg | entity
    mode: str               # HY | VEC | ENTITY | FILTER | LIST
    embedder: Optional[str] # main_1536 | protocol_1024 | None
    priority: int
    why: str
    # GraphSearchQueries 상의 논리 쿼리 키 (예: "SEARCH_PAPER_HYBRID")
    query_key: Optional[str]


class RetrievalParams(TypedDict, total=False):
    """Retrieval 파라미터 (rag_state_v2.RetrievalParams 복사본)"""
    k_seed: int
    k_final: int
    hop_limit: int
    fanout_limit: int


class BioRAGState(TypedDict, total=False):
    """
    Bio RAG + Simulation + Protocol + Semantic Inference 전체 워크플로에서
    공용으로 사용하는 LangGraph State.

    - LangGraph 쪽 rewrite_query.py 노드가 만든 텍스트 리라이트 결과:
        -> state["rewritten_query"] 에 저장
    - 이후 RAG 파이프라인(rag/retriver/query_rewrite_node_v2.py 등)에서만 생성:
        -> state["rewrite"], state["route"], state["retrieval_plan"] 등을 채운다.
    """

    # -----------------------------
    # 1. User Input
    # -----------------------------
    question: str                       # 최종 사용자 질문
    conversation_id: NotRequired[str]   # Django DB PK (chat_room_id)
    user_id: str                        # 사용자 ID

    # -----------------------------
    # 2. Guardrail (Safety Check)
    # -----------------------------
    guardrail_passed: bool             # 가드레일 통과 여부 (True: 통과, False: 차단)

    # -----------------------------
    # 3. Memory (Slot Memory)
    # -----------------------------
    memory_slot: Dict[str, Any]        # DB Slot 구조 (last_case, last_summary 등)
    is_follow_up: bool                 # 이전 대화에 대한 후속 질문인지 여부
    reference_case_type: NotRequired[str]
    relevant_history: NotRequired[List[Dict[str, Any]]]
    history_source: NotRequired[str]   # "CURRENT_TYPE" | "FOLLOW_UP_TYPE"

    # -----------------------------
    # 4. Classifier Result (Main Routing)
    # -----------------------------
    case_type: Literal[
        "NO_RELATION",
        "BIO_Q",
        "SIMULATION_Q",
        "PROTOCOL_Q",
        "INFERENCE_Q",
        "USER_INFO",
    ]

    # -----------------------------
    # 5. Entity Extraction
    # -----------------------------
    # 주의:
    # - graph/nodes/rewrite_query.py 에서 만든 엔티티 리스트에 해당
    # - 필요하다면 RAG 파이프라인 결과(rewrite["entities"] 또는 contexts)에서
    #   retrieval 노드가 문장 리스트로 만들어 보강한다.
    entities: List[str]

    # -----------------------------
    # 6. Query Rewrite
    # -----------------------------
    # (1) LangGraph 용: rewrite_query.py 가 만든 텍스트 리라이트 결과
    rewritten_query: str

    # (2) RAG 파이프라인 전용: rag/retriver/query_rewrite_node_v2.py 가 만드는 상세 구조
    #     -> LangGraph retrieval 노드에서 run_rag_retrieval_pipeline() 결과를 그대로 매핑
    rewrite: RewriteOutput
    rewrite_json_min: str
    rewrite_input_text: str
    route: RouteInfo

    # -----------------------------
    # 7. Retrieval Plan / Embeddings / Contexts (RAG Pipeline)
    # -----------------------------
    # 이 부분도 RAG 파이프라인 (query_router_v2, embedding_router_v2, rag_orchestrator_v2)이 생성하고,
    # LangGraph retrieval 노드가 state 를 통째로 넘겨받아 사용한다.
    retrieval_params: RetrievalParams
    retrieval_plan: List[RetrievalPlanStep]
    embeddings: Dict[str, List[float]]        # key: embedder_name, value: embedding vector
    contexts: List[Dict[str, Any]]            # RAGOrchestrator 결과
    contexts_count: int
    graph_contexts: List[Dict[str, Any]]      # 각 context 의 graph_context 딕셔너리
    primekg_insights: List[Dict[str, Any]]    # 모든 graph_context 에서 모은 PrimeKG 연결 정보

    # -----------------------------
    # 8. Retrieval Results (기존 LangGraph 평가/리랭크 단계에서 사용)
    # -----------------------------
    retrieval_results: Annotated[List[Dict[str, Any]], operator.add]
    reranked_results: Annotated[List[Dict[str, Any]], operator.add]
    selected_chunks: Annotated[List[str], operator.add]
    retrieval_score: float
    used_search_db: NotRequired[str]   # "pgvector" | "neo4j" | "graph_rag" 등

    # -----------------------------
    # 9. Chunk Evaluation
    # -----------------------------
    chunk_is_relevant: bool
    chunk_relevance_score: float

    # -----------------------------
    # 10. Web Search Fallback
    # -----------------------------
    used_web_search: bool
    web_results: NotRequired[Annotated[List[Dict[str, Any]], operator.add]]
    web_selected_chunks: NotRequired[Annotated[List[str], operator.add]]
    should_skip_generation: NotRequired[bool]

    # -----------------------------
    # 11. Answer Generation
    # -----------------------------
    final_context: str
    final_answer: str
    answer_sources: Annotated[List[str], operator.add]
    chat_title: NotRequired[str]

