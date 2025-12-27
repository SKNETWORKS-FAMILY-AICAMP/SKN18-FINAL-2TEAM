"""
시뮬레이션 작업 Producer
"""
import logging
from typing import Dict, Any
from messaging.producers.base import BaseProducer
from messaging.schemas.base import TaskMessage

logger = logging.getLogger(__name__)


class SimulationProducer(BaseProducer):
    """시뮬레이션 작업 Producer"""
    
    def __init__(self, tool_name: str):
        """
        Args:
            tool_name: 시뮬레이션 도구 이름 ("alphafold3", "protein_mpnn", "rfdiffusion")
        """
        routing_key = f"sim.run.{tool_name}"
        super().__init__(routing_key)
        self.tool_name = tool_name
    
    def publish_simulation_task(
        self,
        experiment_sid: int,
        payload: Dict[str, Any],
        user_id: int = None
    ) -> str:
        """
        시뮬레이션 작업 큐에 추가
        
        Args:
            experiment_sid: 실험 ID
            payload: 작업 페이로드 (protein_sequence, protein_name, tool_selections 등)
            user_id: 요청한 사용자 ID
        
        Returns:
            task_id: 생성된 작업 ID
        """
        # 표준 메시지 생성
        message = TaskMessage.create(
            payload={
                "experiment_sid": experiment_sid,
                "tool_name": self.tool_name,
                **payload
            },
            user_id=user_id,
            resource_uri=f"/api/experiments/{experiment_sid}/"
        )
        
        # 메시지 발행
        self.publish(message.to_dict())
        
        logger.info(f"Simulation task queued: tool={self.tool_name}, experiment_sid={experiment_sid}, task_id={message.task_id}")
        
        return message.task_id

