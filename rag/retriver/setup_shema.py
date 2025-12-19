# -*- coding: utf-8 -*-
import os
import sys
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 환경 변수 로드
load_dotenv()

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

def setup_schema():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not password:
        print("❌ Error: Missing Neo4j credentials in .env")
        sys.exit(1)

    print(f"🔌 Connecting to Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))

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