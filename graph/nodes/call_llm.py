"""
각 모델(gpt-4o-mini, gpt-5-nano, SLLM, Local LLM을 호출하는 함수를 제공.
함수 형태로 호출하도록 통합 래퍼 제공.

사용 예:
    from call_llm import gpt4o_mini, sllm
    response = gpt4o_mini("Hello!")
    response = sllm("Hello!")

설정 우선순위:
    AWS 환경: Parameter Store → 환경 변수
    로컬 환경: 환경 변수 (.env 파일)

.env 예시:
    OPENAI_API_KEY=xxxx
    SLLM_BASE_URL=https://podid-7860.proxy.runpod.net/v1  # SLLM 서버 URL
    MODEL_NAME=enapeace_qlora
    RUNPOD_API_KEY=EMPTY

Parameter Store 경로 (AWS 환경):
    /skn18/sllm-model-name
    /skn18/sllm-base-url
    /skn18/sllm-runpod-api-key
"""

import os
import json
import time
from typing import Optional
from graph.logger_config import get_logger

logger = get_logger(__name__)

# Lambda 환경에서는 .env 파일을 로드하지 않음 (환경 변수에서 직접 읽음)
# 로컬 환경에서만 .env 파일 로드
is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

# EC2 환경 감지: 여러 방법으로 감지
is_ec2 = False
if not is_lambda:
    # 방법 1: 환경 변수 확인 (가장 빠름)
    if os.environ.get('AWS_EXECUTION_ENV') or os.environ.get('ECS_CONTAINER_METADATA_URI'):
        is_ec2 = True
    # 방법 2: EC2 인스턴스 메타데이터 서비스 접근 가능 여부로 판단
    elif os.path.exists('/sys/class/dmi/id/product_uuid'):
        try:
            import urllib.request
            import socket
            # 타임아웃을 짧게 설정하여 빠르게 실패
            socket.setdefaulttimeout(0.5)
            urllib.request.urlopen('http://169.254.169.254/latest/meta-data/', timeout=0.5)
            is_ec2 = True
        except (urllib.error.URLError, OSError, socket.timeout, Exception):
            is_ec2 = False
        finally:
            socket.setdefaulttimeout(None)  # 타임아웃 복원

is_aws = is_lambda or is_ec2

if not is_aws:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # dotenv가 설치되지 않은 경우 무시
        pass

# AWS Lambda/EC2 환경에서만 boto3 사용 (로컬에서는 Optional)
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore
    HAS_BOTO3 = False

# OpenAI / Gemini 공식 클라이언트
from openai import OpenAI
# import google.generativeai as genai


# -----------------------------------------
# 1) Parameter Store 헬퍼 함수
# -----------------------------------------
def _get_parameter_from_store(
    parameter_path: str,
    region: str | None = None,
    with_decryption: bool = False,
) -> str | None:
    """
    AWS Parameter Store에서 파라미터 값을 가져온다.
    
    Args:
        parameter_path: Parameter Store 경로
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
        with_decryption: SecureString 타입인 경우 복호화 여부
    
    Returns:
        파라미터 값, 실패 시 None
    """
    if not HAS_BOTO3:
        return None
    
    try:
        if region is None:
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))
        
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(
            Name=parameter_path,
            WithDecryption=with_decryption
        )
        return response["Parameter"]["Value"]
    except (ClientError, Exception) as e:
        # Parameter Store 접근 실패 (권한 없음, 파라미터 없음 등)
        # 로컬 환경에서는 조용히 실패 (환경 변수 fallback 사용)
        if not is_aws:
            return None
        # AWS 환경에서는 상세 로그 출력
        error_type = type(e).__name__
        logger.warning(f"Failed to get parameter {parameter_path}: {error_type}: {e}")
        return None


def _get_env_or_parameter(
    env_var_name: str,
    parameter_path: str,
    with_decryption: bool = False,
) -> str | None:
    """
    환경 변수 또는 Parameter Store에서 값을 가져온다.
    
    우선순위:
        1. 환경 변수
        2. Parameter Store (boto3가 있으면 시도, AWS 환경이 아니어도 시도)
        3. None
    
    Args:
        env_var_name: 환경 변수 이름
        parameter_path: Parameter Store 경로
        with_decryption: SecureString 타입인 경우 복호화 여부
    
    Returns:
        값 문자열, 없으면 None
    """
    # 1. 환경 변수 확인
    value = os.getenv(env_var_name)
    if value:
        return value
    
    # 2. Parameter Store 시도 (boto3가 있으면 항상 시도)
    # AWS 환경 감지가 실패해도 boto3가 있으면 Parameter Store 접근 가능
    if HAS_BOTO3:
        value = _get_parameter_from_store(parameter_path, with_decryption=with_decryption)
        if value:
            return value
    
    return None


# -----------------------------------------
# 2) 환경변수 로드 (지연 로딩 지원)
# -----------------------------------------
# 환경변수 또는 Parameter Store에서 값 로드
# 모듈 로드 시점에 한 번 가져오고, 필요시 재로드 가능
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# SLLM 관련 변수는 지연 로딩 함수로 처리 (함수 호출 시점에 가져옴)
_SLLM_BASE_URL = None
_RUNPOD_API_KEY = None
_MODEL_NAME = None

def _get_sllm_config():
    """SLLM 설정값을 지연 로딩 (모듈 로드 시점이 아닌 실제 호출 시점에 가져옴)"""
    global _SLLM_BASE_URL, _RUNPOD_API_KEY, _MODEL_NAME
    
    # 이미 값이 있으면 재사용 (캐싱)
    if _SLLM_BASE_URL and _RUNPOD_API_KEY and _MODEL_NAME:
        return _SLLM_BASE_URL, _RUNPOD_API_KEY, _MODEL_NAME
    
    # 환경 변수 또는 Parameter Store에서 값 가져오기
    logger.debug(f"환경 감지 - is_lambda: {is_lambda}, is_ec2: {is_ec2}, is_aws: {is_aws}, HAS_BOTO3: {HAS_BOTO3}")
    
    _SLLM_BASE_URL = _get_env_or_parameter(
        "SLLM_BASE_URL",
        "/skn18/sllm-base-url",
        with_decryption=False
    )
    _RUNPOD_API_KEY = _get_env_or_parameter(
        "RUNPOD_API_KEY",
        "/skn18/sllm-runpod-api-key",
        with_decryption=True  # API 키는 SecureString 가능
    )
    _MODEL_NAME = _get_env_or_parameter(
        "MODEL_NAME",
        "/skn18/sllm-model-name",
        with_decryption=False
    )
    
    logger.info(f"SLLM Config 로드 결과 - BASE_URL: {'✓' if _SLLM_BASE_URL else '✗'}, "
                f"API_KEY: {'✓' if _RUNPOD_API_KEY else '✗'}, "
                f"MODEL: {'✓' if _MODEL_NAME else '✗'}")
    
    return _SLLM_BASE_URL, _RUNPOD_API_KEY, _MODEL_NAME

# 하위 호환성을 위해 모듈 레벨 변수도 설정 (초기 로드 시도)
SLLM_BASE_URL = _get_env_or_parameter(
    "SLLM_BASE_URL",
    "/skn18/sllm-base-url",
    with_decryption=False
)
RUNPOD_API_KEY = _get_env_or_parameter(
    "RUNPOD_API_KEY",
    "/skn18/sllm-runpod-api-key",
    with_decryption=True
)
MODEL_NAME = _get_env_or_parameter(
    "MODEL_NAME",
    "/skn18/sllm-model-name",
    with_decryption=False
)


# -----------------------------------------
# 2) 클라이언트 초기화
# -----------------------------------------
# OpenAI 클라이언트는 지연 초기화 (lazy initialization)
openai_client = None

def _get_openai_client():
    """OpenAI 클라이언트를 지연 초기화 (lazy initialization)"""
    global openai_client
    if openai_client is None:
        if not OPENAI_API_KEY:
            raise ValueError("❌ OPENAI_API_KEY not found in .env")
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return openai_client


# SLLM 클라이언트도 지연 초기화 (lazy initialization) - 커넥션 재사용
sllm_client = None

def _get_sllm_client():
    """SLLM 클라이언트를 지연 초기화 (lazy initialization) - 커넥션 풀 재사용"""
    global sllm_client
    
    # 설정값 가져오기 (지연 로딩)
    sllm_base_url, runpod_api_key, model_name = _get_sllm_config()
    
    # 사용 시점에 환경변수 또는 Parameter Store 값 검증
    if not sllm_base_url:
        if is_aws:
            raise ValueError("❌ SLLM_BASE_URL not found in environment variables or Parameter Store (/skn18/sllm-base-url)")
        else:
            raise ValueError("❌ SLLM_BASE_URL not found in .env or environment variables")
    if not runpod_api_key:
        if is_aws:
            raise ValueError("❌ RUNPOD_API_KEY not found in environment variables or Parameter Store (/skn18/sllm-runpod-api-key)")
        else:
            raise ValueError("❌ RUNPOD_API_KEY not found in .env or environment variables")
    if not model_name:
        if is_aws:
            raise ValueError("❌ MODEL_NAME not found in environment variables or Parameter Store (/skn18/sllm-model-name)")
        else:
            raise ValueError("❌ MODEL_NAME not found in .env or environment variables")
    
    # 클라이언트가 없거나 base_url이 변경된 경우 재생성
    if sllm_client is None or sllm_client.base_url != sllm_base_url:
        logger.info(f"[SLLM] 클라이언트 {'재생성' if sllm_client else '생성'} - Base URL: {sllm_base_url}")
        sllm_client = OpenAI(
            base_url=sllm_base_url,
            api_key=runpod_api_key,
            timeout=60.0  # 60초 타임아웃
        )
    
    return sllm_client, model_name


# -----------------------------------------
# 3) 공통 response 처리 함수
# -----------------------------------------
def _parse_openai_response(resp):
    """OpenAI response에서 텍스트만 추출."""
    try:
        return resp.choices[0].message.content
    except Exception:
        return str(resp)


# -----------------------------------------
# 4) 모델별 LLM 함수
# -----------------------------------------

def gpt4_1_nano(prompt: str):
    """GPT-4.1-nano 호출"""
    start_time = time.time()
    
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    response_text = _parse_openai_response(resp)
    
    elapsed = time.time() - start_time
    logger.info(f"[GPT-4.1-nano] 응답 성공 - Elapsed Time: {elapsed:.2f}s, "
                f"Response Length: {len(response_text)} chars")
    
    return response_text


def gpt4o_mini(prompt: str):
    """GPT-4o-mini 호출"""
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return _parse_openai_response(resp)


def gpt5_nano(prompt: str):
    """GPT-5-nano 호출"""
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_openai_response(resp)


def gpt5_2(prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2048):
    """
    GPT-5.2 호출 (fallback 모델용)
    
    Args:
        prompt: 입력 프롬프트 (user 메시지)
        system_prompt: 시스템 프롬프트 (선택적)
        temperature: 생성 온도 (기본값: 0.7)
        max_tokens: 최대 토큰 수 (기본값: 2048)
    
    Returns:
        모델 응답 텍스트
    """
    client = _get_openai_client()
    
    # 메시지 구성 (System/User role 분리)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    resp = client.chat.completions.create(
        model="gpt-5.2",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return _parse_openai_response(resp)

# -----------------------------------------
# 5) SLLM 호출 (실험결과해석 모델)
# -----------------------------------------
def sllm(prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2048):
    """
    SLLM 모델 호출 (RunPod 프록시 사용)
    Gemma3-12B-it 기반 파인튜닝 모델용
    
    클라이언트는 모듈 레벨에서 캐싱되어 커넥션 풀을 재사용합니다.

    Args:
        prompt: 입력 프롬프트 (user 메시지)
        system_prompt: 시스템 프롬프트 (선택적, 규칙/지침용)
        temperature: 생성 온도 (기본값: 0.7)
        max_tokens: 최대 토큰 수 (기본값: 2048, 동적으로 조정됨)

    Returns:
        모델 응답 텍스트

    Raises:
        Exception: Pod가 비활성화되었거나 연결 오류가 발생한 경우
    """
    import time

    # 캐싱된 클라이언트 가져오기 (커넥션 풀 재사용)
    client, model_name = _get_sllm_client()
    sllm_base_url = client.base_url

    # 입력 토큰 수 계산 (system + user)
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4/GPT-3.5와 호환
        total_input = (system_prompt or "") + prompt
        input_tokens = len(encoding.encode(total_input))
    except (ImportError, Exception):
        # tiktoken이 없거나 에러 발생 시 근사치 사용 (평균 1 토큰 ≈ 4 문자)
        total_input = (system_prompt or "") + prompt
        input_tokens = len(total_input) // 4
        logger.debug("[SLLM] tiktoken을 사용할 수 없어 근사치로 계산")

    # 모델 최대 컨텍스트 길이 (Gemma3-12B-it 기반, 일반적으로 4096)
    MAX_CONTEXT_LENGTH = 8192
    # 안전 마진 (시스템 메시지, 응답 형식 등 고려)
    SAFETY_MARGIN = 100
    
    # 사용 가능한 최대 출력 토큰 수 계산
    available_tokens = MAX_CONTEXT_LENGTH - input_tokens - SAFETY_MARGIN
    
    # max_tokens를 동적으로 조정 (최소 200 토큰 보장)
    if available_tokens < 200:
        logger.error(f"[SLLM] ❌ 사용 가능한 토큰이 심각하게 부족합니다! "
                    f"입력: {input_tokens} 토큰, 사용 가능: {available_tokens} 토큰, "
                    f"최대 컨텍스트: {MAX_CONTEXT_LENGTH} 토큰")
        logger.warning(f"[SLLM] 최소값(200) 사용 - 응답이 잘릴 수 있습니다")
        adjusted_max_tokens = 200
    elif max_tokens > available_tokens:
        logger.warning(f"[SLLM] ⚠️ 요청된 max_tokens({max_tokens})가 사용 가능한 토큰({available_tokens})보다 큽니다. "
                      f"입력: {input_tokens} 토큰, 최대 컨텍스트: {MAX_CONTEXT_LENGTH} 토큰. "
                      f"동적으로 조정: {available_tokens} 토큰")
        adjusted_max_tokens = available_tokens
    else:
        adjusted_max_tokens = max_tokens
        logger.debug(f"[SLLM] ✅ max_tokens 조정 불필요: {max_tokens} 토큰 (사용 가능: {available_tokens} 토큰)")

    # 메시지 구성 (System/User role 분리)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    logger.info(f"[SLLM] 호출 시작 - Model: {model_name}, Base URL: {sllm_base_url}, "
                f"Temperature: {temperature}, Max Context: {MAX_CONTEXT_LENGTH}, "
                f"Input Tokens: {input_tokens} (System: {len(encoding.encode(system_prompt or ''))}, User: {len(encoding.encode(prompt))}), "
                f"Requested Max Tokens: {max_tokens}, Adjusted Max Tokens: {adjusted_max_tokens}")
    logger.debug(f"System Prompt Preview: {(system_prompt or '')[:100]}...")
    logger.debug(f"User Prompt Preview: {prompt[:100]}...")

    try:
        start_time = time.time()

        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=adjusted_max_tokens
        )

        elapsed = time.time() - start_time
        response_text = _parse_openai_response(resp)

        logger.info(f"[SLLM] 응답 성공 - Elapsed Time: {elapsed:.2f}s, "
                   f"Response Length: {len(response_text)} chars")
        logger.debug(f"Response Preview: {response_text[:100]}...")

        return response_text

    except Exception as e:
        error_msg = f"Pod가 비활성화되었거나 연결할 수 없습니다: {str(e)}"
        logger.error(f"[SLLM ERROR] {error_msg}", exc_info=True)
        raise RuntimeError(error_msg) from e


# -----------------------------------------
# 6) Local LLM (프로토콜 제시 모델)
# -----------------------------------------
# def local_llm(prompt: str):
#     """
#     vLLM 등 로컬 모델 호출
#     — REST API 라고 가정.
#     """
#     import requests
#     url = "http://localhost:8000/generate"
#     data = {"prompt": prompt}

#     try:
#         resp = requests.post(url, json=data)
#         return resp.json().get("text")
#     except Exception as e:
#         return f"[LOCAL LLM ERROR] {e}"



