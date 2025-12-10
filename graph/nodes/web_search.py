
'''
# nodes/web_search.py
from langchain_community.tools.tavily_search import TavilySearchResults
from graph.state import SelfRAGState


def web_search(state: SelfRAGState) -> SelfRAGState:
    """
    WebSearch 노드
    Tavily를 사용해 용어 정의 검색
    """
    query = state.get("question", "").strip()

    # 시작 로그
    print(f"• [WebSearch] start (query=\"{query[:50]}...\", max_results=3)")

    # Tavily 검색 도구 초기화 (max_results=3으로 상위 3개 결과만)
    search_tool = TavilySearchResults(max_results=3)

    try:
        # 검색 실행
        results = search_tool.invoke({"query": query})

        # 결과를 state에 저장
        state["web_search_results"] = results

        # 컨텍스트 구성
        context_parts = []
        sources = []
        seen_urls = set()  # 중복 URL 체크용

        for i, result in enumerate(results, 1):
            content = result.get("content", "")
            url = result.get("url", "")

            context_parts.append(f"[출처 {i}] {content}")
            if url and url not in seen_urls:
                sources.append(f"[{i}] {url}")  # 중복 제거 후 번호와 URL 함께 저장
                seen_urls.add(url)

        state["context"] = "\n\n".join(context_parts)
        state["sources"] = sources

        # 완료 로그
        print(f"• [WebSearch] complete (results={len(results)})")

    except Exception as e:
        # 검색 실패 시
        state["web_search_results"] = []
        state["context"] = ""
        state["sources"] = []
        print(f"웹 검색 오류: {e}")

    return state
'''