# -*- coding: utf-8 -*-
"""
query_router.py

2) 쿼리 라우팅(Query Routing)
- query_rewrite 결과(track/intent/domains/retrieval 설정)를 기반으로
  "어떤 리트리버를 어떤 순서로 실행할지" 계획(retrieval_plan)을 만든다.

의존:
- state["rewrite"] (query_rewrite_node_soft.py가 작성)
출력:
- state["retrieval_plan"] : List[dict]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from rag_state import PipelineRAGState

@dataclass
class RetrievalStep:
    domain: str                 # paper | clinical | protocol | kg | entity | fulltext
    mode: str                   # HY | VEC | FT | ENTITY
    embedder: Optional[str]     # main_1536 | protocol_1024 | None
    priority: int = 100         # 낮을수록 먼저 실행
    why: str = ""               # 디버그용


class QueryRoutingNode:
    """
    state["rewrite"]를 읽고 state["retrieval_plan"]을 만든다.
    """
    def __init__(self) -> None:
        pass

    def __call__(self, state: PipelineRAGState) -> PipelineRAGState:
        rewrite = state.get("rewrite") or {}
        question = (state.get("question") or "").strip()

        track = (rewrite.get("track") or "T2").strip()
        intent = (rewrite.get("intent") or "evidence_search").strip()
        domains = rewrite.get("domains")
        if not isinstance(domains, list):
            domains = []

        # retrieval params (defaults are set in rewrite node)
        retrieval = rewrite.get("retrieval") or {}
        state["retrieval_params"] = retrieval

        plan: List[RetrievalStep] = []

        # -----------------------------
        # Track-based heuristics
        # -----------------------------
        # T1: 개념/정의 질문은 "FT/ENTITY 우선" (필요 시 HY로 보강)
        if track == "T1":
            plan.append(RetrievalStep(domain="entity", mode="ENTITY", embedder=None, priority=10,
                                    why="T1: entity/term grounding first"))
            plan.append(RetrievalStep(domain="paper", mode="FT", embedder=None, priority=20,
                                    why="T1: fulltext for definitions"))
            plan.append(RetrievalStep(domain="paper", mode="HY", embedder="main_1536", priority=40,
                                    why="T1: fallback hybrid if sparse"))
            return self._finalize(state, plan, question, track, intent, domains)

        # -----------------------------
        # Intent-based routing
        # -----------------------------
        if intent == "protocol_search":
            plan.append(RetrievalStep(domain="protocol", mode="HY", embedder="protocol_1024", priority=10,
                                    why="intent=protocol_search"))
            # protocol-only가 아니라면 paper도 보강
            if "paper" in domains or "clinical" in domains:
                plan.append(RetrievalStep(domain="paper", mode="HY", embedder="main_1536", priority=30,
                                        why="protocol + paper/clinical supplement"))
            return self._finalize(state, plan, question, track, intent, domains)

        if intent == "clinical_search":
            plan.append(RetrievalStep(domain="clinical", mode="HY", embedder="main_1536", priority=10,
                                    why="intent=clinical_search (1536 index)"))
            # 임상 질문은 paper evidence가 같이 필요할 때가 많아 보강
            plan.append(RetrievalStep(domain="paper", mode="HY", embedder="main_1536", priority=30,
                                    why="clinical -> paper supplement"))
            return self._finalize(state, plan, question, track, intent, domains)

        # -----------------------------
        # Multi-domain: entity -> domain별 HY
        # -----------------------------
        if intent == "multi_domain" or track == "T4":
            plan.append(RetrievalStep(domain="entity", mode="ENTITY", embedder=None, priority=5,
                                    why="T4: entity seed first (Neo4j FT entity resolve)"))

            # domains가 없거나 1개면 안전 디폴트
            if len(domains) < 2:
                domains = ["paper", "protocol"]

            if "kg" in domains:
                plan.append(RetrievalStep(domain="kg", mode="ENTITY", embedder=None, priority=8,
                                        why="T4: KG expansion based on entities"))

            if "paper" in domains:
                plan.append(RetrievalStep(domain="paper", mode="HY", embedder="main_1536", priority=15,
                                        why="T4: paper hybrid"))

            if "clinical" in domains:
                plan.append(RetrievalStep(domain="clinical", mode="HY", embedder="main_1536", priority=16,
                                        why="T4: clinical hybrid (1536)"))

            if "protocol" in domains:
                plan.append(RetrievalStep(domain="protocol", mode="HY", embedder="protocol_1024", priority=17,
                                        why="T4: protocol hybrid (1024)"))

            return self._finalize(state, plan, question, track, intent, domains)

        # -----------------------------
        # Default: evidence_search (T2/T3)
        # -----------------------------
        # domains 힌트가 있으면 그걸 우선, 없으면 paper 중심
        if "protocol" in domains:
            plan.append(RetrievalStep(domain="protocol", mode="HY", embedder="protocol_1024", priority=12,
                                    why="domains include protocol"))
        if "clinical" in domains:
            plan.append(RetrievalStep(domain="clinical", mode="HY", embedder="main_1536", priority=13,
                                    why="domains include clinical"))
        if "paper" in domains or not domains:
            plan.append(RetrievalStep(domain="paper", mode="HY", embedder="main_1536", priority=15,
                                    why="default paper hybrid"))

        # KG는 evidence_search에서도 트리거되면 함께(단, 우선순위는 뒤)
        if "kg" in domains:
            plan.append(RetrievalStep(domain="kg", mode="ENTITY", embedder=None, priority=40,
                                    why="domains include kg"))

        return self._finalize(state, plan, question, track, intent, domains)

    @staticmethod
    def _finalize(
        state: Dict[str, Any],
        plan: List[RetrievalStep],
        question: str,
        track: str,
        intent: str,
        domains: List[str],
    ) -> PipelineRAGState:
        plan_sorted = sorted(plan, key=lambda s: (s.priority, s.domain, s.mode))
        # dict로 직렬화
        state["retrieval_plan"] = [
                    {
                        "domain": s.domain,
                        "mode": s.mode,
                        "embedder": s.embedder,
                        "priority": s.priority,
                        "why": s.why,
                    }
                    for s in plan_sorted
            ]
                
            # Route 정보 갱신
        if state.get("route"):
            state["route"].update({"track": track, "intent": intent, "domains": domains})
        else:
            state["route"] = {
                "track": track, "intent": intent, "domains": domains, 
                "confidence": 0.0, "reason_short": "", "track_why": "", "intent_why": ""
                }
                    
        return state