"""
테스트용 그래프 메트릭 재계산 스텁.
"""


def run() -> None:
    """Neo4j 메트릭 대신 호출 사실만 출력한다."""
    print("[KG:MAINTENANCE] recompute_graph_metrics called")
