"""
알림 생성 유틸리티 함수
각 기능에서 알림을 생성할 때 사용하는 공통 함수들
"""
import logging
from typing import Optional, List
from django.utils import timezone
from django.db import transaction
from apps.dashboard.models import Notification
from apps.account.models import CustomUser

logger = logging.getLogger(__name__)


def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    related_sid: Optional[int] = None,
    read_yn: str = 'N'
) -> Notification:
    """
    알림 생성 함수
    
    Args:
        user_id: 알림을 받을 사용자 ID
        notification_type: 알림 타입 ('E': 실험, 'M': 미팅, 'A': 분석, 'S': 세미나, 'N': 노트, 'C': 채팅, 'SYS': 시스템)
        title: 알림 제목
        message: 알림 메시지
        related_sid: 관련 ID (experiment_sid, schedule_sid, note_sid, chat_sid 등)
        read_yn: 읽음 여부 ('Y': 읽음, 'N': 읽지 않음)
    
    Returns:
        생성된 Notification 객체
    """
    try:
        notification = Notification.objects.create(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_sid=related_sid,
            read_yn=read_yn,
        )
        logger.info(f"Notification created: {notification.notification_sid} for user {user_id}")
        return notification
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}", exc_info=True)
        raise


def create_schedule_share_notification(
    schedule_title: str,
    shared_user_id: str,
    owner_name: str,
    schedule_id: int
) -> Notification:
    """
    일정 공유 알림 생성
    
    Args:
        schedule_title: 일정 제목
        shared_user_id: 공유받은 사용자 ID
        owner_name: 일정 소유자 이름
        schedule_id: 일정 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "일정 공유 알림"
    message = f"{owner_name}님이 '{schedule_title}' 일정을 공유했습니다."
    
    return create_notification(
        user_id=shared_user_id,
        notification_type='M',  # 미팅 타입
        title=title,
        message=message,
        related_sid=schedule_id,
    )


def create_organization_invitation_notification(
    organization_name: str,
    invited_user_id: str,
    inviter_name: str,
    organization_id: Optional[int] = None
) -> Notification:
    """
    조직 초대 알림 생성
    
    Args:
        organization_name: 조직 이름
        invited_user_id: 초대받은 사용자 ID
        inviter_name: 초대한 사용자 이름
        organization_id: 조직 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "조직 초대 알림"
    message = f"{inviter_name}님이 '{organization_name}' 조직에 초대했습니다."
    
    return create_notification(
        user_id=invited_user_id,
        notification_type='SYS',  # 시스템 타입
        title=title,
        message=message,
        related_sid=organization_id,
    )


def create_schedule_reminder_notification(
    schedule_title: str,
    user_id: str,
    schedule_id: int,
    reminder_minutes: int
) -> Notification:
    """
    일정 리마인더 알림 생성
    
    Args:
        schedule_title: 일정 제목
        user_id: 사용자 ID
        schedule_id: 일정 ID
        reminder_minutes: 몇 분 전 알림인지
    
    Returns:
        생성된 Notification 객체
    """
    if reminder_minutes == 0:
        time_text = "지금"
    elif reminder_minutes < 60:
        time_text = f"{reminder_minutes}분 후"
    elif reminder_minutes < 1440:  # 24시간
        hours = reminder_minutes // 60
        time_text = f"{hours}시간 후"
    else:
        days = reminder_minutes // 1440
        time_text = f"{days}일 후"
    
    title = "일정 알림"
    message = f"'{schedule_title}' 일정이 {time_text} 시작됩니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='M',  # 미팅 타입
        title=title,
        message=message,
        related_sid=schedule_id,
    )


def create_experiment_tool_complete_notification(
    experiment_title: str,
    tool_name: str,
    user_id: str,
    experiment_id: int
) -> Notification:
    """
    실험 도구 완료 알림 생성
    
    Args:
        experiment_title: 실험 제목/파이프라인 이름
        tool_name: 완료된 도구 이름
        user_id: 사용자 ID
        experiment_id: 실험 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "실험 도구 완료"
    message = f"'{experiment_title}' 실험의 {tool_name} 도구가 완료되었습니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='E',  # 실험 타입
        title=title,
        message=message,
        related_sid=experiment_id,
    )


def create_experiment_created_notification(
    experiment_title: str,
    user_id: str,
    experiment_id: int,
    tools_count: int = 0
) -> Notification:
    """
    실험 생성 알림 생성
    
    Args:
        experiment_title: 실험 제목/파이프라인 이름
        user_id: 사용자 ID
        experiment_id: 실험 ID
        tools_count: 사용된 도구 개수
    
    Returns:
        생성된 Notification 객체
    """
    title = "실험 생성"
    if tools_count > 0:
        message = f"'{experiment_title}' 실험이 생성되었습니다. ({tools_count}개 도구 사용)"
    else:
        message = f"'{experiment_title}' 실험이 생성되었습니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='E',  # 실험 타입
        title=title,
        message=message,
        related_sid=experiment_id,
    )


def create_experiment_start_notification(
    experiment_title: str,
    user_id: str,
    experiment_id: int
) -> Notification:
    """
    실험 시작 알림 생성 (큐에 등록되어 실행 시작)
    
    Args:
        experiment_title: 실험 제목/파이프라인 이름
        user_id: 사용자 ID
        experiment_id: 실험 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "실험 시작"
    message = f"'{experiment_title}' 실험이 시작되었습니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='E',  # 실험 타입
        title=title,
        message=message,
        related_sid=experiment_id,
    )


def create_experiment_complete_notification(
    experiment_title: str,
    user_id: str,
    experiment_id: int
) -> Notification:
    """
    실험 전체 완료 알림 생성
    
    Args:
        experiment_title: 실험 제목/파이프라인 이름
        user_id: 사용자 ID
        experiment_id: 실험 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "실험 완료"
    message = f"'{experiment_title}' 실험이 완료되었습니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='E',  # 실험 타입
        title=title,
        message=message,
        related_sid=experiment_id,
    )


def create_experiment_final_tool_complete_notification(
    experiment_title: str,
    tool_name: str,
    user_id: str,
    experiment_id: int
) -> Notification:
    """
    마지막 도구 완료 및 실험 완료 통합 알림 생성
    
    Args:
        experiment_title: 실험 제목/파이프라인 이름
        tool_name: 마지막 도구 이름
        user_id: 사용자 ID
        experiment_id: 실험 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "실험 완료"
    message = f"'{experiment_title}' 실험의 {tool_name} 도구가 완료되어 실험이 완료되었습니다."
    
    return create_notification(
        user_id=user_id,
        notification_type='E',  # 실험 타입
        title=title,
        message=message,
        related_sid=experiment_id,
    )


def create_note_share_notification(
    note_title: str,
    shared_user_id: str,
    owner_name: str,
    note_id: int
) -> Notification:
    """
    노트 공유 알림 생성
    
    Args:
        note_title: 노트 제목
        shared_user_id: 공유받은 사용자 ID
        owner_name: 노트 소유자 이름
        note_id: 노트 ID
    
    Returns:
        생성된 Notification 객체
    """
    title = "노트 공유 알림"
    message = f"{owner_name}님이 '{note_title}' 노트를 공유했습니다."
    
    return create_notification(
        user_id=shared_user_id,
        notification_type='N',  # 노트 타입
        title=title,
        message=message,
        related_sid=note_id,
    )


def bulk_create_notifications(notifications_data: List[dict]) -> List[Notification]:
    """
    여러 알림을 한 번에 생성 (성능 최적화)
    
    Args:
        notifications_data: 알림 데이터 리스트
    
    Returns:
        생성된 Notification 객체 리스트
    """
    notifications = []
    for data in notifications_data:
        notifications.append(
            Notification(
                user_id=data['user_id'],
                notification_type=data['notification_type'],
                title=data['title'],
                message=data['message'],
                related_sid=data.get('related_sid'),
                read_yn=data.get('read_yn', 'N'),
            )
        )
    
    created_notifications = Notification.objects.bulk_create(notifications)
    logger.info(f"Bulk created {len(created_notifications)} notifications")
    return created_notifications


def get_user_display_name(user: CustomUser) -> str:
    """
    사용자 표시 이름 가져오기 (full_name > email > user_id)
    
    Args:
        user: CustomUser 객체
    
    Returns:
        사용자 표시 이름
    """
    if hasattr(user, 'full_name') and user.full_name:
        return user.full_name
    if hasattr(user, 'email') and user.email:
        return user.email
    if hasattr(user, 'user_id') and user.user_id:
        return str(user.user_id)
    return "알 수 없는 사용자"