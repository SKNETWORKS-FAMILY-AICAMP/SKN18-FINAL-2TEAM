"""
web_search.py
--------------------
RAG 검색이 실패했을 때 웹 검색을 수행하는 fallback 노드
BioRAGState 구조에 맞게 구현
"""

import os
import requests
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv

load_dotenv()


def tavily_search(query: str, top_k: int = 5) -> Tuple[List[Dict[str, str]], str]:
    """
    Tavily API를 이용해 웹 검색을 수행하고,
    title, snippet, link 형태의 리스트를 반환합니다.
    
    매개변수:
        query (str): 검색할 질문이나 키워드
        top_k (int): 가져올 검색 결과 개수 (기본값: 5개)
    
    반환값:
        Tuple[List[Dict[str, str]], str]:
            - 검색 결과 리스트
            - 사용된 검색 엔진 이름 ("tavily", "none")
    
    작동 방식:
        1. Tavily API에 검색 요청을 보냅니다
        2. 검색 결과를 받아옵니다
        3. 결과를 정리해서 반환합니다
    """
    # 환경변수에서 Tavily API 키를 가져옵니다
    # Tavily는 AI 기반 웹 검색 서비스입니다
    # API 키는 .env 파일에 저장되어 있어야 합니다
    api_key = os.getenv("TAVILY_API_KEY")

    # API 키가 없으면 검색을 수행할 수 없습니다
    if not api_key:
        print("[WebSearch Warning] TAVILY_API_KEY 환경변수가 없습니다.")
        return [], "none"  # 빈 리스트를 반환합니다 (검색 결과 없음)

    # Tavily API 엔드포인트
    url = "https://api.tavily.com/search"
    
    # Tavily API에 보낼 요청 데이터를 만듭니다
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",  # "basic" 또는 "advanced"
        "max_results": top_k,     # 가져올 검색 결과 개수
    }

    try:
        # Tavily API 서버에 HTTP POST 요청을 보냅니다
        # requests.post()은 인터넷에 POST 요청을 보내는 함수입니다
        response = requests.post(url, json=payload, timeout=10)
        
        # HTTP 응답 상태 코드를 확인합니다
        # 200은 성공을 의미합니다
        response.raise_for_status()
        
        # 응답을 JSON 형식으로 변환합니다
        data = response.json()
        
    except requests.exceptions.Timeout:
        # 타임아웃 오류
        print(f"[WebSearch Error] Tavily 요청 시간 초과")
        return [], "none"
    except requests.exceptions.HTTPError as e:
        # HTTP 오류
        print(f"[WebSearch Error] Tavily HTTP 오류 → {e}")
        return [], "none"
    except requests.exceptions.RequestException as e:
        # 네트워크 오류나 HTTP 오류가 발생했을 때
        print(f"[WebSearch Error] Tavily 요청 실패 → {e}")
        return [], "none"
    except Exception as e:
        # 기타 오류가 발생했을 때
        print(f"[WebSearch Error] Tavily 예상치 못한 오류 → {e}")
        return [], "none"

    # 검색 결과에서 "results"를 가져옵니다
    # Tavily는 "results" 키에 검색 결과를 저장합니다
    results_data = data.get("results", [])
    
    # 검색 결과가 없으면 빈 리스트를 반환합니다
    if not results_data:
        return [], "none"

    # 검색 결과를 정리해서 저장할 리스트를 만듭니다
    results = []
    
    # 검색 결과를 순회하면서 필요한 정보만 추출합니다
    for item in results_data[:top_k]:
        # Tavily API의 응답 형식에 맞게 데이터 추출
        title = item.get("title", "")
        content = item.get("content", "")  # Tavily는 "content"를 사용
        url = item.get("url", "")

        # 제목이나 내용이 있는 경우에만 결과에 추가합니다
        if title or content:
            results.append({
                "title": title,           # 검색 결과의 제목
                "snippet": content[:200] if content else "",  # 검색 결과의 요약 내용 (최대 200자)
                "link": url              # 검색 결과의 웹페이지 링크
            })

    # 정리된 검색 결과 리스트를 반환합니다
    return results, "tavily"


def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    웹 검색 노드 - RAG 검색이 실패했을 때 fallback으로 사용
    
    Input:
        - state["question"]: 사용자 질문
        - state["rewritten_query"]: 재작성된 쿼리 (선택적)
        - state["entities"]: 추출된 키워드들 (retriever에서 설정, 선택적)
    
    Output:
        - state["web_results"]: 웹 검색 결과
        - state["used_web_search"]: 웹 검색 사용 여부
        - state["answer_sources"]: 출처 정보 (누적)
    """
    
    # 노드 진입 로그
    print(f"\n{'='*60}")
    print(f"[WEB_SEARCH NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")
    
    question = state.get("question", "").strip()
    rewritten_query = state.get("rewritten_query", "")
    entities = state.get("entities", [])  # retriever에서 설정됨
    
    # 검색 쿼리 결정 (우선순위: rewritten_query > question)
    search_query = rewritten_query if rewritten_query else question
    
    # 엔티티티가 있으면 검색 쿼리에 추가
    if entities:
        search_query += " " + " ".join(entities[:5])  # 최대 3개 엔티티만 추가
    
    print(f"[WebSearch] 시작 - 쿼리: \"{search_query[:50]}...\"")
    
    # 검색할 질문이 없는 경우
    if not search_query:
        print("[WebSearch] 검색 쿼리가 없음")
        state["web_results"] = []
        state["used_web_search"] = False
        return state
    
    # 웹 검색 실행 (Tavily 사용)
    try:
        print(f"[WEB SEARCH] Tavily로 검색 시도: {search_query}")
        results, engine_used = tavily_search(search_query, top_k=3)  # 최대 3개 결과
        
        if results:
            # 검색 결과를 BioRAGState 형식으로 변환
            web_results = []
            sources = state.get("answer_sources", [])
            
            for idx, result in enumerate(results, 1):
                web_result = {
                    "content": f"{result.get('title', '')} - {result.get('snippet', '')}",
                    "url": result.get("link", ""),
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", "")
                }
                web_results.append(web_result)
                
                # 검색 결과 내용 일부 출력 (앞 50글자)
                snippet_preview = result.get("snippet", "")[:50]
                print(f"  [{idx}] {result.get('title', 'No Title')[:40]}")
                print(f"      내용: {snippet_preview}...")
                print(f"      URL: {result.get('link', '')}")
                
                # 출처 정보 추가
                if web_result["url"]:
                    sources.append(web_result["url"])
            
            state["web_results"] = web_results
            state["used_web_search"] = True
            state["answer_sources"] = sources
            
            print(f"\n[WebSearch] 완료 - {len(web_results)}개 결과 ({engine_used})")
            
        else:
            # 검색 결과가 없는 경우
            state["web_results"] = []
            state["used_web_search"] = True  # 시도는 했지만 결과 없음
            
            print(f"[WebSearch] 완료 - 결과 없음 ({engine_used})")

    except Exception as e:
        print(f"[WebSearch] 오류 발생: {e}")
        state["web_results"] = []
        state["used_web_search"] = False
    
    # 노드 종료 로그
    print(f"\n[WEB_SEARCH NODE] 종료")
    print(f"  web_results: {len(state.get('web_results', []))}개")
    print(f"  used_web_search: {state.get('used_web_search', False)}")
    print(f"{'='*60}\n")

    return state
