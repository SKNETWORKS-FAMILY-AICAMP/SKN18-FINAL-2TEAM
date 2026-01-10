"""
일정 리마인더 체크 및 알림 생성 관리 명령어

사용법:
    python django_app/manage.py check_schedule_reminders
    
설정:
    - Cron 또는 Celery Beat로 주기적으로 실행 (예: 매 5분마다)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.schedule.models import Schedule
from apps.notification.notification_utils import create_schedule_reminder_notification
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check schedule reminders and create notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-minutes',
            type=int,
            default=60,
            help='Check schedules within the next N minutes (default: 60)'
        )

    def handle(self, *args, **options):
        check_minutes = options['check_minutes']
        now = timezone.now()
        check_until = now + timedelta(minutes=check_minutes)
        
        self.stdout.write(f"Checking schedules from {now} to {check_until}")
        
        # 예정된 일정 중에서 리마인더가 필요한 일정 찾기
        # TODO: 일정의 notification 설정에 따라 리마인더 생성
        # 현재는 간단한 예시로 구현 (실제로는 Schedule 모델에 notification 필드가 필요)
        
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
                # 해당 시간대에 맞는 알림 생성 (예: 5분 전이면 5분 후에 시작하는 일정에 대해 알림)
                if minutes_until <= reminder_minutes and minutes_until > reminder_minutes - 5:
                    try:
                        create_schedule_reminder_notification(
                            schedule_title=schedule.title,
                            user_id=schedule.created_id,
                            schedule_id=schedule.schedule_sid,
                            reminder_minutes=minutes_until
                        )
                        notifications_created += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created reminder for schedule {schedule.schedule_sid} "
                                f"({minutes_until} minutes before)"
                            )
                        )
                        break  # 하나만 생성
                    except Exception as e:
                        logger.error(
                            f"Failed to create reminder notification for schedule {schedule.schedule_sid}: {e}",
                            exc_info=True
                        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {upcoming_schedules.count()} schedules, "
                f"created {notifications_created} notifications"
            )
        )
