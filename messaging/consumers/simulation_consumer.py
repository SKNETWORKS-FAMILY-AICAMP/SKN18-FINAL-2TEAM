"""
시뮬레이션 작업 Consumer
기존 sim_tools 코드를 재사용하여 시뮬레이션 실행
"""
import logging
import subprocess
import os
from typing import Dict, Any
from datetime import datetime
from messaging.consumers.base import BaseConsumer
from messaging.producers.topic_producer import TopicProducer
from messaging.schemas.base import StatusMessage

logger = logging.getLogger(__name__)


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
    output_dir: str
) -> Dict[str, Any]:
    """
    Docker 컨테이너로 시뮬레이션 실행
    
    Args:
        tool_name: 도구 이름 ("alphafold3", "protein_mpnn", "rfdiffusion")
        config_path: YAML 설정 파일 경로
        output_dir: 출력 디렉토리
    
    Returns:
        실행 결과 딕셔너리
    """
    docker_image = f"bio-med/{tool_name}:latest"
    
    # Docker 실행 명령
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{config_path}:/app/config.yml:ro",
        "-v", f"{output_dir}:/output",
        docker_image
    ]
    
    try:
        logger.info(f"Launching simulation: {tool_name}, config={config_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1시간 타임아웃
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "output_dir": output_dir,
                "stdout": result.stdout,
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "returncode": result.returncode,
            }
            
    except subprocess.TimeoutExpired:
        logger.error(f"Simulation timeout: {tool_name}")
        return {
            "success": False,
            "error": "Simulation timeout (1 hour)",
        }
    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def handle_simulation_task(message: Dict[str, Any]):
    """
    시뮬레이션 작업 처리
    
    Args:
        message: 메시지 딕셔너리
    """
    task_id = message.get("task_id")
    payload = message.get("payload", {})
    experiment_sid = payload.get("experiment_sid")
    tool_name = payload.get("tool_name")
    
    if not experiment_sid or not tool_name:
        logger.error(f"Invalid message: missing experiment_sid or tool_name")
        return
    
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
        
        # 출력 디렉토리
        output_dir = f"/data/sim_results/{experiment_sid}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 3. 진행률 업데이트: 25%
        update_experiment_status(experiment_sid, 'R', 25)
        publish_status(task_id, experiment_sid, 'R', 25)
        
        # 4. 시뮬레이션 실행
        result = launch_simulation_docker(tool_name, config_path, output_dir)
        
        if result["success"]:
            # 5. 진행률 업데이트: 75%
            update_experiment_status(experiment_sid, 'R', 75)
            publish_status(task_id, experiment_sid, 'R', 75)
            
            # 6. 결과 저장 (t_experiment_result 테이블)
            # TODO: 결과 파일을 t_experiment_result에 저장
            
            # 7. 완료: 상태 업데이트 + 피드백 발행
            update_experiment_status(experiment_sid, 'C', 100)
            publish_status(
                task_id,
                experiment_sid,
                'C',
                100,
                {"output_dir": output_dir, "result": result}
            )
            
            logger.info(f"Simulation completed: experiment_sid={experiment_sid}")
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
