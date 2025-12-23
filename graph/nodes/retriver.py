"""
retrieval.py
-------------------------------------
질문 유형별로 RAG 검색을 수행하는 LangGraph 노드.

이 버전에서는 기존 임시 pgvector/neo4j 더미 검색 대신
rag/retriver/retriever_runner.py 에 정의된 RAG 파이프라인을 호출해서
실제 Retrieval Plan + Embeddings + Contexts 를 가져오도록 연동한다.
"""

from typing import Dict, Any, List

from graph.nodes.rag_retriever_bridge import run_rag_retrieval_pipeline


# ============================================
# BIO_Q 리트리버 노드 (RAG 파이프라인 연동)
# ============================================

def retriever_bio_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q 용 리트리버 노드.

    - rag/retriver/retriever_runner.py 의 파이프라인을 호출해서
      rewrite / route / retrieval_plan / embeddings / contexts 를 생성
    - LangGraph 에서 사용하던 state 필드(retrieval_results, entities 등)에 매핑
    """

    print(f"\n{'='*60}")
    print(f"[RETRIEIVER_BIO NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")

    question = state.get("question", "") or ""

    try:
        rag_state = run_rag_retrieval_pipeline(question)
    except Exception as e:
        # RAG 파이프라인 오류 시, 이후 노드에서 graceful 하게 처리할 수 있도록
        # 최소 구조만 채워서 반환
        print(f"[BIO Retriever] RAG 파이프라인 실행 중 오류 발생: {e}")
        state.setdefault("retrieval_results", [])
        state.setdefault("entities", [])
        state.setdefault("used_search_db", "graph_rag_error")
        return state

    # -----------------------------
    # RAG Pipeline -> LangGraph State 매핑
    # -----------------------------

    # 1) Rewrite 관련 필드 (RAG 파이프라인 결과)
    rewrite = rag_state.get("rewrite") or {}
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = rag_state.get("rewrite_json_min", "")
    state["rewrite_input_text"] = rag_state.get("rewrite_input_text", question)
    state["route"] = rag_state.get("route") or {}

    # 기존 문자열 기반 rewritten_query 와 최대한 호환
    normalized_q = rewrite.get("normalized_question") or question
    state["rewritten_query"] = normalized_q

    # 2) Retrieval Plan / Embeddings / Contexts
    state["retrieval_params"] = rag_state.get("retrieval_params") or {}
    state["retrieval_plan"] = rag_state.get("retrieval_plan") or []
    state["embeddings"] = rag_state.get("embeddings") or {}

    contexts: List[Dict[str, Any]] = rag_state.get("contexts") or []
    state["contexts"] = contexts
    state["contexts_count"] = int(rag_state.get("contexts_count", len(contexts)))

    # LangGraph 의 downstream 노드들이 사용하던 필드에 그대로 연결
    state["retrieval_results"] = contexts
    state["used_search_db"] = "graph_rag"

    # 3) Entity 리스트
    #   - LangGraph rewrite_query.py 에서는 엔티티를 추출하지 않는다.
    #   - 필요하다면 RAG 쪽 rewrite["entities"] 를 간단한 문자열 리스트로 변환해서 사용.
    entities_from_rewrite = rewrite.get("entities") or []
    entities: List[str] = []
    for ent in entities_from_rewrite:
        try:
            name = ent.get("name") or ent.get("label") or ent.get("id")
            entities.append(str(name) if name is not None else str(ent))
        except Exception:
            entities.append(str(ent))
    state["entities"] = entities

    print(f"\n[RETRIEIVER_BIO NODE] 완료")
    print(f"  contexts: {len(contexts)}개")
    print(f"  entities: {len(entities)}개")
    print(f"{'='*60}\n")

    return state


# ============================================
# PROTOCOL_Q 리트리버 노드 (RAG 파이프라인 재사용)
# ============================================

def retriever_protocol_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q 용 리트리버 노드.

    현재는 BIO_Q 와 동일하게 retriever_runner 파이프라인을 호출하고,
    결과를 그대로 매핑한다.
    (추후 필요 시 RAG 쪽 Router / Orchestrator 정책에서
     protocol 도메인 전용 플랜을 세우도록 확장 가능)
    """

    print(f"\n{'='*60}")
    print(f"[RETRIEIVER_PROTOCOL NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")

    question = state.get("question", "") or ""

    try:
        rag_state = run_rag_retrieval_pipeline(question)
    except Exception as e:
        print(f"[PROTOCOL Retriever] RAG 파이프라인 실행 중 오류 발생: {e}")
        state.setdefault("retrieval_results", [])
        state.setdefault("entities", [])
        state.setdefault("used_search_db", "graph_rag_error")
        return state

    # Rewrite / Route
    rewrite = rag_state.get("rewrite") or {}
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = rag_state.get("rewrite_json_min", "")
    state["rewrite_input_text"] = rag_state.get("rewrite_input_text", question)
    state["route"] = rag_state.get("route") or {}

    normalized_q = rewrite.get("normalized_question") or question
    state["rewritten_query"] = normalized_q

    # Retrieval Plan / Embeddings / Contexts
    state["retrieval_params"] = rag_state.get("retrieval_params") or {}
    state["retrieval_plan"] = rag_state.get("retrieval_plan") or []
    state["embeddings"] = rag_state.get("embeddings") or {}

    contexts: List[Dict[str, Any]] = rag_state.get("contexts") or []
    state["contexts"] = contexts
    state["contexts_count"] = int(rag_state.get("contexts_count", len(contexts)))

    state["retrieval_results"] = contexts
    state["used_search_db"] = "graph_rag"

    # Entity 리스트
    entities_from_rewrite = rewrite.get("entities") or []
    entities: List[str] = []
    for ent in entities_from_rewrite:
        try:
            name = ent.get("name") or ent.get("label") or ent.get("id")
            entities.append(str(name) if name is not None else str(ent))
        except Exception:
            entities.append(str(ent))
    state["entities"] = entities

    print(f"\n[RETRIEIVER_PROTOCOL NODE] 완료")
    print(f"  contexts: {len(contexts)}개")
    print(f"  entities: {len(entities)}개")
    print(f"{'='*60}\n")

    return state    