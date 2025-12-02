"""
테스트용 청킹 스텁.
"""


def run(processed_dir: str, chunks_dir: str) -> None:
    """청크 생성 대신 경로 정보만 출력한다."""
    print(f"[CHUNK] processed_dir={processed_dir}, chunks_dir={chunks_dir}")
