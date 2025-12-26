"""
실험 관련 View 예시 (참고용)
실제 구현 시 이 패턴을 따라 구현하세요
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_app.apps.core.queue import publish_simulation
from django_app.apps.experiments.utils import update_experiment_status


@login_required
@require_http_methods(["POST"])
def run_simulation(request, experiment_sid):
    """
    시뮬레이션 실행 요청 (비동기)
    
    예시:
        POST /api/experiments/123/run/
        {
            "tool_name": "alphafold3",
            "protein_sequence": "ACDEFGHIKLMNPQRSTVWY",
            "protein_name": "Test Protein"
        }
    """
    try:
        # 1. 실험 조회 및 검증
        from django_app.apps.experiments.models import Experiment
        experiment = Experiment.objects.get(experiment_sid=experiment_sid)
        
        # 이미 진행 중이거나 완료된 실험은 재실행 불가
        if experiment.status in ['R', 'C']:
            return JsonResponse({
                "error": f"Experiment is already {experiment.status}"
            }, status=400)
        
        # 2. 요청 데이터 파싱
        tool_name = request.POST.get("tool_name") or request.json.get("tool_name")
        protein_sequence = request.POST.get("protein_sequence") or request.json.get("protein_sequence")
        protein_name = request.POST.get("protein_name") or request.json.get("protein_name")
        
        if not tool_name or not protein_sequence:
            return JsonResponse({
                "error": "tool_name and protein_sequence are required"
            }, status=400)
        
        # 3. 실험 정보 업데이트
        experiment.pipeline_name = tool_name
        experiment.protein_sequence = protein_sequence
        experiment.protein_name = protein_name
        experiment.status = 'E'  # 준비 상태
        experiment.progress = 0
        experiment.save()
        
        # 4. 메시지 큐에 작업 발행
        task_id = publish_simulation(
            tool_name=tool_name,
            experiment_sid=experiment.experiment_sid,
            payload={
                "protein_sequence": protein_sequence,
                "protein_name": protein_name,
                # tool_selections는 별도 조회 필요
                # "tool_selections": get_tool_selections(experiment.experiment_sid),
            },
            user_id=request.user.id
        )
        
        # 5. 상태를 'R' (진행중)로 업데이트
        update_experiment_status(experiment.experiment_sid, 'R', 0)
        
        # 6. 즉시 응답 (작업은 백그라운드에서 처리)
        return JsonResponse({
            "status": "queued",
            "experiment_sid": experiment.experiment_sid,
            "task_id": task_id,
            "message": "Simulation task has been queued"
        })
        
    except Experiment.DoesNotExist:
        return JsonResponse({
            "error": "Experiment not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def experiment_status(request, experiment_sid):
    """
    실험 상태 조회
    
    예시:
        GET /api/experiments/123/status/
    """
    try:
        from django_app.apps.experiments.models import Experiment
        experiment = Experiment.objects.get(experiment_sid=experiment_sid)
        
        return JsonResponse({
            "experiment_sid": experiment.experiment_sid,
            "status": experiment.status,
            "progress": experiment.progress,
            "pipeline_name": experiment.pipeline_name,
            "updated_at": experiment.updated_at.isoformat(),
        })
        
    except Experiment.DoesNotExist:
        return JsonResponse({
            "error": "Experiment not found"
        }, status=404)

