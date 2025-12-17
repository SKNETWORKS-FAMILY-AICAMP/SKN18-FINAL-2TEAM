"""
memory_db_stetting.py
---------------------
PostgreSQL 연결 및 ORM 테이블 초기화
- chat_room_id 기반 채팅창 관리
- chat_id 자동증가 개별 대화 관리
- LLM 응답 요약 저장
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from memory_db_schema import Base, ConversationMemory

# -----------------------------
# 1) .env 로드
# -----------------------------
load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

if not all([POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]):
    raise RuntimeError("❌ DB 설정이 .env에 없습니다. POSTGRES_* 변수를 확인하세요.")


# -----------------------------
# 2) SQLAlchemy 엔진 생성
# -----------------------------
# psycopg (psycopg3) 사용을 위해 postgresql+psycopg:// 사용
DATABASE_URL = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

# -----------------------------
# 3) 세션팩토리 생성
# -----------------------------
Connect_PostgreSQL = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# -----------------------------
# 4) 테이블 생성 함수
# -----------------------------
def init_db():
    """
    모든 ORM 모델의 테이블을 생성한다.
    """
    print("▶️ Creating PostgreSQL tables...")
    print("   - t_memory (각 질문마다 새 row)")
    print("   - case_type: 데이터 타입 컬럼 (SIMULATION_Q, INFERENCE_Q, BIO_Q, PROTOCOL_Q)")
    print("   - full_response: 원본 답변 컬럼")
    print("   - summary: 질문과 답변 요약 컬럼")
    
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")


# -----------------------------
# 5) 기존 테이블 삭제 함수 (마이그레이션용)
# -----------------------------
def drop_old_tables():
    """
    기존 테이블들을 삭제한다. (주의: 데이터 손실!)
    """
    print("⚠️  WARNING: 기존 테이블을 삭제합니다!")
    response = input("정말 삭제하시겠습니까? (yes/no): ")
    
    if response.lower() == 'yes':
        Base.metadata.drop_all(bind=engine)
        print("🗑️ Old tables dropped!")
    else:
        print("❌ 삭제 취소됨")


# -----------------------------
# 6) 스크립트로 실행시키기
# -----------------------------
if __name__ == "__main__":
    print("🆕 메모리 DB 스키마 초기화")
    print("1. 새 테이블 생성: python memory_db_stetting.py")
    print("2. 기존 테이블 삭제 후 생성: python memory_db_stetting.py --reset")
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        drop_old_tables()
    
    init_db()
