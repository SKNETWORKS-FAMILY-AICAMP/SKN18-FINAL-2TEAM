"""
Neo4j 데이터베이스 연결 및 쿼리 유틸리티
"""

from neo4j import GraphDatabase
from typing import Optional, Dict, List, Any


class Neo4jConnector:
    """Neo4j 데이터베이스 연결 클래스"""
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Neo4j 연결 초기화
        
        Args:
            uri: Neo4j 데이터베이스 URI (예: bolt://localhost:7687)
            user: 사용자 이름
            password: 비밀번호
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """데이터베이스 연결 종료"""
        self.driver.close()
    
    def execute_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Cypher 쿼리 실행
        
        Args:
            query: 실행할 Cypher 쿼리
            parameters: 쿼리 파라미터
            
        Returns:
            쿼리 결과 리스트
        """
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    
    def test_connection(self) -> bool:
        """
        데이터베이스 연결 테스트
        
        Returns:
            연결 성공 여부
        """
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            print(f"연결 실패: {e}")
            return False

