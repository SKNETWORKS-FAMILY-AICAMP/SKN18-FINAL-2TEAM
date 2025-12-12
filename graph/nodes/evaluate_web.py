"""
evaluate_web.py
--------------------
웹 검색 결과의 관련성을 평가하는 노드
BioRAGState 구조에 맞게 구현
"""

from typing import Dict, Any
from graph.nodes.call_llm import gpt4o_mini


def evaluate_web_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    웹 검색 결과 평가 노드
    웹 검색 결과에서 질문과 관련된 내용만 선별하여 정제
    
    Input:
        - state["question"]: 사용자 질문
        - state["web_results"]: 웹 검색 결과
    
    Output:
        - state["web_selected_chunks"]: 선별된 웹 검색 청크들
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[EVALUATE_WEB NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  web_results: {len(state.get('web_results', []))}개")
    print(f"{'='*60}\n")
    
    question = state.get("question", "")
    web_results = state.get("web_results", [])
    
    print(f"[EvaluateWeb] 시작 - {len(web_results)}개 웹 검색 결과 평가")
    
    # 웹 검색 결과가 없는 경우
    if not web_results:
        state["web_selected_chunks"] = []
        print("[EvaluateWeb] 완료 - 웹 검색 결과 없음")
        return state
    
    # 웹 검색 결과를 컨텍스트로 변환
    context_parts = []
    for i, result in enumerate(web_results, 1):
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        
        # 각 웹 검색 결과의 앞 50글자 로그 출력
        snippet_preview = snippet[:50] if snippet else ""
        print(f"  [웹자료 {i}] {title[:40]}")
        print(f"      내용: {snippet_preview}...")
        
        content = f"제목: {title}\n내용: {snippet}"
        if url:
            content += f"\n출처: {url}"
        
        context_parts.append(f"[웹자료 {i}]\n{content}")
    
    context = "\n\n".join(context_parts)
    
    # LLM을 사용하여 관련성 평가 및 정제
    prompt = f"""다음 웹 검색 결과에서 사용자 질문과 관련된 내용만 선별하여 정제해주세요.

사용자 질문: {question}

웹 검색 결과:
---
{context}
---

위 웹 검색 결과에서 질문과 관련된 핵심 정보만 추출하여 정리해주세요.
각 자료별로 관련된 내용이 있으면 간결하게 요약하고, 관련 없는 내용은 제외해주세요.

출력 형식:
- 관련 자료가 있으면: "웹자료 N: [요약된 관련 내용]" 형태로 출력
- 관련 자료가 없으면: "관련 정보 없음" 출력
"""

    try:
        # GPT-4o-mini를 사용하여 웹 검색 결과 정제
        result = gpt4o_mini(prompt)
        
        # 결과를 청크 단위로 분리
        web_selected_chunks = []
        
        if "관련 정보 없음" not in result:
            # 결과를 줄 단위로 분리하고 의미있는 내용만 추출
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and ('웹자료' in line or len(line) > 20):  # 의미있는 내용만
                    web_selected_chunks.append(line)
        
        state["web_selected_chunks"] = web_selected_chunks
        
        print(f"[EvaluateWeb] 완료 - {len(web_selected_chunks)}개 청크 선별")
        
    except Exception as e:
        print(f"[EvaluateWeb] 오류 발생: {e}")
        # 오류 시 원본 웹 검색 결과를 간단히 변환
        web_selected_chunks = []
        for i, result in enumerate(web_results[:2], 1):  # 최대 2개만
            content = result.get("content", "")
            if content:
                web_selected_chunks.append(f"웹자료 {i}: {content[:200]}...")
        
        state["web_selected_chunks"] = web_selected_chunks
    
    # 노드 종료 로그
    print(f"\n[EVALUATE_WEB NODE] 종료")
    print(f"  web_selected_chunks: {len(state.get('web_selected_chunks', []))}개")
    print(f"{'='*60}\n")
    
    return state