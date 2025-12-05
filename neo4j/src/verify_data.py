"""
데이터 검증 및 복구 유틸리티
로드된 데이터가 완전한지 확인하고 문제를 진단합니다.
"""

import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_connector import Neo4jConnector


def verify_and_report(uri="bolt://localhost:7687", user="neo4j", password="password"):
    """데이터 검증 및 리포트 생성"""
    connector = Neo4jConnector(uri, user, password)
    
    if not connector.test_connection():
        print("❌ Neo4j 연결 실패")
        return False
    
    print("\n" + "=" * 70)
    print("📊 PrimeKG 데이터 검증 리포트")
    print("=" * 70)
    
    # CSV 파일 통계
    csv_stats = {}
    csv_files = {
        'nodes': 'import/nodes.csv',
        'edges': 'import/edges.csv',
        'disease_features': 'import/disease_features.csv',
        'drug_features': 'import/drug_features.csv',
        'kg_grouped_diseases': 'import/kg_grouped_diseases.csv'
    }
    
    print("\n📁 CSV 파일 통계:")
    print("-" * 70)
    for name, path in csv_files.items():
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
        if os.path.exists(full_path):
            try:
                df = pd.read_csv(full_path)
                csv_stats[name] = len(df)
                print(f"  {name:25s}: {csv_stats[name]:,} 행")
            except Exception as e:
                print(f"  {name:25s}: ❌ 읽기 실패 - {e}")
                csv_stats[name] = 0
        else:
            print(f"  {name:25s}: ❌ 파일 없음")
            csv_stats[name] = 0
    
    # Neo4j 통계
    print("\n🗄️  Neo4j 데이터베이스 통계:")
    print("-" * 70)
    
    node_count = connector.execute_query("MATCH (n:BaseNode) RETURN count(n) as count")[0]['count']
    rel_count = connector.execute_query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
    rel_types_count = connector.execute_query("MATCH ()-[r]->() RETURN count(DISTINCT type(r)) as count")[0]['count']
    
    print(f"  노드 수 (BaseNode)        : {node_count:,}")
    print(f"  관계 수                   : {rel_count:,}")
    print(f"  관계 타입 종류            : {rel_types_count}개")
    
    # 관계 타입별 상세
    rel_type_query = """
    MATCH ()-[r]->()
    RETURN type(r) as rel_type, count(r) as count
    ORDER BY count DESC
    """
    rel_types_detail = connector.execute_query(rel_type_query)
    
    print(f"\n📋 관계 타입별 상세 (총 {len(rel_types_detail)}개):")
    print("-" * 70)
    for rel_info in rel_types_detail:
        print(f"  {rel_info['rel_type']:35s}: {rel_info['count']:,}")
    
    # 검증 결과
    print("\n" + "=" * 70)
    print("🔍 검증 결과:")
    print("-" * 70)
    
    issues = []
    warnings = []
    
    # 노드 수 검증
    if 'nodes' in csv_stats:
        if node_count == 0:
            issues.append("❌ 노드가 하나도 없습니다!")
        elif node_count < csv_stats['nodes'] * 0.9:
            issues.append(f"⚠️  노드 수 불일치: CSV {csv_stats['nodes']:,}개 vs Neo4j {node_count:,}개 ({node_count/csv_stats['nodes']*100:.1f}%)")
        elif node_count < csv_stats['nodes'] * 0.95:
            warnings.append(f"⚠️  노드 수가 약간 부족: CSV {csv_stats['nodes']:,}개 vs Neo4j {node_count:,}개 ({node_count/csv_stats['nodes']*100:.1f}%)")
        else:
            print(f"✅ 노드 수 정상: {node_count:,}개")
    
    # 관계 수 검증
    if 'edges' in csv_stats:
        if rel_count == 0:
            issues.append("❌ 관계가 하나도 없습니다!")
        elif rel_count < csv_stats['edges'] * 0.9:
            issues.append(f"⚠️  관계 수 불일치: CSV {csv_stats['edges']:,}개 vs Neo4j {rel_count:,}개 ({rel_count/csv_stats['edges']*100:.1f}%)")
        elif rel_count < csv_stats['edges'] * 0.95:
            warnings.append(f"⚠️  관계 수가 약간 부족: CSV {csv_stats['edges']:,}개 vs Neo4j {rel_count:,}개 ({rel_count/csv_stats['edges']*100:.1f}%)")
        else:
            print(f"✅ 관계 수 정상: {rel_count:,}개")
    
    # 관계 타입 검증
    if rel_types_count < 10:
        issues.append(f"⚠️  관계 타입이 적습니다: {rel_types_count}개 (예상: 18개)")
    elif rel_types_count < 15:
        warnings.append(f"⚠️  관계 타입이 일부 누락되었을 수 있습니다: {rel_types_count}개 (예상: 18개)")
    else:
        print(f"✅ 관계 타입 정상: {rel_types_count}개")
    
    # 이슈 출력
    if issues:
        print("\n❌ 발견된 문제:")
        for issue in issues:
            print(f"  {issue}")
    
    if warnings:
        print("\n⚠️  경고:")
        for warning in warnings:
            print(f"  {warning}")
    
    if not issues and not warnings:
        print("\n✨ 모든 검증을 통과했습니다!")
    
    # 해결 방법 제시
    if issues:
        print("\n" + "=" * 70)
        print("💡 해결 방법:")
        print("-" * 70)
        print("  1. 데이터베이스 초기화 후 재로드:")
        print("     python src/data_loader.py --clear")
        print("\n  2. Neo4j 로그 확인:")
        print("     docker logs neo4j-rag")
        print("\n  3. Docker 컨테이너 재시작:")
        print("     docker restart neo4j-rag")
        print("\n  4. 메모리 부족 시 배치 크기 조정:")
        print("     queries.py의 batchSize를 1000~2000으로 줄이기")
        print("=" * 70)
    
    connector.close()
    return len(issues) == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='PrimeKG 데이터 검증')
    parser.add_argument('--uri', default='bolt://localhost:7687', help='Neo4j URI')
    parser.add_argument('--user', default='neo4j', help='Neo4j 사용자명')
    parser.add_argument('--password', default='password', help='Neo4j 비밀번호')
    
    args = parser.parse_args()
    
    success = verify_and_report(args.uri, args.user, args.password)
    sys.exit(0 if success else 1)

