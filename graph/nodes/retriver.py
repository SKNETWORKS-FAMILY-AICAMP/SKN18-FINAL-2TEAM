"""
retriver.py
-------------------------------------
LangGraph에서 BIO_Q / PROTOCOL_Q 질문을 RAG 파이프라인에 넘겨
검색 결과(contexts)를 받아오고, 여기서 바로 Cross-Encoder 기반 rerank까지 수행한다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from graph.nodes.rag_retriever_bridge import run_rag_retrieval_pipeline
from graph.nodes.rerank import rerank_with_cross_encoder


def _log_contexts_brief(contexts: List[Dict[str, Any]], label: str) -> None:
    """검색된 컨텍스트 개수만 간단히 로깅."""
    print(f"[{label}] contexts: {len(contexts)}개")


def _extract_entities_from_rewrite(rewrite: Dict[str, Any]) -> List[str]:
    """rewrite 결과에서 엔티티 이름 리스트만 추출."""
    entities_from_rewrite = rewrite.get("entities") or []
    entities: List[str] = []
    for ent in entities_from_rewrite:
        try:
            name = ent.get("name") or ent.get("label") or ent.get("id")
            entities.append(str(name) if name is not None else str(ent))
        except Exception:
            entities.append(str(ent))
    return entities


# ============================================
# BIO_Q 리트리버 노드
# ============================================

def retriever_bio_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q 용 RAG 리트리버 노드.
    - rag/retriver/retriever_runner.py 파이프라인을 실행해 contexts 를 받아오고
    - 여기서 Cross-Encoder 기반 rerank 를 수행해 retrieval_results 에 저장한다.
    """

    print("\n" + "=" * 60)
    print("[RETRIEIVER_BIO NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print("=" * 60 + "\n")

    question = (state.get("question") or "").strip()

    try:
        rag_state = run_rag_retrieval_pipeline(question)
    except Exception as e:
        print(f"[BIO Retriever] RAG 파이프라인 실행 중 오류 발생: {e}")
        state.setdefault("retrieval_results", [])
        state.setdefault("entities", [])
        state.setdefault("used_search_db", "graph_rag_error")
        return state

    # 1) Rewrite / Route 매핑
    rewrite = rag_state.get("rewrite") or {}
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = rag_state.get("rewrite_json_min", "")
    state["rewrite_input_text"] = rag_state.get("rewrite_input_text", question)
    state["route"] = rag_state.get("route") or {}

    normalized_q = rewrite.get("normalized_question") or question
    state["rewritten_query"] = normalized_q

    # 2) Retrieval Plan / Embeddings / Contexts
    state["retrieval_params"] = rag_state.get("retrieval_params") or {}
    state["retrieval_plan"] = rag_state.get("retrieval_plan") or []
    state["embeddings"] = rag_state.get("embeddings") or {}

    contexts: List[Dict[str, Any]] = rag_state.get("contexts") or []
    state["contexts"] = contexts
    state["contexts_count"] = int(rag_state.get("contexts_count", len(contexts)))

    # 🔍 DEBUG: RAG 파이프라인에서 받은 contexts 구조 확인
    import json
    print(f"\n{'='*60}")
    print(f"[DEBUG RAG Contexts] contexts 개수: {len(contexts)}")
    if contexts and len(contexts) > 0:
        first_context = contexts[0]
        print(f"[DEBUG RAG Contexts] 첫 번째 context 타입: {type(first_context)}")
        print(f"[DEBUG RAG Contexts] 첫 번째 context keys: {list(first_context.keys()) if isinstance(first_context, dict) else 'Not a dict'}")
        
        try:
            if isinstance(first_context, dict):
                print(f"[DEBUG RAG Contexts] 첫 번째 context 전체 구조:")
                print(json.dumps(first_context, indent=2, default=str, ensure_ascii=False))
            else:
                print(f"[DEBUG RAG Contexts] 첫 번째 context (직렬화 불가): {first_context}")
        except Exception as json_err:
            print(f"[DEBUG RAG Contexts] JSON 직렬화 실패: {json_err}")
            print(f"[DEBUG RAG Contexts] 첫 번째 context (raw): {first_context}")
        
        # metadata 구조 상세 확인
        if isinstance(first_context, dict):
            metadata = first_context.get("metadata", {})
            print(f"[DEBUG RAG Contexts] metadata 타입: {type(metadata)}")
            print(f"[DEBUG RAG Contexts] metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
            if isinstance(metadata, dict):
                print(f"[DEBUG RAG Contexts] metadata 내용:")
                print(json.dumps(metadata, indent=2, default=str, ensure_ascii=False))
                
                # title 관련 필드 확인
                title_fields = [k for k in metadata.keys() if 'title' in k.lower() or 'Title' in k]
                if title_fields:
                    print(f"[DEBUG RAG Contexts] metadata에 title 관련 필드: {title_fields}")
                    for field in title_fields:
                        print(f"[DEBUG RAG Contexts]   {field}: {metadata.get(field)}")
                else:
                    print(f"[DEBUG RAG Contexts] ⚠️ metadata에 title 관련 필드 없음")
        
        # content/text 필드 확인
        if isinstance(first_context, dict):
            content_fields = [k for k in first_context.keys() if k in ['content', 'text', 'chunk', 'document']]
            if content_fields:
                print(f"[DEBUG RAG Contexts] content 관련 필드: {content_fields}")
            else:
                print(f"[DEBUG RAG Contexts] ⚠️ content/text 필드를 찾을 수 없음")
    print(f"{'='*60}\n")

    # 3) Cross-Encoder 기반 rerank (retrieval 단계에서 수행)
    try:
        reranked = rerank_with_cross_encoder(
            query=normalized_q,
            documents=contexts,
            top_k=min(20, len(contexts)) or 20,
        )
        
        # 🔍 DEBUG: rerank 후 결과 구조 확인
        print(f"\n{'='*60}")
        print(f"[DEBUG RAG Reranked] reranked 개수: {len(reranked)}")
        if reranked and len(reranked) > 0:
            first_reranked = reranked[0]
            print(f"[DEBUG RAG Reranked] 첫 번째 reranked 타입: {type(first_reranked)}")
            print(f"[DEBUG RAG Reranked] 첫 번째 reranked keys: {list(first_reranked.keys()) if isinstance(first_reranked, dict) else 'Not a dict'}")
            
            try:
                if isinstance(first_reranked, dict):
                    print(f"[DEBUG RAG Reranked] 첫 번째 reranked 전체 구조:")
                    print(json.dumps(first_reranked, indent=2, default=str, ensure_ascii=False))
            except Exception as json_err:
                print(f"[DEBUG RAG Reranked] JSON 직렬화 실패: {json_err}")
        print(f"{'='*60}\n")
        
        state["retrieval_results"] = reranked
        state["retrieval_score"] = (
            reranked[0].get("rerank_score", 0.0) if reranked else 0.0
        )
    except Exception as e:
        print(f"[RETRIEIVER_BIO NODE] rerank 실패, 원본 contexts 사용: {e}")
        state["retrieval_results"] = contexts
        state["retrieval_score"] = 0.0

    state["used_search_db"] = "graph_rag"

    # 4) 엔티티 리스트 매핑
    entities = _extract_entities_from_rewrite(rewrite)
    state["entities"] = entities

    _log_contexts_brief(contexts, "RETRIEIVER_BIO NODE")
    print("=" * 60 + "\n")

    return state


# ============================================
# PROTOCOL_Q 리트리버 노드
# ============================================

def retriever_protocol_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q 용 RAG 리트리버 노드.
    BIO_Q 와 동일한 RAG 파이프라인을 사용하되, case_type 이 PROTOCOL_Q 인 상태에서 호출된다.
    """

    print("\n" + "=" * 60)
    print("[RETRIEIVER_PROTOCOL NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print("=" * 60 + "\n")

    question = (state.get("question") or "").strip()

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

    # PROTOCOL 도 retrieval 시점에 Cross-Encoder rerank 적용
    try:
        reranked = rerank_with_cross_encoder(
            query=normalized_q,
            documents=contexts,
            top_k=min(20, len(contexts)) or 20,
        )
        state["retrieval_results"] = reranked
        state["retrieval_score"] = (
            reranked[0].get("rerank_score", 0.0) if reranked else 0.0
        )
    except Exception as e:
        print(f"[RETRIEIVER_PROTOCOL NODE] rerank 실패, 원본 contexts 사용: {e}")
        state["retrieval_results"] = contexts
        state["retrieval_score"] = 0.0

    state["used_search_db"] = "graph_rag"

    # 엔티티 리스트 매핑
    entities = _extract_entities_from_rewrite(rewrite)
    state["entities"] = entities

    _log_contexts_brief(contexts, "[RETRIEIVER_PROTOCOL NODE]")
    print("=" * 60 + "\n")

    return state
