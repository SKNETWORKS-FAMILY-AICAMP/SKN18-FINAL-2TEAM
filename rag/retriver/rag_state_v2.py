    # -*- coding: utf-8 -*-
"""
rag_state.py

RAG 파이프라인에서 공유되는 State 구조 정의.
TypedDict를 사용해서 코드 자동완성 및 타입 체크에 도움을 준다.
"""

from typing import TypedDict, List, Dict, Any, Optional

# -------------------------------------------------------------------------
# Sub-structures (State 내부의 복잡한 객체용 서브 타입)
# -------------------------------------------------------------------------


class RewriteOutput(TypedDict, total=False):
    """LLM Rewrite 결과 구조"""
    # 리라이트 기본 정보
    intent: str
    domains: Optional[List[str]]       # ["paper","clinical","protocol"] 중 다수 허용
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
    """최종 라우팅 정보 (로그/디버깅용)"""
    intent: str
    domains: Optional[List[str]]
    question_type: str
    need_kg: bool
    needs_chunks: bool

    confidence: float
    reason_short: str
    intent_why: Optional[str]


class RetrievalPlanStep(TypedDict):
    """개별 검색 단계 계획"""
    domain: str             # paper | clinical | protocol | kg | entity
    mode: str               # HY | VEC | ENTITY | FILTER | LIST
    embedder: Optional[str] # main_1536 | protocol_1024 | None
    priority: int
    why: str
    # GraphSearchQueries 상의 논리 쿼리 키 (예: "SEARCH_PAPER_HYBRID")
    query_key: Optional[str]


class RetrievalParams(TypedDict, total=False):
    """검색 파라미터 (k, hop_limit 등)"""
    k_seed: int
    k_final: int
    hop_limit: int
    fanout_limit: int


# -------------------------------------------------------------------------
# Main State
# -------------------------------------------------------------------------


class PipelineRAGState(TypedDict, total=False):
    """
    RAG 파이프라인 전체에서 공유되는 State 객체.
    total=False: 단계별로 점진적으로 채워지도록 모든 필드를 optional 로 둔다.
    """
    # 1. Input
    question: str

    # 2. Rewrite Node Output
    rewrite: RewriteOutput
    rewrite_json_min: str
    rewrite_input_text: str
    route: RouteInfo

    # 3. Router Node Output
    retrieval_params: RetrievalParams
    retrieval_plan: List[RetrievalPlanStep]

    # 4. Embedding Node Output
    # Key: embedder_name (e.g., 'main_1536'), Value: List[float]
    embeddings: Dict[str, List[float]]

    # 5. Executor / Orchestrator Output
    contexts: List[Dict[str, Any]]
    contexts_count: int

    # 6. Graph context snapshots (Assembly 결과에서 꺼낸 부분)
    graph_contexts: List[Dict[str, Any]]          # 각 context 의 graph_context 딕셔너리
    primekg_insights: List[Dict[str, Any]]        # 모든 graph_context 에서 모은 PrimeKG 엣지들
