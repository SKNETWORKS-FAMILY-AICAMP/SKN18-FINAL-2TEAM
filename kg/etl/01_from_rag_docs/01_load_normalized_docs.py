"""
테스트용 정규화 문서 로더 스텁.
"""


def run(processed_dir: str, source: str | None):
    """정규화 디렉터리와 소스 정보를 출력하고 더미 문서를 반환한다."""
    print(
        "[KG:RAG_DOCS] load_normalized_docs "
        f"processed_dir={processed_dir}, source={source}"
    )
    return [
        {
            "doc_id": "DOC-STUB",
            "title": "Stubbed Document",
            "source": source or "all",
        }
    ]
