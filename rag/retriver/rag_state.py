# -*- coding: utf-8 -*-
"""
rag_state.py

RAG 파이프라인 전체에서 공유되는 State 딕셔너리의 스키마 정의.
TypedDict를 사용하여 코드 자동완성 및 타입 힌트 지원.
"""

from typing import TypedDict, List, Dict, Any, Optional, Union

# -------------------------------------------------------------------------
# Sub-structures (State 내부의 복잡한 객체들 정의)
# -------------------------------------------------------------------------

class RewriteOutput(TypedDict, total=False):
    """LLM Rewrite 결과 구조"""
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
    """라우팅 결정 정보"""
    track: str
    intent: str
    domains: Optional[List[str]]
    confidence: float
    reason_short: str
    track_why: Optional[str]
    intent_why: Optional[str]

class RetrievalPlanStep(TypedDict):
    """개별 검색 단계 계획"""
    domain: str             # paper | clinical | protocol | kg | entity
    mode: str               # HY | VEC | ENTITY
    embedder: Optional[str] # main_1536 | protocol_1024
    priority: int
    why: str

class RetrievalParams(TypedDict, total=False):
    """검색 파라미터"""
    k_seed: int
    k_final: int
    hop_limit: int
    fanout_limit: int

# -------------------------------------------------------------------------
# Main State
# -------------------------------------------------------------------------

class PipelineRAGState(TypedDict, total=False):
    """
    RAG 파이프라인 전체를 관통하는 State 객체
    total=False: 단계별로 키가 추가되므로 초기화 시 모든 키가 없어도 됨
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

    # 5. Executor Output
    contexts: List[Dict[str, Any]]
    contexts_count: int