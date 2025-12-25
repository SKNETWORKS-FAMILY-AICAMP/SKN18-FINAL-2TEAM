"""
테스트용 관계 추출 스텁.
"""


def run(entities_dir: str, source: str | None = None) -> None:
    """관계 추출 대신 호출 인자만 출력한다."""
    print(f"[EXTRACT:Relations] entities_dir={entities_dir}, source={source}")
