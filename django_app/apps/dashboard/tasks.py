"""
Dashboard 앱의 Celery Tasks

일정 리마인더 체크 등의 주기적 작업과 알림 생성을 Celery task로 정의합니다.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from typing import Optional, List, Dict
from apps.schedule.models import Schedule
from apps.dashboard.notification_utils import (
    create_schedule_reminder_notification,
    create_notification,
    bulk_create_notifications
)
import logging

logger = logging.getLogger(__name__)


@shared_task(name='apps.dashboard.tasks.check_schedule_reminders')
def check_schedule_reminders(check_minutes=60):
    """
    일정 리마인더 체크 및 알림 생성 Celery Task
    
    이 task는 Celery Beat에 의해 주기적으로 실행됩니다.
    (예: 매 5분마다)
    
    Args:
        check_minutes: 체크할 시간 범위 (분 단위, 기본값: 60분)
    
    Returns:
        dict: 처리 결과 정보
    """
    try:
        now = timezone.now()
        check_until = now + timedelta(minutes=check_minutes)
        
        logger.info(f"Checking schedules from {now} to {check_until}")
        
        # 예정된 일정 중에서 리마인더가 필요한 일정 찾기
        upcoming_schedules = Schedule.objects.filter(
            start_date__gte=now,
            start_date__lte=check_until,
            use_yn='Y',
            schedule_status='E'  # 예정 상태
        ).select_related('calendar')
        
        notifications_created = 0
        
        for schedule in upcoming_schedules:
            # 일정 시작까지 남은 시간 계산
            time_diff = schedule.start_date - now
            minutes_until = int(time_diff.total_seconds() / 60)
            
            # 리마인더 시간대별로 알림 생성
            reminder_times = [60, 30, 15, 5]  # 1시간 전, 30분 전, 15분 전, 5분 전
            
            for reminder_minutes in reminder_times:
                # 해당 시간대에 정확히 맞는 알림 생성 (범위: reminder_minutes-2 ~ reminder_minutes)
                # 예: 15분 전 알림은 13분~15분 사이에 생성 (정확도 향상)
                if minutes_until >= reminder_minutes - 2 and minutes_until <= reminder_minutes:
                    # 이미 해당 리마인더 시간대의 알림이 생성되었는지 확인 (중복 방지)
                    from apps.dashboard.models import Notification
                    existing_notification = Notification.objects.filter(
                        user_id=schedule.created_id,
                        notification_type='M',  # 미팅 타입
                        related_sid=schedule.schedule_sid,
                        title='일정 알림',
                        created_at__gte=now - timedelta(minutes=10)  # 최근 10분 이내 생성된 알림만 체크
                    ).first()
                    
                    if existing_notification:
                        # 이미 알림이 생성되었으면 스킵
                        logger.debug(
                            f"Skipping reminder for schedule {schedule.schedule_sid} "
                            f"({minutes_until} minutes before) - notification already exists"
                        )
                        break
                    
                    try:
                        # DB 연결 확인
                        from django.db import connection
                        connection.ensure_connection()
                        
                        # Task 내부에서는 동기 처리로 알림 생성 (DB 저장 보장)
                        # 실제 남은 시간을 사용하여 알림 메시지 생성
                        create_schedule_reminder_notification(
                            schedule_title=schedule.title,
                            user_id=schedule.created_id,
                            schedule_id=schedule.schedule_sid,
                            reminder_minutes=minutes_until  # 실제 남은 시간 사용
                        )
                        
                        notifications_created += 1
                        logger.info(
                            f"Created reminder for schedule {schedule.schedule_sid} "
                            f"({minutes_until} minutes before, target: {reminder_minutes} minutes)"
                        )
                        break  # 하나만 생성
                    except Exception as e:
                        logger.error(
                            f"Failed to create reminder notification for schedule {schedule.schedule_sid}: {e}",
                            exc_info=True
                        )
        
        result = {
            'status': 'success',
            'schedules_processed': upcoming_schedules.count(),
            'notifications_created': notifications_created,
            'checked_until': check_until.isoformat()
        }
        
        logger.info(
            f"Schedule reminder check completed: "
            f"processed {upcoming_schedules.count()} schedules, "
            f"created {notifications_created} notifications"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in check_schedule_reminders task: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='apps.dashboard.tasks.create_notification_async', bind=True, max_retries=3)
def create_notification_async(
    self,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    related_sid: Optional[int] = None,
    read_yn: str = 'N'
):
    """
    알림 생성 Celery Task (비동기 처리)
    
    대량 알림 생성이나 응답 시간이 중요한 경우 사용합니다.
    
    Args:
        user_id: 알림을 받을 사용자 ID
        notification_type: 알림 타입
        title: 알림 제목
        message: 알림 메시지
        related_sid: 관련 ID
        read_yn: 읽음 여부
    
    Returns:
        dict: 생성 결과
    """
    from django.db import transaction
    from apps.dashboard.models import Notification
    
    try:
        # DB 연결 확인
        from django.db import connection
        connection.ensure_connection()
        
        # 트랜잭션 내에서 알림 생성 (atomic 블록이 자동으로 커밋)
        with transaction.atomic():
            notification = Notification.objects.create(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                related_sid=related_sid,
                read_yn=read_yn,
            )
            # atomic 블록이 끝나면 자동으로 커밋됨
            
            logger.info(
                f"Notification created via Celery Task: "
                f"notification_sid={notification.notification_sid}, "
                f"user_id={user_id}, title={title}"
            )
            
            return {
                'status': 'success',
                'notification_sid': notification.notification_sid,
                'user_id': user_id
            }
    except Exception as exc:
        logger.error(
            f"Failed to create notification asynchronously: {exc}",
            exc_info=True,
            extra={
                'user_id': user_id,
                'notification_type': notification_type,
                'title': title
            }
        )
        # 재시도 (최대 3회)
        raise self.retry(exc=exc, countdown=60)  # 60초 후 재시도


@shared_task(name='apps.dashboard.tasks.bulk_create_notifications_async', bind=True)
def bulk_create_notifications_async(
    self,
    notifications_data: List[Dict]
):
    """
    여러 알림을 비동기로 일괄 생성 Celery Task
    
    대량 알림 발송 시 성능 개선을 위해 사용합니다.
    
    Args:
        notifications_data: 알림 데이터 리스트
            [{
                'user_id': str,
                'notification_type': str,
                'title': str,
                'message': str,
                'related_sid': Optional[int],
                'read_yn': str
            }, ...]
    
    Returns:
        dict: 생성 결과
    """
    try:
        created_notifications = bulk_create_notifications(notifications_data)
        return {
            'status': 'success',
            'count': len(created_notifications),
            'notification_sids': [n.notification_sid for n in created_notifications]
        }
    except Exception as exc:
        logger.error(f"Failed to bulk create notifications asynchronously: {exc}", exc_info=True)
        return {
            'status': 'error',
            'error': str(exc)
        }
