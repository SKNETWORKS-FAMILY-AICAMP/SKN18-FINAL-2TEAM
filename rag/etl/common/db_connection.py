"""
PostgreSQL 연결 설정 공통 모듈

DATABASE 접속 정보는 다음의 우선순위로 사용된다:
1. 특정 환경 변수 (예: PROTOCOL_SCHEDULE_DATABASE_URL)
2. DATABASE_URL (환경 변수)
3. 개별 POSTGRES_* 변수 조합

참고: https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING

AWS Lambda 환경에서는 Parameter Store에서 비밀번호를 가져와서 [PASSWORD] 플레이스홀더를 대체합니다.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import urlparse, urlunparse, quote_plus

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

# AWS Lambda 환경에서만 boto3 사용 (로컬에서는 Optional)
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore
    HAS_BOTO3 = False


def _get_password_from_parameter_store(
    parameter_path: str = "/skn18/postgres-password",
    region: Optional[str] = None,
) -> Optional[str]:
    """
    AWS Parameter Store에서 비밀번호를 가져온다.
    
    Args:
        parameter_path: Parameter Store 경로 (기본값: /skn18/postgres-password)
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
    
    Returns:
        비밀번호 문자열, 실패 시 None
    """
    if not HAS_BOTO3:
        return None
    
    try:
        if region is None:
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
        
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=parameter_path, WithDecryption=True)
        return response["Parameter"]["Value"]
    except (ClientError, Exception):
        return None


def _replace_password_placeholder(conn_url: str, password: Optional[str] = None) -> str:
    """
    연결 URL에서 [PASSWORD] 플레이스홀더를 실제 비밀번호로 대체한다.
    
    Args:
        conn_url: PostgreSQL 연결 URL (postgresql://user:[PASSWORD]@host:port/db 형식)
        password: 비밀번호 (None이면 Parameter Store에서 가져옴)
    
    Returns:
        비밀번호가 대체된 연결 URL
    """
    if "[PASSWORD]" not in conn_url:
        return conn_url
    
    if password is None:
        password = _get_password_from_parameter_store()
        if password is None:
            raise RuntimeError(
                f"Failed to retrieve password from Parameter Store for URL: {conn_url[:50]}...\n"
                "Make sure Lambda execution role has ssm:GetParameter permission for /skn18/postgres-password"
            )
    
    # URL 파싱하여 비밀번호 대체 (비밀번호는 URL 인코딩 필요)
    try:
        parsed = urlparse(conn_url)
        # netloc 형식: user:[PASSWORD]@host:port
        if "@" in parsed.netloc:
            user_pass, host_port = parsed.netloc.rsplit("@", 1)
            if ":" in user_pass:
                user, _ = user_pass.split(":", 1)
                # 비밀번호를 URL 인코딩 (특수 문자 @, :, /, # 등 처리)
                encoded_password = quote_plus(password)
                new_netloc = f"{user}:{encoded_password}@{host_port}"
            else:
                encoded_password = quote_plus(password)
                new_netloc = f"{user_pass}:{encoded_password}@{host_port}"
        else:
            new_netloc = parsed.netloc
        
        # URL 재구성
        new_parsed = parsed._replace(netloc=new_netloc)
        return urlunparse(new_parsed)
    except Exception as e:
        # 파싱 실패 시 단순 문자열 치환 (비밀번호는 URL 인코딩)
        encoded_password = quote_plus(password)
        return conn_url.replace("[PASSWORD]", encoded_password)


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
           
    AWS Lambda 환경에서는 Parameter Store에서 비밀번호를 가져와서 [PASSWORD] 플레이스홀더를 대체합니다.
    """
    # 1. 특정 용도 전용 URL 우선
    if specific_url_env:
        url_env = os.getenv(specific_url_env)
        if url_env:
            # [PASSWORD] 플레이스홀더 대체
            return _replace_password_placeholder(url_env)

    # 2. 전체 서비스 DB URL (docker, compose 등에서 사용)
    url_env = os.getenv("DATABASE_URL")
    if url_env:
        # [PASSWORD] 플레이스홀더 대체
        return _replace_password_placeholder(url_env)

    # 3. .env 내 postgres 개별 변수 조합
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")

    # 비밀번호가 없으면 Parameter Store에서 가져오기 시도
    if password is None and HAS_BOTO3:
        password = _get_password_from_parameter_store()

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

    # 비밀번호가 없으면 Parameter Store에서 가져오기 시도
    if password is None and HAS_BOTO3:
        password = _get_password_from_parameter_store()

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
