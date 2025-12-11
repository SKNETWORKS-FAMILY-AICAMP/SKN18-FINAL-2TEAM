"""
rewrite_query.py
--------------------
사용자 질문을 검색에 최적화된 형태로 재작성하는 노드
BioRAGState 구조에 맞게 구현
"""

from typing import Dict, Any
from graph.nodes.call_llm import gpt4o_mini


def rewrite_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    쿼리 재작성 노드
    사용자 질문과 추출된 키워드/엔티티를 바탕으로 검색에 최적화된 쿼리 생성
    
    Input:
        - state["question"]: 사용자 질문
        - state["extracted_keywords"]: 추출된 키워드들
        - state["extracted_entities"]: 추출된 엔티티들
        - state["memory_slot"]: 메모리 슬롯 (선택적)
    
    Output:
        - state["rewritten_query"]: 재작성된 검색 쿼리
    """
    
    question = state.get("question", "")
    keywords = state.get("extracted_keywords", [])
    entities = state.get("extracted_entities", [])
    memory_slot = state.get("memory_slot", {})
    
    print(f"[RewriteQuery] 시작 - 원본: \"{question[:50]}...\"")
    
    # 질문이 없으면 빈 쿼리 반환
    if not question:
        state["rewritten_query"] = ""
        return state
    
    # 메모리에서 이전 주제 정보 가져오기
    previous_topic = memory_slot.get("topic", "") if memory_slot else ""
    
    # 프롬프트 구성
    prompt = f"""다음 사용자 질문을 검색에 최적화된 형태로 재작성해주세요.

원본 질문: {question}

추출된 키워드: {keywords}
추출된 엔티티: {entities}"""

    if previous_topic:
        prompt += f"\n이전 대화 주제: {previous_topic}"

    prompt += """

재작성 규칙:
1. 검색에 효과적인 핵심 키워드들을 포함하세요
2. 생물학/의학 전문 용어는 정확히 유지하세요
3. 불필요한 조사나 어미는 제거하세요
4. 영어 전문 용어가 있으면 함께 포함하세요
5. 간결하고 명확하게 작성하세요

재작성된 검색 쿼리만 출력하세요:"""

    try:
        # GPT-4o-mini를 사용하여 쿼리 재작성
        rewritten_query = gpt4o_mini(prompt).strip()
        
        # 결과가 너무 길면 자르기 (최대 200자)
        if len(rewritten_query) > 200:
            rewritten_query = rewritten_query[:200] + "..."
        
        # 빈 결과면 원본 질문 사용
        if not rewritten_query:
            rewritten_query = question
        
        state["rewritten_query"] = rewritten_query
        
        print(f"[RewriteQuery] 완료 - 재작성: \"{rewritten_query[:50]}...\"")
        
    except Exception as e:
        print(f"[RewriteQuery] 오류 발생: {e}")
        # 오류 시 간단한 재작성 로직 사용
        rewritten_parts = [question]
        
        # 키워드와 엔티티 추가
        if keywords:
            rewritten_parts.extend(keywords[:3])  # 최대 3개
        if entities:
            rewritten_parts.extend(entities[:3])  # 최대 3개
        
        rewritten_query = " ".join(rewritten_parts)
        state["rewritten_query"] = rewritten_query
        
        print(f"[RewriteQuery] 폴백 완료 - 재작성: \"{rewritten_query[:50]}...\"")
    
    return state