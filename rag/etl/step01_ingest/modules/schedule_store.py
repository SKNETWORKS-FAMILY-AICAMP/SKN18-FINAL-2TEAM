"""
PostgreSQL 기반으로 keyword별 ingestion 진행 상황을 저장/조회한다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional
from datetime import datetime

from rag.etl.common.db_connection import get_connection

TABLE_NAME = "zh_protocol_schedule"


@contextmanager
def _get_connection() -> Generator:
    """Protocol 스케줄 전용 DB 연결"""
    with get_connection(specific_url_env="PROTOCOL_SCHEDULE_DATABASE_URL") as conn:
        yield conn


def ensure_table() -> None:
    """테이블 생성 및 마이그레이션 (병렬 실행 안전)"""
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        keyword TEXT PRIMARY KEY,
        next_page INTEGER NOT NULL DEFAULT 1,
        is_completed BOOLEAN NOT NULL DEFAULT FALSE,
        schedule_started_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            # 테이블 생성
            cur.execute(ddl)
            
            # 기존 테이블에 컬럼이 있는지 확인하고 추가 (병렬 실행 시 race condition 방지)
            columns_to_check = [
                ("is_completed", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("schedule_started_at", "TIMESTAMPTZ")
            ]
            
            for col_name, col_type in columns_to_check:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (TABLE_NAME, col_name))
                
                if not cur.fetchone():
                    # 컬럼이 없으면 추가
                    try:
                        cur.execute(f"""
                            ALTER TABLE {TABLE_NAME} 
                            ADD COLUMN IF NOT EXISTS {col_name} {col_type};
                        """)
                        print(f"[SCHEDULE] Added column {col_name} to {TABLE_NAME} table", flush=True)
                    except Exception as e:
                        # 다른 프로세스가 이미 추가했을 수 있음 (race condition)
                        error_msg = str(e).lower()
                        if "already exists" in error_msg or "duplicate column" in error_msg:
                            # 정상적인 상황이므로 무시
                            pass
                        else:
                            # 다른 에러는 다시 발생
                            raise


def get_next_page(keyword: str) -> Optional[int]:
    """
    다음 페이지 번호를 조회한다.
    
    is_completed가 True이면 None을 반환한다 (실행 중단).
    """
    query = f"SELECT next_page, is_completed FROM {TABLE_NAME} WHERE keyword=%s"
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (keyword,))
            row = cur.fetchone()
            if not row:
                return None
            
            next_page, is_completed = row
            
            # 완료된 경우 실행 중단
            if is_completed:
                print(
                    f"[SCHEDULE][{keyword}] All pages collected. Stopping execution.",
                    flush=True,
                )
                return None
            
            return next_page


def update_next_page(
    keyword: str, 
    next_page: int, 
    is_completed: bool = False
) -> None:
    """
    다음 페이지 번호를 업데이트한다.
    
    Args:
        keyword: 키워드
        next_page: 다음 페이지 번호
        is_completed: 마지막 페이지 도달 여부 (True이면 모든 페이지 수집 완료)
    """
    query = f"""
        INSERT INTO {TABLE_NAME} (keyword, next_page, is_completed, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (keyword)
        DO UPDATE SET 
            next_page=EXCLUDED.next_page, 
            is_completed=EXCLUDED.is_completed,
            updated_at=NOW();
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (keyword, next_page, is_completed))
            if is_completed:
                print(
                    f"[SCHEDULE][{keyword}] Last page reached. Execution will stop on next run.",
                    flush=True,
                )


def get_and_reserve_next_page(keyword: str, pages_to_reserve: int = 10) -> Optional[int]:
    """
    다음 페이지 번호를 조회하고 예약한다 (원자적 연산).
    
    여러 람다가 동시에 실행되어도 같은 페이지를 처리하지 않도록 보장.
    is_completed가 True이면 None을 반환하여 실행을 중단한다.
    
    Args:
        keyword: 키워드
        pages_to_reserve: 예약할 페이지 수 (기본값: 10)
    
    Returns:
        시작 페이지 번호, None이면 모든 페이지 처리 완료 또는 실행 중단
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            # 트랜잭션 시작
            cur.execute("BEGIN")
            try:
                # 현재 상태 확인
                cur.execute(
                    f"SELECT next_page, is_completed FROM {TABLE_NAME} WHERE keyword = %s FOR UPDATE",
                    (keyword,)
                )
                row = cur.fetchone()
                
                if not row:
                    # 레코드가 없으면 생성 (schedule_started_at도 함께 설정)
                    cur.execute(
                        f"""
                        INSERT INTO {TABLE_NAME} (keyword, next_page, is_completed, schedule_started_at)
                        VALUES (%s, 1, FALSE, NOW())
                        ON CONFLICT (keyword) DO NOTHING
                        RETURNING next_page, is_completed;
                        """,
                        (keyword,)
                    )
                    row = cur.fetchone()
                    if not row:
                        # 다른 프로세스가 이미 생성했을 수 있음, 다시 조회
                        cur.execute(
                            f"SELECT next_page, is_completed FROM {TABLE_NAME} WHERE keyword = %s FOR UPDATE",
                            (keyword,)
                        )
                        row = cur.fetchone()
                
                if not row:
                    return None
                
                next_page, is_completed = row
                
                # 이미 완료된 경우 실행 중단
                if is_completed:
                    print(
                        f"[SCHEDULE][{keyword}] All pages collected. Stopping execution.",
                        flush=True,
                    )
                    conn.commit()
                    return None
                
                # schedule_started_at이 없으면 설정 (첫 실행인 경우)
                cur.execute(
                    f"""
                    UPDATE {TABLE_NAME}
                    SET schedule_started_at = COALESCE(schedule_started_at, NOW())
                    WHERE keyword = %s AND schedule_started_at IS NULL;
                    """,
                    (keyword,)
                )
                
                # 페이지 예약 (원자적 연산)
                start_page = next_page
                new_next_page = next_page + pages_to_reserve
                
                cur.execute(
                    f"""
                    UPDATE {TABLE_NAME}
                    SET next_page = %s,
                        updated_at = NOW()
                    WHERE keyword = %s
                    RETURNING next_page;
                    """,
                    (new_next_page, keyword)
                )
                
                conn.commit()
                return start_page
                
            except Exception as e:
                conn.rollback()
                raise


def update_ingestion_completed(keyword: str) -> None:
    """
    순수 ingest (API 호출) 완료 시점을 기록한다.
    clean, chunking 등 후속 단계는 포함하지 않는다.
    
    Args:
        keyword: 키워드
    """
    query = f"""
        UPDATE {TABLE_NAME}
        SET updated_at = NOW()
        WHERE keyword = %s;
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (keyword,))
            print(
                f"[SCHEDULE][{keyword}] API 호출 완료 시점 기록 완료",
                flush=True,
            )
