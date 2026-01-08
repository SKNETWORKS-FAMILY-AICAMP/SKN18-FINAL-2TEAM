# -*- coding: utf-8 -*-
"""
retriever_runner.py
[수정 사항]
- rag_state.py의 PipelineRAGState 적용
- 검색 결과 파일 저장 기능 추가 (Rewritten Query, Routing Path, Contexts)
- AWS EC2 환경에서 Parameter Store 지원 추가
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from datetime import datetime  
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# [New] State Config Import
from rag_state import PipelineRAGState

from query_rewrite_node import query_rewrite_node
from query_router import QueryRoutingNode
from embedding_router import EmbeddingRoutingNode
from rag_orchestrator import RAGOrchestrator
from pathlib import Path

# AWS boto3 지원 확인 (선택적)
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    boto3 = None
    HAS_BOTO3 = False

def _call_with_supported_kwargs(fn: Callable[..., Any], **kwargs) -> Any:
    sig = inspect.signature(fn)
    supported = {}
    for k, v in kwargs.items():
        if k in sig.parameters:
            supported[k] = v
    return fn(**supported)

def _pick_id(item: Any) -> str:
    if isinstance(item, dict):
        for k in ("chunk_id", "chunking_id", "protocol_chunking_id", "id", "doc_id", "pmid", "pmcid", "doi", "nct_id"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return f"{k}:{v.strip()}"
            if isinstance(v, int):
                return f"{k}:{v}"
        return "dict:" + json.dumps(item, ensure_ascii=False, sort_keys=True)[:500]
    return f"obj:{str(item)[:500]}"


def _get_parameter_from_store(
    parameter_path: str,
    region: str | None = None,
    with_decryption: bool = False,
) -> str | None:
    """
    AWS Parameter Store에서 파라미터 값을 가져옵니다.
    
    Args:
        parameter_path: Parameter Store 경로
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
        with_decryption: SecureString 타입인 경우 복호화 여부
    
    Returns:
        파라미터 값, 실패 시 None
    """
    if not HAS_BOTO3:
        return None
    
    try:
        if region is None:
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
        
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(
            Name=parameter_path,
            WithDecryption=with_decryption
        )
        return response["Parameter"]["Value"]
    except (ClientError, Exception):
        return None


def _get_env_or_parameter(
    env_var_name: str,
    parameter_path: str,
    with_decryption: bool = False,
) -> str | None:
    """
    환경 변수 또는 Parameter Store에서 값을 가져옵니다.
    
    우선순위:
        1. 환경 변수
        2. Parameter Store (EC2 환경이고 boto3가 있으면 시도)
        3. None
    
    Args:
        env_var_name: 환경 변수 이름
        parameter_path: Parameter Store 경로
        with_decryption: SecureString 타입인 경우 복호화 여부
    
    Returns:
        값 문자열, 없으면 None
    """
    # 1. 환경 변수 확인
    value = os.getenv(env_var_name)
    if value:
        return value
    
    # 2. AWS EC2 환경인지 확인
    is_aws_ec2 = False
    try:
        import urllib.request
        urllib.request.urlopen("http://169.254.169.254/latest/meta-data/instance-id", timeout=1)
        is_aws_ec2 = True
    except:
        pass
    
    # 3. EC2 환경이고 boto3가 있으면 Parameter Store 시도
    if is_aws_ec2 and HAS_BOTO3:
        value = _get_parameter_from_store(parameter_path, with_decryption=with_decryption)
        if value:
            return value
    
    return None


def _get_neo4j_config() -> Tuple[str, str, str]:
    """
    Neo4j 연결 정보를 가져옵니다 (환경 변수 → Parameter Store 순서).
    
    Returns:
        (uri, user, password) 튜플
    """
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
    if is_aws_ec2 and HAS_BOTO3:
        try:
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
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
        except Exception:
            pass
    
    return uri, user, password

def make_llm_call() -> Callable[[str], str]:
    # 환경 변수 또는 Parameter Store에서 API 키 가져오기
    api_key = _get_env_or_parameter(
        "OPENAI_API_KEY",
        "/skn18/openai-api-key",
        with_decryption=True
    )
    if not api_key:
        raise ValueError(
            "❌ OPENAI_API_KEY is missing. "
            "Please check your .env file or Parameter Store (/skn18/openai-api-key)."
        )
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def _call(prompt: str) -> str:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise e
    return _call


class RetrieverExecutor:
    def __init__(self, neo4j_driver) -> None:
        self.orchestrator = RAGOrchestrator(neo4j_driver)

    def __call__(self, state: PipelineRAGState) -> PipelineRAGState:
        question = (state.get("question") or "").strip()
        rewrite = state.get("rewrite") or {}
        plan = state.get("retrieval_plan") or []
        embeddings = state.get("embeddings") or {}
        params = state.get("retrieval_params") or {}

        must_terms = rewrite.get("must_terms_expanded") or []
        must_not_terms = rewrite.get("must_not_terms_expanded") or []

        contexts: List[Any] = []

        # 메서드 바인딩
        fn_entity = getattr(self.orchestrator, "route_by_entity", None)
        fn_paper_hy = getattr(self.orchestrator, "route_by_hybrid_search", None)
        fn_protocol_hy = getattr(self.orchestrator, "route_for_protocol", None)
        fn_clinical_hy = getattr(self.orchestrator, "route_for_clinical", None) or getattr(self.orchestrator, "route_by_hybrid_search", None)
        fn_kg = getattr(self.orchestrator, "route_for_kg", None)

        for step in plan:
            domain = step.get("domain")
            mode = step.get("mode")
            embedder = step.get("embedder")

            common_kwargs = dict(
                question=question,
                k_seed=params.get("k_seed"),
                k_final=params.get("k_final"),
                hop_limit=params.get("hop_limit"),
                fanout_limit=params.get("fanout_limit"),
                must_terms=must_terms,
                must_not_terms=must_not_terms,
                rewrite=rewrite,
                route_hint=state.get("route"),
            )

            # Entity 모드
            if mode == "ENTITY" and fn_entity:
                res = _call_with_supported_kwargs(fn_entity, q=question, domain=domain, **common_kwargs)
                if res: contexts.extend(res)

            # Hybrid Modes
            elif domain == "paper" and mode in ("HY", "VEC") and fn_paper_hy:
                emb = embeddings.get(embedder) if embedder else None
                res = _call_with_supported_kwargs(fn_paper_hy, q=question, embedding=emb, **common_kwargs)
                if res: contexts.extend(res)

            elif domain == "clinical" and mode in ("HY", "VEC") and fn_clinical_hy:
                emb = embeddings.get(embedder) if embedder else None
                res = _call_with_supported_kwargs(fn_clinical_hy, q=question, embedding=emb, **common_kwargs)
                if res: contexts.extend(res)

            elif domain == "protocol" and mode in ("HY", "VEC") and fn_protocol_hy:
                emb = embeddings.get(embedder) if embedder else None
                res = _call_with_supported_kwargs(fn_protocol_hy, q=question, embedding=emb, **common_kwargs)
                if res: contexts.extend(res)

            elif domain == "kg" and fn_kg:
                res = _call_with_supported_kwargs(fn_kg, q=question, **common_kwargs)
                if res: contexts.extend(res)

            else:
                continue

        # Dedup
        uniq: List[Any] = []
        seen = set()
        for it in contexts:
            key = _pick_id(it)
            if key in seen: continue
            seen.add(key)
            uniq.append(it)

        state["contexts"] = uniq
        state["contexts_count"] = len(uniq)
        return state


def main() -> None:
    # 프로젝트 루트 기준으로 .env 로드
    project_root = Path(__file__).resolve().parents[2]  # SKN18-FINAL-2TEAM/
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True, help="사용자 질문")
    ap.add_argument("--pretty", action="store_true", help="JSON pretty print")
    # [New] 저장 파일명 옵션 추가
    ap.add_argument("--save", default="rag_result.json", help="결과 저장 파일 경로 (기본: rag_result.json)")
    args = ap.parse_args()

    # Neo4j 연결 정보 가져오기 (환경 변수 → Parameter Store)
    uri, user, password = _get_neo4j_config()
    if not uri or not user or not password:
        sys.exit(
            "❌ Missing Neo4j configuration. "
            "Please set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD environment variables "
            "or configure Parameter Store (/skn18/neo4j-host, /skn18/neo4j-user, /skn18/neo4j-password)."
        )
    
    driver = GraphDatabase.driver(uri, auth=(user, password))

    # OpenAI API 키는 make_llm_call에서 검증됨
    # HUGGINGFACEHUB_API_TOKEN은 embedding_router.py에서 검증됨
    llm_call = make_llm_call()

    try:
        router = QueryRoutingNode()
        embed_router = EmbeddingRoutingNode()
        executor = RetrieverExecutor(driver)

        # TypedDict 초기화
        state: PipelineRAGState = {"question": args.question}

        # 파이프라인 실행
        state = query_rewrite_node(state, llm_call)
        state = router(state)
        state = embed_router(state)
        state = executor(state)

        # ---------------------------------------------------------
        # [New] 결과 저장 로직 (Rewrite, Route, Contexts)
        # ---------------------------------------------------------
        result_record = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "question_original": state.get("question")
            },
            "process": {
                "1_rewrite": state.get("rewrite"),          # 재작성된 쿼리 정보
                "2_route": state.get("route"),              # 상위 라우팅 결과
                "3_plan": state.get("retrieval_plan")       # 상세 실행 계획
            },
            "results": {
                "count": state.get("contexts_count"),
                "contexts": state.get("contexts")           # 최종 검색 결과
            }
        }

        # 파일 저장
        if args.save:
            try:
                with open(args.save, "w", encoding="utf-8") as f:
                    json.dump(result_record, f, ensure_ascii=False, indent=2)
                # stdout 출력을 방해하지 않기 위해 stderr로 로그 출력
                print(f"💾 Search results saved to: {args.save}", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ Failed to save results: {e}", file=sys.stderr)
        # ---------------------------------------------------------

        # 기존 stdout 출력 (파이프라이닝용)
        out = {
            "question": state.get("question"),
            "route": state.get("route"),
            "retrieval_plan": state.get("retrieval_plan"),
            "contexts_count": state.get("contexts_count"),
            "contexts": state.get("contexts"),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))
    
    except Exception as e:
        print(f"❌ Pipeline Error: {str(e)}")
        sys.exit(1)
    finally:
        driver.close()

if __name__ == "__main__":
    main()