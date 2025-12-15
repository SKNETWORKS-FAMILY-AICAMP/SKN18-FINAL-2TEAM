"""
테스트용 PubMed normalize 스텁.
"""


def run(raw_dir: str, processed_dir: str) -> None:
    """정규화 대신 경로 정보만 출력한다."""
    print(f"[NORMALIZE:PubMed] raw_dir={raw_dir}, processed_dir={processed_dir}")
