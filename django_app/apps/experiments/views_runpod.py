import os
import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


RUNPOD_BASE_URL = os.environ.get(
    "RUNPOD_BASE_URL",
    "https://cx3s6h26lsl1am-8000.proxy.runpod.net",
)
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")

@extend_schema(
    summary="Run RFdiffusion on RunPod",
    description="Forward RFdiffusion parameters to RunPod /run endpoint.",
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
def rfdiffusion_runpod_api(request):
    '''
    API가 동작하는지만 테스트하는 더미 API
    '''
    
    print("출력이야..")
    
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
    health_url = RUNPOD_BASE_URL.rstrip("/") + "/health"
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
    description="Forward POST payload to the RunPod /run endpoint deployed via sim_tools/unified/api_server.py.",
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

    run_url = RUNPOD_BASE_URL.rstrip("/") + "/run"
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
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as exc:
        return Response({"detail": f"RunPod run request failed: {exc}"}, status=502)

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text}

    return Response(data, status=resp.status_code)



