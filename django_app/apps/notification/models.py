from django.db import models
from django.utils import timezone
from datetime import timedelta


class Notification(models.Model):
    """
    알림 모델 (t_notification 테이블)
    """
    
    class NotificationType(models.TextChoices):
        """알림 타입"""
        EXPERIMENT = 'E', '실험'
        MEETING = 'M', '미팅'
        ANALYSIS = 'A', '분석'
        SEMINAR = 'S', '세미나'
        NOTE = 'N', '노트'
        CHAT = 'C', '채팅'
        SYSTEM = 'SYS', '시스템'
    
    class ReadStatus(models.TextChoices):
        """읽음 상태"""
        READ = 'Y', '읽음'
        UNREAD = 'N', '읽지 않음'
    
    notification_sid = models.AutoField(
        primary_key=True,
        db_column='notification_sid',
        verbose_name='알림 ID'
    )
    user_id = models.CharField(
        max_length=60,
        db_column='user_id',
        verbose_name='사용자 ID'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        db_column='notification_type',
        verbose_name='알림 타입'
    )
    title = models.CharField(
        max_length=255,
        db_column='title',
        verbose_name='제목'
    )
    message = models.TextField(
        db_column='message',
        verbose_name='메시지'
    )
    read_yn = models.CharField(
        max_length=1,
        choices=ReadStatus.choices,
        default=ReadStatus.UNREAD,
        db_column='read_yn',
        verbose_name='읽음 여부'
    )
    related_sid = models.IntegerField(
        null=True,
        blank=True,
        db_column='related_sid',
        verbose_name='관련 ID',
        help_text='experiment_sid, schedule_sid, note_sid, chat_sid 등'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='created_at',
        verbose_name='생성일시'
    )
    
    class Meta:
        db_table = 't_notification'
        ordering = ['-created_at']
        verbose_name = '알림'
        verbose_name_plural = '알림들'
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['user_id', 'read_yn']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_notification_type_display()})"
    
    @property
    def unread(self):
        """읽지 않음 여부 (템플릿에서 사용)"""
        return self.read_yn == self.ReadStatus.UNREAD
    
    @property
    def time(self):
        """상대 시간 표시 (예: "5분 전", "1시간 전")"""
        now = timezone.now()
        diff = now - self.created_at
        
        if diff < timedelta(minutes=1):
            return "방금 전"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}분 전"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}시간 전"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days}일 전"
        else:
            return self.created_at.strftime("%Y-%m-%d")
