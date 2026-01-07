from __future__ import annotations
from typing import Any, Dict, Optional
import os
import sys
import threading
from dotenv import load_dotenv
from neo4j import GraphDatabase
from graph.logger_config import get_logger

logger = get_logger(__name__)

# 전역 Neo4j 드라이버 인스턴스 (연결 풀링을 위해 재사용)
_neo4j_driver: Optional[Any] = None
_neo4j_driver_lock = threading.Lock()

def _ensure_rag_retriver_on_syspath() -> None:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    rag_retriver_dir = os.path.join(base_dir, "rag", "retriver")
    if rag_retriver_dir not in sys.path:
        sys.path.append(rag_retriver_dir)


def _get_neo4j_driver_config() -> tuple[str, str, str]:
    """
    Neo4j 연결 정보를 가져옵니다 (환경 변수 → Parameter Store 순서).
    
    Returns:
        (uri, user, password) 튜플
    """
    # .env 파일 로드
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv()
    
    # Neo4j 환경 변수 가져오기
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    # AWS EC2 환경인지 확인
    is_aws_ec2 = False
    try:
        import urllib.request
        urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id", timeout=1)
        is_aws_ec2 = True
    except:
        pass
    
    # AWS EC2 환경이고 환경 변수가 없으면 Parameter Store에서 가져오기
    if is_aws_ec2:
        try:
            import boto3
            region = os.getenv("AWS_REGION", "ap-northeast-2")
            ssm = boto3.client("ssm", region_name=region)
            
            # NEO4J_URI가 없으면 구성
            if not uri:
                bolt_host = os.getenv("NEO4J_BOLT_HOST")
                if not bolt_host:
                    try:
                        response = ssm.get_parameter(Name="/skn18/neo4j-host")
                        bolt_host = response["Parameter"]["Value"]
                    except:
                        pass
                
                if not bolt_host:
                    try:
                        cf = boto3.client("cloudformation", region_name=region)
                        stack_name = os.getenv("STACK_NAME", "skn18-final-infra")
                        response = cf.describe_stacks(StackName=stack_name)
                        outputs = response["Stacks"][0]["Outputs"]
                        for output in outputs:
                            if output["OutputKey"] == "Neo4jPublicIp":
                                bolt_host = output["OutputValue"]
                                break
                    except:
                        pass
                
                if bolt_host:
                    bolt_port = os.getenv("NEO4J_BOLT_PORT", "7687")
                    uri = f"bolt://{bolt_host}:{bolt_port}"
            
            # NEO4J_USERNAME이 없으면 가져오기
            if not user:
                try:
                    response = ssm.get_parameter(Name="/skn18/neo4j-user")
                    user = response["Parameter"]["Value"]
                except:
                    user = "neo4j"
            
            # NEO4J_PASSWORD가 없으면 가져오기
            if not password:
                try:
                    response = ssm.get_parameter(Name="/skn18/neo4j-password", WithDecryption=True)
                    password = response["Parameter"]["Value"]
                except:
                    pass
        except Exception as e:
            logger.debug(f"Failed to load from Parameter Store: {e}", exc_info=True)
    
    if not uri or not user or not password:
        raise RuntimeError("NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD 환경 변수가 설정되어 있어야 합니다.")
    
    return uri, user, password


def _get_neo4j_driver():
    """
    전역 Neo4j 드라이버 인스턴스를 가져오거나 생성합니다 (싱글톤 패턴).
    연결 풀링을 위해 드라이버를 재사용합니다.
    """
    global _neo4j_driver
    
    with _neo4j_driver_lock:
        if _neo4j_driver is None:
            uri, user, password = _get_neo4j_driver_config()
            
            # 연결 풀 설정으로 드라이버 생성
            _neo4j_driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=3600,  # 1시간
                max_connection_pool_size=50,   # 최대 연결 풀 크기
                connection_acquisition_timeout=30,  # 연결 획득 타임아웃 (초)
                connection_timeout=10,  # 초기 연결 타임아웃 (초)
            )
            
            # 연결 즉시 검증
            try:
                _neo4j_driver.verify_connectivity()
                logger.info("✅ Neo4j Driver connected successfully (connection pool initialized).")
            except Exception as e:
                logger.error(f"❌ Connection failed: {e}", exc_info=True)
                _neo4j_driver.close()
                _neo4j_driver = None
                raise e
        
        return _neo4j_driver

def run_rag_retrieval_pipeline(question: str) -> Dict[str, Any]:
    """
    RAG 검색 파이프라인을 실행합니다.
    
    Neo4j 드라이버는 연결 풀링을 위해 전역 인스턴스를 재사용합니다.
    """
    _ensure_rag_retriver_on_syspath()

    from rag.retriver.rag_state import PipelineRAGState
    from rag.retriver.retriever_runner import RetrieverExecutor, make_llm_call
    from rag.retriver.query_rewrite_node import query_rewrite_node
    from rag.retriver.query_router import QueryRoutingNode
    from rag.retriver.embedding_router import EmbeddingRoutingNode

    # 전역 드라이버 인스턴스 가져오기 (연결 풀링)
    driver = _get_neo4j_driver()

    llm_call = make_llm_call()
    router = QueryRoutingNode()
    embed_router = EmbeddingRoutingNode()
    executor = RetrieverExecutor(driver)

    # 드라이버는 재사용되므로 close()하지 않음
    state: PipelineRAGState = {"question": question}
    state = query_rewrite_node(state, llm_call)
    state = router(state)
    state = embed_router(state)
    state = executor(state)
    return dict(state)