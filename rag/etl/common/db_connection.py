"""
PostgreSQL 연결 설정 공통 모듈

DATABASE 접속 정보는 다음의 우선순위로 사용된다:
1. 특정 환경 변수 (예: PROTOCOL_SCHEDULE_DATABASE_URL)
2. DATABASE_URL (환경 변수)
3. 개별 POSTGRES_* 변수 조합

참고: https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import psycopg  # type: ignore
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore

try:
    import psycopg2  # type: ignore
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore


def build_conninfo(
    specific_url_env: Optional[str] = None,
) -> str:
    """
    PostgreSQL 연결 문자열을 생성한다.

    Args:
        specific_url_env: 특정 용도를 위한 환경 변수명 (예: "PROTOCOL_SCHEDULE_DATABASE_URL")
                          이 값이 설정되어 있으면 우선 사용한다.

    Returns:
        PostgreSQL 연결 문자열 (postgresql://... 형식)

    Raises:
        RuntimeError: 연결 정보를 찾을 수 없을 때

    우선순위:
        1. specific_url_env로 지정된 환경 변수
        2. DATABASE_URL (환경 변수)
        3. 개별 POSTGRES_* 변수 조합:
           - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    """
    # 1. 특정 용도 전용 URL 우선
    if specific_url_env:
        url_env = os.getenv(specific_url_env)
        if url_env:
            return url_env

    # 2. 전체 서비스 DB URL (docker, compose 등에서 사용)
    url_env = os.getenv("DATABASE_URL")
    if url_env:
        return url_env

    # 3. .env 내 postgres 개별 변수 조합
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")

    if all([user, password, host, port, db]):
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    raise RuntimeError(
        "Database connection info not found: "
        "DATABASE_URL or POSTGRES_* env variables are required.\n"
        f"{f'({specific_url_env} is also available)' if specific_url_env else ''}\n"
        "Check your .env file configuration.\n"
    )


@contextmanager
def get_connection(
    specific_url_env: Optional[str] = None,
    autocommit: bool = True,
) -> Generator:
    """
    PostgreSQL 연결을 생성하고 반환한다.

    Args:
        specific_url_env: 특정 용도를 위한 환경 변수명 (예: "PROTOCOL_SCHEDULE_DATABASE_URL")
        autocommit: 자동 커밋 여부 (기본값: True)

    Yields:
        PostgreSQL 연결 객체 (psycopg 또는 psycopg2)

    Raises:
        RuntimeError: psycopg 또는 psycopg2 패키지가 없을 때
    """
    conninfo = build_conninfo(specific_url_env)

    if psycopg is not None:
        conn = psycopg.connect(conninfo, autocommit=autocommit)  # type: ignore[arg-type]
    elif psycopg2 is not None:
        conn = psycopg2.connect(conninfo)  # type: ignore[call-arg]
        conn.autocommit = autocommit
    else:  # pragma: no cover
        raise RuntimeError("psycopg (v3) 또는 psycopg2 패키지가 필요합니다.")

    try:
        yield conn
    finally:
        conn.close()


def get_connection_params() -> dict[str, str]:
    """
    개별 연결 파라미터를 딕셔너리로 반환한다.
    (psycopg2.connect()에 직접 전달할 때 사용)

    Returns:
        {"host": ..., "port": ..., "dbname": ..., "user": ..., "password": ...}

    Raises:
        RuntimeError: 필수 환경 변수가 없을 때
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if not all([host, port, dbname, user, password]):
        raise RuntimeError(
            "Database connection params not found: "
            "POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are required.\n"
            "Check your .env file configuration.\n"
        )

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }
