"""
테스트용 임베딩 스텁.
"""


def run(chunks_dir: str, embeddings_dir: str) -> None:
    """임베딩 계산 대신 경로 정보만 출력한다."""
    print(f"[EMBED] chunks_dir={chunks_dir}, embeddings_dir={embeddings_dir}")
