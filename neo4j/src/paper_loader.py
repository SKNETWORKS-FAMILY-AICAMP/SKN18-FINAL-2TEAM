# paper_loader.py
import sys
import os
from tqdm import tqdm

# src 폴더 경로 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from db_connector import Neo4jConnector
from queries import PaperRAGQueries

class PaperLoader:
    def __init__(self, uri, user, password):
        self.connector = Neo4jConnector(uri, user, password)

    def clear_paper_data(self):
        print("🗑️  Paper RAG 데이터 초기화 중 (PrimeKG 보존)...")
        # Entity 노드 추가됨
        labels = [
            "Article", "Section", "Chunk", "Asset", "Figure", "Equation",
            "Keyword", "Entity", "Reference", "Topic", "Journal", "StudyDesign"
        ]
        for label in labels:
            query = f"CALL apoc.periodic.iterate('MATCH (n:{label}) RETURN n', 'DETACH DELETE n', {{batchSize:10000}})"
            self.connector.execute_query(query)

    def load(self, clear=False):
        if clear: self.clear_paper_data()

        print("\n🚀 논문 RAG 지식 그래프 구축 (Hybrid Model)")
        
        # 작업 리스트 (순서 중요)
        tasks = [
            ("1. 제약조건 & 인덱스", PaperRAGQueries.CREATE_CONSTRAINTS + PaperRAGQueries.CREATE_VECTOR_INDEX),
            ("2. 논문(Article) 로딩", PaperRAGQueries.LOAD_ARTICLES),
            ("3. 그림(Figure) 로딩", PaperRAGQueries.LOAD_FIGURES),
            ("4. 수식(Equation) 로딩", PaperRAGQueries.LOAD_EQUATIONS),
            ("5. 섹션(Section) 로딩 & 그림 연결", PaperRAGQueries.LOAD_SECTIONS),
            ("6. 청크(Chunk) 로딩", PaperRAGQueries.LOAD_CHUNKS),
            ("7. 청크 순서 연결", PaperRAGQueries.LINK_CHUNKS_NEXT),
            ("8. 참고문헌(Reference) 로딩", PaperRAGQueries.LOAD_REFERENCES),
            
            # [Entity & Keyword 분리 로딩]
            ("9-1. 엔티티(Entity) 노드 생성", PaperRAGQueries.LOAD_ENTITIES),
            ("9-2. 키워드 및 정규화 연결", PaperRAGQueries.LOAD_KEYWORDS_RELATION),
            
            ("10. ★ PrimeKG 지식 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG)
        ]

        with tqdm(total=len(tasks), ncols=100, colour='cyan') as pbar:
            for name, query in tasks:
                pbar.set_description(f"Processing: {name}")
                try:
                    queries = query if isinstance(query, list) else [query]
                    for q in queries: self.connector.execute_query(q)
                except Exception as e:
                    print(f"\n❌ 오류 ({name}): {e}")
                pbar.update(1)
        
        print("\n✅ 그래프 구축 완료!")
        self.connector.close()

if __name__ == "__main__":
    # 설정 (Docker 환경에 맞게 수정)
    loader = PaperLoader("bolt://localhost:7687", "neo4j", "password")
    
    if loader.connector.test_connection():
        loader.load(clear=True) # 처음 실행 시 True 권장
    else:
        print("❌ DB 연결 실패")