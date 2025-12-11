'''
retrieval.py   mook데이터터
-------------------------------------

-------------------------------------
RAG 검색 노드 (bio_q, protocol_q 케이스에서 실행)
- pgvector에서 검색
- neo4j의 특정 임베딩 노드에서 검색
- 둘 중 하나를 선택하여 최종 결과 반환

리턴되는 state값:
    retrieval_results: List[Dict[str, Any]]   # VectorDB/Neo4j RAW 검색 결과
    reranked_results: List[Dict[str, Any]]    # rerank 이후 정렬된 문서
    retrieval_score: float                    # rerank 최상위 점수
'''


def retrieval_node(state):
    """
    RAG 검색 노드 - rewritten_query를 사용하여 pgvector 또는 neo4j에서 검색

    Args:
        state: BioRAGState
        - rewritten_query: 재작성된 검색 쿼리
        - case_type: 케이스 타입
        - extracted_keywords: 추출된 키워드

    Returns:
        state 업데이트:
        - retrieval_results: 검색된 문서 리스트
        - reranked_results: rerank된 문서 리스트
        - retrieval_score: 최상위 문서 점수
    
    query = state.get("question", "").strip()

    # 시작 로그
    print(f"• [Retrieve] start (top_k=5, query=\"{query[:50]}...\")")

    try:
        # VectorRetriever 인스턴스 가져오기
        retriever = get_vector_retriever()

        # 문서 검색 (상위 5개)
        docs = retriever.search(query, top_k=5)

    
    """

    rewritten_query = state.get("rewritten_query", state.get("question", ""))
    case_type = state.get("case_type", "bio_q")

    # TODO: 실제 구현 시 pgvector 또는 neo4j 검색 로직 추가

    # TODO: pgvector 또는 neo4j 검색 (top_k=50)
    # 더미 검색 결과 (초기 검색 - 많은 수)
    dummy_results = [
        {
            "content": f"This is a dummy search result for query: {rewritten_query}",
            "metadata": {
                "source": "dummy_vector_db",
                "case_type": case_type,
                "chunk_id": 1
            },
            "score": 0.85
        },
        {
            "content": f"Another relevant document about: {rewritten_query}",
            "metadata": {
                "source": "dummy_vector_db",
                "case_type": case_type,
                "chunk_id": 2
            },
            "score": 0.78
        },
        {
            "content": f"Additional context for: {rewritten_query}",
            "metadata": {
                "source": "dummy_neo4j",
                "case_type": case_type,
                "chunk_id": 3
            },
            "score": 0.72
        },
        {
            "content": f"More information related to: {rewritten_query}",
            "metadata": {
                "source": "dummy_vector_db",
                "case_type": case_type,
                "chunk_id": 4
            },
            "score": 0.65
        },
        {
            "content": f"Background knowledge for: {rewritten_query}",
            "metadata": {
                "source": "dummy_neo4j",
                "case_type": case_type,
                "chunk_id": 5
            },
            "score": 0.58
        }
    ]

    # System log 추가
    system_log = state.get("system_log", [])
    system_log.append(f"[retrieval] Retrieved {len(dummy_results)} documents for case_type={case_type}")

    return {
        "retrieval_results": dummy_results,
        "system_log": system_log
    }
