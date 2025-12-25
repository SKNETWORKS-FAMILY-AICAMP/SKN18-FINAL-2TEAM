"""
표준 메시지 스키마 정의
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class TaskMessage:
    """표준 작업 메시지 스키마"""
    task_id: str
    requested_by: Optional[int]  # user_id
    resource_uri: Optional[str]  # 관련 리소스 URI (예: /api/experiments/123/)
    timestamp: str
    payload: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "task_id": self.task_id,
            "requested_by": self.requested_by,
            "resource_uri": self.resource_uri,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
    
    @classmethod
    def create(
        cls,
        payload: Dict[str, Any],
        user_id: Optional[int] = None,
        resource_uri: Optional[str] = None
    ) -> 'TaskMessage':
        """새 작업 메시지 생성"""
        return cls(
            task_id=str(uuid.uuid4()),
            requested_by=user_id,
            resource_uri=resource_uri,
            timestamp=datetime.utcnow().isoformat(),
            payload=payload,
        )


@dataclass
class StatusMessage:
    """상태 피드백 메시지 스키마"""
    task_id: str
    experiment_sid: Optional[int]
    status: str  # 'E', 'R', 'C', 'F'
    progress: int  # 0-100
    data: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "task_id": self.task_id,
            "experiment_sid": self.experiment_sid,
            "status": self.status,
            "progress": self.progress,
            "data": self.data or {},
            "timestamp": self.timestamp,
        }

