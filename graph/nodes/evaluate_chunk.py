"""
evaluate_chunk.py
--------------------
검색된 문서 청크들의 관련성을 평가하는 노드
BioRAGState 구조에 맞게 구현
"""

from typing import Dict, Any
from graph.nodes.call_llm import gpt4o_mini


def evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    청크 평가 노드
    검색된 문서 청크들의 관련성을 평가하여 웹 검색 필요 여부 결정
    
    Input:
        - state["question"]: 사용자 질문
        - state["retrieval_results"]: 검색 결과
        - state["reranked_results"]: 재순위 결과 (선택적)
    
    Output:
        - state["chunk_is_relevant"]: 청크 관련성 여부
        - state["chunk_relevance_score"]: 관련성 점수
        - state["selected_chunks"]: 선택된 청크들
    """
    
    question = state.get("question", "").strip()
    retrieval_results = state.get("retrieval_results", [])
    reranked_results = state.get("reranked_results", retrieval_results)  # rerank 결과가 없으면 원본 사용
    
    # 시작 로그
    retrieved_count = len(retrieval_results)
    print(f"[EvaluateChunk] 시작 - 총 {retrieved_count}개 청크, 질문: \"{question[:50]}...\"")
    
    # 검색 결과가 없는 경우
    if not question or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print(f"[EvaluateChunk] 완료 - 검색 결과 없음, 웹 검색으로 이동")
        return state

    # 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(reranked_results[:5], 1):  # 최대 5개만 평가
        if isinstance(result, dict):
            content = result.get("content", str(result))
        else:
            content = str(result)
        context_parts.append(f"[문서 {i}] {content[:500]}...")  # 각 문서당 최대 500자
    
    context = "\n\n".join(context_parts)
    
    # LLM을 사용한 관련성 평가
    prompt = f"""다음 검색된 문서들이 사용자 질문에 답변하기에 충분히 관련성이 있는지 평가하세요.

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

    try:
        # GPT-4o-mini를 사용하여 관련성 평가
        result = gpt4o_mini(prompt)
        
        # 관련성 평가 결과 파싱
        if "높음" in result:
            is_relevant = True
            relevance_score = 0.8  # 기본값
        else:
            is_relevant = False
            relevance_score = 0.3  # 기본값
        
        # 점수 추출 시도
        if "점수:" in result:
            try:
                score_part = result.split("점수:")[1].split("\n")[0].strip()
                relevance_score = round(float(score_part), 2)
            except:
                pass
        
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
        
        print(f"[EvaluateChunk] 완료 - 관련성: {is_relevant}, 점수: {relevance_score}, 선택된 청크: {len(selected_chunks)}개")
        
    except Exception as e:
        print(f"[EvaluateChunk] 오류 발생: {e}")
        # 오류 시 기본값 설정
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
    
    return state
