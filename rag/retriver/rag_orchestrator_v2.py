# -*- coding: utf-8 -*-
import concurrent.futures
from typing import Any, Dict, List, Optional

import neo4j

from rag.retriver.rag_queries_v2 import GraphSearchQueries, GraphCellQueries


def _to_safe_fulltext_query(text: str) -> str:
    """
    Neo4j fulltext.queryNodes 에 넣기 좋은 Lucene 쿼리 문자열로 변환.
    - 특수문자(/, ?, :, ~ 등)를 공백으로 치환
    - 전체를 phrase 쿼리로 감싼다.
    """
    if not text:
        return ""
    for ch in ["/", "?", ":", "{", "}", "[", "]", "(", ")", "^", "~", "*"]:
        text = text.replace(ch, " ")
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped.strip()}"'


class RAGOrchestrator:
    """
    GraphSearchQueries / GraphCellQueries 를 이용해
    retrieval_plan 의 각 스텝을 실행해 contexts 를 만드는 역할.
    """

    def __init__(self, driver: neo4j.Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Low-level query runner
    # ------------------------------------------------------------------
    def _run_query(self, cypher_query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Neo4j 쿼리 실행 래퍼."""
        with self.driver.session() as session:
            result = session.run(cypher_query, params)
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # Public: plan 전체를 병렬 실행
    # ------------------------------------------------------------------
    def run_plan_parallel(
        self,
        plan: List[Dict[str, Any]],
        question: str,
        embeddings: Dict[str, List[float]],
        rewrite: Dict[str, Any],
        retrieval_params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        QueryRoutingNode 가 만든 retrieval_plan 을 받아
        각 스텝을 병렬로 실행한 뒤 contexts 를 합쳐 반환한다.
        """
        if not plan:
            return []

        # 각 스텝을 개별 작업으로 실행
        contexts: List[Dict[str, Any]] = []

        max_workers = min(len(plan), 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for step in plan:
                futures.append(
                    executor.submit(
                        self._execute_step,
                        step=step,
                        question=question,
                        embeddings=embeddings,
                        rewrite=rewrite,
                        retrieval_params=retrieval_params,
                    )
                )

            for f in concurrent.futures.as_completed(futures):
                try:
                    res = f.result()
                    if res:
                        contexts.extend(res)
                except Exception as e:  # 로깅 용도
                    print(f"[RAGOrchestrator] step execution error: {e}")

        return contexts

    # ------------------------------------------------------------------
    # Step 실행: domain/mode/query_key 에 따라 분기
    # ------------------------------------------------------------------
    def _execute_step(
        self,
        step: Dict[str, Any],
        question: str,
        embeddings: Dict[str, List[float]],
        rewrite: Dict[str, Any],
        retrieval_params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        domain = step.get("domain")
        mode = step.get("mode")
        embedder = step.get("embedder")
        query_key = step.get("query_key")

        if not query_key:
            print(f"[RAGOrchestrator] step without query_key skipped: {step}")
            return []

        question_safe = _to_safe_fulltext_query(question)
        k_final = retrieval_params.get("k_final", 50)
        need_kg = bool(rewrite.get("need_kg", False))

        # HYBRID / VEC (chunk 기반 검색)
        if mode in ("HY", "VEC"):
            embedding = embeddings.get(embedder) if embedder else None
            if not embedding:
                print(f"[RAGOrchestrator] missing embedding for step: {step}")
                return []

            if domain == "paper" and query_key == "SEARCH_PAPER_HYBRID":
                return self._search_paper_hybrid(question_safe, embedding, k_final, need_kg)

            if domain == "protocol" and query_key == "SEARCH_PROTOCOL_HYBRID":
                return self._search_protocol_hybrid(question_safe, embedding, k_final, need_kg)

            if domain == "clinical" and query_key == "SEARCH_CLINICAL_HYBRID":
                return self._search_clinical_hybrid(question_safe, k_final)

            # KG hybrid 검색 (paper/clinical context)
            if domain == "kg" and query_key in ("SEARCH_KG_PAPER_HYBRID", "SEARCH_KG_CLINICAL_HYBRID"):
                return self._search_kg_hybrid(query_key, question_safe, embedding, k_final)

            print(f"[RAGOrchestrator] unsupported HY/VEC step: {step}")
            return []

        # FILTER
        if mode == "FILTER":
            return self._run_filter_query(domain, query_key, k_final, rewrite)

        # LIST
        if mode == "LIST":
            return self._run_list_query(domain, query_key, question_safe, k_final)

        # ENTITY (현재는 KG 확장용만 사용)
        if mode == "ENTITY":
            if domain == "kg" and query_key in ("SEARCH_KG_PAPER_HYBRID", "SEARCH_KG_CLINICAL_HYBRID"):
                embedding = embeddings.get(embedder) if embedder else None
                return self._search_kg_hybrid(query_key, question_safe, embedding, k_final)
            print(f"[RAGOrchestrator] ENTITY step not wired: {step}")
            return []

        print(f"[RAGOrchestrator] unknown mode '{mode}' in step: {step}")
        return []

    # ------------------------------------------------------------------
    # HYBRID helpers
    # ------------------------------------------------------------------
    def _search_paper_hybrid(
        self,
        safe_q: str,
        embedding: List[float],
        k_final: int,
        include_primekg: bool,
    ) -> List[Dict[str, Any]]:
        # 1) chunk 검색
        search_params = {
            "q": safe_q,
            "embedding": embedding,
            "k": k_final,
        }
        search_results = self._run_query(GraphSearchQueries.SEARCH_PAPER_HYBRID, search_params)
        if not search_results:
            return []

        chunk_ids = [r["chunk_id"] for r in search_results]
        scores = {r["chunk_id"]: r.get("hy_score", 0.0) for r in search_results}

        # 2) Assembly (문서+그래프+청크)
        cell_params = {
            "chunk_ids": chunk_ids,
            "chunk_score_by_id": scores,
            "include_primekg": bool(include_primekg),
        }
        return self._run_query(GraphCellQueries.ASSEMBLY_PAPER, cell_params)

    def _search_protocol_hybrid(
        self,
        safe_q: str,
        embedding: List[float],
        k_final: int,
        include_primekg: bool,
    ) -> List[Dict[str, Any]]:
        search_params = {
            "q": safe_q,
            "embedding": embedding,
            "k": k_final,
        }
        rows = self._run_query(GraphSearchQueries.SEARCH_PROTOCOL_HYBRID, search_params)
        if not rows:
            return []

        # protocol 타입만 선택
        proto_ids = [r["id"] for r in rows if r.get("type") == "protocol"]
        scores = {r["id"]: r.get("hy_score", 0.0) for r in rows if r.get("type") == "protocol"}

        if not proto_ids:
            return []

        cell_params = {
            "chunk_ids": proto_ids,
            "chunk_score_by_id": scores,
            "include_primekg": bool(include_primekg),
        }
        return self._run_query(GraphCellQueries.ASSEMBLY_PROTOCOL, cell_params)

    def _search_clinical_hybrid(
        self,
        safe_q: str,
        k_final: int,
        ) -> List[Dict[str, Any]]:
        """
        임상 HYBRID 쿼리는 이미 trial 레벨 결과를 반환하므로
        추가 assembly 없이 그대로 contexts로 사용.
        """
        params = {
            "q": safe_q,
            "k": k_final,
            "phase": None,
            "status": None,
            "year_from": None,
        }
        return self._run_query(GraphSearchQueries.SEARCH_CLINICAL_HYBRID, params)

    def _search_kg_hybrid(
        self,
        query_key: str,
        safe_q: str,
        embedding: Optional[List[float]],
        k_final: int,
    ) -> List[Dict[str, Any]]:
        """
        KG 기반 하이브리드 쿼리 (paper/clinical context).
        결과는 그대로 contexts 로 사용.
        """
        if not embedding:
            print("[RAGOrchestrator] KG search requested but embedding is missing")
            return []

        cypher = getattr(GraphSearchQueries, query_key)
        params = {
            "q": safe_q,
            "embedding": embedding,
            "k": k_final,
        }
        return self._run_query(cypher, params)

    # ------------------------------------------------------------------
    # FILTER / LIST helpers
    # ------------------------------------------------------------------
    def _run_filter_query(
        self,
        domain: str,
        query_key: str,
        k_final: int,
        rewrite: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        filters = rewrite.get("filters") or {}
        cypher = getattr(GraphSearchQueries, query_key)

        if query_key == "FILTER_ARTICLES":
            params = {
                "year_from": filters.get("year_from"),
                "year_to": filters.get("year_to"),
                "journal": filters.get("journal"),
                "domain": filters.get("domain"),
                "study_type": filters.get("study_type"),
                "k": k_final,
            }
        elif query_key == "FILTER_PROTOCOLS":
            params = {
                "keyword": filters.get("keyword"),
                "category": filters.get("category"),
                "method": filters.get("method"),
                "equipment": filters.get("equipment"),
                "k": k_final,
            }
        elif query_key == "FILTER_TRIALS":
            params = {
                "phase": filters.get("phase"),
                "year_from": filters.get("year_from"),
                "status": filters.get("status"),
                "study_type": filters.get("study_type"),
                "condition": filters.get("condition"),
                "intervention": filters.get("intervention"),
                "k": k_final,
            }
        else:
            # 알 수 없는 FILTER 키는 k만 넣고 그대로 호출
            params = {"k": k_final}

        return self._run_query(cypher, params)

    def _run_list_query(
        self,
        domain: str,
        query_key: str,
        safe_q: str,
        k_final: int,
    ) -> List[Dict[str, Any]]:
        cypher = getattr(GraphSearchQueries, query_key)

        if query_key in ("LIST_SIMILAR_ARTICLES", "LIST_SIMILAR_TRIALS"):
            params = {"q": safe_q, "k": k_final}
        elif query_key in ("LIST_RELATED_METHODS", "LIST_ARTICLE_METHODS"):
            params = {"q": safe_q, "k": k_final}
        else:
            params = {"q": safe_q, "k": k_final}

        return self._run_query(cypher, params)
