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

def serpapi_search(query: str, top_k: int = 5) -> Tuple[List[Dict[str, str]], str]:
    """
    SerpAPI를 이용해 웹 검색을 수행하고,
    title, snippet, link 형태의 리스트를 반환합니다.
    
    매개변수:
        query (str): 검색할 질문이나 키워드
        top_k (int): 가져올 검색 결과 개수 (기본값: 5개)
    
    반환값:
        Tuple[List[Dict[str, str]], str]:
            - 검색 결과 리스트
            - 사용된 검색 엔진 이름 ("serpapi", "tavily", "none")
    """
    # 환경변수에서 SerpAPI 키를 가져옵니다
    # SerpAPI는 Google 검색 결과를 제공하는 서비스입니다
    # API 키는 .env 파일에 저장되어 있어야 합니다
    api_key = os.getenv("SERPAPI_KEY")
    
    # API 키가 없으면 검색을 수행할 수 없습니다
    if not api_key:
        print("[WebSearch Warning] SERPAPI_KEY 환경변수가 없습니다.")
        return [], "credit_exhausted"  # SerpAPI 사용 불가

    # SerpAPI에 보낼 요청 파라미터를 만듭니다
    # 마치 검색 엔진에 "이렇게 검색해주세요"라고 요청하는 것과 같습니다
    params = {
        "engine": "google",  # Google 검색 엔진을 사용합니다
        "q": query,          # 검색할 질문이나 키워드
        "api_key": api_key,  # API 사용을 위한 인증 키
    }

    try:
        # SerpAPI 서버에 HTTP GET 요청을 보냅니다
        # requests.get()은 인터넷에 요청을 보내는 함수입니다
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        
        # HTTP 응답 상태 코드를 확인합니다
        # 401, 403은 인증 오류 (credit 부족 가능성)
        if response.status_code == 401 or response.status_code == 403:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("error", str(response.status_code))
            print(f"[WebSearch Warning] SerpAPI 인증 오류 (credit 부족 가능성): {error_msg}")
            return [], "credit_exhausted"
        
        # HTTP 응답 상태 코드를 확인합니다
        # 200은 성공을 의미합니다
        response.raise_for_status()
        
        # 응답을 JSON 형식으로 변환합니다
        # JSON은 데이터를 주고받을 때 사용하는 형식입니다
        data = response.json()
        
        # SerpAPI 오류 메시지 확인
        if "error" in data:
            error_msg = data.get("error", "")
            # credit 관련 오류 메시지 확인
            if "credit" in error_msg.lower() or "quota" in error_msg.lower() or "limit" in error_msg.lower():
                print(f"[WebSearch Warning] SerpAPI credit 부족: {error_msg}")
                return [], "credit_exhausted"
            else:
                print(f"[WebSearch Error] SerpAPI 오류: {error_msg}")
                return [], error_msg
        
    except requests.exceptions.HTTPError as e:
        # HTTP 오류 중 401/403은 credit 부족 가능성
        if e.response.status_code in [401, 403]:
            print(f"[WebSearch Warning] SerpAPI 인증 오류 (credit 부족 가능성): {e}")
            return [], "credit_exhausted"
        else:
            print(f"[WebSearch Error] SerpAPI HTTP 오류 → {e}")
            return [], str(e)
    except requests.exceptions.RequestException as e:
        # 네트워크 오류나 HTTP 오류가 발생했을 때
        print(f"[WebSearch Error] 요청 실패 → {e}")
        return [], "network_error"
    except Exception as e:
        # 기타 오류가 발생했을 때
        print(f"[WebSearch Error] 예상치 못한 오류 → {e}")
        return [], "unexpected_error"

    # 검색 결과에서 "organic_results"를 가져옵니다
    # organic_results는 일반 검색 결과를 의미합니다 (광고가 아닌 실제 검색 결과)
    organic = data.get("organic_results", [])
    
    # 검색 결과가 없으면 빈 리스트를 반환합니다
    if not organic:
        return [], "no_results"

    # 검색 결과를 정리해서 저장할 리스트를 만듭니다
    results = []
    
    # 검색 결과 중에서 top_k 개수만큼만 가져옵니다 (기본값: 5개)
    # [:top_k]는 리스트의 처음부터 top_k 개만 가져온다는 의미입니다
    for item in organic[:top_k]:
        # 각 검색 결과에서 필요한 정보만 추출합니다
        # get() 메서드는 키가 없으면 None을 반환합니다
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        
        # 제목이나 요약이 있는 경우에만 결과에 추가합니다
        if title or snippet:
            results.append({
                "title": title,      # 검색 결과의 제목
                "snippet": snippet,  # 검색 결과의 요약 내용
                "link": link         # 검색 결과의 웹페이지 링크
            })

    # 정리된 검색 결과 리스트를 반환합니다
    return results, "serpapi"


def tavily_search(query: str, top_k: int = 5) -> List[Dict[str, str]]:
    """
    Tavily API를 이용해 웹 검색을 수행하고,
    title, snippet, link 형태의 리스트를 반환합니다.
    
    매개변수:
        query (str): 검색할 질문이나 키워드
        top_k (int): 가져올 검색 결과 개수 (기본값: 5개)
    
    반환값:
        List[Dict[str, str]]: 검색 결과 리스트
            각 결과는 {"title": 제목, "snippet": 요약, "link": 링크} 형태
    
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
        return []  # 빈 리스트를 반환합니다 (검색 결과 없음)

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
        return []
    except requests.exceptions.HTTPError as e:
        # HTTP 오류
        print(f"[WebSearch Error] Tavily HTTP 오류 → {e}")
        return []
    except requests.exceptions.RequestException as e:
        # 네트워크 오류나 HTTP 오류가 발생했을 때
        print(f"[WebSearch Error] Tavily 요청 실패 → {e}")
        return []
    except Exception as e:
        # 기타 오류가 발생했을 때
        print(f"[WebSearch Error] Tavily 예상치 못한 오류 → {e}")
        return []

    # 검색 결과에서 "results"를 가져옵니다
    # Tavily는 "results" 키에 검색 결과를 저장합니다
    results_data = data.get("results", [])
    
    # 검색 결과가 없으면 빈 리스트를 반환합니다
    if not results_data:
        return []

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
    return results


def web_search_with_fallback(query: str, top_k: int = 5) -> Tuple[List[Dict[str, str]], str]:
    """
    SerpAPI를 먼저 사용하고, credit이 부족하면 자동으로 Tavily로 전환하는 함수입니다.
    
    매개변수:
        query (str): 검색할 질문이나 키워드
        top_k (int): 가져올 검색 결과 개수 (기본값: 5개)
    
    반환값:
        Tuple[List[Dict[str, str]], str]:
            - 검색 결과 리스트
            - 사용된 검색 엔진 이름 ("serpapi", "tavily", "none")
    """
    # 1단계: SerpAPI를 먼저 시도합니다
    print(f"[WEB SEARCH] SerpAPI로 검색 시도: {query}")
    serpapi_results, error = serpapi_search(query, top_k)
    
    # SerpAPI가 성공한 경우
    if error == "serpapi" and serpapi_results:
        print(f"[WEB SEARCH] SerpAPI 성공: {len(serpapi_results)}개 결과")
        return serpapi_results, "serpapi"
    
    # SerpAPI credit이 부족한 경우에만 Tavily로 전환
    if error == "credit_exhausted":
        print(f"[WEB SEARCH] SerpAPI credit 부족 → Tavily로 전환")
        tavily_results = tavily_search(query, top_k)
        
        if tavily_results:
            print(f"[WEB SEARCH] Tavily 성공: {len(tavily_results)}개 결과")
            return tavily_results, "tavily"
        else:
            print(f"[WEB SEARCH] Tavily도 실패")
            return [], "none"
    
    # credit 부족이 아닌 다른 오류인 경우 SerpAPI 결과를 그대로 반환 (빈 결과일 수 있음)
    # Tavily로 전환하지 않고 SerpAPI 오류를 그대로 반환
    if error:
        print(f"[WEB SEARCH] SerpAPI 오류 (credit 부족 아님): {error}")
        return serpapi_results, "serpapi"  # 빈 결과일 수 있지만 SerpAPI로 표시
    
    # 결과가 없는 경우 (오류는 없지만 결과도 없음)
    return [], "none"


def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    웹 검색 노드 - RAG 검색이 실패했을 때 fallback으로 사용
    
    Input:
        - state["question"]: 사용자 질문
        - state["rewritten_query"]: 재작성된 쿼리 (선택적)
        - state["extracted_keywords"]: 추출된 키워드들 (선택적)
    
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
    keywords = state.get("extracted_keywords", [])
    
    # 검색 쿼리 결정 (우선순위: rewritten_query > question)
    search_query = rewritten_query if rewritten_query else question
    
    # 키워드가 있으면 검색 쿼리에 추가
    if keywords:
        search_query += " " + " ".join(keywords[:3])  # 최대 3개 키워드만 추가
    
    print(f"[WebSearch] 시작 - 쿼리: \"{search_query[:50]}...\"")
    
    # 검색할 질문이 없는 경우
    if not search_query:
        print("[WebSearch] 검색 쿼리가 없음")
        state["web_results"] = []
        state["used_web_search"] = False
        return state
    
    # 웹 검색 실행
    try:
        results, engine_used = web_search_with_fallback(search_query, top_k=3)  # 최대 3개 결과
        
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
