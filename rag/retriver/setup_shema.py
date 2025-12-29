# -*- coding: utf-8 -*-
import os
import sys
import time
from typing import Optional

# dotenv는 로컬 환경에서만 사용 (선택적)
try:
    from dotenv import load_dotenv
    # .env 파일이 있으면 로드 (로컬 환경)
    if os.path.exists(".env"):
        load_dotenv()
except ImportError:
    pass  # dotenv가 없어도 동작 (AWS 환경)

from neo4j import GraphDatabase

# S3/Parameter Store 지원 (선택적)
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# rag_queries.py에서 스키마 정의 가져오기
try:
    from rag_queries import GraphSchemaQueries
except ImportError:
    print("❌ Error: 'rag_queries.py' file not found in the current directory.")
    sys.exit(1)

def get_index_name_safe(query, keyword="INDEX"):
    """
    쿼리문에서 인덱스 이름을 안전하게 추출합니다.
    """
    try:
        # 대소문자 무시하고 split
        parts = query.split(keyword)
        if len(parts) > 1:
            # IF 구문 앞까지 자르기
            name_part = parts[1].split("IF")[0].strip()
            # FOR, ON 등이 섞여있을 수 있으므로 공백으로 한 번 더 분리 시도
            return name_part.split()[0] if name_part else "Unknown"
    except Exception:
        pass
    return "Query_Index"


def _get_aws_region() -> str:
    """AWS 리전 감지 (여러 방법 시도)"""
    # 1. 환경 변수 확인
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        return region
    
    # 2. boto3 세션에서 리전 가져오기
    if HAS_BOTO3:
        try:
            import boto3
            session = boto3.Session()
            if session.region_name:
                return session.region_name
        except:
            pass
    
    # 3. EC2 메타데이터에서 리전 가져오기
    try:
        import urllib.request
        url = "http://169.254.169.254/latest/meta-data/placement/region"
        with urllib.request.urlopen(url, timeout=5) as response:
            region = response.read().decode().strip()
            if region:
                return region
    except:
        pass
    
    # 4. 기본값 사용
    return "ap-northeast-2"


def _get_neo4j_password_from_parameter_store() -> Optional[str]:
    """AWS Parameter Store에서 Neo4j 비밀번호 가져오기"""
    if not HAS_BOTO3:
        return None
    
    try:
        import boto3
        
        # AWS 리전 감지
        region = _get_aws_region()
        if not region:
            print("⚠️  AWS 리전을 감지할 수 없습니다.")
            return None
        
        # Parameter Store에서 비밀번호 가져오기
        ssm = boto3.client("ssm", region_name=region)
        response = ssm.get_parameter(
            Name="/skn18/neo4j-password",
            WithDecryption=True
        )
        password = response["Parameter"]["Value"]
        print(f"✅ Parameter Store에서 Neo4j 비밀번호를 가져왔습니다. (Region: {region})")
        return password
    except Exception as e:
        print(f"⚠️  Parameter Store에서 비밀번호를 가져오지 못했습니다: {e}")
        print(f"   리전: {_get_aws_region()}")
        return None

def setup_schema():
    # 환경 변수에서 설정 읽기 (로컬 및 AWS 환경 지원)
    uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_BOLT_HOST")
    if uri and not uri.startswith("bolt://"):
        # NEO4J_BOLT_HOST만 있는 경우 bolt:// 추가
        uri = f"bolt://{uri}"
    if not uri:
        uri = "bolt://localhost:7687"
    
    # 사용자명 (여러 환경 변수 이름 지원)
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    if not user:
        user = "neo4j"
    
    # 비밀번호 가져오기 (환경 변수 → Parameter Store → 기본값 순서)
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        # AWS 환경에서 Parameter Store에서 가져오기 시도
        password = _get_neo4j_password_from_parameter_store()
        if not password:
            # AWS EC2 환경인지 확인
            is_ec2 = os.path.exists("/var/lib/neo4j/import") or os.path.exists("/sys/hypervisor/uuid")
            if is_ec2:
                # EC2 환경에서는 기본값 사용하지 않고 에러
                print("\n❌ Neo4j 비밀번호를 가져올 수 없습니다.")
                print("   AWS EC2 환경에서는 다음 중 하나를 수행하세요:")
                print("   1. 환경 변수로 설정:")
                print("      export NEO4J_PASSWORD='<비밀번호>'")
                print("   2. Parameter Store에서 직접 확인:")
                print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption --query 'Parameter.Value' --output text")
                print("   3. Parameter Store에 비밀번호가 저장되어 있는지 확인:")
                print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption")
                sys.exit(1)
            else:
                # 로컬 환경에서는 기본값 사용
                password = "neo4jpass"
                print("ℹ️  환경 변수 NEO4J_PASSWORD가 설정되지 않았습니다. 기본값을 사용합니다.")

    print(f"🔌 Connecting to Neo4j at {uri}...")
    print(f"   User: {user}")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        # 연결 테스트
        with driver.session() as test_session:
            test_session.run("RETURN 1")
        print("✅ Neo4j 연결 성공")
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        print("\n💡 해결 방법:")
        print("   1. Neo4j Docker 컨테이너가 실행 중인지 확인:")
        print("      docker ps | grep neo4j")
        print("   2. AWS EC2 환경인 경우 Parameter Store에서 비밀번호 확인:")
        print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption --query 'Parameter.Value' --output text")
        print("   3. 환경 변수로 비밀번호 설정:")
        print("      export NEO4J_PASSWORD='<비밀번호>'")
        print("   4. Neo4j 컨테이너 로그 확인:")
        print("      docker logs neo4j-final")
        sys.exit(1)

    try:
        with driver.session() as session:
            # 1. Constraints (제약조건)
            print("\n[1/4] Creating Constraints...")
            for q in GraphSchemaQueries.CREATE_CONSTRAINTS:
                try:
                    session.run(q)
                    print(f"  ✅ Constraint Executed") 
                except Exception as e:
                    print(f"  ⚠️ Error executing constraint: {e}")

            # 2. Indexes (일반 인덱스)
            print("\n[2/4] Creating Regular Indexes...")
            for q in GraphSchemaQueries.CREATE_INDEXES:
                try:
                    session.run(q)
                    name = get_index_name_safe(q, "INDEX")
                    print(f"  ✅ Index: {name}")
                except Exception as e:
                    print(f"  ⚠️ Error executing index: {e}")

            # 3. Vector Indexes (벡터 인덱스)
            print("\n[3/4] Creating Vector Indexes...")
            for q in GraphSchemaQueries.CREATE_VECTOR_INDEXES:
                try:
                    session.run(q)
                    name = get_index_name_safe(q, "INDEX")
                    print(f"  ✅ Vector Index: {name}")
                except Exception as e:
                    print(f"  ❌ Vector Index Error: {e}")
                    # 쿼리 앞부분 일부 출력
                    print(f"     Query Snippet: {q.strip()[:60]}...")

            # 4. Fulltext Indexes (전문 검색 인덱스)
            print("\n[4/4] Creating Fulltext Indexes...")
            for q in GraphSchemaQueries.CREATE_FULLTEXT_INDEXES:
                try:
                    session.run(q)
                    name = get_index_name_safe(q, "INDEX")
                    print(f"  ✅ Fulltext Index: {name}")
                except Exception as e:
                    print(f"  ⚠️ Error executing fulltext index: {e}")
            
            print("\n⏳ Waiting for indexes to populate...")
            # 인덱스 상태 확인 쿼리
            result = session.run("SHOW INDEXES YIELD name, state, type WHERE state = 'ONLINE' RETURN count(*) as cnt")
            record = result.single()
            if record:
                cnt = record["cnt"]
                print(f"   (Currently {cnt} indexes are ONLINE)")
            else:
                print("   (Could not fetch index count)")

    except Exception as e:
        print(f"\n❌ Setup Failed: {e}")
    finally:
        driver.close()
        print("\n✨ Schema setup logic completed.")

if __name__ == "__main__":
    setup_schema()