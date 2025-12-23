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
    evaluate_chunk_protocol_node_llm
)


def _build_evaluation_prompt(question: str, context: str) -> str:
    """
    평가 프롬프트 생성 (공통 템플릿)
    
    Args:
        question: 사용자 질문
        context: 검색된 문서들
        
    Returns:
        평가 프롬프트
    """
    return f"""다음 검색된 문서들이 사용자 질문에 답변하기에 충분히 관련성이 있는지 평가하세요.

질문: {question}

검색된 문서들:
---
{context}
---

위 문서들이 질문에 적합한 답변을 제공할 수 있는 자료인지 평가하세요.

다음 형식으로만 답변하세요:
관련성: [높음/낮음]
점수: [0.0-1.0 사이의 숫자]
이유: [간단한 설명]
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

    # 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(reranked_results[:5], 1):  # 최대 5개만 평가
        if isinstance(result, dict):
            content = result.get("content", str(result))
        else:
            content = str(result)
        context_parts.append(f"[문서 {i}] {content[:500]}...")
    
    context = "\n\n".join(context_parts)
    
    # 평가 프롬프트 생성 (실제 검색에 사용된 질문 사용)
    prompt = _build_evaluation_prompt(search_query, context)

    try:
        # LLM을 사용하여 관련성 평가
        print(f"[BioEvaluate] {llm_model_name} 모델로 평가 중...")
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

    # 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(reranked_results[:5], 1):  # 최대 5개만 평가
        if isinstance(result, dict):
            content = result.get("content", str(result))
        else:
            content = str(result)
        context_parts.append(f"[문서 {i}] {content[:500]}...")
    
    context = "\n\n".join(context_parts)
    
    # 평가 프롬프트 생성 (실제 검색에 사용된 질문 사용)
    prompt = _build_evaluation_prompt(search_query, context)

    try:
        # LLM을 사용하여 관련성 평가
        print(f"[ProtocolEvaluate] {llm_model_name} 모델로 평가 중...")
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
