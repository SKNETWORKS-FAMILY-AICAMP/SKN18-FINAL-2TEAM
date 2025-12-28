"""
evaluate_chunk.py
--------------------
검색된 문서(chunk)들이 질문에 얼마나 관련 있는지 LLM으로 평가하는 노드들.

- BIO_Q: OpenAI 기반 LLM 사용 (evaluate_chunk_bio_node_llm)
- PROTOCOL_Q: sLLM 또는 별도 LLM 사용 (evaluate_chunk_protocol_node_llm)

변경 사항:
- 엔티티 기반 Coarse Filter(Stage 1)는 참고용만 사용하고,
  엔티티가 안 보이더라도 항상 Stage 2(정밀 평가)를 수행한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re

from graph.llm_config import (
    evaluate_chunk_bio_node_llm,
    evaluate_chunk_protocol_node_llm,
)


# ============================================
# Helper: Coarse Filter 프롬프트
# ============================================

def _coarse_filter_prompt(question: str, entities: List[str]) -> str:
    """
    Stage 1: Coarse Filter
    - 특정 엔티티가 문서에 등장하는지 빠르게 스크리닝하는 용도 (참고용).
    """
    entity_list = " / ".join(entities[:10]) if entities else "the entities in the question"

    return f"""Quick screening: Does ANY of the following chunks mention at least one of these entities?

Entities to check: {entity_list}

Question for context: {question}

Instructions:
- Answer "YES" if ANY chunk mentions at least one entity
- Answer "NO" if NO chunks mention any entities

Response format:
Answer: [YES/NO]
"""


def _build_evaluation_prompt(
    question: str,
    context: str,
    entities: List[str] | None = None,
) -> str:
    """
    Stage 2: Mechanistic relevance / 전반적인 관련성 평가용 프롬프트 생성.
    """
    evaluation_question = question
    if entities:
        entity_mentions = " / ".join(entities[:10])
        evaluation_question = (
            f"Does this chunk describe mechanisms or interactions involving: {entity_mentions}?"
        )

    return f"""Evaluate whether the following documents are relevant to answering the user's question.

Original Question: {question}

Evaluation Focus: {evaluation_question}

Retrieved Documents:
---
{context}
---

Respond with:
- Relevance: [High/Low]
- Score: [0.0-1.0]
- Reason: brief explanation
"""


def _parse_evaluation_result(result: str) -> Tuple[bool, float, str]:
    """
    LLM 응답 텍스트에서 (is_relevant, score, reason)을 추출한다.
    포맷이 조금 달라도 최대한 유연하게 파싱한다.
    """
    text = result or ""
    lower = text.lower()

    # 관련성 플래그
    is_relevant = "high" in lower or "yes" in lower or "relevance: high" in lower

    # 점수 파싱 시도
    score = 0.8 if is_relevant else 0.3
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", lower)
    if m:
        try:
            val = float(m.group(1))
            if val > 1.0:
                val = val / 100.0
            score = max(0.0, min(1.0, val))
        except Exception:
            pass

    reason = text.strip()
    if len(reason) > 200:
        reason = reason[:200] + "..."

    return is_relevant, score, reason


# ============================================
# BIO_Q 평가 노드
# ============================================

def bio_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q용 chunk 평가 노드.

    Inputs:
      - state["question"]
      - state["rewritten_query"]
      - state["retrieval_results"]
      - state["retrieval_results"] 또는 state["reranked_results"]

    Outputs:
      - state["chunk_is_relevant"]
      - state["chunk_relevance_score"]
      - state["selected_chunks"]
    """

    llm_model_name = evaluate_chunk_bio_node_llm.__name__

    print("\n" + "=" * 60)
    print("[BIO_EVALUATE_CHUNK NODE] 시작")
    print(f"  LLM 모델: {llm_model_name}")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"  reranked_results: {len(state.get('reranked_results', []))}개")
    print("=" * 60 + "\n")

    search_query = (state.get("rewritten_query") or state.get("question") or "").strip()
    question = (state.get("question") or "").strip()
    retrieval_results = state.get("retrieval_results") or []
    reranked_results = state.get("reranked_results") or retrieval_results

    if not search_query or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print("[BioEvaluate] 검색 결과 없음 → 웹 검색으로 이동")
        return state

    entities = state.get("entities") or []

    # Stage 1: Coarse Filter (참고용만, 더 이상 early-return 하지 않음)
    if entities:
        print("[BioEvaluate] Stage 1: Coarse Filter (엔티티 등장 여부 체크)...")
        context_preview = "\n\n".join(
            [
                f"[문서 {i}] "
                f"{(res.get('content', str(res)) if isinstance(res, dict) else str(res))[:200]}..."
                for i, res in enumerate(reranked_results[:5], 1)
            ]
        )
        coarse_prompt = _coarse_filter_prompt(search_query, entities)
        coarse_prompt += f"\n\nChunks to check:\n---\n{context_preview}\n---"

        try:
            coarse_result = evaluate_chunk_bio_node_llm(coarse_prompt)
            print(f"[BioEvaluate] Coarse Filter 결과: {coarse_result[:120]}")
            if "no" in coarse_result.lower():
                print("[BioEvaluate] Stage 1: 엔티티 미등장 → 그래도 Stage 2로 계속 진행")
            else:
                print("[BioEvaluate] Stage 1: 엔티티 등장/부분 관련 → Stage 2로 진행")
        except Exception as e:
            print(f"[BioEvaluate] Coarse Filter 예외 (계속 진행): {e}")

    # Stage 2: Mechanistic Relevance / 최종 관련성 평가
    print("[BioEvaluate] Stage 2: Mechanistic Relevance 평가...")

    context_parts: List[str] = []
    for i, res in enumerate(reranked_results[:5], 1):
        if isinstance(res, dict):
            content = res.get("content", str(res))
        else:
            content = str(res)
        context_parts.append(f"[문서 {i}] {content[:500]}...")

    context = "\n\n".join(context_parts)
    prompt = _build_evaluation_prompt(question or search_query, context, entities)

    try:
        print(f"[BioEvaluate] {llm_model_name} 모델로 평가 호출...")
        result = evaluate_chunk_bio_node_llm(prompt)
        is_relevant, relevance_score, reason = _parse_evaluation_result(result)

        print("\n[BioEvaluate] LLM 평가 결과:")
        print(f"  모델: {llm_model_name}")
        print(f"  관련성: {'높음' if is_relevant else '낮음'}")
        print(f"  점수: {relevance_score}")
        print(f"  이유: {reason}\n")

        selected_chunks: List[str] = []
        if is_relevant:
            for res in reranked_results[:3]:
                if isinstance(res, dict):
                    content = res.get("content", str(res))
                else:
                    content = str(res)
                selected_chunks.append(content)

        state["chunk_is_relevant"] = is_relevant
        state["chunk_relevance_score"] = relevance_score
        state["selected_chunks"] = selected_chunks

    except Exception as e:
        print(f"[BioEvaluate] Stage 2 평가 중 예외: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []

    print("\n[BIO_EVALUATE_CHUNK NODE] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant')}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score')}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print("=" * 60 + "\n")

    return state


# ============================================
# PROTOCOL_Q 평가 노드
# ============================================

def protocol_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q용 chunk 평가 노드.
    BIO_Q 버전과 동일한 구조지만 evaluate_chunk_protocol_node_llm을 사용한다.
    """

    llm_model_name = evaluate_chunk_protocol_node_llm.__name__

    print("\n" + "=" * 60)
    print("[PROTOCOL_EVALUATE_CHUNK NODE] 시작")
    print(f"  LLM 모델: {llm_model_name}")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"  reranked_results: {len(state.get('reranked_results', []))}개")
    print("=" * 60 + "\n")

    search_query = (state.get("rewritten_query") or state.get("question") or "").strip()
    question = (state.get("question") or "").strip()
    retrieval_results = state.get("retrieval_results") or []
    reranked_results = state.get("reranked_results") or retrieval_results

    if not search_query or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print("[ProtocolEvaluate] 검색 결과 없음 → 웹 검색으로 이동")
        return state

    entities = state.get("entities") or []

    # Stage 1: Coarse Filter (참고용)
    if entities:
        print("[ProtocolEvaluate] Stage 1: Coarse Filter (엔티티 등장 여부 체크)...")
        context_preview = "\n\n".join(
            [
                f"[문서 {i}] "
                f"{(res.get('content', str(res)) if isinstance(res, dict) else str(res))[:200]}..."
                for i, res in enumerate(reranked_results[:5], 1)
            ]
        )
        coarse_prompt = _coarse_filter_prompt(search_query, entities)
        coarse_prompt += f"\n\nChunks to check:\n---\n{context_preview}\n---"

        try:
            coarse_result = evaluate_chunk_protocol_node_llm(coarse_prompt)
            print(f"[ProtocolEvaluate] Coarse Filter 결과: {coarse_result[:120]}")
            if "no" in coarse_result.lower():
                print("[ProtocolEvaluate] Stage 1: 엔티티 미등장 → 그래도 Stage 2로 계속 진행")
            else:
                print("[ProtocolEvaluate] Stage 1: 엔티티 등장/부분 관련 → Stage 2로 진행")
        except Exception as e:
            print(f"[ProtocolEvaluate] Coarse Filter 예외 (계속 진행): {e}")

    # Stage 2: Mechanistic relevance / 최종 평가
    print("[ProtocolEvaluate] Stage 2: Mechanistic Relevance 평가...")

    context_parts: List[str] = []
    for i, res in enumerate(reranked_results[:5], 1):
        if isinstance(res, dict):
            content = res.get("content", str(res))
        else:
            content = str(res)
        context_parts.append(f"[문서 {i}] {content[:500]}...")

    context = "\n\n".join(context_parts)
    prompt = _build_evaluation_prompt(question or search_query, context, entities)

    try:
        print(f"[ProtocolEvaluate] {llm_model_name} 모델로 평가 호출...")
        result = evaluate_chunk_protocol_node_llm(prompt)
        is_relevant, relevance_score, reason = _parse_evaluation_result(result)

        print("\n[ProtocolEvaluate] LLM 평가 결과:")
        print(f"  모델: {llm_model_name}")
        print(f"  관련성: {'높음' if is_relevant else '낮음'}")
        print(f"  점수: {relevance_score}")
        print(f"  이유: {reason}\n")

        selected_chunks: List[str] = []
        if is_relevant:
            for res in reranked_results[:3]:
                if isinstance(res, dict):
                    content = res.get("content", str(res))
                else:
                    content = str(res)
                selected_chunks.append(content)

        state["chunk_is_relevant"] = is_relevant
        state["chunk_relevance_score"] = relevance_score
        state["selected_chunks"] = selected_chunks

    except Exception as e:
        print(f"[ProtocolEvaluate] Stage 2 평가 중 예외: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []

    print("\n[PROTOCOL_EVALUATE_CHUNK NODE] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant')}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score')}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print("=" * 60 + "\n")

    return state

