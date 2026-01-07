from typing import List, Dict, Any, TypedDict, Literal, NotRequired, Annotated, Optional
import operator


# -------------------------------------------------------------------------
# RAG Pipeline 서브 구조 (rag/retriver/rag_state.py 와 동일한 구조 복사)
#  - 여기의 필드들은 LangGraph 노드가 직접 만드는 게 아니라
#    rag/retriver/query_rewrite_node.py, query_router.py 등이 채웁니다.
# -------------------------------------------------------------------------

class RewriteOutput(TypedDict, total=False):
    """RAG 쪽 LLM Rewrite 결과 구조 (rag_state.RewriteOutput 복사본)"""
    track: str
    intent: str
    domains: Optional[List[str]]
    confidence: float
    reason_short: str
    normalized_question: str
    entities: List[Dict[str, Any]]
    must: List[str]
    should: List[str]
    must_not: List[str]
    filters: Dict[str, Any]
    retrieval: Dict[str, Any]
    # Debug info
    track_debug: Dict[str, Any]
    intent_debug: Dict[str, Any]
    must_terms_expanded: List[str]
    must_not_terms_expanded: List[str]


class RouteInfo(TypedDict, total=False):
    """RAG 쪽 Query Routing 결과 (rag_state.RouteInfo 복사본)"""
    track: str
    intent: str
    domains: Optional[List[str]]
    confidence: float
    reason_short: str
    track_why: Optional[str]
    intent_why: Optional[str]


class RetrievalPlanStep(TypedDict):
    """개별 Retrieval Plan Step (rag_state.RetrievalPlanStep 복사본)"""
    domain: str             # paper | clinical | protocol | kg | entity
    mode: str               # HY | VEC | ENTITY
    embedder: Optional[str] # main_1536 | protocol_1024
    priority: int
    why: str


class RetrievalParams(TypedDict, total=False):
    """Retrieval 파라미터 (rag_state.RetrievalParams 복사본)"""
    k_seed: int
    k_final: int
    hop_limit: int
    fanout_limit: int


class BioRAGState(TypedDict, total=False):
    """
    Bio RAG + Simulation + Protocol + Semantic Inference 전체 워크플로에서
    공용으로 사용하는 LangGraph State.

    - LangGraph 쪽 rewrite_query.py 는 오직 문자열 리라이팅만 담당:
        -> state["rewritten_query"] 만 사용
    - 키워드/엔티티(must/should/must_not 등)와 상세 rewrite/route/plans 는
      RAG 파이프라인(rag/retriver/query_rewrite_node.py 등)에서만 생성:
        -> state["rewrite"], state["route"], state["retrieval_plan"] 등은
           retrieval 노드에서 RAG 결과를 매핑해서 채운다.
    """

    # -----------------------------
    # 1. User Input
    # -----------------------------
    question: str                       # 사용자 최종 질문
    conversation_id: NotRequired[str]   # Django DB PK (chat_room_id)
    user_id: str                        # 사용자 ID
    filter_type: NotRequired[str]       # 프론트엔드에서 선택한 필터 타입 (paper, protocol, simulation, interpretation)
    attached_images: NotRequired[List[Dict[str, Any]]]  # 첨부된 이미지 정보 (base64 또는 S3 URL)
    image_analysis_result: NotRequired[Dict[str, Any]]  # 이미지 분석 결과 (JSON)

    # -----------------------------
    # 2. Guardrail (Safety Check)
    # -----------------------------
    guardrail_passed: bool             # 가드레일 통과 여부 (True: 안전, False: 차단)

    # -----------------------------
    # 3. Memory (Slot Memory)
    # -----------------------------
    memory_slot: Dict[str, Any]        # DB Slot 구조 (last_case, last_summary 등)
    is_follow_up: bool                 # 이전 대화에 대한 후속 질문 여부
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
    # - graph/nodes/rewrite_query.py 에서는 엔티티를 만들지 않는다.
    # - 필요하다면 RAG 파이프라인 결과(rewrite["entities"] 또는 contexts)에서
    #   retrieval 노드가 문자열 리스트로 만들어서 채운다.
    entities: List[str]

    # -----------------------------
    # 6. Query Rewrite
    # -----------------------------
    # (1) LangGraph 전용: rewrite_query.py 가 만드는 단순 리라이트 문자열
    rewritten_query: str

    # (2) RAG 파이프라인 전용: rag/retriver/query_rewrite_node.py 가 만드는 상세 구조
    #     -> LangGraph retrieval 노드에서 run_rag_retrieval_pipeline() 결과를 매핑해서 채운다.
    rewrite: RewriteOutput
    rewrite_json_min: str
    rewrite_input_text: str
    route: RouteInfo

    # -----------------------------
    # 7. Retrieval Plan / Embeddings / Contexts (RAG Pipeline)
    # -----------------------------
    # 이 부분도 RAG 파이프라인 (query_router, embedding_router, RAGOrchestrator)이 생성하고,
    # LangGraph retrieval 노드가 state 로 옮겨 준다.
    retrieval_params: RetrievalParams
    retrieval_plan: List[RetrievalPlanStep]
    embeddings: Dict[str, List[float]]        # key: embedder_name, value: embedding vector
    contexts: List[Dict[str, Any]]            # RAGOrchestrator 결과
    contexts_count: int

    # -----------------------------
    # 8. Retrieval Results (기존 LangGraph 평가/리랭크 단계에서 사용)
    # -----------------------------
    # 보통 retrieval_results 는 contexts 와 동일하게 맞춰두고,
    # rerank/evaluate_chunk 노드에서 이 값을 사용한다.
    retrieval_results: Annotated[List[Dict[str, Any]], operator.add]
    reranked_results: Annotated[List[Dict[str, Any]], operator.add]
    selected_chunks: Annotated[List[str], operator.add]
    retrieval_score: float
    used_search_db: NotRequired[str]   # "pgvector" | "neo4j" | "graph_rag" 등

    #9. Chunk Evaluation
    # -----------------------------
    chunk_is_relevant: bool              # evaluate_chunk 결과
    chunk_relevance_score: float         # LLM relevance score

    # -----------------------------
    # 10. Web Search Fallback
    # -----------------------------
    used_web_search: bool                                                       # 검색 실패 시 fallback 여부
    web_results: NotRequired[Annotated[List[Dict[str, Any]], operator.add]]    # 웹 검색 결과 (optional)
    web_selected_chunks: NotRequired[Annotated[List[str], operator.add]]       # evaluate_web으로 선별된 chunk (optional)
    should_skip_generation: NotRequired[bool]                


    # -----------------------------
    # 11. Answer Generation
    # -----------------------------
    final_context: str
    final_answer: str
    answer_sources: Annotated[List[str], operator.add]
    chat_title: NotRequired[str]
