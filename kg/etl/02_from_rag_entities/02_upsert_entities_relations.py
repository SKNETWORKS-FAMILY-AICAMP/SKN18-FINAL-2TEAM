"""
테스트용 엔터티/관계 업서트 스텁.
"""


def run(entities) -> None:
    """받은 엔터티 수만 출력한다."""
    count = len(entities) if entities else 0
    print(f"[KG:RAG_ENTITIES] upsert_entities_relations count={count}")
