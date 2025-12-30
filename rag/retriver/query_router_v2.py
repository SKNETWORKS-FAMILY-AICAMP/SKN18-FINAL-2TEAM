# -*- coding: utf-8 -*-
"""
query_router.py

query_rewrite_node 출력(intent/domains/question_type/need_kg 등)을 기반으로
어떤 도메인에서 어떤 타입의 쿼리(Search/Filter/List/KG)를 실행할지 결정한다.

입력:
- state["rewrite"] (query_rewrite_node.py 결과)

출력:
- state["retrieval_params"] : Dict (k_seed, k_final 등)
- state["retrieval_plan"]   : List[dict] (각 단계별 계획)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rag_state_v2 import PipelineRAGState


@dataclass
class RetrievalStep:
    domain: str                 # paper | clinical | protocol | kg | entity
    mode: str                   # HY | VEC | ENTITY | FILTER | LIST
    embedder: Optional[str]     # main_1536 | protocol_1024 | None
    priority: int = 100         # 숫자가 작을수록 먼저
    why: str = ""               # 디버깅용 설명
    # GraphSearchQueries 상의 논리 쿼리 키 (예: SEARCH_PAPER_HYBRID, FILTER_TRIALS, LIST_ARTICLE_METHODS ...)
    query_key: Optional[str] = None


class QueryRoutingNode:
    """
    state["rewrite"]를 보고 state["retrieval_plan"]을 생성한다.
    """

    def __init__(self) -> None:
        pass
    
    @staticmethod
    def _is_method_list_question(question: str, rewrite: Dict[str, Any]) -> bool:
        """
        논문에서 '실험 방법/프로토콜/장비' 리스트를 원하는 질문인지 여부를 추정.
        """
        q = (question or "").lower()

        # 1) 질문 텍스트 기반 키워드
        method_keywords = [
            "방법", "실험", "프로토콜", "protocol", "method", "방법들",
            "조건", "buffer", "buffer 조건", "용액", "solution",
            "장비", "equipment", "reagent", "시약", "세팅", "세팅값",
        ]
        if any(k in q for k in method_keywords):
            return True

        # 2) intent 힌트 (리라이트에서 protocol_search 로 잡힌 경우)
        intent = (rewrite.get("intent") or "").lower()
        if intent == "protocol_search":
            return True

        return False


    def __call__(self, state: PipelineRAGState) -> PipelineRAGState:
        rewrite = state.get("rewrite") or {}
        question = (state.get("question") or "").strip()

        intent = (rewrite.get("intent") or "evidence_search").strip()
        domains = rewrite.get("domains") or []
        if not isinstance(domains, list):
            domains = []
        if not domains:
            domains = ["paper"]

        # question_type: chunk | list | filter
        question_type = (rewrite.get("question_type") or "chunk").strip()
        need_kg = bool(rewrite.get("need_kg", False))
        needs_chunks = bool(rewrite.get("needs_chunks", question_type == "chunk"))

        # retrieval params (defaults are set in rewrite node)
        retrieval = rewrite.get("retrieval") or {}
        state["retrieval_params"] = retrieval

        plan: List[RetrievalStep] = []

        # -----------------------------
        # 1) FILTER: 메타데이터 기반 조회
        #    - 여러 도메인이 들어오면 각 도메인별 FILTER_* 쿼리를 모두 추가
        # -----------------------------
        if question_type == "filter":
            if "paper" in domains:
                plan.append(
                    RetrievalStep(
                        domain="paper",
                        mode="FILTER",
                        embedder=None,
                        priority=10,
                        why="filter articles by metadata",
                        query_key="FILTER_ARTICLES",
                    )
                )
            if "protocol" in domains:
                plan.append(
                    RetrievalStep(
                        domain="protocol",
                        mode="FILTER",
                        embedder=None,
                        priority=11,
                        why="filter protocols by category/method/equipment",
                        query_key="FILTER_PROTOCOLS",
                    )
                )
            if "clinical" in domains:
                plan.append(
                    RetrievalStep(
                        domain="clinical",
                        mode="FILTER",
                        embedder=None,
                        priority=12,
                        why="filter clinical trials by phase/status/condition/intervention",
                        query_key="FILTER_TRIALS",
                    )
                )

            # KG 필요하면 KG 스텝도 추가
            self._maybe_add_kg_step(plan, domains, need_kg, base_priority=40)

            return self._finalize(
                state,
                plan,
                question=question,
                intent=intent,
                domains=domains,
                question_type=question_type,
                need_kg=need_kg,
                needs_chunks=needs_chunks,
            )

        # -----------------------------
        # 2) LIST: 리스트/추천형 조회
        #    - 여러 도메인 포함 시 각 도메인별 LIST_* 쿼리 모두 라우팅
        #    - paper 도메인인 경우 LIST_SIMILAR_ARTICLES + LIST_ARTICLE_METHODS 둘 다 추가
        # -----------------------------
        if question_type == "list":
            if "paper" in domains:
                # 항상: 유사 논문 리스트
                plan.append(
                    RetrievalStep(
                        domain="paper",
                        mode="LIST",
                        embedder=None,
                        priority=10,
                        why="list similar/related articles (topic-based)",
                        query_key="LIST_SIMILAR_ARTICLES",
                    )
                )

            # 조건: 방법/프로토콜/장비 리스트가 필요한 경우에만
            if self._is_method_list_question(question, rewrite):
                plan.append(
                    RetrievalStep(
                        domain="paper",
                        mode="LIST",
                        embedder=None,
                        priority=11,
                        why="list methods/entities used in the article",
                        query_key="LIST_ARTICLE_METHODS",
                    )
                )


            if "clinical" in domains:
                plan.append(
                    RetrievalStep(
                        domain="clinical",
                        mode="LIST",
                        embedder=None,
                        priority=12,
                        why="list similar clinical trials (shared entities)",
                        query_key="LIST_SIMILAR_TRIALS",
                    )
                )

            if "protocol" in domains:
                plan.append(
                    RetrievalStep(
                        domain="protocol",
                        mode="LIST",
                        embedder=None,
                        priority=13,
                        why="list related methods/protocols (co-occurrence)",
                        query_key="LIST_RELATED_METHODS",
                    )
                )

            # KG 필요하면 KG 스텝도 추가 (예: 메소드/엔티티 리스트 후 KG 확장)
            self._maybe_add_kg_step(plan, domains, need_kg, base_priority=50)

            return self._finalize(
                state,
                plan,
                question=question,
                intent=intent,
                domains=domains,
                question_type=question_type,
                need_kg=need_kg,
                needs_chunks=needs_chunks,
            )

        # -----------------------------
        # 3) 기본: chunk 기반 evidence search (SEARCH_* 하이브리드)
        #    - 여러 도메인이면 각 도메인별 HY 스텝 모두 추가
        # -----------------------------
        if needs_chunks:
            for d in domains:
                if d == "paper":
                    plan.append(
                        RetrievalStep(
                            domain="paper",
                            mode="HY",
                            embedder="main_1536",
                            priority=10,
                            why="paper hybrid search (vector + fulltext + graph)",
                            query_key="SEARCH_PAPER_HYBRID",
                        )
                    )
                elif d == "protocol":
                    plan.append(
                        RetrievalStep(
                            domain="protocol",
                            mode="HY",
                            embedder="protocol_1024",
                            priority=11,
                            why="protocol hybrid search (vector + text + graph)",
                            query_key="SEARCH_PROTOCOL_HYBRID",
                        )
                    )
                elif d == "clinical":
                    plan.append(
                        RetrievalStep(
                            domain="clinical",
                            mode="HY",
                            embedder="main_1536",
                            priority=12,
                            why="clinical hybrid search (entity + trial metadata)",
                            query_key="SEARCH_CLINICAL_HYBRID",
                        )
                    )

        # -----------------------------
        # 4) KG (PrimeKG) 필요 시 KG 확장 스텝 추가
        #    - domains 조합에 따라 paper/clinical용 KG 쿼리 선택
        # -----------------------------
        self._maybe_add_kg_step(plan, domains, need_kg, base_priority=30)

        return self._finalize(
            state,
            plan,
            question=question,
            intent=intent,
            domains=domains,
            question_type=question_type,
            need_kg=need_kg,
            needs_chunks=needs_chunks,
        )

    @staticmethod
    def _maybe_add_kg_step(
        plan: List[RetrievalStep],
        domains: List[str],
        need_kg: bool,
        base_priority: int,
    ) -> None:
        """need_kg=True이면 도메인 조합에 맞는 KG 하이브리드 스텝을 플랜에 추가한다."""
        if not need_kg:
            return

        # clinical만 있는 경우에는 임상 KG, 그 외에는 paper KG를 기본 사용
        if "clinical" in domains and "paper" not in domains:
            kg_query = "SEARCH_KG_CLINICAL_HYBRID"
        else:
            kg_query = "SEARCH_KG_PAPER_HYBRID"

        plan.append(
            RetrievalStep(
                domain="kg",
                # Orchestrator는 HY/VEC 모드에서 KG 하이브리드 쿼리를 처리하고,
                # 임베딩은 "main_1536" 키로 가져가기 때문에 이렇게 맞춰준다.
                mode="HY",
                embedder="main_1536",
                priority=base_priority,
                why="PrimeKG-based graph expansion",
                query_key=kg_query,
            )
        )


    @staticmethod
    def _finalize(
        state: Dict[str, Any],
        plan: List[RetrievalStep],
        question: str,
        intent: str,
        domains: List[str],
        question_type: str,
        need_kg: bool,
        needs_chunks: bool,
    ) -> PipelineRAGState:
        plan_sorted = sorted(plan, key=lambda s: (s.priority, s.domain, s.mode))

        state["retrieval_plan"] = [
            {
                "domain": s.domain,
                "mode": s.mode,
                "embedder": s.embedder,
                "priority": s.priority,
                "why": s.why,
                "query_key": s.query_key,
            }
            for s in plan_sorted
        ]

        # Route 메타 정보 업데이트 (track 없이 새 필드만 사용)
        route = state.get("route") or {}
        route.update(
            {
                "intent": intent,
                "domains": domains,
                "question_type": question_type,
                "need_kg": bool(need_kg),
                "needs_chunks": bool(needs_chunks),
            }
        )
        state["route"] = route

        return state
