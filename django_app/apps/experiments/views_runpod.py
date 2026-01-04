# django_app/apps/experiments/views_runpod.py (FULL)

import os
import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.chat.models.models import RunpodJob


def get_runpod_base_url():
    """
    Runpod URL 조회
    우선순위:
    1. DB 캐시 (로그인 시 로드됨)
    2. 환경변수
    3. 하드코딩된 기본값
    """
    # 1. DB 캐시에서 조회 (가장 빠름, 로그인 시 이미 로드됨)
    cached_url = RunpodJob.get_url()
    if cached_url:
        print(f"[RUNPOD URL SOURCE] Django 캐시에서 URL 조회: {cached_url}")
        return cached_url

    # 2. 환경변수 fallback
    env_url = os.environ.get("RUNPOD_BASE_URL")
    if env_url:
        print(f"[RUNPOD URL SOURCE] 환경변수에서 URL 조회: {env_url}")
        return env_url

    # 3. 기본값
    default_url = "https://cx3s6h26lsl1am-8000.proxy.runpod.net"
    print(f"[RUNPOD URL SOURCE] 기본 URL 사용: {default_url}")
    return default_url


RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")

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
    runpod_url = get_runpod_base_url()
    health_url = runpod_url.rstrip("/") + "/health"
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

    runpod_url = get_runpod_base_url()
    run_url = runpod_url.rstrip("/") + "/run"
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    if RUNPOD_API_KEY:
        headers["X-API-KEY"] = RUNPOD_API_KEY

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