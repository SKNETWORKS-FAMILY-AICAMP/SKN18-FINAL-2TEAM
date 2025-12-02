"""
테스트용 제약 조건 적용 스텁.
"""


def run() -> None:
    """실제 Neo4j 대신 단순히 메시지를 출력한다."""
    print("[KG:MAINTENANCE] apply_constraints called")
