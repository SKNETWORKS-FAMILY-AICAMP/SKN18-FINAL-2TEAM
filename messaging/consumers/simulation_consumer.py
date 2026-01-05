"""
시뮬레이션 작업 Consumer
기존 sim_tools 코드를 재사용하여 시뮬레이션 실행
"""
import logging
import subprocess
import os
import json
from typing import Dict, Any
from datetime import datetime
import requests
from django_app.apps.experiments import views_runpod 
import sys
from pathlib import Path
import time

# 프로젝트 루트(SKN18-FINAL-2TEAM) 기준으로 django_app 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DJANGO_APP_DIR = PROJECT_ROOT / "django_app"
if str(DJANGO_APP_DIR) not in sys.path:
    sys.path.insert(0, str(DJANGO_APP_DIR))

from messaging.consumers.base import BaseConsumer
from messaging.producers.base import TopicProducer
from messaging.schemas.base import StatusMessage
from apps.experiments.models import ExperimentToolSelection
from apps.core.queue import publish_simulation 
logger = logging.getLogger(__name__)

TOOL_NAME_QUEUE_MAP = {
    "RFdiffusion": "rfdiffusion",
    "ProteinMPNN": "protein_mpnn",
    "AlphaFold3": "alphafold3",
}

def update_experiment_status(
    experiment_sid: int,
    status: str,
    progress: int = None,
    error_message: str = None
):
    """
    실험 상태 업데이트 (Django ORM 사용)
    
    Args:
        experiment_sid: 실험 ID
        status: 상태 ('E', 'R', 'C', 'F')
        progress: 진행률 (0-100)
        error_message: 에러 메시지 (실패 시)
    """
    try:
        # Django 설정 로드
        import django
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()
        
        from django_app.apps.experiments.utils import update_experiment_status as update_status
        update_status(experiment_sid, status, progress, error_message)
            
    except Exception as e:
        logger.error(f"Failed to update experiment status: {e}", exc_info=True)
        raise


def publish_status(
    task_id: str,
    experiment_sid: int,
    status: str,
    progress: int,
    data: Dict[str, Any] = None
):
    """상태 피드백 발행"""
    try:
        status_producer = TopicProducer(exchange="status.topic")
        status_message = StatusMessage(
            task_id=task_id,
            experiment_sid=experiment_sid,
            status=status,
            progress=progress,
            data=data or {}
        )
        status_producer.publish("sim.status", status_message.to_dict())
        logger.info(f"Status published: experiment_sid={experiment_sid}, status={status}")
    except Exception as e:
        logger.error(f"Failed to publish status: {e}", exc_info=True)


def launch_simulation_docker(
    tool_name: str,
    config_path: str,
    output_dir: str,
) -> Dict[str, Any]:
    try:
        base = views_runpod._get_runpod_base_url()
        run_url = f"{base}/run"
    except RuntimeError as e:
        logger.error(f"[RunPod] base url error: {e}")
        return {"success": False, "error": str(e)}

    from pathlib import Path
    exp_part = Path(output_dir).name or "unknown"
    job_name = f"{exp_part}__{tool_name}"  # 앞에서 정리한 형식 유지

    body = {
        "mode": "backbone",
        "name": job_name,
        "contigs": "100",
        "iterations": 1,
        "s3_upload_logs": False,
    }

    # 1) /run 호출
    try:
        resp = requests.post(
            run_url,
            json=body,
            headers=views_runpod._headers(),
            timeout=60,
        )
    except requests.RequestException as exc:
        logger.error(f"[RunPod] /run request failed: {exc}", exc_info=True)
        return {"success": False, "error": str(exc)}

    try:
        data = resp.json()
    except ValueError:
        data = {"detail": resp.text}

    ok = resp.ok and bool(data.get("ok", False))
    run_outputs_dir = data.get("outputs_dir")
    run_name = data.get("name", job_name)

    if not ok:
        error_msg = data.get("detail") or f"HTTP {resp.status_code}"
        logger.error(f"[RunPod] simulation enqueue error: {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "status_code": resp.status_code,
            "raw": data,
        }

    # 여기까지가 “작업 큐에 올림” 단계

    # 2) /status/{name} 폴링 (동기 완료 대기)
    status_url = f"{base}/status/{run_name}"

    max_wait_seconds = 60 * 60 * 24     # 최대 1시간 대기 (원하시면 조정)
    poll_interval = 60 * 3                # 30초마다 상태 체크
    start_ts = time.time()

    last_status = None
    last_payload = None

    while True:
        # timeout 체크
        elapsed = time.time() - start_ts
        if elapsed > max_wait_seconds:
            logger.error(
                f"[RunPod] status timeout: name={run_name}, "
                f"last_status={last_status}"
            )
            return {
                "success": False,
                "error": f"RunPod status timeout after {int(elapsed)}s",
                "status": last_status,
                "raw": last_payload,
            }

        try:
            s_resp = requests.get(
                status_url,
                headers=views_runpod._headers(),
                timeout=30,
            )
            try:
                s_data = s_resp.json()
            except ValueError:
                s_data = {"detail": s_resp.text}

        except requests.RequestException as exc:
            # 네트워크가 잠깐 끊긴 경우에는 한 번 더 재시도하고,
            # 심각한 장애로 보고 싶으면 바로 실패로 리턴해도 됨
            logger.warning(f"[RunPod] /status request failed: {exc}")
            time.sleep(poll_interval)
            continue

        last_payload = s_data
        status = s_data.get("status")
        last_status = status

        logger.info(f"[RunPod] status check: name={run_name}, status={status}")

        if status == "done":
            # unified/api_server.py 기준:
            # expected_pdb = OUTPUTS_DIR/name_0.pdb
            expected_pdb = s_data.get("expected_pdb")
            return {
                "success": True,
                "output_dir": run_outputs_dir,
                "job_name": run_name,
                "expected_pdb": expected_pdb,
                "raw": s_data,
            }

        if status == "failed":
            log_path = s_data.get("log_path")
            logger.error(
                f"[RunPod] simulation failed: name={run_name}, "
                f"log={log_path}"
            )
            return {
                "success": False,
                "error": "RunPod simulation failed",
                "status": status,
                "log_path": log_path,
                "raw": s_data,
            }

        # running / unknown 이면 잠깐 대기 후 다시 체크
        time.sleep(poll_interval)



# def has_older_pending_experiment(current_experiment_sid: int) -> bool:
    """
    현재 experiment_sid 보다 먼저 생성된 실험 중에
    아직 완료되지 않은(E, R, P) 것이 있는지 확인.
    있으면 True → 지금 메시지는 나중에 처리해야 함.
    """
    import django
    import os as _os
    from django.db.models import Q

    _os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.experiments.models import Experiment

    return Experiment.objects.filter(
        experiment_sid__lt=current_experiment_sid,
        status__in=["E", "R", "P"],
    ).exists()

def enqueue_next_selection(experiment_sid: int, current_sort_order: int, requested_by: int | None):
    """
    현재 sort_order 이후의 다음 ExperimentToolSelection을 찾아
    그 도구를 RabbitMQ 큐에 넣는다.
    다음 단계가 없으면 None 반환.
    """
    try:
        import django
        import os as _os
        _os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()

        qs = (
            ExperimentToolSelection.objects
            .select_related("experiment", "tool")
            .filter(experiment_id=experiment_sid)
            .order_by("sort_order")
        )
        next_sel = qs.filter(sort_order__gt=current_sort_order).first()
        if not next_sel:
            return None  # 더 이상 다음 단계 없음

        total_steps = qs.count()

        tool_name_display = next_sel.tool.tool_name
        tool_name_for_queue = TOOL_NAME_QUEUE_MAP.get(tool_name_display)
        if not tool_name_for_queue:
            logger.warning(f"Unknown tool for queue: {tool_name_display}")
            return None

        try:
            tool_options = json.loads(next_sel.tool_options_json or "{}")
        except json.JSONDecodeError:
            tool_options = {}

        payload = {
            "protein_sequence": next_sel.experiment.protein_sequence,
            "protein_name": next_sel.experiment.protein_name,
            "selection_sid": next_sel.selection_sid,
            "tool_sid": next_sel.tool_id,
            "tool_name": tool_name_display,
            "sort_order": next_sel.sort_order,
            "total_steps": total_steps,
            "tool_options": tool_options,
        }

        user_id = requested_by

        last_error = None
        for attempt in range(3):
            try:
                task_id = publish_simulation(
                    tool_name=tool_name_for_queue,
                    experiment_sid=experiment_sid,
                    payload=payload,
                    user_id=user_id,
                )
                break
            except Exception as e:
                last_error = e
                logger.error(
                    "[Simulation] Failed to enqueue next selection "
                    "(experiment_sid=%s, sort_order=%s, attempt=%s): %s",
                    experiment_sid,
                    current_sort_order,
                    attempt + 1,
                    e,
                )
                time.sleep(2)
        else:
            # 재시도 3번 모두 실패하면 그대로 예외 올림
            raise last_error

        logger.info(
            "Enqueued next step: experiment_sid=%s, sort_order=%s, task_id=%s",
            experiment_sid,
            next_sel.sort_order,
            task_id,
        )
        return task_id

    except Exception as e:
        logger.error("Failed to enqueue next selection: %s", e, exc_info=True)
        return None




def handle_simulation_task(message: Dict[str, Any]):
    """
    시뮬레이션 작업 처리
    
    Args:
        message: 메시지 딕셔너리
    """
    task_id = message.get("task_id")
    payload = message.get("payload") or {}
    experiment_sid_raw = payload.get("experiment_sid")

    tool_name = payload.get("tool_name")
    
    # 파이프라인 단계 정보 / 요청자 ID
    current_sort_order = payload.get("sort_order", 0)
    total_steps = payload.get("total_steps", 1)
    requested_by = message.get("requested_by")
    
    if experiment_sid_raw is None:
        logger.error("Received message without experiment_sid: %s", message)
        return  # 더 할 수 있는 게 없으니 그냥 ACK 처리
    
    experiment_sid = int(experiment_sid_raw)
    sort_order = int(payload.get("sort_order", 0))

    # # 2) 첫 스텝일 때만 “앞선 미완료 실험 있으면 재큐잉”
    # if sort_order == 0 and has_older_pending_experiment(experiment_sid):
    #     logger.info(
    #         "Skip for now: experiment_sid=%s has older pending experiments. Requeue.",
    #         experiment_sid,
    #     )
    #     raise RuntimeError("Older pending experiment exists")
    
    # if has_older_pending_experiment(experiment_sid):
    #     logger.info(
    #         f"Skip for now: experiment_sid={experiment_sid} has older pending experiments. Requeue."
    #     )
    #     # 그냥 예외를 던지면 BaseConsumer가 basic_nack(..., requeue=True) 해서
    #     # 메시지를 큐 뒤로 다시 넣어 줍니다.
    #     raise RuntimeError("Older pending experiment exists")
    
    try:
        # 1. 시작: 상태 업데이트 + 피드백 발행
        logger.info(f"Processing simulation: tool={tool_name}, experiment_sid={experiment_sid}")
        update_experiment_status(experiment_sid, 'R', 0)
        publish_status(task_id, experiment_sid, 'R', 0)
        
        # 2. 시뮬레이션 실행 준비
        protein_sequence = payload.get("protein_sequence")
        protein_name = payload.get("protein_name", "unknown")
        
        # 설정 파일 생성 (임시)
        config_dir = f"/tmp/sim_configs/{experiment_sid}"
        os.makedirs(config_dir, exist_ok=True)
        config_path = f"{config_dir}/config.yml"
        
        # YAML 설정 파일 작성 (간단한 예시)
        import yaml
        config_data = {
            "model": tool_name,
            "input": {
                "sequence": protein_sequence,
            },
            "output": {
                "save_dir": f"/output/{experiment_sid}",
            }
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # 출력 디렉토리/ 수정함
        output_dir = str(experiment_sid)
        os.makedirs(output_dir, exist_ok=True)
        
        # 3. 진행률 업데이트: 25%
        update_experiment_status(experiment_sid, 'R', 25)
        publish_status(task_id, experiment_sid, 'R', 25)
        
        result = launch_simulation_docker(tool_name, config_path, output_dir)

        if result["success"]:
            # 파이프라인 진행률 계산 (0-based sort_order → 1-based 단계)
            step_index = current_sort_order + 1
            pipeline_progress = int(100 * step_index / max(total_steps, 1))

            # 다음 단계 큐잉 시도
            next_task_id = enqueue_next_selection(
                experiment_sid=experiment_sid,
                current_sort_order=current_sort_order,
                requested_by=requested_by,
            )

            if next_task_id:
                # 아직 남은 단계가 있으므로 진행 중 상태 유지
                update_experiment_status(experiment_sid, 'R', pipeline_progress)
                publish_status(
                    task_id,
                    experiment_sid,
                    'R',
                    pipeline_progress,
                    {"next_task_id": next_task_id},
                )
                logger.info(
                    f"Step completed: experiment_sid={experiment_sid}, "
                    f"sort_order={current_sort_order}, next_task_id={next_task_id}"
                )
            else:
                # 마지막 단계 → 전체 파이프라인 완료
                update_experiment_status(experiment_sid, 'C', 100)
                publish_status(
                    task_id,
                    experiment_sid,
                    'C',
                    100,
                    {"output_dir": output_dir, "result": result},
                )
                logger.info(f"Simulation pipeline completed: experiment_sid={experiment_sid}")
        else:
            # 실패 처리
            error_msg = result.get("error", "Unknown error")
            update_experiment_status(experiment_sid, 'F', 0, error_msg)
            publish_status(
                task_id,
                experiment_sid,
                'F',
                0,
                {"error": error_msg}
            )
            logger.error(f"Simulation failed: experiment_sid={experiment_sid}, error={error_msg}")
            
    except Exception as e:
        logger.error(f"Error processing simulation task: {e}", exc_info=True)
        # 실패 처리
        update_experiment_status(experiment_sid, 'F', 0, str(e))
        publish_status(
            task_id,
            experiment_sid,
            'F',
            0,
            {"error": str(e)}
        )


def start_simulation_consumer(tool_name: str):
    """
    시뮬레이션 Consumer 시작
    
    Args:
        tool_name: 도구 이름 ("alphafold3", "protein_mpnn", "rfdiffusion")
    """
    routing_key = f"sim.run.{tool_name}"
    consumer = BaseConsumer(routing_key, handle_simulation_task)
    consumer.start_consuming()

