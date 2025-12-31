# -*- coding: utf-8 -*-
import neo4j
from typing import Any, Dict, List, Optional

# rag_queries.py에서 정의된 쿼리 그래프 임포트
from rag_queries import GraphSearchQueries, GraphCellQueries


def _to_safe_fulltext_query(text: str) -> str:
    """
    Neo4j fulltext.queryNodes에 넘길 Lucene 쿼리를 안전하게 변환한다.
    - 위험한 특수문자(/, ?, :, ~ 등)를 제거하고
    - 전체를 phrase 쿼리로 감싸고
    - 내부의 역슬래시와 따옴표를 escape 한다.
    """
    if not text:
        return ""
    # Lucene 쿼리 문법에서 문제 되는 기호들은 일단 제거
    for ch in ["/", "?", ":", "{", "}", "[", "]", "(", ")", "^", "~", "*"]:
        text = text.replace(ch, " ")
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped.strip()}"'



class RAGOrchestrator:
    def __init__(self, driver: neo4j.Driver):
        self.driver = driver

    def _run_query(self, cypher_query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Neo4j 쿼리 실행 헬퍼"""
        with self.driver.session() as session:
            result = session.run(cypher_query, params)
            return [record.data() for record in result]

    # =========================================================================
    # [A] Vector/Hybrid Search -> T2 Cell (Chunk ID 기반)
    # =========================================================================
    
    def route_by_hybrid_search(self, question: str, embedding: List[float], domain: str = "paper", **kwargs):
        """
        [Track T2] Evidence Search
        Flow: Vector/Keyword Search (OP) -> Chunk IDs -> Domain-specific T2 Cell
        """
        k_seed = kwargs.get("k_seed", 150)
        # 최종 반환할 chunk 목표 개수 (기본 100으로 상향)
        k_final = kwargs.get("k_final", 100)
        must_terms = kwargs.get("must_terms", [])
        must_not_terms = kwargs.get("must_not_terms", [])
        
        # [설정 1] Cell 쿼리에서 사용할 기본 파라미터
        defaults = {
            "evidence_per_article": 5, 
            "evidence_per_trial": 5,
            "evidence_per_protocol": 5,
            "limit_articles": 30,
            "limit_protocols": 15,
            "limit_trials": 20
        }

        # [설정 2] Hybrid Search(RRF)용 파라미터 준비
        # k_vec/k_ft는 RRF 튜닝을 위해 최종 k보다 넓게 잡는 것이 좋음 (예: k*2 또는 80)
        hybrid_params = {
            "q": _to_safe_fulltext_query(question),
            "embedding": embedding, 
            "fetch_vec": k_seed,    # 벡터 검색 시도 개수
            "k": k_final,           # 최종 리턴 개수
            "k_vec": 80,            # [추가] RRF용 벡터 후보 개수
            "k_ft": 80,             # [추가] RRF용 키워드 후보 개수
            "rrf_k0": 60,           # [추가] RRF 상수
            "must_terms": must_terms,
            "must_not_terms": must_not_terms
        }

        # 1. PAPER (T2)
        if domain == "paper":
            print(f"[Orchestrator] Domain: PAPER | Track: T2 -> PAPER_T2")
            search_results = self._run_query(
                GraphSearchQueries.HY_PAPER_CHUNK_DUAL_RRF, 
                hybrid_params
            )
            # must_terms 조건으로 결과가 없으면, must_terms를 제거하고 한 번 더 시도 (should-only)
            if not search_results and must_terms:
                print("[Orchestrator] PAPER: must_terms 적용 결과 없음 → must_terms 없이 재검색 시도")
                relaxed_params = dict(hybrid_params)
                relaxed_params["must_terms"] = []
                search_results = self._run_query(
                    GraphSearchQueries.HY_PAPER_CHUNK_DUAL_RRF,
                    relaxed_params,
                )

            if not search_results:
                return []
            
            chunk_ids = [r["chunk_id"] for r in search_results]
            scores = {r["chunk_id"]: r["hy_score"] for r in search_results}
            
            params = {
                "chunk_ids": chunk_ids, 
                "chunk_score_by_id": scores, 
                "limit_articles": len(chunk_ids),
                "evidence_per_article": defaults["evidence_per_article"],
            }
            return self._run_query(GraphCellQueries.PAPER_T2, params)

        # 2. PROTOCOL (T2)
        elif domain == "protocol":
            print(f"[Orchestrator] Domain: PROTOCOL | Track: T2 -> PROTOCOL_T2")
            search_results = self._run_query(
                GraphSearchQueries.HY_PROTOCOL_CHUNK_DUAL_RRF,
                hybrid_params
            )
            if not search_results and must_terms:
                print("[Orchestrator] PROTOCOL: must_terms 적용 결과 없음 → must_terms 없이 재검색 시도")
                relaxed_params = dict(hybrid_params)
                relaxed_params["must_terms"] = []
                search_results = self._run_query(
                    GraphSearchQueries.HY_PROTOCOL_CHUNK_DUAL_RRF,
                    relaxed_params,
                )

            if not search_results:
                return []

            # Protocol 쿼리는 'protocol_chunk_id'를 반환함에 주의
            chunk_ids = [r["protocol_chunk_id"] for r in search_results]
            scores = {r["protocol_chunk_id"]: r["hy_score"] for r in search_results}
            
            params = {
                "protocol_chunk_ids": chunk_ids, 
                "chunk_score_by_id": scores, 
                "limit_protocols": len(chunk_ids),
                "evidence_per_article": defaults["evidence_per_protocol"],
            }
            return self._run_query(GraphCellQueries.PROTOCOL_T2, params)

        # 3. CLINICAL (T2)
        elif domain == "clinical":
            print(f"[Orchestrator] Domain: CLINICAL | Track: T2 -> CLINICAL_T2")
            search_results = self._run_query(
                GraphSearchQueries.HY_CLINICAL_CHUNK_DUAL_RRF,
                hybrid_params
            )
            if not search_results and must_terms:
                print("[Orchestrator] CLINICAL: must_terms 적용 결과 없음 → must_terms 없이 재검색 시도")
                relaxed_params = dict(hybrid_params)
                relaxed_params["must_terms"] = []
                search_results = self._run_query(
                    GraphSearchQueries.HY_CLINICAL_CHUNK_DUAL_RRF,
                    relaxed_params,
                )

            if not search_results:
                return []

            chunk_ids = [r["clinical_chunk_id"] for r in search_results]
            scores = {r["clinical_chunk_id"]: r["hy_score"] for r in search_results}
            
            params = {
                "clinical_chunk_ids": chunk_ids, 
                "chunk_score_by_id": scores, 
                "limit_trials": len(chunk_ids),
                "evidence_per_trial": defaults["evidence_per_trial"],
            }
            return self._run_query(GraphCellQueries.CLINICAL_T2, params)

        else:
            print(f"[Orchestrator] Unknown domain for Hybrid Search: {domain}")
            return []

    # =========================================================================
    # [B] Entity Search -> T1, T3, T4 Cell (Entity ID 기반)
    # =========================================================================
    
    def route_by_entity(self, q: str, rewrite: Dict[str, Any] = None, domain: str = "paper", **kwargs):
        """
        [Track T1, T3, T4] Entity Search
        """
        safe_q = _to_safe_fulltext_query(q)
        entities = self._run_query(GraphSearchQueries.FT_ENTITY_RESOLVE, {"q": safe_q, "k": 1})
        if not entities:
            print(f"[Orchestrator] Entity not found for: {q}")
            return []
        
        entity_id = entities[0]["entity_id"]
        track = rewrite.get("track", "T4") if rewrite else "T4"
        
        if not domain or domain == "entity":
            domain = "paper"

        print(f"[Orchestrator] Entity Search '{q}' (ID: {entity_id}) -> Domain: {domain}, Track: {track}")

        # 공통 파라미터
        common_params = {
            "entity_ids": [entity_id],
            "limit_articles": 30,
            "evidence_per_article": 5,
            "limit_protocols": 15,
            "evidence_per_protocol": 5,
            "limit_trials": 20,
            "evidence_per_trial": 10,
            "set_size_target": 250,
        }

        # DOMAIN: PAPER
        if domain == "paper":
            if track == "T1":
                print("[Orchestrator] PAPER + T1 -> PAPER_T1")
                return self._run_query(GraphCellQueries.PAPER_T1, common_params)
            
            elif track == "T3":
                print("[Orchestrator] PAPER + T3 -> PAPER_T3")
                return self._run_query(GraphCellQueries.PAPER_T3, common_params)
            
            else:  # T4 or Default
                print("[Orchestrator] PAPER + T4 -> PAPER_T4")
                return self._run_query(GraphCellQueries.PAPER_T4, common_params)

        # DOMAIN: PROTOCOL
        elif domain == "protocol":
            if track == "T1":
                print("[Orchestrator] PROTOCOL + T1 -> PROTOCOL_T1")
                return self._run_query(GraphCellQueries.PROTOCOL_T1, common_params)
            elif track == "T3":
                print("[Orchestrator] PROTOCOL + T3 -> PROTOCOL_T3")
                return self._run_query(GraphCellQueries.PROTOCOL_T3, common_params)
            else:
                print("[Orchestrator] PROTOCOL + T4 -> PROTOCOL_T4")
                return self._run_query(GraphCellQueries.PROTOCOL_T4, common_params)

        # DOMAIN: CLINICAL
        elif domain == "clinical":
            if track == "T1":
                print("[Orchestrator] Redirecting T1 to T3 for Entity input")
                return self._run_query(GraphCellQueries.CLINICAL_T3, common_params)
            elif track == "T3":
                print("[Orchestrator] CLINICAL + T3 -> CLINICAL_T3")
                return self._run_query(GraphCellQueries.CLINICAL_T3, common_params)
            else:
                print("[Orchestrator] CLINICAL + T4 -> CLINICAL_T4")
                return self._run_query(GraphCellQueries.CLINICAL_T4, common_params)

        # DOMAIN: KG
        elif domain == "kg":
            print("[Orchestrator] KG -> PAPER_T4 (Multi-domain)")
            return self._run_query(GraphCellQueries.PAPER_T4, common_params)

        else:
            print(f"[Orchestrator] Unknown Domain '{domain}'. Defaulting to PAPER_T4.")
            return self._run_query(GraphCellQueries.PAPER_T4, common_params)

    # 프로토콜/클리니컬/그래프용 라우터
    def route_for_protocol(self, question: str, embedding: List[float], **kwargs):
        return self.route_by_hybrid_search(question, embedding, domain="protocol", **kwargs)

    def route_for_clinical(self, question: str, embedding: List[float], **kwargs):
        return self.route_by_hybrid_search(question, embedding, domain="clinical", **kwargs)
        
    def route_for_kg(self, q: str, **kwargs):
        return self.route_by_entity(q, domain="kg", **kwargs)
