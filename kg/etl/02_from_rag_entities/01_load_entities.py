"""
테스트용 엔터티 로더 스텁.
"""


def run(entities_dir: str, source: str | None):
    """엔터티 디렉터리와 소스를 출력하고 더미 엔터티 목록을 반환한다."""
    print(
        "[KG:RAG_ENTITIES] load_entities "
        f"entities_dir={entities_dir}, source={source}"
    )
    return [
        {
            "entity_id": "ENT-STUB",
            "type": "Protein",
            "name": "Stub Protein",
            "source": source or "all",
        }
    ]
