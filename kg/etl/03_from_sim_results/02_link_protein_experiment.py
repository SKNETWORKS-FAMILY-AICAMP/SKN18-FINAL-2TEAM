"""
테스트용 시뮬 결과 링크 스텁.
"""


def run(sim_results) -> None:
    """연결할 시뮬 결과 개수만 출력한다."""
    count = len(sim_results) if sim_results else 0
    print(f"[KG:SIM] link_protein_experiment count={count}")
