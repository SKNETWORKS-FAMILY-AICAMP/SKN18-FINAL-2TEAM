# -*- coding: utf-8 -*-
"""
retriever_runner.py
[수정 사항]
- rag_state.py의 PipelineRAGState 적용
- 검색 결과 파일 저장 기능 추가 (Rewritten Query, Routing Path, Contexts)
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from datetime import datetime  # [New] 시간 기록용
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# [New] State Config Import
from rag_state import PipelineRAGState

from query_rewrite_node import query_rewrite_node
from query_router import QueryRoutingNode
from embedding_router import EmbeddingRoutingNode
from rag_orchestrator import RAGOrchestrator


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

def make_llm_call() -> Callable[[str], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("❌ OPENAI_API_KEY is missing. Check your .env file.")
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
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True, help="사용자 질문")
    ap.add_argument("--pretty", action="store_true", help="JSON pretty print")
    # [New] 저장 파일명 옵션 추가
    ap.add_argument("--save", default="rag_result.json", help="결과 저장 파일 경로 (기본: rag_result.json)")
    args = ap.parse_args()

    required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "OPENAI_API_KEY", "HUGGINGFACEHUB_API_TOKEN"]
    if any(not os.getenv(v) for v in required_vars):
        sys.exit("❌ Missing environment variables.")

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, password))

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