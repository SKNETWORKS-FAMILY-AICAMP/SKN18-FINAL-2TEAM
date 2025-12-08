# paper_loader.py
import sys
import os
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from db_connector import Neo4jConnector
from queries import PaperRAGQueries

class PaperLoader:
    def __init__(self, uri, user, password):
        self.connector = Neo4jConnector(uri, user, password)

    def clear_paper_data(self):
        """
        PrimeKG(BaseNode)는 보존하고, Paper RAG 관련 노드만 삭제합니다.
        """
        print("\n🗑️  Paper RAG 데이터 초기화 중 (PrimeKG는 안전하게 보존됩니다)...")
        
        # 1. 삭제할 라벨 목록 정의
        # 주의: 'BaseNode'나 PrimeKG 관련 라벨이 여기 포함되면 안 됩니다!
        rag_labels = [
            "Article",          # 논문
            "Section", "Chunk", # 본문 구조
            "Asset", "Figure", "Table", "Equation", # 자산
            "Keyword", "Entity", # 추출된 키워드/엔티티 (PrimeKG와 연결되는 다리 역할)
            "Reference",        # 개별 참고문헌
            "CitedWork",        # [NEW] 통합된 참고문헌 노드 (이전 대화에서 추가됨)
            "Topic", "Journal", "StudyDesign" # 메타데이터
        ]
        
        # 2. 라벨별로 순차 삭제 (메모리 보호를 위해 배치 처리)
        with tqdm(total=len(rag_labels), ncols=100, colour='red') as pbar:
            for label in rag_labels:
                pbar.set_description(f"Deleting {label}")
                
                # 해당 라벨을 가진 노드를 찾아서 삭제 (관계도 같이 끊어짐)
                # PrimeKG 노드(BaseNode)는 건드리지 않음
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
        
        print("✨ 초기화 완료: Paper RAG 데이터가 삭제되었습니다.\n")

    def load(self, clear=False):
        # 1. 초기화 요청 시 삭제 실행
        if clear: 
            self.clear_paper_data()

        print("🚀 논문 RAG 지식 그래프 구축 시작...")
        
        # 로딩 작업 목록
        tasks = [
            ("1. 제약조건 & 인덱스", PaperRAGQueries.CREATE_CONSTRAINTS + PaperRAGQueries.CREATE_VECTOR_INDEX),
            ("2. 논문(Article) 로딩", PaperRAGQueries.LOAD_ARTICLES),
            
            # [자산 먼저 로딩]
            ("3. 그림(Figure) 로딩", PaperRAGQueries.LOAD_FIGURES),
            ("4. 표(Table) 로딩", PaperRAGQueries.LOAD_TABLES),
            ("5. 수식(Equation) 로딩", PaperRAGQueries.LOAD_EQUATIONS),
            
            # [섹션 로딩] - 여기서 자산과 연결됨
            ("6. 섹션(Section) 로딩", PaperRAGQueries.LOAD_SECTIONS),
            
            # [청크 로딩]
            ("7. 청크(Chunk) 로딩", PaperRAGQueries.LOAD_CHUNKS),
            ("8. 청크 순서 연결", PaperRAGQueries.LINK_CHUNKS_NEXT),
            
            # [참고문헌 로딩] - 통합 로직 적용된 쿼리 사용
            ("9. 참고문헌(Reference) 로딩", PaperRAGQueries.LOAD_REFERENCES),
            
            # [지식 연결]
            ("10. 엔티티(Entity) 노드 생성", PaperRAGQueries.LOAD_ENTITIES),
            ("11. 키워드 관계 연결", PaperRAGQueries.LOAD_KEYWORDS_RELATION),
            ("12. PrimeKG 지식 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG)
        ]

        # 작업 실행
        with tqdm(total=len(tasks), ncols=100, colour='cyan') as pbar:
            for name, query in tasks:
                pbar.set_description(f"Processing: {name}")
                try:
                    queries = query if isinstance(query, list) else [query]
                    for q in queries: 
                        self.connector.execute_query(q)
                except Exception as e:
                    print(f"\n❌ 오류 ({name}): {e}")
                    # 오류가 나도 다음 단계 진행 (필요시 raise로 변경)
                pbar.update(1)
        
        print("\n✅ 모든 작업이 완료되었습니다!")
        self.connector.close()

if __name__ == "__main__":
    # 설정 값 (docker-compose 환경에 맞게 수정)
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "password"

    loader = PaperLoader(URI, USER, PASSWORD)
    
    if loader.connector.test_connection():
        # clear=True로 설정하여 "삭제 후 다시 로딩" 실행
        loader.load(clear=True)