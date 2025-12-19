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
                    # IF NOT EXISTS 구문이 포함되어 있어 중복 실행해도 안전함
                    session.run(q)
                    name = q.split("REQUIRE")[0].split("FOR")[1].strip()
                    print(f"  ✅ Constraint on {name}")
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")

            # 2. Indexes (일반 인덱스)
            print("\n[2/4] Creating Regular Indexes...")
            for q in GraphSchemaQueries.CREATE_INDEXES:
                try:
                    session.run(q)
                    name = q.split("ON")[0].split("FOR")[1].strip()
                    print(f"  ✅ Index on {name}")
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")

            # 3. Vector Indexes (벡터 인덱스 - 핵심!)
            print("\n[3/4] Creating Vector Indexes...")
            for q in GraphSchemaQueries.CREATE_VECTOR_INDEXES:
                try:
                    # 인덱스 이름 추출
                    if "indexConfig" in q:
                        idx_name = q.split("INDEX")[1].split("IF")[0].strip()
                    else:
                        idx_name = "Unknown Vector Index"
                    
                    session.run(q)
                    print(f"  ✅ Vector Index: {idx_name}")
                except Exception as e:
                    print(f"  ❌ Vector Index Error ({idx_name}): {e}")

            # 4. Fulltext Indexes (전문 검색 인덱스)
            print("\n[4/4] Creating Fulltext Indexes...")
            for q in GraphSchemaQueries.CREATE_FULLTEXT_INDEXES:
                try:
                    idx_name = q.split("INDEX")[1].split("IF")[0].strip()
                    session.run(q)
                    print(f"  ✅ Fulltext Index: {idx_name}")
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")
                    
            print("\n⏳ Waiting for indexes to come online...")
            time.sleep(2) 
            
    except Exception as e:
        print(f"\n❌ Setup Failed: {e}")
    finally:
        driver.close()
        print("\n✨ Schema setup completed. You can now run retriever_runner.py")

if __name__ == "__main__":
    setup_schema()