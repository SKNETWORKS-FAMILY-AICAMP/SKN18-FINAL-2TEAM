# -*- coding: utf-8 -*-
"""
retriever_runner.py
[역할]
- rag_state.PipelineRAGState 사용
- 검색 파이프라인 실행 + 결과를 파일/STDOUT 으로 출력
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
from pathlib import Path

from rag_state_v2 import PipelineRAGState
from query_rewrite_node_v2 import query_rewrite_node
from query_router_v2 import QueryRoutingNode
from rag.retriver.embedding_router_v2 import EmbeddingRoutingNode
from rag_orchestrator_v2 import RAGOrchestrator


def _pick_id(item: Any) -> str:
    """context 객체에서 ID 비슷한 키를 찾아 dedup 키를 만든다."""
    if isinstance(item, dict):
        for k in (
            "chunk_id",
            "chunking_id",
            "protocol_chunking_id",
            "id",
            "doc_id",
            "pmid",
            "pmcid",
            "doi",
            "nct_id",
        ):
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
        raise ValueError("OPENAI_API_KEY is missing. Check your .env file.")
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def _call(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content

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

        # Orchestrator가 plan 전체를 병렬 실행
        contexts_raw: List[Any] = self.orchestrator.run_plan_parallel(
            plan=plan,
            question=question,
            embeddings=embeddings,
            rewrite=rewrite,
            retrieval_params=params,
        )

        # Dedup (간단한 ID 기반)
        uniq: List[Any] = []
        seen = set()
        for it in contexts_raw:
            key = _pick_id(it)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)

        state["contexts"] = uniq
        state["contexts_count"] = len(uniq)

        # 그래프 컨텍스트 / PrimeKG 인사이트 추출
        graph_contexts: List[Dict[str, Any]] = []
        primekg_all: List[Dict[str, Any]] = []

        for ctx in uniq:
            if not isinstance(ctx, dict):
                continue
            gc = ctx.get("graph_context")
            if isinstance(gc, dict):
                graph_contexts.append(gc)
                ins = gc.get("primekg_insights")
                if isinstance(ins, list):
                    for item in ins:
                        if isinstance(item, dict):
                            primekg_all.append(item)

        state["graph_contexts"] = graph_contexts
        state["primekg_insights"] = primekg_all

        return state


def main() -> None:
    # 프로젝트 루트 기준으로 .env 로드
    project_root = Path(__file__).resolve().parents[2]  # SKN18-FINAL-2TEAM/
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)

    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True, help="사용자 질문")
    ap.add_argument("--pretty", action="store_true", help="JSON pretty print")
    ap.add_argument(
        "--save",
        default="rag_result.json",
        help="결과 저장 파일 경로 (기본: rag_result.json)",
    )
    args = ap.parse_args()

    required_vars = [
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "OPENAI_API_KEY",
        "HUGGINGFACEHUB_API_TOKEN",
    ]
    if any(not os.getenv(v) for v in required_vars):
        sys.exit("Missing environment variables.")

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    llm_call = make_llm_call()

    try:
        router = QueryRoutingNode()
        embed_router = EmbeddingRoutingNode()
        executor = RetrieverExecutor(driver)

        # 초기 state
        state: PipelineRAGState = {"question": args.question}

        # 파이프라인 실행
        state = query_rewrite_node(state, llm_call)
        state = router(state)
        state = embed_router(state)
        state = executor(state)

        # ---------------------------------------------------------
        # 결과 로그용 레코드 (Rewrite, Route, Plan, Contexts, Graph 부분)
        # ---------------------------------------------------------
        result_record = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "question_original": state.get("question"),
            },
            "process": {
                "1_rewrite": state.get("rewrite"),
                "2_route": state.get("route"),
                "3_plan": state.get("retrieval_plan"),
            },
            "results": {
                "count": state.get("contexts_count"),
                "contexts": state.get("contexts"),
                "graph_contexts": state.get("graph_contexts"),
                "primekg_insights": state.get("primekg_insights"),
            },
        }

        # 파일로 저장
        if args.save:
            try:
                with open(args.save, "w", encoding="utf-8") as f:
                    json.dump(result_record, f, ensure_ascii=False, indent=2)
                print(f"[retriever_runner] Search results saved to: {args.save}", file=sys.stderr)
            except Exception as e:
                print(f"[retriever_runner] Failed to save results: {e}", file=sys.stderr)

        # STDOUT 출력 (간략/pretty 선택)
        out = {
            "question": state.get("question"),
            "route": state.get("route"),
            "retrieval_plan": state.get("retrieval_plan"),
            "contexts_count": state.get("contexts_count"),
            "contexts": state.get("contexts"),
            "graph_contexts": state.get("graph_contexts"),
            "primekg_insights": state.get("primekg_insights"),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))

    except Exception as e:
        print(f"[retriever_runner] Pipeline Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
