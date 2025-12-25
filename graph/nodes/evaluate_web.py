"""
evaluate_web.py
--------------------
웹 검색 결과의 관련성을 평가하는 노드
BioRAGState 구조에 맞게 구현
"""

from typing import Dict, Any
from graph.llm_config import evaluate_web_node_llm


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

        # BIO_Q인 경우 조기 종료 메시지 설정
        case_type = state.get("case_type", "")
        if case_type == "BIO_Q":
            state["final_answer"] = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 질문을 해주시거나, 더 구체적인 정보를 제공해주시면 도움을 드리겠습니다."
            state["should_skip_generation"] = True
            print("[EvaluateWeb] BIO_Q - 웹 검색 결과 없음, 조기 종료")
        else:
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
    prompt = f"""다음 웹 검색 결과에서 사용자 질문과 **직접적으로 관련된** 핵심 정보만 선별해주세요.

사용자 질문: {question}

웹 검색 결과:
---
{context}
---

**중요 지침:**
1. 질문과 직접적으로 관련된 웹 자료만 선택하세요 (관련성이 높은 것만)
2. 최대 3개의 웹 자료만 선택하세요
3. 각 자료는 한 줄로 핵심만 요약하세요 (최대 100자)
4. 관련성이 낮거나 부정확한 정보는 제외하세요

출력 형식:
- 관련 자료가 있으면: "웹자료 N: [핵심 내용 한 줄 요약]" 형태로 최대 3개만 출력
- 관련 자료가 없으면: "관련 정보 없음" 출력
"""

    try:
        # GPT-4o-mini를 사용하여 웹 검색 결과 정제
        result = evaluate_web_node_llm(prompt)
        
        # 결과를 청크 단위로 분리
        web_selected_chunks = []

        if "관련 정보 없음" not in result:
            # 결과를 줄 단위로 분리하고 의미있는 내용만 추출
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                # "웹자료 N:" 형식의 줄만 추출
                if line and line.startswith('웹자료') and ':' in line:
                    web_selected_chunks.append(line)
                    if len(web_selected_chunks) >= 20:  # 최대 20개로 제한
                        break

        # BIO_Q이고 관련 정보가 없는 경우 조기 종료 (citations 추가하지 않음)
        if not web_selected_chunks:
            case_type = state.get("case_type", "")
            if case_type == "BIO_Q":
                state["final_answer"] = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 질문을 해주시거나, 더 구체적인 정보를 제공해주시면 도움을 드리겠습니다."
                state["should_skip_generation"] = True
                state["web_selected_chunks"] = []
                print("[EvaluateWeb] ⚠️ BIO_Q - 관련 정보 없음, GENERATE_ANSWER 건너뛰고 END로 이동")
                print(f"[EvaluateWeb] should_skip_generation = {state.get('should_skip_generation')}")
                print(f"[EvaluateWeb] final_answer = {state.get('final_answer')[:50]}...")
                print(f"[EvaluateWeb] citations = {len(state.get('citations', []))}개 (citations 추가 안 함)")
                return state

        # web_selected_chunks를 state에 저장 (services.py에서 references 생성 시 사용)
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