import sys
import os
from tqdm import tqdm

# src 폴더 경로 설정 (paper_loader.py가 프로젝트 루트에 있다고 가정)
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from db_connector import Neo4jConnector
from queries_v2 import PaperRAGQueries, ProtocolQueries, ClinicalTrialQueries


class PaperLoader:
    """Neo4j 적재/연결 로더

    - PaperRAGQueries / ProtocolQueries / ClinicalTrialQueries 의 쿼리를 순서대로 실행합니다.
    - BaseNode(PrimeKG)는 보존하고, 나머지 라벨은 clear 옵션 시 제거합니다.
    """

    def __init__(self, uri: str, user: str, password: str):
        self.connector = Neo4jConnector(uri, user, password)

    def _run(self, query: str, desc: str = ""):
        if desc:
            # 쿼리가 리스트인 경우(여러 쿼리 묶음) 처리하지 않고, 단일 문자열일 때만 실행한다고 가정
            # (아래 load 함수에서 리스트를 풀어서 호출하므로 여기서는 단순 실행)
            pass 
        
        # tqdm progress bar와 겹치지 않게 로그 출력 (선택 사항)
        # print(f"[NEO4J][RUN] {desc}") 
        self.connector.execute_query(query)

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

        print("[CLEAR] Start clearing graph (excluding BaseNode)...")
        for label in tqdm(labels_to_clear, desc="Clearing Labels"):
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
        # 0) 인덱스/제약조건 준비 (쿼리 리스트 취합)
        # ---------------------------
        
        # [PaperRAG]
        paper_indices = []
        # 1. 제약조건 (Unique Constraints)
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_CONSTRAINTS", []))
        # 2. [NEW] 일반 인덱스 (검색/연결 속도 향상용) - queries_v2.py에 추가된 내용 반영
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_INDEXES", []))
        # 3. 벡터 인덱스
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_VECTOR_INDEX", []))

        # [Protocol]
        protocol_indices = []
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_CONSTRAINTS", []))
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_INDEXES", [])) # 혹시 추가될 경우 대비
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_VECTOR_INDEX", []))

        # [ClinicalTrial]
        clinical_indices = []
        clinical_indices.extend(getattr(ClinicalTrialQueries, "CREATE_CONSTRAINTS", []))
        # [NEW] 일반 인덱스 (NCT ID 검색용)
        clinical_indices.extend(getattr(ClinicalTrialQueries, "CREATE_INDEXES", []))

        tasks = [
            # ---------------------------
            # [Part 1] Paper
            # ---------------------------
            ("1. [Paper] 제약조건/인덱스 생성", paper_indices),
            ("2. [Paper] Article 로딩", PaperRAGQueries.LOAD_ARTICLES),
            ("3. [Paper] Figure/Table/Equation 메타 로딩", [
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
            
            # Mentions 로딩 (최적화된 버전 사용)
            ("9-1. [Paper] Mentions 노드 생성 (집계 제외)", PaperRAGQueries.LOAD_MENTIONS_FAST),
            ("9-2. [Paper] Mentions-Section 연결", PaperRAGQueries.LINK_MENTIONS_TO_SECTIONS),
            ("9-3. [Paper] Article-Entity 집계 계산", PaperRAGQueries.CALC_ARTICLE_ENTITY_AGGREGATION),
            # 1. 실험 이동 (아까 한 것)
            
            
            # PrimeKG 연결 (인덱스 덕분에 빨라짐)
            ("10. [Paper] PrimeKG 1차(name) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG),
            ("11. [Paper] PrimeKG 2차(primekg_label) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG_SECONDARY),

            # ---------------------------
            # [Part 2] Protocol
            # ---------------------------
            ("12. [Protocol] 제약조건/인덱스 생성", protocol_indices),
            ("13. [Protocol] 메타데이터 로딩", ProtocolQueries.LOAD_PROTOCOL_METADATA),
            # ("14. [Protocol] 레퍼런스 로딩", ProtocolQueries.LOAD_PROTOCOL_REFERENCES), # 필요시 주석 해제
            ("15. [Protocol] Chunk/임베딩 로딩", ProtocolQueries.LOAD_PROTOCOL_CHUNKS),

            # [중요] 마이그레이션 단계 (Experiment & Protocol)
            ("16. [Migration] Experiment: CategoryLeaf -> Entity(Method)", PaperRAGQueries.LOAD_EXPERIMENTS_METHOD_AS_ENTITY),
            ("17. [Migration] Protocol: CategoryLeaf -> Entity(Method)", ProtocolQueries.MIGRATE_PROTOCOL_TO_ENTITY_METHOD),

            # ---------------------------
            # [Part 3] ClinicalTrials
            # ---------------------------
            ("18. [ClinicalTrial] 제약조건/인덱스 생성", clinical_indices),
            ("19. [ClinicalTrial] 메타데이터 로딩", ClinicalTrialQueries.LOAD_METADATA),
            ("20. [ClinicalTrial] Trial용 Mention 생성 및 연결", ClinicalTrialQueries.LOAD_TRIAL_MENTIONS),
            ("21. [ClinicalTrial] (mention 기반) Trial -> Entity 집계", ClinicalTrialQueries.LINK_TRIAL_ENTITIES_FROM_MENTIONS),

            # ---------------------------
            # [Part 4] Cleanup (마지막 자동 청소)
            # ---------------------------
            ("99. [Cleanup] 구버전(CategoryLeaf) 연결 삭제 및 고아 노드 정리", [
                "MATCH (:Experiment)-[r:HAS_LEAF_CATEGORY]->() DELETE r",
                "MATCH (:Protocol)-[r:HAS_LEAF_CATEGORY]->() DELETE r",
                "MATCH (n:CategoryLeaf) WHERE NOT (n)--() DELETE n"
            ])
        ]

        # 실행
        for desc, q in tqdm(tasks, desc="Neo4j Full Loading & Migration"):
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
        print("🚀 [Full Load & Migration] 전체 데이터 적재 및 구조 개선 작업을 시작합니다.")
        # clear=True로 기존 데이터를 지우고, 처음부터 깨끗하게 다시 적재합니다.
        # 이 과정에서 마이그레이션과 자동 청소까지 모두 수행됩니다.
        loader.load(clear=True)
        print("✅ [Done] 모든 데이터 적재, 변환, 청소가 완료되었습니다!")