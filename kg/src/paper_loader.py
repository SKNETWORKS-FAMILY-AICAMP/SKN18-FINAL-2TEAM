import sys
import os
from tqdm import tqdm

# src 폴더 경로 설정
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from db_connector import Neo4jConnector
# 쿼리 클래스들 임포트 (ClinicalTrialQueries 포함 확인)
from queries import PaperRAGQueries, ProtocolQueries, ClinicalTrialQueries

class PaperLoader:
    # ✅ [수정됨] 초기화 메서드 (__init__)가 반드시 있어야 합니다.
    def __init__(self, uri, user, password):
        self.connector = Neo4jConnector(uri, user, password)

    def clear_paper_data(self):
        """
        PrimeKG(BaseNode)는 보존하고, Paper RAG 및 Protocol, Clinical 관련 노드만 삭제합니다.
        """
        print("\n🗑️  데이터 초기화 중 (PrimeKG 보존)...")
        
        # 삭제할 라벨 목록
        rag_labels = [
            "Article", "Section", "Chunk", 
            "Asset", "Figure", "Table", "Equation", 
            "Keyword", "Entity", "Reference", "CitedWork", 
            "Topic", "Journal", "StudyDesign", 
            "Experiment", "Protocol", "ProtocolChunk", "ProtocolReference",
            "CategoryParent", "CategoryLeaf", "Material", "Equipment",
            "ClinicalTrial" 
        ]
        
        with tqdm(total=len(rag_labels), ncols=100, colour='red') as pbar:
            for label in rag_labels:
                pbar.set_description(f"Deleting {label}")
                query = f"""
                CALL apoc.periodic.iterate(
                    'MATCH (n:{label}) RETURN n', 
                    'DETACH DELETE n', 
                    {{batchSize: 10000, parallel: true}}
                )
                """
                try:
                    self.connector.execute_query(query)
                except Exception as e:
                    print(f"  ⚠️ {label} 삭제 중 경고: {e}")
                pbar.update(1)
        
        print("✨ 초기화 완료.\n")

    def fix_connections(self):
        """
        [데이터 무결성 보정]
        ProtocolChunk와 논문 Chunk가 섞이지 않도록 관계를 정리합니다.
        """
        print("\n🔧 데이터 무결성 보정 중...")
        
        queries = [
            # 1. Protocol -> 논문 Chunk (chunk_id 보유) 잘못된 연결 삭제
            ("""
            MATCH (p:Protocol)-[r:HAS_CHUNK]->(n)
            WHERE n.chunk_id IS NOT NULL
            DELETE r
            RETURN count(r) as count
            """, "Protocol -> 논문 Chunk 연결 삭제"),

            # 2. Section -> 프로토콜 Chunk (chunking_id 보유) 잘못된 연결 삭제
            ("""
            MATCH (s:Section)-[r:HAS_CHUNK]->(n)
            WHERE n.chunking_id IS NOT NULL
            DELETE r
            RETURN count(r) as count
            """, "Section -> 프로토콜 Chunk 연결 삭제"),

            # 3. ProtocolChunk 노드에서 불필요한 'Chunk' 라벨 제거
            ("""
            MATCH (n)
            WHERE n.chunking_id IS NOT NULL AND n:Chunk
            REMOVE n:Chunk
            RETURN count(n) as count
            """, "ProtocolChunk에서 Chunk 라벨 제거")
        ]

        for query, desc in queries:
            try:
                result = self.connector.execute_query(query)
                count = result[0]['count'] if result else 0
                if count > 0:
                    print(f"  ✅ {desc}: {count}개 처리됨")
            except Exception as e:
                print(f"  ⚠️ {desc} 처리 중 오류: {e}")

    def load(self, clear=False):
        if clear: 
            self.clear_paper_data()

        print("🚀 논문, 프로토콜, 임상실험 지식 그래프 구축 시작...")
        
        # 인덱스 리스트 준비
        paper_indices = getattr(PaperRAGQueries, 'CREATE_CONSTRAINTS', []) + getattr(PaperRAGQueries, 'CREATE_VECTOR_INDEX', [])
        protocol_indices = getattr(ProtocolQueries, 'CREATE_CONSTRAINTS', []) + getattr(ProtocolQueries, 'CREATE_VECTOR_INDEX', [])
        clinical_indices = getattr(ClinicalTrialQueries, 'CREATE_CONSTRAINTS', [])

        tasks = [
            # --- [Part 1] 논문(Paper) 데이터 ---
            ("1. [Paper] 제약조건 & 벡터 인덱스", paper_indices),
            ("2. [Paper] 논문(Article) 로딩", PaperRAGQueries.LOAD_ARTICLES),
            ("3. [Paper] 그림/표/수식 로딩", [PaperRAGQueries.LOAD_FIGURES, PaperRAGQueries.LOAD_TABLES, PaperRAGQueries.LOAD_EQUATIONS]),
            ("4. [Paper] 섹션/청크 로딩", [PaperRAGQueries.LOAD_SECTIONS, PaperRAGQueries.LOAD_CHUNKS]),
            ("5. [Paper] 청크 순서 연결", PaperRAGQueries.LINK_CHUNKS_NEXT),
            ("6. [Paper] 참고문헌/실험 로딩", [PaperRAGQueries.LOAD_REFERENCES, PaperRAGQueries.LOAD_EXPERIMENTS]),

            # --- [Part 2] 프로토콜(Protocol) 데이터 ---
            ("7. [Protocol] 인덱스 생성", protocol_indices),
            ("8. [Protocol] 메타/재료/레퍼런스", [ProtocolQueries.LOAD_PROTOCOL_METADATA, ProtocolQueries.LOAD_PROTOCOL_MATERIALS, ProtocolQueries.LOAD_PROTOCOL_REFERENCES]),
            ("9. [Protocol] 청크/임베딩 로딩", ProtocolQueries.LOAD_PROTOCOL_CHUNKS),

            # --- [Part 3] 임상실험(Clinical Trial) 데이터 ---
            ("10. [Clinical] 인덱스 생성", clinical_indices),
            ("11. [Clinical] 메타데이터 로딩", ClinicalTrialQueries.LOAD_METADATA),
            ("12. [Clinical] 엔티티 연결 (Trial -> Entity)", ClinicalTrialQueries.LOAD_CLINICAL_ENTITIES),

            # --- [Part 4] 지식 연결 (공통) ---
            # 논문/프로토콜/임상실험의 Entity들을 통합하여 메타데이터 보강
            ("13. [Common] 엔티티 메타데이터 보강 (entities_all_dbs.csv)", PaperRAGQueries.LOAD_ENTITIES),
            ("14. [Common] 청크-엔티티 관계", PaperRAGQueries.LOAD_KEYWORDS_RELATION),
            
            # ✅ PrimeKG 연결: 모든 Entity가 로딩된 후 마지막에 수행
            ("15. [Common] PrimeKG 연결 (1차: Name)", PaperRAGQueries.CONNECT_TO_PRIMEKG),
            ("16. [Common] PrimeKG 연결 (2차: Standard Name)", PaperRAGQueries.CONNECT_TO_PRIMEKG_SECONDARY)
        ]

        with tqdm(total=len(tasks), ncols=100, colour='cyan') as pbar:
            for name, query in tasks:
                pbar.set_description(f"Processing: {name.split(']')[1] if ']' in name else name}")
                try:
                    queries = query if isinstance(query, list) else [query]
                    for q in queries: 
                        if q and q.strip(): 
                            self.connector.execute_query(q)
                except Exception as e:
                    print(f"\n❌ 오류 ({name}): {e}")
                pbar.update(1)
        
        self.fix_connections()
        print("\n✅ 모든 작업(Paper + Protocol + Clinical)이 완료되었습니다!")
        self.connector.close()

if __name__ == "__main__":
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4jpass"  # docker-compose에 맞게 수정

    loader = PaperLoader(URI, USER, PASSWORD)

    if loader.connector.test_connection():
        loader.load(clear=True)