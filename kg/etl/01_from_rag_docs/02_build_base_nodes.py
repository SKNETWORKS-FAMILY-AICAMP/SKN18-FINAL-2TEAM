"""
테스트용 베이스 노드 빌더 스텁.
"""


def run(docs) -> None:
    """로드된 문서 개수만 출력한다."""
    count = len(docs) if docs else 0
    print(f"[KG:RAG_DOCS] build_base_nodes docs_count={count}")
