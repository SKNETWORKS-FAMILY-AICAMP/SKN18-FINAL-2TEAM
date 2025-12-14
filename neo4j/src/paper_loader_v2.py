import sys
import os
from tqdm import tqdm

# src 폴더 경로 설정 (paper_loader.py가 프로젝트 루트에 있다고 가정)
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from db_connector import Neo4jConnector
from queries import PaperRAGQueries, ProtocolQueries, ClinicalTrialQueries


class PaperLoader:
    """Neo4j 적재/연결 로더

    - PaperRAGQueries / ProtocolQueries / ClinicalTrialQueries 의 쿼리를 순서대로 실행합니다.
    - BaseNode(PrimeKG)는 보존하고, 나머지 라벨은 clear 옵션 시 제거합니다.
    """

    def __init__(self, uri: str, user: str, password: str):
        self.connector = Neo4jConnector(uri, user, password)

    def _run(self, query: str, desc: str = ""):
        if not query or not isinstance(query, str):
            return
        self.connector.execute_query(query, description=desc)

    def clear_graph(self):
        """PrimeKG(BaseNode) 제외하고 RAG/ETL에서 생성한 노드들을 정리"""

        # 주의: BaseNode(PrimeKG)는 남깁니다.
        labels_to_clear = [
            # paper
            "Article", "Section", "Chunk",
            "Reference", "CitedWork",
            "Entity", "Mention",
            "Topic", "Domain", "Journal", "StudyDesign",
            # experiments
            "Experiment", "CategoryParent", "CategoryLeaf",
            "ExpMaterial", "ExpEquipment",
            # legacy (과거에 Material/Equipment로 만들었다면 같이 지움)
            "Material", "Equipment",
            # protocol
            "Protocol", "ProtocolChunk", "ProtocolReference",
            # clinical
            "ClinicalTrial",
        ]

        for label in labels_to_clear:
            q = f"""
            CALL apoc.periodic.iterate(
              "MATCH (n:{label}) RETURN n",
              "DETACH DELETE n",
              {{batchSize: 5000, parallel: true}}
            )
            """
            self._run(q, desc=f"[CLEAR] :{label}")

        # 잘못 연결된 관계 정리(안전장치)
        cleanup_rels = [
            # Protocol -> 논문 Chunk 연결(잘못된 경우) 제거
            (
                """
                MATCH (p:Protocol)-[r:HAS_CHUNK]->(n)
                WHERE n:Chunk OR n.chunk_id IS NOT NULL
                DELETE r
                RETURN count(r) AS removed
                """,
                "cleanup Protocol-[:HAS_CHUNK]->Chunk"
            ),
            # Section -> ProtocolChunk 연결(잘못된 경우) 제거
            (
                """
                MATCH (s:Section)-[r:HAS_CHUNK]->(n)
                WHERE n:ProtocolChunk OR n.chunking_id IS NOT NULL
                DELETE r
                RETURN count(r) AS removed
                """,
                "cleanup Section-[:HAS_CHUNK]->ProtocolChunk"
            ),
        ]
        for q, d in cleanup_rels:
            self._run(q, desc=d)

    def load(self, clear: bool = False):
        if clear:
            self.clear_graph()

        # ---------------------------
        # 0) 인덱스/제약조건
        # ---------------------------
        paper_indices = []
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_CONSTRAINTS", []))
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_VECTOR_INDEX", []))

        protocol_indices = []
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_CONSTRAINTS", []))
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_VECTOR_INDEX", []))

        clinical_indices = []
        clinical_indices.extend(getattr(ClinicalTrialQueries, "CREATE_CONSTRAINTS", []))

        tasks = [
            # ---------------------------
            # [Part 1] Paper
            # ---------------------------
            ("1. [Paper] 제약조건/인덱스", paper_indices),
            ("2. [Paper] Article 로딩", PaperRAGQueries.LOAD_ARTICLES),
            ("3. [Paper] Figure/Table/Equation (Article property)", [
                PaperRAGQueries.LOAD_FIGURES,
                PaperRAGQueries.LOAD_TABLES,
                PaperRAGQueries.LOAD_EQUATIONS,
            ]),
            ("4. [Paper] Section/Chunk 로딩", [
                PaperRAGQueries.LOAD_SECTIONS,
                PaperRAGQueries.LOAD_CHUNKS,
            ]),
            ("5. [Paper] Chunk NEXT 연결", PaperRAGQueries.LINK_CHUNKS_NEXT),
            ("6. [Paper] References 로딩", PaperRAGQueries.LOAD_REFERENCES),
            ("7. [Paper] Experiments(+ExpMaterial/ExpEquipment) 로딩", PaperRAGQueries.LOAD_EXPERIMENTS),
            ("8. [Paper] Entities 로딩(entity_id 기반)", PaperRAGQueries.LOAD_ENTITIES),
            ("9. [Paper] Mentions 노드 유지 + (Article/Section/Entity 연결)", PaperRAGQueries.LOAD_MENTIONS_WITH_NODES),
            ("10. [Paper] PrimeKG 1차(name) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG),
            ("11. [Paper] PrimeKG 2차(primekg_label) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG_SECONDARY),

            # ---------------------------
            # [Part 2] Protocol
            # ---------------------------
            ("12. [Protocol] 제약조건/인덱스", protocol_indices),
            ("13. [Protocol] 메타데이터 로딩", ProtocolQueries.LOAD_PROTOCOL_METADATA),
            ("14. [Protocol] 레퍼런스 로딩", ProtocolQueries.LOAD_PROTOCOL_REFERENCES),
            ("15. [Protocol] Chunk/임베딩 로딩", ProtocolQueries.LOAD_PROTOCOL_CHUNKS),

            # ---------------------------
            # [Part 3] ClinicalTrials
            # ---------------------------
            ("16. [ClinicalTrial] 제약조건", clinical_indices),
            ("17. [ClinicalTrial] 메타데이터 로딩", ClinicalTrialQueries.LOAD_METADATA),
            # 아래 2개는 '기존 Mention 노드가 이미 있고, 거기에 nct_id가 들어있다'는 전제의 연결만 수행
            ("18. [ClinicalTrial] Trial -> Mention 연결", ClinicalTrialQueries.LINK_TRIAL_MENTIONS),
            ("19. [ClinicalTrial] (mention 기반) Trial -> Entity 연결/집계", ClinicalTrialQueries.LINK_TRIAL_ENTITIES_FROM_MENTIONS),
        ]

        # 실행
        for desc, q in tqdm(tasks, desc="Neo4j Loading"):
            if isinstance(q, list):
                for sub_q in q:
                    self._run(sub_q, desc=desc)
            else:
                self._run(q, desc=desc)


if __name__ == "__main__":
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpass")

    loader = PaperLoader(URI, USER, PASSWORD)

    if loader.connector.test_connection():
        loader.load(clear=True)
