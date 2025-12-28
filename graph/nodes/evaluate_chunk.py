"""
evaluate_chunk.py
--------------------
검색된 문서 청크들의 관련성을 평가하는 노드
질문 타입에 따라 다른 LLM 사용:
- BIO_Q: OpenAI GPT-4o-mini (외부 API)
- PROTOCOL_Q: sllm (로컬 모델, 보안)
"""

from typing import Dict, Any, List
from graph.llm_config import (
    evaluate_chunk_bio_node_llm,
    evaluate_chunk_protocol_node_llm,
    get_model_name
)


# ============================================
# Helper: 2단계 평가 (Coarse Filter → Mechanistic Relevance)
# ============================================

def _coarse_filter_prompt(question: str, entities: List[str]) -> str:
    """
    ✅ 방법 2 - Stage 1: Coarse Filter
    엔티티 등장 여부만 빠르게 체크

    Args:
        question: 사용자 질문
        entities: 추출된 엔티티 리스트

    Returns:
        Coarse filter 프롬프트
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


def _build_evaluation_prompt(question: str, context: str, entities: List[str] = None) -> str:
    """
    평가 프롬프트 생성 (개선된 템플릿)

    ✅ 방법 1: Indirect mechanistic relevance 명시
    ✅ 방법 3: 질문을 mini 친화적으로 재구성

    Args:
        question: 사용자 질문
        context: 검색된 문서들
        entities: 추출된 엔티티 리스트 (optional)

    Returns:
        평가 프롬프트
    """

    # 엔티티 기반 mini 친화적 질문 재구성
    evaluation_question = question
    if entities and len(entities) > 0:
        entity_mentions = " / ".join(entities[:10])  # 최대 10개까지만
        evaluation_question = f"Does this chunk describe mechanisms or interactions involving: {entity_mentions}?"

    return f"""Evaluate whether the following documents are relevant to answering the user's question.

**CRITICAL INSTRUCTION - Consider indirect mechanistic relevance:**
A chunk is relevant if it provides part of a causal chain needed to answer the question, even if the question entities are not directly linked in one sentence.

For example:
- If the question asks "How does A affect C?", a chunk describing "A → B" or "B → C" is RELEVANT.
- If the chunk mentions regulatory pathways, protein interactions, or upstream/downstream mechanisms related to the entities, it is RELEVANT.

Original Question: {question}

Evaluation Focus: {evaluation_question}

Retrieved Documents:
---
{context}
---

Evaluate whether these documents can provide information to answer the question.

**Response Format:**
Relevance: [High/Low]
Score: [0.0-1.0]
Reason: [Brief explanation]
"""


def _parse_evaluation_result(result: str) -> tuple[bool, float, str]:
    """
    평가 결과 파싱

    Args:
        result: LLM 응답

    Returns:
        (is_relevant, relevance_score, reason)
    """
    # 관련성 판단
    if "높음" in result or "high" in result.lower():
        is_relevant = True
        relevance_score = 0.8  # 기본값
    else:
        is_relevant = False
        relevance_score = 0.3  # 기본값

    # 점수 추출 시도
    if "점수:" in result or "score:" in result.lower():
        try:
            if "점수:" in result:
                score_part = result.split("점수:")[1].split("\n")[0].strip()
            else:
                score_part = result.split("score:")[1].split("\n")[0].strip()

            # 숫자 추출
            import re
            numbers = re.findall(r'\d+\.?\d*', score_part)
            if numbers:
                relevance_score = round(float(numbers[0]), 2)
                # 0-1 범위로 정규화
                if relevance_score > 1.0:
                    relevance_score = relevance_score / 100.0
        except:
            pass

    # 이유 추출
    reason = ""
    if "이유:" in result:
        reason = result.split("이유:")[1].strip()
    elif "reason:" in result.lower():
        reason_lower = result.lower()
        idx = reason_lower.find("reason:")
        reason = result[idx + 7:].strip()

    # 이유가 너무 길면 첫 200자만
    if len(reason) > 200:
        reason = reason[:200] + "..."

    return is_relevant, relevance_score, reason


# ============================================
# 🔹 BIO_Q용 평가 노드 (OpenAI GPT-4o-mini)
# ============================================

def bio_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q용 청크 평가 노드 (OpenAI GPT-4o-mini 사용)
    
    Input:
        - state["question"]: 사용자 질문
        - state["rewritten_query"]: 실제 검색에 사용된 질문 (우선 사용)
        - state["retrieval_results"]: 검색 결과
        - state["reranked_results"]: 재순위 결과 (선택적)
    
    Output:
        - state["chunk_is_relevant"]: 청크 관련성 여부
        - state["chunk_relevance_score"]: 관련성 점수
        - state["selected_chunks"]: 선택된 청크들
    """
    
    # 사용 중인 LLM 모델 확인
    from graph.llm_config import evaluate_chunk_bio_node_llm
    llm_model_name = evaluate_chunk_bio_node_llm.__name__  # gpt4_1_nano, gpt4o_mini 등

    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[BIO_EVALUATE_CHUNK NODE] 시작")
    print(f"  LLM 모델: {llm_model_name}")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"  reranked_results: {len(state.get('reranked_results', []))}개")
    print(f"{'='*60}\n")
    
    # 실제 검색에 사용된 질문 사용 (rewritten_query 우선, 없으면 question)
    search_query = state.get("rewritten_query", state.get("question", "")).strip()
    question = state.get("question", "").strip()
    retrieval_results = state.get("retrieval_results", [])
    reranked_results = state.get("reranked_results", retrieval_results)
    
    # 검색 결과가 없는 경우
    if not search_query or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print(f"[OpenEvaluate] 검색 결과 없음, 웹 검색으로 이동")
        return state

    # 엔티티 정보 가져오기 (state에서)
    entities = state.get("entities", [])

    # ✅ 방법 2: 2단계 평가 - Stage 1 (Coarse Filter)
    if entities:
        print(f"[BioEvaluate] Stage 1: Coarse Filter (엔티티 등장 여부 체크)...")
        context_preview = "\n\n".join([
            f"[문서 {i}] {(result.get('content', str(result)) if isinstance(result, dict) else str(result))[:200]}..."
            for i, result in enumerate(reranked_results[:5], 1)
        ])

        coarse_prompt = _coarse_filter_prompt(search_query, entities)
        coarse_prompt += f"\n\nChunks to check:\n---\n{context_preview}\n---"

        try:
            coarse_result = evaluate_chunk_bio_node_llm(coarse_prompt)
            print(f"[BioEvaluate] Coarse Filter 결과: {coarse_result[:100]}")

            # "NO" 또는 "없음"이면 조기 종료
            if "NO" in coarse_result.upper() or "없음" in coarse_result or "none" in coarse_result.lower():
                print(f"[BioEvaluate] Stage 1 Failed: 엔티티 미등장, 웹 검색으로 이동")
                state["chunk_is_relevant"] = False
                state["chunk_relevance_score"] = 0.0
                state["selected_chunks"] = []
                return state
        except Exception as e:
            print(f"[BioEvaluate] Coarse Filter 오류 (계속 진행): {e}")

    # ✅ 방법 2: Stage 2 (Mechanistic Relevance) - 통과한 경우만
    print(f"[BioEvaluate] Stage 2: Mechanistic Relevance 평가...")

    # 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(reranked_results[:5], 1):  # 최대 5개만 평가
        if isinstance(result, dict):
            content = result.get("content", str(result))
        else:
            content = str(result)
        context_parts.append(f"[문서 {i}] {content[:500]}...")

    context = "\n\n".join(context_parts)

    # ✅ 평가 프롬프트 생성 (엔티티 정보 포함)
    prompt = _build_evaluation_prompt(search_query, context, entities)

    try:
        # 사용 모델 확인
        model_name = get_model_name(evaluate_chunk_bio_node_llm)
        print(f"[OpenEvaluate] 사용 모델: {model_name}")
        
        # LLM을 사용하여 관련성 평가
        result = evaluate_chunk_bio_node_llm(prompt)

        # 결과 파싱
        is_relevant, relevance_score, reason = _parse_evaluation_result(result)

        # LLM 판단 근거 로그 출력
        print(f"\n[BioEvaluate] LLM 평가 결과:")
        print(f"  모델: {llm_model_name}")
        print(f"  관련성: {'높음 ✅' if is_relevant else '낮음 ❌'}")
        print(f"  점수: {relevance_score}")
        print(f"  이유: {reason}\n")

        # 선택된 청크 생성 (관련성이 높은 경우에만)
        selected_chunks = []
        if is_relevant:
            for i, result_item in enumerate(reranked_results[:3], 1):  # 최대 3개
                if isinstance(result_item, dict):
                    content = result_item.get("content", str(result_item))
                else:
                    content = str(result_item)
                selected_chunks.append(content)

        # 결과를 state에 저장
        state["chunk_is_relevant"] = is_relevant
        state["chunk_relevance_score"] = relevance_score
        state["selected_chunks"] = selected_chunks

        print(f"[BioEvaluate] 완료 - 관련성: {is_relevant}, 점수: {relevance_score}, 청크: {len(selected_chunks)}개")
        
    except Exception as e:
        print(f"[OpenEvaluate] 오류 발생: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
    
    # 노드 종료 로그
    print(f"\n[BIO_EVALUATE_CHUNK NODE] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant', False)}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score', 0.0)}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    return state


# ============================================
# 🔹 PROTOCOL_Q용 평가 노드 (sllm - 로컬 모델)
# ============================================

def protocol_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q용 청크 평가 노드 (sllm 로컬 모델 사용 - 보안)
    
    Input:
        - state["question"]: 사용자 질문
        - state["rewritten_query"]: 실제 검색에 사용된 질문 (우선 사용)
        - state["retrieval_results"]: 검색 결과
        - state["reranked_results"]: 재순위 결과 (선택적)
    
    Output:
        - state["chunk_is_relevant"]: 청크 관련성 여부
        - state["chunk_relevance_score"]: 관련성 점수
        - state["selected_chunks"]: 선택된 청크들
    """
    
    # 사용 중인 LLM 모델 확인
    from graph.llm_config import evaluate_chunk_protocol_node_llm
    llm_model_name = evaluate_chunk_protocol_node_llm.__name__  # gpt4_1_nano, sllm 등

    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[PROTOCOL_EVALUATE_CHUNK NODE] 시작")
    print(f"  LLM 모델: {llm_model_name}")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"  reranked_results: {len(state.get('reranked_results', []))}개")
    print(f"{'='*60}\n")
    
    # 실제 검색에 사용된 질문 사용 (rewritten_query 우선, 없으면 question)
    search_query = state.get("rewritten_query", state.get("question", "")).strip()
    question = state.get("question", "").strip()
    retrieval_results = state.get("retrieval_results", [])
    reranked_results = state.get("reranked_results", retrieval_results)
    
    # 검색 결과가 없는 경우
    if not search_query or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print(f"[SLLMEvaluate] 검색 결과 없음, 웹 검색으로 이동")
        return state

    # 엔티티 정보 가져오기 (state에서)
    entities = state.get("entities", [])

    # ✅ 방법 2: 2단계 평가 - Stage 1 (Coarse Filter) - Protocol도 동일 적용
    if entities:
        print(f"[ProtocolEvaluate] Stage 1: Coarse Filter (엔티티 등장 여부 체크)...")
        context_preview = "\n\n".join([
            f"[문서 {i}] {(result.get('content', str(result)) if isinstance(result, dict) else str(result))[:200]}..."
            for i, result in enumerate(reranked_results[:5], 1)
        ])

        coarse_prompt = _coarse_filter_prompt(search_query, entities)
        coarse_prompt += f"\n\nChunks to check:\n---\n{context_preview}\n---"

        try:
            coarse_result = evaluate_chunk_protocol_node_llm(coarse_prompt)
            print(f"[ProtocolEvaluate] Coarse Filter 결과: {coarse_result[:100]}")

            # "NO" 또는 "없음"이면 조기 종료
            if "NO" in coarse_result.upper() or "없음" in coarse_result or "none" in coarse_result.lower():
                print(f"[ProtocolEvaluate] Stage 1 Failed: 엔티티 미등장, 웹 검색으로 이동")
                state["chunk_is_relevant"] = False
                state["chunk_relevance_score"] = 0.0
                state["selected_chunks"] = []
                return state
        except Exception as e:
            print(f"[ProtocolEvaluate] Coarse Filter 오류 (계속 진행): {e}")

    # ✅ 방법 2: Stage 2 (Mechanistic Relevance) - 통과한 경우만
    print(f"[ProtocolEvaluate] Stage 2: Mechanistic Relevance 평가...")

    # 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(reranked_results[:5], 1):  # 최대 5개만 평가
        if isinstance(result, dict):
            content = result.get("content", str(result))
        else:
            content = str(result)
        context_parts.append(f"[문서 {i}] {content[:500]}...")

    context = "\n\n".join(context_parts)

    # ✅ 평가 프롬프트 생성 (엔티티 정보 포함)
    prompt = _build_evaluation_prompt(search_query, context, entities)

    try:
        # 사용 모델 확인
        model_name = get_model_name(evaluate_chunk_protocol_node_llm)
        print(f"[SLLMEvaluate] 사용 모델: {model_name}")
        
        # LLM을 사용하여 관련성 평가
        result = evaluate_chunk_protocol_node_llm(prompt)

        # 결과 파싱
        is_relevant, relevance_score, reason = _parse_evaluation_result(result)

        # LLM 판단 근거 로그 출력
        print(f"\n[ProtocolEvaluate] LLM 평가 결과:")
        print(f"  모델: {llm_model_name}")
        print(f"  관련성: {'높음 ✅' if is_relevant else '낮음 ❌'}")
        print(f"  점수: {relevance_score}")
        print(f"  이유: {reason}\n")

        # 선택된 청크 생성 (관련성이 높은 경우에만)
        selected_chunks = []
        if is_relevant:
            for i, result_item in enumerate(reranked_results[:3], 1):  # 최대 3개
                if isinstance(result_item, dict):
                    content = result_item.get("content", str(result_item))
                else:
                    content = str(result_item)
                selected_chunks.append(content)

        # 결과를 state에 저장
        state["chunk_is_relevant"] = is_relevant
        state["chunk_relevance_score"] = relevance_score
        state["selected_chunks"] = selected_chunks

        print(f"[ProtocolEvaluate] 완료 - 관련성: {is_relevant}, 점수: {relevance_score}, 청크: {len(selected_chunks)}개")
        
    except Exception as e:
        print(f"[SLLMEvaluate] 오류 발생: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
    
    # 노드 종료 로그
    print(f"\n[PROTOCOL_EVALUATE_CHUNK NODE] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant', False)}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score', 0.0)}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    return state
