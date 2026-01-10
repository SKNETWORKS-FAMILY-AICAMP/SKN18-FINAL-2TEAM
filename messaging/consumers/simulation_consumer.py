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


def _ensure_django_setup():
    """Django가 setup되어 있는지 확인하고 필요시 setup"""
    try:
        import django
        if not django.apps.apps.ready:
            import os
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            django.setup()
    except Exception:
        # 이미 setup되어 있거나 다른 방식으로 setup된 경우
        pass


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
        _ensure_django_setup()
        
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
    options: dict | None = None,
    progress_callback: callable = None,
    ) -> Dict[str, Any]:
    try:
        base = views_runpod._get_runpod_sims_base_url()
        run_url = f"{base}/run"
    except RuntimeError as e:
        logger.error(f"[RunPod] base url error: {e}")
        return {"success": False, "error": str(e)}

    from pathlib import Path
    exp_part = Path(output_dir).name or "unknown"
    step_for_runpod = TOOL_NAME_QUEUE_MAP.get(tool_name, tool_name)
    job_name = f"{exp_part}__{tool_name}" 

    body = {
        "experiment_id": str(exp_part),
        "step": step_for_runpod,
        "options": options or {},   # ← 여기서만 options 사용
        "s3_upload_logs": True,
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
    poll_interval = 5                # 30초마다 상태 체크
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
                timeout=10,
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

        logger.info(f"[RunPod] status check: name={run_name}, status={status}, raw={s_data}")

        # 진행률 콜백 호출 (실행 중일 때)
        if progress_callback:
            try:
                progress_callback(status)  # status를 전달하여 콜백에서 상태에 따라 처리
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

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


def _get_previous_step_options(experiment_sid: int, tool_name: str) -> dict:
    """
    이전 단계의 tool_options를 조회
    
    Args:
        experiment_sid: 실험 ID
        tool_name: 도구 이름 ("RFdiffusion", "ProteinMPNN")
    
    Returns:
        tool_options 딕셔너리
    """
    _ensure_django_setup()
    
    try:
        selection = ExperimentToolSelection.objects.filter(
            experiment_id=experiment_sid,
            tool__tool_name=tool_name
        ).select_related("tool").order_by("sort_order").first()
        
        if selection and selection.tool_options_json:
            return json.loads(selection.tool_options_json)
    except Exception as e:
        logger.warning(f"Failed to get previous step options for {tool_name}: {e}")
    
    return {}


def enqueue_next_selection(experiment_sid: int, current_sort_order: int, requested_by: int | None):
    """
    현재 sort_order 이후의 다음 ExperimentToolSelection을 찾아
    그 도구를 RabbitMQ 큐에 넣는다.
    다음 단계가 없으면 None 반환.
    """
    try:
        _ensure_django_setup()

        qs = (
            ExperimentToolSelection.objects
            .select_related("experiment", "tool")
            .filter(experiment_id=experiment_sid)
            .order_by("sort_order")
        )

        # 🔹 추가: 현재 파이프라인 상태 찍기
        logger.info(
            "[enqueue_next] experiment_sid=%s, current_sort_order=%s, tools=%s",
            experiment_sid,
            current_sort_order,
            [(r.sort_order, r.tool.tool_name) for r in qs],
        )

        next_sel = qs.filter(sort_order__gt=current_sort_order).first()
        if not next_sel:
            return None  # 더 이상 다음 단계 없음

        total_steps = qs.count()

        tool_name_display = next_sel.tool.tool_name
        tool_name_for_queue = TOOL_NAME_QUEUE_MAP.get(tool_name_display)

        logger.info(
            "[enqueue_next] selected next tool: display=%s, queue=%s",
            tool_name_display,
            tool_name_for_queue,
        )

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
    """
    task_id = message.get("task_id")
    payload = message.get("payload") or {}
    experiment_sid_raw = payload.get("experiment_sid")

    tool_name = payload.get("tool_name")
    current_sort_order = int(payload.get("sort_order", 0))
    total_steps = int(payload.get("total_steps", 1))
    requested_by = message.get("requested_by")

    protein_sequence = payload.get("protein_sequence")
    tool_options = payload.get("tool_options") or {}

    # 🔹 AlphaFold3가 파이프라인 첫 단계일 때만 sequence-only 모드 ON
    #    (정확한 기준에 맞게 0/1 중 하나만 쓰셔도 됩니다)
    if tool_name == "AlphaFold3" and int(current_sort_order) == 1:
        if protein_sequence:
            tool_options["protein_sequence"] = protein_sequence
        tool_options["af_sequence_only"] = True

    if experiment_sid_raw is None:
        logger.error("Received message without experiment_sid: %s", message)
        return

    experiment_sid = int(experiment_sid_raw)
    
    try:
        # 진행률 계산 헬퍼 함수
        def calculate_step_progress(step_index, total_steps, phase="start"):
            """
            단계별 진행률 계산
            - 각 도구는 동일한 비율(100/total_steps)을 차지
            - 도구 완료 시: (step_index + 1) * (100 / total_steps)
            - 도구 시작 시: step_index * (100 / total_steps)
            phase: "start", "prepared", "running", "complete"
            """
            if total_steps <= 0:
                return 0
            
            # 각 단계가 차지하는 진행률 범위
            step_range = 100 / total_steps
            
            if phase == "complete":
                # 도구 완료 시: (step_index + 1) 단계까지 완료된 진행률
                # 예: step_index=0 (첫 번째) 완료 → 1 * 33.33 = 33%
                #     step_index=1 (두 번째) 완료 → 2 * 33.33 = 66%
                return min(100, int((step_index + 1) * step_range))
            elif phase == "start":
                # 도구 시작 시: step_index 단계까지 완료된 진행률
                # 예: step_index=0 (첫 번째) 시작 → 0 * 33.33 = 0%
                #     step_index=1 (두 번째) 시작 → 1 * 33.33 = 33%
                return min(100, int(step_index * step_range))
            else:
                # prepared, running: 완료된 단계 + 현재 단계 내 진행률
                previous_progress = step_index * step_range
                phase_progress = {
                    "prepared": 0.2,    # 준비 완료 (20%)
                    "running": 0.5,     # 실행 중 (50%)
                }.get(phase, 0.0)
                current_step_progress = step_range * phase_progress
                return min(100, int(previous_progress + current_step_progress))
        
        # 1. 워커 시작: 상태를 'E' (활성)로 업데이트 + 피드백 발행
        logger.info(f"Processing simulation: tool={tool_name}, experiment_sid={experiment_sid}")
        step_index = current_sort_order  # 0-based
        start_progress = calculate_step_progress(step_index, total_steps, "start")
        update_experiment_status(experiment_sid, 'E', start_progress)  # 워커 시작 → 활성
        publish_status(task_id, experiment_sid, 'E', start_progress)
        
        # 실험 시작 알림 생성 (첫 번째 단계일 때만)
        if current_sort_order == 0:  # 첫 번째 단계
            try:
                _ensure_django_setup()
                from apps.experiments.models import Experiment
                from apps.notification.notification_utils import create_experiment_start_notification
                
                experiment = Experiment.objects.get(experiment_sid=experiment_sid)
                user_id = experiment.created_id
                
                create_experiment_start_notification(
                    experiment_title=experiment.pipeline_name,
                    user_id=user_id,
                    experiment_id=experiment_sid
                )
                logger.info(f"Created experiment start notification for experiment {experiment_sid}")
            except Exception as e:
                logger.error(f"Failed to create experiment start notification: {e}", exc_info=True)
        
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
        
        # #출력 디렉토리/ 수정함
        output_dir = str(experiment_sid)
        # os.makedirs(output_dir, exist_ok=True)
        
        # 3. 준비 완료: 진행률 업데이트 (단계별 계산)
        prepared_progress = calculate_step_progress(step_index, total_steps, "prepared")
        update_experiment_status(experiment_sid, 'E', prepared_progress)  # 활성 상태 유지
        publish_status(task_id, experiment_sid, 'E', prepared_progress)
        
        # 진행률 콜백 함수 (RunPod 상태 폴링 시 진행률 업데이트)
        def update_running_progress(runpod_status):
            """RunPod 실행 중 진행률 업데이트"""
            running_progress = calculate_step_progress(step_index, total_steps, "running")
            # RunPod 상태가 "running"일 때만 'P' (진행중)로 변경
            if runpod_status == "running":
                update_experiment_status(experiment_sid, 'P', running_progress)  # 실행 중 → 진행중
                publish_status(task_id, experiment_sid, 'P', running_progress)
            else:
                # 아직 running이 아니면 활성 상태 유지
                update_experiment_status(experiment_sid, 'E', running_progress)
                publish_status(task_id, experiment_sid, 'E', running_progress)
        
        result = launch_simulation_docker(
            tool_name, 
            config_path, 
            output_dir, 
            options=tool_options,
            progress_callback=update_running_progress
            )
        
        logger.info(
            "[handle] RunPod result: tool=%s, success=%s, raw=%s",
            tool_name,
            result.get("success"),
            result.get("raw"),
        )

        if result["success"]:
            try:
                from django_app.apps.experiments.utils import (
                    register_experiment_results_for_step,
                )

                step_api = TOOL_NAME_QUEUE_MAP.get(tool_name, tool_name)
                expected_pdb = result.get("expected_pdb")

                # 각 도구별로 num_designs, num_seqs 추출
                num_designs = None
                num_seqs = None

                if step_api == "rfdiffusion":
                    # rfdiffusion: numSteps → num_designs
                    try:
                        num_designs = int((tool_options or {}).get("numSteps") or 1)
                    except (TypeError, ValueError):
                        num_designs = None
                
                elif step_api == "protein_mpnn":
                    # proteinMPNN: numSequences → num_seqs
                    try:
                        num_seqs = int((tool_options or {}).get("numSequences") or 1)
                    except (TypeError, ValueError):
                        num_seqs = None
                
                elif step_api == "alphafold3":
                    # alphafold: 
                    # - num_designs: 이전 단계(RFdiffusion)의 numSteps 값
                    # - num_seqs: 이전 단계(ProteinMPNN)의 numSequences 값
                    try:
                        # 이전 단계의 tool_options 조회
                        rfdiffusion_options = _get_previous_step_options(experiment_sid, "RFdiffusion")
                        mpnn_options = _get_previous_step_options(experiment_sid, "ProteinMPNN")
                        
                        # RFdiffusion의 numSteps → num_designs
                        num_designs = int(rfdiffusion_options.get("numSteps") or 1)
                        
                        # ProteinMPNN의 numSequences → num_seqs
                        num_seqs = int(mpnn_options.get("numSequences") or 8)
                            
                        logger.info(
                            f"[alphafold3] Extracted from previous steps: "
                            f"num_designs={num_designs} (from RFdiffusion), "
                            f"num_seqs={num_seqs} (from ProteinMPNN)"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract previous step values for alphafold3: {e}. "
                            f"Using defaults: num_designs=1, num_seqs=8",
                            exc_info=True
                        )
                        num_designs = 1
                        num_seqs = 8
                # expected_pdb가 있으면 모든 도구에 대해 결과 등록
                # expected_pdb는 각 도구별로 다른 파일 타입일 수 있지만,
                # 경로 구조는 동일하므로 이를 기반으로 날짜/step 추출 가능
                if expected_pdb:
                    register_experiment_results_for_step(
                        experiment_sid=experiment_sid,
                        step_api=step_api,
                        expected_local_path=expected_pdb,
                        num_designs=num_designs,
                        num_seqs=num_seqs,
                    )
                    logger.info(
                        f"Registered results for experiment {experiment_sid}, "
                        f"step={step_api}, num_designs={num_designs}, num_seqs={num_seqs}"
                    )
                else:
                    logger.warning(
                        f"No expected_pdb in result for experiment {experiment_sid}, "
                        f"step={step_api}. Results not registered."
                    )
            except Exception as e:
                logger.error(
                    "Failed to register experiment results: %s", e, exc_info=True
                )
            
            # 파이프라인 진행률 계산 (현재 단계 완료)
            # step_index는 0-based이므로 현재 단계 완료 = (step_index + 1) 단계 완료
            step_complete_progress = calculate_step_progress(step_index, total_steps, "complete")

            # 다음 단계 큐잉 시도
            next_task_id = enqueue_next_selection(
                experiment_sid=experiment_sid,
                current_sort_order=current_sort_order,
                requested_by=requested_by,
            )

            # 실험 정보 및 도구 이름 가져오기 (알림용)
            _ensure_django_setup()
            from apps.experiments.models import Experiment, ExperimentToolSelection
            
            try:
                experiment = Experiment.objects.get(experiment_sid=experiment_sid)
                user_id = experiment.created_id
                pipeline_name = experiment.pipeline_name
                
                # 현재 단계의 도구 이름 가져오기
                tool_selection = ExperimentToolSelection.objects.filter(
                    experiment_id=experiment_sid,
                    sort_order=current_sort_order
                ).select_related('tool').first()
                
                tool_name = tool_selection.tool.tool_name if tool_selection and tool_selection.tool else "알 수 없는 도구"
                
            except Exception as e:
                logger.error(f"Failed to get experiment info for notification: {e}", exc_info=True)
                user_id = None
                pipeline_name = "알 수 없는 실험"
                tool_name = "알 수 없는 도구"
            
            if next_task_id:
                # 아직 남은 단계가 있으므로 진행 중 상태 유지
                update_experiment_status(experiment_sid, 'P', step_complete_progress)
                publish_status(
                    task_id,
                    experiment_sid,
                    'P',
                    step_complete_progress,
                    {"next_task_id": next_task_id},
                )
                
                # 중간 단계: 도구 완료 알림만 생성
                if user_id:
                    try:
                        from apps.notification.notification_utils import create_experiment_tool_complete_notification
                        create_experiment_tool_complete_notification(
                            experiment_title=pipeline_name,
                            tool_name=tool_name,
                            user_id=user_id,
                            experiment_id=experiment_sid
                        )
                        logger.info(f"Created tool complete notification for {tool_name} in experiment {experiment_sid}")
                    except Exception as e:
                        logger.error(f"Failed to create tool complete notification: {e}", exc_info=True)
                
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
                
                # 마지막 단계: 통합 알림 생성 (도구 완료 + 실험 완료)
                if user_id:
                    try:
                        from apps.notification.notification_utils import create_experiment_final_tool_complete_notification
                        create_experiment_final_tool_complete_notification(
                            experiment_title=pipeline_name,
                            tool_name=tool_name,
                            user_id=user_id,
                            experiment_id=experiment_sid
                        )
                        logger.info(f"Created final tool complete notification for {tool_name} (experiment {experiment_sid} completed)")
                    except Exception as e:
                        logger.error(f"Failed to create final tool complete notification: {e}", exc_info=True)
                
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

