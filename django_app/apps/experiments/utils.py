"""
실험 관련 유틸리티 함수
상태 업데이트, 멱등성 보장 등
"""
import logging
from django.db import transaction
from django.utils import timezone
from typing import Optional

logger = logging.getLogger(__name__)


def update_experiment_status(
    experiment_sid: int,
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
):
    """
    실험 상태 업데이트 (멱등성 보장)
    
    Args:
        experiment_sid: 실험 ID
        status: 상태 ('E': 준비, 'R': 진행중, 'C': 완료, 'F': 실패)
        progress: 진행률 (0-100, 선택)
        error_message: 에러 메시지 (실패 시, 선택)
    """
    from django_app.apps.experiments.models import Experiment
    
    with transaction.atomic():
        # SELECT FOR UPDATE로 동시성 제어
        experiment = Experiment.objects.select_for_update().get(
            experiment_sid=experiment_sid
        )
        
        # 상태 전이 검증
        valid_transitions = {
            'E': ['R', 'F'],  # 준비 → 진행중/실패
            'R': ['C', 'F'],  # 진행중 → 완료/실패
            'C': [],  # 완료는 최종 상태
            'F': [],  # 실패는 최종 상태
        }
        
        if status not in valid_transitions.get(experiment.status, []):
            logger.warning(
                f"Invalid status transition: {experiment.status} → {status} "
                f"for experiment {experiment_sid}"
            )
            return
        
        # 업데이트
        experiment.status = status
        if progress is not None:
            experiment.progress = progress
        experiment.updated_at = timezone.now()
        experiment.save()
        
        logger.info(
            f"Experiment {experiment_sid} status updated: {status}, "
            f"progress={progress}%"
        )

