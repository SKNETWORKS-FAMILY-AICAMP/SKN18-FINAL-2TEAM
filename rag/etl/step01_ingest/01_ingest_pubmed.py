"""
테스트용 PubMed ingest 스텁.
"""


def run(raw_dir: str, limit: int | None = None) -> None:
    """원격 데이터 대신 경로와 제한값만 출력한다."""
    print(f"[INGEST:PubMed] raw_dir={raw_dir}, limit={limit}")
