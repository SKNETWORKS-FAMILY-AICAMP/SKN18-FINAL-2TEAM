import time
import sys
import os
from tqdm import tqdm  # 진행바 라이브러리 추가

# src 폴더 경로 설정
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from db_connector import Neo4jConnector
from queries import PrimeKGQueries

class PrimeKGLoader:
    def __init__(self, uri, user, password):
        self.connector = Neo4jConnector(uri, user, password)

    def clear_database(self):
        """데이터베이스의 모든 노드와 관계 삭제 (배치 처리로 메모리 절약)"""
        print("\n🗑️  기존 데이터 삭제 중...")
        try:
            # 제약 조건 삭제
            print("  제약 조건 삭제 중...")
            drop_constraints_query = """
            SHOW CONSTRAINTS
            """
            constraints = self.connector.execute_query(drop_constraints_query)
            for constraint in constraints:
                constraint_name = constraint.get('name', '')
                if constraint_name:
                    try:
                        self.connector.execute_query(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
                    except:
                        pass
            
            # APOC를 사용한 배치 삭제 (메모리 효율적)
            print("  노드와 관계 삭제 중... (배치 처리)")
            try:
                # APOC를 사용한 배치 삭제
                batch_delete_query = """
                CALL apoc.periodic.iterate(
                "MATCH (n) RETURN n",
                "DETACH DELETE n",
                {batchSize: 1000, parallel: false}
                )
                """
                self.connector.execute_query(batch_delete_query)
                print("✅ 데이터베이스가 초기화되었습니다.\n")
            except Exception as apoc_error:
                # APOC가 없거나 실패한 경우, 작은 배치로 직접 삭제
                print("  APOC 배치 삭제 실패, 직접 삭제 시도...")
                try:
                    # 관계 먼저 삭제
                    rel_count = 1
                    while rel_count > 0:
                        delete_rels_query = """
                        MATCH ()-[r]->()
                        WITH r LIMIT 10000
                        DELETE r
                        RETURN count(r) as deleted
                        """
                        result = self.connector.execute_query(delete_rels_query)
                        rel_count = result[0]['deleted'] if result else 0
                        if rel_count > 0:
                            print(f"    관계 {rel_count}개 삭제됨...")
                    
                    # 노드 삭제
                    node_count = 1
                    while node_count > 0:
                        delete_nodes_query = """
                        MATCH (n)
                        WITH n LIMIT 10000
                        DELETE n
                        RETURN count(n) as deleted
                        """
                        result = self.connector.execute_query(delete_nodes_query)
                        node_count = result[0]['deleted'] if result else 0
                        if node_count > 0:
                            print(f"    노드 {node_count}개 삭제됨...")
                    
                    print("✅ 데이터베이스가 초기화되었습니다.\n")
                except Exception as direct_error:
                    print(f"⚠️  직접 삭제도 실패: {direct_error}")
                    print("💡 해결 방법:")
                    print("   1. Neo4j 컨테이너 재시작: docker restart neo4j-rag")
                    print("   2. 데이터 폴더 삭제 후 재시작: docker-compose down && rm -rf data && docker-compose up -d")
                    raise direct_error
        except Exception as e:
            print(f"⚠️  초기화 중 오류: {e}")
            print("💡 해결 방법:")
            print("   1. Neo4j 컨테이너 재시작 후 다시 시도")
            print("   2. 또는 데이터 폴더를 직접 삭제: docker-compose down && rm -rf data && docker-compose up -d")

    def run_query_with_status(self, query, max_retries=3, retry_delay=5):
        """실제 쿼리를 실행하는 내부 함수 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                with self.connector.driver.session() as session:
                    # 쿼리가 리스트인 경우 (예: 인덱스 생성) 하나씩 실행
                    if isinstance(query, list):
                        for q in query:
                            try:
                                result = session.run(q)
                                # 제약 조건 생성의 경우 결과 확인
                                summary = result.consume()
                                if 'CONSTRAINT' in q.upper() and 'IF NOT EXISTS' not in q.upper():
                                    # 제약 조건이 이미 존재하는 경우 무시
                                    pass
                            except Exception as constraint_error:
                                # 제약 조건이 이미 존재하는 경우 무시 (IF NOT EXISTS가 없는 경우)
                                error_msg = str(constraint_error)
                                if 'EquivalentSchemaRuleAlreadyExists' in error_msg or 'already exists' in error_msg.lower():
                                    print(f"  ℹ️  제약 조건이 이미 존재합니다: {q[:60]}...")
                                    continue
                                else:
                                    raise constraint_error
                    else:
                        result = session.run(query)
                        # APOC 쿼리의 경우 결과 확인
                        if 'apoc.periodic.iterate' in query:
                            summary = result.consume()
                            if summary.counters.nodes_created == 0 and 'LOAD_NODES' in str(query):
                                print(f"  ⚠️  경고: 노드가 생성되지 않았을 수 있습니다.")
                return True
            except Exception as e:
                # 제약 조건이 이미 존재하는 경우는 오류로 처리하지 않음
                error_msg = str(e)
                if 'EquivalentSchemaRuleAlreadyExists' in error_msg or 'already exists' in error_msg.lower():
                    print(f"  ℹ️  제약 조건이 이미 존재합니다. 계속 진행합니다.")
                    return True
                
                if attempt < max_retries - 1:
                    print(f"  ⚠️  시도 {attempt + 1}/{max_retries} 실패, {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                else:
                    raise e
        return False
    
    def verify_data(self):
        """로드된 데이터 검증"""
        print("\n" + "=" * 60)
        print("📊 데이터 검증 중...")
        print("=" * 60)
        
        # CSV 파일 행 수 확인
        import pandas as pd
        import os
        
        csv_stats = {}
        csv_files = {
            'nodes': 'import/nodes.csv',
            'edges': 'import/edges.csv',
            'disease_features': 'import/disease_features.csv',
            'drug_features': 'import/drug_features.csv',
            'kg_grouped_diseases': 'import/kg_grouped_diseases.csv'
        }
        
        for name, path in csv_files.items():
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    csv_stats[name] = len(df)
                except Exception as e:
                    print(f"  ⚠️  {name} 파일 읽기 실패: {e}")
                    csv_stats[name] = 0
        
        # Neo4j 데이터 확인
        node_count = self.connector.execute_query("MATCH (n:BaseNode) RETURN count(n) as count")[0]['count']
        rel_count = self.connector.execute_query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        rel_types = self.connector.execute_query("MATCH ()-[r]->() RETURN count(DISTINCT type(r)) as count")[0]['count']
        
        print(f"\n📈 CSV 파일 통계:")
        for name, count in csv_stats.items():
            print(f"  {name:25s}: {count:,} 행")
        
        print(f"\n📈 Neo4j 데이터 통계:")
        print(f"  노드 수                    : {node_count:,}")
        print(f"  관계 수                    : {rel_count:,}")
        print(f"  관계 타입 종류             : {rel_types}개")
        
        # 관계 타입별 상세 확인
        rel_type_query = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """
        rel_types_detail = self.connector.execute_query(rel_type_query)
        print(f"\n📋 관계 타입별 상세:")
        for rel_info in rel_types_detail:
            print(f"  {rel_info['rel_type']:30s}: {rel_info['count']:,}")
        
        # 검증 결과
        print("\n" + "=" * 60)
        issues = []
        
        if 'nodes' in csv_stats and node_count < csv_stats['nodes'] * 0.9:
            issues.append(f"⚠️  노드 수 불일치: CSV {csv_stats['nodes']:,}개 vs Neo4j {node_count:,}개")
        
        if 'edges' in csv_stats and rel_count < csv_stats['edges'] * 0.9:
            issues.append(f"⚠️  관계 수 불일치: CSV {csv_stats['edges']:,}개 vs Neo4j {rel_count:,}개")
        
        if rel_types < 10:  # 예상 관계 타입이 18개이므로
            issues.append(f"⚠️  관계 타입이 적습니다: {rel_types}개 (예상: 18개)")
        
        if issues:
            print("❌ 검증 실패:")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 해결 방법:")
            print("  1. --clear 옵션으로 데이터베이스를 초기화하고 재로드")
            print("  2. Neo4j 로그 확인: docker logs neo4j-rag")
            print("  3. 메모리 부족 시 배치 크기 조정 (queries.py의 batchSize 수정)")
        else:
            print("✅ 데이터 검증 통과!")
        
        print("=" * 60 + "\n")
        
        return len(issues) == 0

    def load_all(self, verify=True):
        print("\n🚀 PrimeKG 데이터 로딩을 시작합니다... (Neo4j)\n")

        # 1. 작업 목록 정의 (표시 이름, 실행할 쿼리)
        tasks = [
            ("1/6 인덱스 생성 (필수)", PrimeKGQueries.CREATE_CONSTRAINTS),
            ("2/6 노드 로딩 (nodes.csv)", PrimeKGQueries.LOAD_NODES),
            ("3/6 엣지 연결 (edges.csv - 오래 걸림)", PrimeKGQueries.LOAD_EDGES),
            ("4/6 질병 상세정보 추가 (disease_features)", PrimeKGQueries.UPDATE_DISEASE_FEATURES),
            ("5/6 약물 상세정보 추가 (drug_features)", PrimeKGQueries.UPDATE_DRUG_FEATURES),
            ("6/6 질병 그룹 매핑 (grouped_diseases)", PrimeKGQueries.UPDATE_DISEASE_GROUPS)
        ]

        # 2. tqdm을 사용한 진행바 생성
        # ncols=100: 바 길이 조절, desc: 설명 텍스트
        failed_tasks = []
        
        with tqdm(total=len(tasks), ncols=100, colour='green') as pbar:
            
            for task_name, query in tasks:
                # 진행바 옆에 현재 작업 이름 표시
                pbar.set_description(f"Processing: {task_name}")
                
                try:
                    # 쿼리 실행 (재시도 로직 포함)
                    success = self.run_query_with_status(query, max_retries=3)
                    
                    if success:
                        # 성공 시 진행바 1칸 전진
                        pbar.update(1)
                    else:
                        failed_tasks.append(task_name)
                        print(f"\n⚠️  [{task_name}] 재시도 후에도 실패했습니다.")
                        pbar.update(1)  # 실패해도 진행바는 업데이트
                    
                except Exception as e:
                    # 에러 발생 시 상세 정보 출력
                    failed_tasks.append(task_name)
                    print(f"\n❌ 오류 발생 [{task_name}]: {e}")
                    print(f"   오류 타입: {type(e).__name__}")
                    import traceback
                    print(f"   상세 정보:\n{traceback.format_exc()}")
                    # 계속 진행 (다음 작업 시도)
                    pbar.update(1)

        # 결과 요약
        print("\n" + "=" * 60)
        if failed_tasks:
            print(f"⚠️  실패한 작업: {len(failed_tasks)}개")
            for task in failed_tasks:
                print(f"  - {task}")
            print("\n💡 해결 방법:")
            print("  1. Neo4j 로그 확인: docker logs neo4j-rag")
            print("  2. --clear 옵션으로 재시도")
            print("  3. Docker 컨테이너 재시작: docker restart neo4j-rag")
        else:
            print("✨ 모든 데이터 로딩 작업이 완료되었습니다!")
        print("=" * 60)
        
        # 데이터 검증
        if verify:
            self.verify_data()
        
        self.connector.close()

if __name__ == "__main__":
    import argparse
    
    # 설정 값 (docker-compose.yml과 일치해야 함)
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "neo4jpass"  # docker-compose.yml의 NEO4J_AUTH=neo4j/neo4jpass와 일치 

    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='PrimeKG 데이터를 Neo4j에 로드')
    parser.add_argument('--clear', action='store_true', help='기존 데이터를 삭제하고 새로 로드')
    parser.add_argument('--no-verify', action='store_true', help='데이터 검증 건너뛰기')
    args = parser.parse_args()

    loader = PrimeKGLoader(URI, USER, PASSWORD)
    
    # 연결 테스트
    if not loader.connector.test_connection():
        print("❌ Neo4j 연결에 실패했습니다. Docker 컨테이너가 실행 중인지 확인하세요.")
        exit(1)
    
    # 기존 데이터 삭제 옵션
    if args.clear:
        loader.clear_database()
    
    loader.load_all(verify=not args.no_verify)