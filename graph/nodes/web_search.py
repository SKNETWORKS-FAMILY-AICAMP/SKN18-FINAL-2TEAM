"""
web_search.py
--------------------
RAG 검색이 실패했을 때 웹 검색을 수행하는 fallback 노드
BioRAGState 구조에 맞게 구현
"""

import os
import requests
from typing import Dict, Any, List, Tuple
from pathlib import Path

# Django 환경 변수 로딩 지원
try:
    from django.conf import settings
    # Django가 설정되어 있으면 Django의 환경 변수 로딩 방식 사용
    DJANGO_AVAILABLE = True
except ImportError:
    # Django가 없으면 dotenv 사용
    from dotenv import load_dotenv
    # 프로젝트 루트에서 .env 파일 찾기
    PROJECT_ROOT = Path(__file__).resolve().parents[2]  # graph/nodes/web_search.py -> graph -> PROJECT_ROOT
    env_files = [PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"]
    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            break
    DJANGO_AVAILABLE = False


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
    # 환경변수에서 Tavily API 키 가져오기
    if DJANGO_AVAILABLE:
        try:
            from config.env import env
            api_key = env("TAVILY_API_KEY", default=None)
        except:
            api_key = os.getenv("TAVILY_API_KEY")
    else:
        api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key or not api_key.strip():
        print("[WebSearch] TAVILY_API_KEY가 설정되지 않았습니다.")
        return [], "none"
    
    api_key = api_key.strip()

    url = "https://api.tavily.com/search"
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": top_k,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # Authorization header 실패 시 JSON payload 방식으로 재시도
        if response.status_code == 401:
            payload["api_key"] = api_key
            response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 401:
            print(f"[WebSearch Error] Tavily 인증 실패: {response.json().get('error', 'Invalid API key')}")
            return [], "none"
        
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.Timeout:
        print(f"[WebSearch Error] Tavily 요청 시간 초과")
        return [], "none"
    except requests.exceptions.HTTPError as e:
        print(f"[WebSearch Error] Tavily HTTP 오류: {e}")
        return [], "none"
    except requests.exceptions.RequestException as e:
        print(f"[WebSearch Error] Tavily 요청 실패: {e}")
        return [], "none"
    except Exception as e:
        print(f"[WebSearch Error] Tavily 오류: {e}")
        return [], "none"

    results_data = data.get("results", [])
    if not results_data:
        return [], "none"

    results = []
    for item in results_data[:top_k]:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        if title or content:
            results.append({
                "title": title,
                "snippet": content[:200] if content else "",
                "link": url
            })

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
    
    question = state.get("question", "").strip()
    rewritten_query = state.get("rewritten_query", "")
    entities = state.get("entities", [])
    
    search_query = rewritten_query if rewritten_query else question
    if entities:
        search_query += " " + " ".join(entities[:5])
    
    if not search_query:
        state["web_results"] = []
        state["used_web_search"] = False
        return state
    
    try:
        results, engine_used = tavily_search(search_query, top_k=3)
        
        if results:
            web_results = []
            sources = state.get("answer_sources", [])
            
            for result in results:
                web_result = {
                    "content": f"{result.get('title', '')} - {result.get('snippet', '')}",
                    "url": result.get("link", ""),
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", "")
                }
                web_results.append(web_result)
                
                if web_result["url"]:
                    sources.append(web_result["url"])
            
            state["web_results"] = web_results
            state["used_web_search"] = True
            state["answer_sources"] = sources
        else:
            state["web_results"] = []
            state["used_web_search"] = True

    except Exception as e:
        print(f"[WebSearch] 오류: {e}")
        state["web_results"] = []
        state["used_web_search"] = False

    return state
