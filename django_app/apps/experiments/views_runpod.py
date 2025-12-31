import os
import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


RUNPOD_BASE_URL = os.environ.get(
    "RUNPOD_BASE_URL",
    "https://fclsjznz4y1zs0-8888.proxy.runpod.net",
)


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
    if not isinstance(request.data, dict):
        return Response({"detail": "JSON body is required."}, status=400)

    run_url = RUNPOD_BASE_URL.rstrip("/") + "/run"
    try:
        resp = requests.post(
            run_url,
            json=request.data,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    except requests.RequestException as exc:
        return Response({"detail": f"RunPod request failed: {exc}"}, status=502)

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text}

    return Response(data, status=resp.status_code)
