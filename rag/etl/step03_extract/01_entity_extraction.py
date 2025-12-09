"""
테스트용 엔터티 추출 스텁.
"""


def run(processed_dir: str, entities_dir: str, source: str | None = None) -> None:
    """엔터티 추출 대신 호출 인자만 출력한다."""
    print(
        "[EXTRACT:Entities] "
        f"processed_dir={processed_dir}, entities_dir={entities_dir}, source={source}"
    )
