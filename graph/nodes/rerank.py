'''
rerank.py
-------------------------------------
Cross-Encoder based reranking node
Reranks retrieval results for better relevance

Input state:
    - retrieval_results: List of retrieved documents
    - question or rewritten_query: User query string

Output state:
    - reranked_results: Top N reranked documents
    - retrieval_score: Highest rerank score
'''


def rerank_node(state):
    """
    Cross-Encoder based reranking node

    Args:
        state: BioRAGState
        - retrieval_results: List of documents from retrieval
        - question: Original user question
        - rewritten_query: Rewritten query (preferred)

    Returns:
        state update:
        - reranked_results: Top N reranked documents
        - retrieval_score: Highest rerank score
    """

    retrieval_results = state.get("retrieval_results", [])
    query = state.get("rewritten_query", state.get("question", ""))

    if not retrieval_results:
        return {
            "reranked_results": [],
            "retrieval_score": 0.0,
            "system_log": state.get("system_log", []) + ["[rerank] No results to rerank"]
        }

    # TODO: Implement actual Cross-Encoder reranking
    # from sentence_transformers import CrossEncoder
    # model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    #
    # pairs = [[query, doc["content"]] for doc in retrieval_results]
    # scores = model.predict(pairs)
    #
    # for doc, score in zip(retrieval_results, scores):
    #     doc["rerank_score"] = float(score)

    # Dummy implementation: Add small bonus to original scores
    reranked = []
    for i, doc in enumerate(retrieval_results):
        # Give small bonus to top 3 results based on query length
        bonus = 0.01 * len(query.split()) if i < 3 else 0.0
        rerank_score = doc.get("score", 0.5) + bonus

        reranked.append({
            **doc,
            "rerank_score": rerank_score,
            "original_rank": i + 1
        })

    # Sort by rerank score descending
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

    # Take top N documents
    top_n = 10
    reranked_top = reranked[:top_n]

    # System log
    system_log = state.get("system_log", [])
    system_log.append(
        f"[rerank] Reranked {len(retrieval_results)} to {len(reranked_top)} documents "
        f"(top_score={reranked_top[0]['rerank_score']:.3f})"
    )

    return {
        "reranked_results": reranked_top,
        "retrieval_score": reranked_top[0]["rerank_score"] if reranked_top else 0.0,
        "system_log": system_log
    }
