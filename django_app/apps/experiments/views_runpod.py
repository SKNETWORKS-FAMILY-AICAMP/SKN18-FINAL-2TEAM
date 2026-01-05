# django_app/apps/experiments/views_runpod.py (FULL)

import os
import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


def _get_runpod_sims_base_url() -> str:
    """
    RUNPOD_SIMS_BASE_URL은 반드시 환경변수(.env)로 주입해야 함.
    예) https://xxxx.proxy.runpod.net
    """
    base = (os.environ.get("RUNPOD_SIMS_BASE_URL") or "").strip()

    if not base:
        # 운영에서 하드코딩으로 넘어가면 사고나기 쉬워서 "없으면 명확히 에러"로 처리
        raise RuntimeError(
            "RUNPOD_SIMS_BASE_URL is not set. Put it in .env (RUNPOD_SIMS_BASE_URL=https://...)"
        )

    if not (base.startswith("http://") or base.startswith("https://")):
        raise RuntimeError(
            f"RUNPOD_SIMS_BASE_URL must start with http:// or https:// (got: {base})"
        )

    return base.rstrip("/")


def _headers() -> dict:
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    api_key = (os.environ.get("RUNPOD_SIMS_API_KEY") or "").strip()
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