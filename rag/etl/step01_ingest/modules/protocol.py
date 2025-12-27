import os
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

# Lambda 환경에서는 .env 파일을 로드하지 않음 (환경 변수에서 직접 읽음)
# 로컬 환경에서만 .env 파일 로드
is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
if not is_lambda:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # dotenv가 설치되지 않은 경우 무시
        pass

# AWS Lambda 환경에서만 boto3 사용 (로컬에서는 Optional)
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore
    HAS_BOTO3 = False


def _get_token_from_parameter_store(
    parameter_path: str,
    region: str | None = None,
) -> str | None:
    """
    AWS Parameter Store에서 토큰을 가져온다.
    
    Args:
        parameter_path: Parameter Store 경로
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
    
    Returns:
        토큰 문자열, 실패 시 None
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


# 토큰 설정 (발급받은 CLIENT_ACCESS_TOKEN)
# Lambda 환경: Parameter Store 또는 환경 변수에서 읽음
# 로컬 환경: .env 파일에서 읽음
CLIENT_ACCESS_TOKEN = os.getenv("CLIENT_ACCESS_TOKEN")

# Lambda 환경에서 토큰이 없으면 Parameter Store에서 가져오기 시도
if not CLIENT_ACCESS_TOKEN and is_lambda and HAS_BOTO3:
    parameter_path = os.getenv("CLIENT_ACCESS_TOKEN_PARAMETER_PATH", "/skn18/client-access-token")
    CLIENT_ACCESS_TOKEN = _get_token_from_parameter_store(parameter_path)

if not CLIENT_ACCESS_TOKEN:
    env_type = "Lambda environment variables or Parameter Store" if is_lambda else ".env file"
    raise RuntimeError(f"CLIENT_ACCESS_TOKEN not found in {env_type}.")

# 공통 헤더 구성
headers = {
    "Authorization": f"Bearer {CLIENT_ACCESS_TOKEN}",
    "Accept": "application/json",
}

MAX_RETRIES = int(os.getenv("PROTOCOLS_IO_MAX_RETRIES", "3"))
RETRYABLE_STATUS = {504}
INITIAL_BACKOFF = float(os.getenv("PROTOCOLS_IO_BACKOFF_SECONDS", "1.0"))


def _request_with_retry(url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    attempt = 0
    backoff = INITIAL_BACKOFF
    while True:
        attempt += 1
        resp = requests.get(
            url,
            headers=headers,
            params=params,
        )
        status_code = resp.status_code
        if status_code in RETRYABLE_STATUS:
            if attempt >= MAX_RETRIES:
                resp.raise_for_status()
            wait = backoff
            backoff *= 2
            print(
                f"[Protocol.io] request retry (attempt {attempt}/{MAX_RETRIES}, status={status_code}) "
                f"sleeping {wait:.1f}s",
                flush=True,
            )
            time.sleep(wait)
            continue

        resp.raise_for_status()
        return resp


# 공개 프로토콜 목록 조회 (public protocols)
def get_public_protocols(page_size=10, page_id=1, search_key=None):
    url = "https://www.protocols.io/api/v3/protocols"
    params = {
        "filter": "public",
        "page_size": page_size,
        "page_id": page_id,
    }
    if search_key:
        params["key"] = search_key

    print(
        f"[Protocol.io] GET {url} page_id={page_id}, page_size={page_size}, "
        f"search={search_key}",
        flush=True,
    )
    resp = _request_with_retry(url, params=params)
    data = resp.json()
    print(
        f"[Protocol.io] GET {url} done status={resp.status_code}, "
        f"items={len(data.get('items', [])) if isinstance(data, dict) else 'N/A'}",
        flush=True,
    )

    return data

# 특정 프로토콜 상세 조회 (ID 또는 URI 사용 가능)
def get_protocol(protocol_id_or_uri):
    # API 문서상 protocols 조회는 v4 엔드포인트도 존재 (문서 참고) :contentReference[oaicite:2]{index=2}
    url = f"https://www.protocols.io/api/v4/protocols/{protocol_id_or_uri}"
    params = {
        "include": "steps,components,files,annotations,changelog",  # << 추가
        "content_format": "html",  # ← HTML 형식으로 요청
        "last_version": 1
    }
    print(f"[Protocol.io] GET {url}", flush=True)
    resp = _request_with_retry(url, params=params)
    data = resp.json()
    print(f"[Protocol.io] GET {url} done status={resp.status_code}", flush=True)
    return data

# 제곱수 및 지수 처리
def html_to_text_with_superscript(html_content):
    if not html_content:
        return "<no data>"
    soup = BeautifulSoup(html_content, "html.parser")

    # <sup> 변환
    for sup in soup.find_all("sup"):
        sup.replace_with("^" + sup.get_text())

    # vertical-align: super 변환
    for span in soup.find_all("span", style=True):
        if "vertical-align: super" in span["style"]:
            span.replace_with("^" + span.get_text())

    return soup.get_text()
