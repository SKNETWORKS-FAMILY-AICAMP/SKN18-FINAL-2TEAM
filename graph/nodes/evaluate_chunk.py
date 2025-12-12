"""
evaluate_chunk.py
--------------------
검색된 문서 청크들의 관련성을 평가하는 노드
질문 타입에 따라 다른 LLM 사용:
- BIO_Q: OpenAI GPT-4o-mini (외부 API)
- PROTOCOL_Q: sllm (로컬 모델, 보안)
"""

from typing import Dict, Any, List
from graph.nodes.call_llm import gpt4o_mini, sllm


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

위 문서들이 질문에 답변하기에 충분한 정보를 포함하고 있는지 평가하세요.

다음 형식으로만 답변하세요:
관련성: [높음/낮음]
점수: [0.0-1.0 사이의 숫자]
이유: [간단한 설명]
"""


def _parse_evaluation_result(result: str) -> tuple[bool, float]:
    """
    평가 결과 파싱
    
    Args:
        result: LLM 응답
        
    Returns:
        (is_relevant, relevance_score)
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
    
    return is_relevant, relevance_score


# ============================================
# 🔹 BIO_Q용 평가 노드 (OpenAI GPT-4o-mini)
# ============================================

def bio_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q용 청크 평가 노드 (OpenAI GPT-4o-mini 사용)
    
    Input:
        - state["question"]: 사용자 질문
        - state["retrieval_results"]: 검색 결과
        - state["reranked_results"]: 재순위 결과 (선택적)
    
    Output:
        - state["chunk_is_relevant"]: 청크 관련성 여부
        - state["chunk_relevance_score"]: 관련성 점수
        - state["selected_chunks"]: 선택된 청크들
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[OPEN_EVALUATE_CHUNK NODE] 시작 (GPT-4o-mini)")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"{'='*60}\n")
    
    question = state.get("question", "").strip()
    retrieval_results = state.get("retrieval_results", [])
    reranked_results = state.get("reranked_results", retrieval_results)
    
    # 검색 결과가 없는 경우
    if not question or not retrieval_results:
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
    
    # 평가 프롬프트 생성
    prompt = _build_evaluation_prompt(question, context)

    try:
        # GPT-4o-mini를 사용하여 관련성 평가
        print(f"[OpenEvaluate] GPT-4o-mini로 평가 중...")
        result = gpt4o_mini(prompt)
        
        # 결과 파싱
        is_relevant, relevance_score = _parse_evaluation_result(result)
        
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
        
        print(f"[OpenEvaluate] 완료 - 관련성: {is_relevant}, 점수: {relevance_score}, 청크: {len(selected_chunks)}개")
        
    except Exception as e:
        print(f"[OpenEvaluate] 오류 발생: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
    
    # 노드 종료 로그
    print(f"\n[OPEN_EVALUATE_CHUNK NODE] 종료")
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
        - state["retrieval_results"]: 검색 결과
        - state["reranked_results"]: 재순위 결과 (선택적)
    
    Output:
        - state["chunk_is_relevant"]: 청크 관련성 여부
        - state["chunk_relevance_score"]: 관련성 점수
        - state["selected_chunks"]: 선택된 청크들
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[SLLM_EVALUATE_CHUNK NODE] 시작 (로컬 sllm)")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"{'='*60}\n")
    
    question = state.get("question", "").strip()
    retrieval_results = state.get("retrieval_results", [])
    reranked_results = state.get("reranked_results", retrieval_results)
    
    # 검색 결과가 없는 경우
    if not question or not retrieval_results:
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
    
    # 평가 프롬프트 생성
    prompt = _build_evaluation_prompt(question, context)

    try:
        # sllm (로컬 모델)을 사용하여 관련성 평가
        print(f"[SLLMEvaluate] 로컬 sllm으로 평가 중 (보안)...")
        result = sllm(prompt)
        
        # 결과 파싱
        is_relevant, relevance_score = _parse_evaluation_result(result)
        
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
        
        print(f"[SLLMEvaluate] 완료 - 관련성: {is_relevant}, 점수: {relevance_score}, 청크: {len(selected_chunks)}개")
        
    except Exception as e:
        print(f"[SLLMEvaluate] 오류 발생: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
    
    # 노드 종료 로그
    print(f"\n[SLLM_EVALUATE_CHUNK NODE] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant', False)}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score', 0.0)}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    return state
