# django_app/apps/experiments/views_runpod.py (FULL)

import os
import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

# AWS Parameter Store 지원
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    HAS_BOTO3 = True
except ImportError:
    boto3 = None  # type: ignore
    HAS_BOTO3 = False


def _get_parameter_from_store(
    parameter_path: str,
    region: str = None,
    with_decryption: bool = False,
) -> str | None:
    """
    AWS Parameter Store에서 파라미터 값을 가져온다.
    
    Args:
        parameter_path: Parameter Store 경로 (예: /skn18/runpod-sims-base-url)
        region: AWS 리전 (None이면 환경 변수 또는 기본값 사용)
        with_decryption: SecureString인 경우 True
    
    Returns:
        파라미터 값 문자열, 실패 시 None
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
    except (ClientError, Exception):
        return None


def _get_runpod_sims_base_url() -> str:
    """
    RUNPOD_SIMS_BASE_URL 가져오기
    우선순위: 환경 변수 > Parameter Store > 에러
    
    Parameter Store 경로: /skn18/runpod-sims-base-url
    예) https://xxxx.proxy.runpod.net
    """
    # 1순위: 환경 변수
    base = (os.environ.get("RUNPOD_SIMS_BASE_URL") or "").strip()
    
    # 2순위: Parameter Store에서 가져오기
    if not base:
        base = _get_parameter_from_store("/skn18/runpod-sims-base-url") or ""
        base = base.strip()
    
    if not base:
        # 운영에서 하드코딩으로 넘어가면 사고나기 쉬워서 "없으면 명확히 에러"로 처리
        raise RuntimeError(
            "RUNPOD_SIMS_BASE_URL is not set. "
            "Set environment variable RUNPOD_SIMS_BASE_URL or "
            "AWS Parameter Store parameter /skn18/runpod-sims-base-url"
        )
    
    if not (base.startswith("http://") or base.startswith("https://")):
        raise RuntimeError(
            f"RUNPOD_SIMS_BASE_URL must start with http:// or https:// (got: {base})"
        )
    
    return base.rstrip("/")


def _headers() -> dict:
    """
    RunPod API 요청 헤더 생성
    RUNPOD_SIMS_API_KEY 가져오기
    우선순위: 환경 변수 > Parameter Store > 없으면 None (헤더에 포함하지 않음)
    
    Parameter Store 경로: /skn18/runpod-sims-api-key (SecureString)
    """
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    
    # 1순위: 환경 변수
    api_key = (os.environ.get("RUNPOD_SIMS_API_KEY") or "").strip()
    
    # 2순위: Parameter Store에서 가져오기 (SecureString)
    if not api_key:
        api_key = _get_parameter_from_store(
            "/skn18/runpod-sims-api-key",
            with_decryption=True
        ) or ""
        api_key = api_key.strip()
    
    if api_key:
        headers["X-API-KEY"] = api_key
    
    return headers


@extend_schema(
    summary="Run RFdiffusion on RunPod (dummy)",
    description="API가 동작하는지만 테스트하는 더미 API",
    tags=["Experiments"],
    responses={200: {"type": "object"}},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rfdiffusion_runpod_api(request):
    return Response({"detail": "REST API가 동작하는지 확인만 하자!"}, status=200)


@extend_schema(
    summary="Check RunPod health",
    description="Proxy a health check request to the configured RunPod endpoint.",
    tags=["Experiments"],
    responses={200: {"type": "object"}},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def runpod_api_health(request):
    try:
        base = _get_runpod_sims_base_url()
    except RuntimeError as e:
        return Response({"detail": str(e)}, status=500)

    health_url = f"{base}/health"

    try:
        resp = requests.get(
            health_url,
            headers={"accept": "application/json"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return Response({"detail": f"RunPod health request failed: {exc}"}, status=502)

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text}

    return Response(data, status=resp.status_code)


@extend_schema(
    summary="Trigger RunPod run",
    description="Forward POST payload to the RunPod /run endpoint deployed via unified/api_server.py.",
    tags=["Experiments"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "example": "backbone"},
                "name": {"type": "string", "example": "job_001"},
                "contigs": {"type": "string", "example": "100"},
                "iterations": {"type": "integer", "example": 1},
            },
            "required": ["contigs"],
        }
    },
    responses={200: {"type": "object"}},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def runpod_api_run(request):
    if not isinstance(request.data, dict):
        return Response({"detail": "JSON body is required."}, status=400)

    try:
        base = _get_runpod_sims_base_url()
    except RuntimeError as e:
        return Response({"detail": str(e)}, status=500)

    run_url = f"{base}/run"

    try:
        resp = requests.post(
            run_url,
            json=request.data,
            headers=_headers(),
            timeout=60,
        )
    except requests.RequestException as exc:
        return Response({"detail": f"RunPod run request failed: {exc}"}, status=502)

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text}

    return Response(data, status=resp.status_code)