from __future__ import annotations
from typing import Any, Dict
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

def _ensure_rag_retriver_on_syspath() -> None:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    rag_retriver_dir = os.path.join(base_dir, "rag", "retriver")
    if rag_retriver_dir not in sys.path:
        sys.path.append(rag_retriver_dir)

def run_rag_retrieval_pipeline(question: str) -> Dict[str, Any]:
    # [수정 1] .env 경로를 명시적으로 지정 (이 파일 기준 상위 디렉터리 등 실제 위치로 조정 필요)
    # 예: 현재 파일이 프로젝트 깊은 곳에 있다면, 프로젝트 루트의 .env를 찾도록 설정
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) # 상위, 상위, 상위 (상황에 맞춰 조정)
    env_path = os.path.join(base_dir, ".env") 
    
    # .env 파일이 존재하면 로드, 없으면 시스템 환경변수 의존
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
        print(f"[Debug] .env loaded from: {env_path}")
    else:
        load_dotenv() # Fallback
        print("[Debug] .env loaded from default location (CWD)")

    _ensure_rag_retriver_on_syspath()

    from rag.retriver.rag_state_v2 import PipelineRAGState
    from rag.retriver.retriever_runner_v2 import RetrieverExecutor, make_llm_call
    from rag.retriver.query_rewrite_node_v2 import query_rewrite_node
    from rag.retriver.query_router_v2 import QueryRoutingNode
    from rag.retriver.embedding_router_v2 import EmbeddingRoutingNode

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    # [수정 3] 디버깅: 실제로 로드된 값 확인 (보안상 앞 2글자만 출력)
    print(f"[Debug] URI: {uri}")
    print(f"[Debug] USER: {user}")
    print(f"[Debug] PW Check: {password[:2]}... (Length: {len(password) if password else 0})")

    if not uri or not user or not password:
        raise RuntimeError("NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD 환경 변수가 설정되어 있어야 합니다.")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # [수정 2] 연결 즉시 검증
    try:
        driver.verify_connectivity()
        print("✅ [Bridge] Neo4j Driver connected successfully.")
    except Exception as e:
        print(f"❌ [Bridge] Connection failed: {e}")
        driver.close()
        raise e

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
        return dict(state)
    finally:
        driver.close()