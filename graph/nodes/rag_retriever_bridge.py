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

    from rag.retriver.rag_state import PipelineRAGState
    from rag.retriver.retriever_runner import RetrieverExecutor, make_llm_call
    from rag.retriver.query_rewrite_node import query_rewrite_node
    from rag.retriver.query_router import QueryRoutingNode
    from rag.retriver.embedding_router import EmbeddingRoutingNode

    # Neo4j 환경 변수 가져오기 (환경 변수 → Parameter Store 순서로 시도)
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    # AWS EC2 환경인지 확인 (메타데이터 서비스 접근 가능 여부)
    is_aws_ec2 = False
    try:
        import urllib.request
        urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id", timeout=1)
        is_aws_ec2 = True
    except:
        pass
    
    # AWS EC2 환경이고 환경 변수가 없으면 Parameter Store에서 가져오기
    if is_aws_ec2:
        import boto3
        try:
            region = os.getenv("AWS_REGION", "ap-northeast-2")
            ssm = boto3.client("ssm", region_name=region)
            
            # NEO4J_URI가 없으면 구성
            if not uri:
                bolt_host = os.getenv("NEO4J_BOLT_HOST")
                if not bolt_host:
                    # 1순위: Parameter Store에서 가져오기 (이미 등록된 /skn18/neo4j-host 사용)
                    try:
                        response = ssm.get_parameter(Name="/skn18/neo4j-host")
                        bolt_host = response["Parameter"]["Value"]
                    except:
                        pass
                
                if not bolt_host:
                    # 2순위: CloudFormation Stack에서 가져오기
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
                    user = "neo4j"  # 기본값
            
            # NEO4J_PASSWORD가 없으면 가져오기
            if not password:
                try:
                    response = ssm.get_parameter(Name="/skn18/neo4j-password", WithDecryption=True)
                    password = response["Parameter"]["Value"]
                except:
                    pass
        except Exception as e:
            print(f"[Debug] Failed to load from Parameter Store: {e}")

    # [수정 3] 디버깅: 실제로 로드된 값 확인 (보안상 앞 2글자만 출력)
    print(f"[Debug] URI: {uri}")
    print(f"[Debug] USER: {user}")
    print(f"[Debug] PW Check: {password[:2] if password else None}... (Length: {len(password) if password else 0})")
    print(f"[Debug] AWS EC2: {is_aws_ec2}")

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