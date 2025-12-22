from __future__ import annotations

"""
LangGraph retrieval 노드에서 RAG retriever_runner 파이프라인을 호출하기 위한 브리지 모듈.

- sys.path 에 rag/retriver 디렉터리를 동적으로 추가해서
  기존 RAG 코드(import 경로 유지)를 그대로 재사용한다.
- retriever_runner.py 에서 사용하는 전체 파이프라인
  (query_rewrite_node -> QueryRoutingNode -> EmbeddingRoutingNode -> RetrieverExecutor)
  를 함수형 인터페이스로 감싼다.
"""

from typing import Any, Dict
import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase


def _ensure_rag_retriver_on_syspath() -> None:
    """
    rag/retriver 디렉터리를 sys.path 에 추가해서
    기존 RAG 코드가 기대하는 top-level import (from rag_state import ...) 가 동작하도록 만든다.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    rag_retriver_dir = os.path.join(base_dir, "rag", "retriver")
    if rag_retriver_dir not in sys.path:
        sys.path.append(rag_retriver_dir)


def run_rag_retrieval_pipeline(question: str) -> Dict[str, Any]:
    """
    retriever_runner.py 에 정의된 RAG 파이프라인을 그대로 호출해서
    PipelineRAGState 딕셔너리(one-shot)를 반환한다.

    Args:
        question: 원본 사용자 질문 텍스트

    Returns:
        RAG 파이프라인이 사용하는 PipelineRAGState (실행 후 최종 상태 딕셔너리)
    """
    load_dotenv()
    _ensure_rag_retriver_on_syspath()

    # 늦은 import: sys.path 세팅 이후에 불러와야 함
    from rag_state import PipelineRAGState  # type: ignore
    from retriever_runner import RetrieverExecutor, make_llm_call  # type: ignore
    from query_rewrite_node import query_rewrite_node  # type: ignore
    from query_router import QueryRoutingNode  # type: ignore
    from embedding_router import EmbeddingRoutingNode  # type: ignore

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        raise RuntimeError("NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD 환경 변수가 설정되어 있어야 합니다.")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    llm_call = make_llm_call()
    router = QueryRoutingNode()
    embed_router = EmbeddingRoutingNode()
    executor = RetrieverExecutor(driver)

    try:
        state: PipelineRAGState = {"question": question}
        state = query_rewrite_node(state, llm_call)
        state = router(state)
        state = embed_router(state)
        state = executor(state)
        # TypedDict 이지만 실제로는 dict 이므로 그대로 Dict[str, Any] 로 반환
        return dict(state)
    finally:
        driver.close()
