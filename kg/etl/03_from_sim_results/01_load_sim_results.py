"""
테스트용 시뮬 결과 로더 스텁.
"""


def run(sim_results_dir: str):
    """시뮬 결과 경로를 출력하고 더미 결과 목록을 반환한다."""
    print(f"[KG:SIM] load_sim_results sim_results_dir={sim_results_dir}")
    return [
        {
            "result_id": "SIM-STUB",
            "protein": "StubProtein",
            "experiment": "EXP-STUB",
        }
    ]
