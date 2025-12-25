"""
Django 메시지 큐 래퍼 모듈
간단한 인터페이스로 메시지 발행
"""
import logging
from typing import Dict, Any, Optional
from messaging.producers.simulation_producer import SimulationProducer
from messaging.schemas.base import TaskMessage

logger = logging.getLogger(__name__)


def publish_simulation(
    tool_name: str,
    experiment_sid: int,
    payload: Dict[str, Any],
    user_id: Optional[int] = None
) -> str:
    """
    시뮬레이션 작업 메시지 발행
    
    Args:
        tool_name: 시뮬레이션 도구 이름 ("alphafold3", "protein_mpnn", "rfdiffusion")
        experiment_sid: 실험 ID
        payload: 작업 페이로드 (protein_sequence, protein_name, tool_selections 등)
        user_id: 요청한 사용자 ID (선택)
    
    Returns:
        task_id: 생성된 작업 ID
    """
    try:
        producer = SimulationProducer(tool_name=tool_name)
        task_id = producer.publish_simulation_task(
            experiment_sid=experiment_sid,
            payload=payload,
            user_id=user_id
        )
        logger.info(f"Simulation task queued: tool={tool_name}, experiment_sid={experiment_sid}, task_id={task_id}")
        return task_id
    except Exception as e:
        logger.error(f"Failed to publish simulation task: {e}", exc_info=True)
        raise


# 확장 가능한 인터페이스 (향후 다른 작업 타입 추가 시)
def publish(topic: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> str:
    """
    범용 메시지 발행 인터페이스 (확장 가능)
    
    Args:
        topic: 라우팅 키 또는 토픽 (예: "sim.run.alphafold3", "rag.etl.pubmed")
        payload: 메시지 페이로드
        user_id: 요청한 사용자 ID (선택)
    
    Returns:
        task_id: 생성된 작업 ID
    """
    # 시뮬레이션 작업인 경우
    if topic.startswith("sim.run."):
        tool_name = topic.replace("sim.run.", "")
        experiment_sid = payload.get("experiment_sid")
        if not experiment_sid:
            raise ValueError("experiment_sid is required for simulation tasks")
        return publish_simulation(tool_name, experiment_sid, payload, user_id)
    
    # 향후 다른 작업 타입 추가 가능
    # elif topic.startswith("rag.etl."):
    #     return publish_etl(...)
    # elif topic.startswith("kg.sync."):
    #     return publish_kg_sync(...)
    
    else:
        raise ValueError(f"Unknown topic: {topic}")

