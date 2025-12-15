"""
테스트용 pgvector 업서트 스텁.
"""


def run(embeddings_dir: str) -> None:
    """DB 업서트 대신 경로 정보만 출력한다."""
    print(f"[UPSERT:pgvector] embeddings_dir={embeddings_dir}")
