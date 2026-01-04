from django.db import models
from django.conf import settings


# ============================================================
# Schedule (웹 캘린더 일정)
# ============================================================
class Schedule(models.Model):
    """
    일정 모델
    """
    
    # 타입 선택지
    TYPE_CHOICES = [
        ('E', '실험'),
        ('M', '미팅'),
        ('A', '분석'),
        ('S', '세미나'),
    ]
    
    # 상태 선택지 (주석: E: 예정, R: 진행중, C: 완료)
    STATUS_CHOICES = [
        ('E', '예정'),
        ('R', '진행중'),
        ('C', '완료'),
    ]
    
    # 반복 타입 선택지
    REPEAT_CHOICES = [
        ('N', '반복 안 함'),
        ('D', '매일'),
        ('W', '매주'),
        ('M', '매월'),
        ('Y', '매년'),
    ]
    
    schedule_sid = models.AutoField(primary_key=True, db_column='schedule_sid')
    title = models.CharField(max_length=255, db_column='title')
    description = models.TextField(null=True, blank=True, db_column='description')

    schedule_type = models.CharField(
        max_length=1, choices=TYPE_CHOICES, db_column='schedule_type'
    )
    schedule_status = models.CharField(
        max_length=1, choices=STATUS_CHOICES, default='E', db_column='schedule_status'
    )

    use_yn = models.CharField(max_length=1, default='Y', db_column='use_yn')

    start_date = models.DateTimeField(db_column='start_date')
    end_date = models.DateTimeField(db_column='end_date')
    is_all_day = models.CharField(max_length=1, default='N', db_column='is_all_day')

    location = models.CharField(max_length=255, null=True, blank=True, db_column='location')
    # 일정 자체 색상 (웹 캘린더용)
    color = models.CharField(max_length=50, null=True, blank=True, db_column='color')
    # TODO: Note 모델 생성 후 ForeignKey로 변경
    # linked_note = models.ForeignKey('notes.Note', on_delete=models.SET_NULL, null=True, blank=True, db_column='linked_note_sid')
    linked_note_sid = models.IntegerField(null=True, blank=True, db_column='linked_note_sid')

    calendar = models.ForeignKey(
        'UserCalendar',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='schedules',
        db_column='calendar_sid',
    )

    repeat_type = models.CharField(
        max_length=1, choices=REPEAT_CHOICES, default='N', db_column='repeat_type'
    )

    original_schedule = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='shared_copies',
        db_column='original_schedule_sid'
    )
    is_shared_copy = models.BooleanField(default=False, db_column='is_shared_copy')
    
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_schedule'
        ordering = ['-created_at']
        verbose_name = '일정'
        verbose_name_plural = '일정들'
    
    def __str__(self):
        return f"{self.title} ({self.get_schedule_type_display()})"
    
    @property
    def start_datetime(self):
        """FullCalendar와 호환을 위한 속성"""
        return self.start_date
    
    @property
    def end_datetime(self):
        """FullCalendar와 호환을 위한 속성"""
        return self.end_date
    
    @property
    def type(self):
        """schedule_type의 별칭"""
        return self.schedule_type
    
    @property
    def status(self):
        """schedule_status를 소문자로 변환 (scheduled, in_progress, completed)"""
        status_map = {
            'E': 'scheduled',
            'R': 'in_progress',
            'C': 'completed',
        }
        return status_map.get(self.schedule_status, 'scheduled')
    
    @property
    def get_type_display(self):
        """타입 표시명"""
        return self.get_schedule_type_display()


# ============================================================
# 반복 규칙 (RRULE)
# ============================================================
class ScheduleRecurrence(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "DAILY", "매일"
        WEEKLY = "WEEKLY", "매주"
        MONTHLY = "MONTHLY", "매월"
        YEARLY = "YEARLY", "매년"

    schedule = models.OneToOneField(
        Schedule,
        on_delete=models.CASCADE,
        related_name="recurrence",
        db_column="schedule_sid",
        primary_key=True,
    )

    freq = models.CharField(max_length=20, choices=Frequency.choices, db_column="freq")
    interval = models.PositiveIntegerField(default=1, db_column="interval")
    week_days = models.JSONField(default=list, blank=True, db_column="week_days")
    month_days = models.JSONField(default=list, blank=True, db_column="month_days")
    count = models.PositiveIntegerField(null=True, blank=True, db_column="count")
    until = models.DateTimeField(null=True, blank=True, db_column="until")
    timezone = models.CharField(max_length=64, default="Asia/Seoul", db_column="timezone")
    metadata = models.JSONField(default=dict, blank=True, db_column="metadata")

    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")
    updated_at = models.DateTimeField(auto_now=True, db_column="updated_at")

    class Meta:
        db_table = "t_schedule_recurrence"

    def __str__(self):
        return f"Recurrence({self.schedule_id}, {self.freq})"


# ============================================================
# 반복 예외(스킵/변경)
# ============================================================
class ScheduleException(models.Model):
    recurrence = models.ForeignKey(
        ScheduleRecurrence,
        on_delete=models.CASCADE,
        related_name="exceptions",
        db_column="recurrence_sid",
    )
    exception_date = models.DateField(db_column="exception_date")
    note = models.CharField(max_length=255, blank=True, db_column="note")
    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")

    class Meta:
        db_table = "t_schedule_exception"
        unique_together = ("recurrence", "exception_date")

    def __str__(self):
        return f"{self.recurrence_id} @ {self.exception_date}"


# ============================================================
# ScheduleInvitation (일정 공유 초대)
# ============================================================
class ScheduleInvitation(models.Model):
    """
    일정 공유 초대 모델
    공유자가 수락/거부하기 전의 초대 상태를 관리
    """
    
    class Status(models.TextChoices):
        PENDING = "pending", "대기중"
        ACCEPTED = "accepted", "수락됨"
        REJECTED = "rejected", "거절됨"
    
    invitation_sid = models.AutoField(primary_key=True, db_column='invitation_sid')
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='invitations',
        db_column='schedule_sid'
    )
    user_id = models.CharField(max_length=60, db_column='user_id')  # 초대받은 사용자
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_column='status'
    )
    accepted_at = models.DateTimeField(null=True, blank=True, db_column='accepted_at')
    rejected_at = models.DateTimeField(null=True, blank=True, db_column='rejected_at')
    accepted_calendar = models.ForeignKey(
        'UserCalendar',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_invitations',
        db_column='accepted_calendar_sid'
    )
    shared_schedule = models.ForeignKey(
        'Schedule',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='shared_from_invitation',
        db_column='shared_schedule_sid'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')  # 초대한 사용자
    
    class Meta:
        db_table = 't_schedule_invitation'
        ordering = ['-created_at']
        verbose_name = '일정 공유 초대'
        verbose_name_plural = '일정 공유 초대들'
        indexes = [
            models.Index(fields=['schedule', 'user_id']),
            models.Index(fields=['user_id', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.schedule.title} → {self.user_id} ({self.status})"


# ============================================================
# ScheduleShare (수락된 일정 공유)
# ============================================================
class ScheduleShare(models.Model):
    """
    일정 공유 모델 (수락된 공유만 저장)
    """
    
    schedule_share_sid = models.AutoField(primary_key=True, db_column='schedule_share_sid')
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='shares',
        db_column='schedule_sid'
    )
    user_id = models.CharField(max_length=60, db_column='user_id')
    shared_schedule = models.ForeignKey(
        'Schedule',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='shared_from',
        db_column='shared_schedule_sid'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_schedule_share'
        ordering = ['-created_at']
        verbose_name = '일정 공유'
        verbose_name_plural = '일정 공유들'
        indexes = [
            models.Index(fields=['schedule', 'user_id']),
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"{self.schedule.title} - {self.user_id}"

# ============================================================
# UserCalendar (웹 캘린더 그룹)
# ============================================================
class UserCalendar(models.Model):
    class Source(models.TextChoices):
        LOCAL = "local", "로컬"
        GOOGLE = "google", "Google"

    """
    사용자 캘린더 모델
    """
    
    calendar_sid = models.AutoField(primary_key=True, db_column='calendar_sid')
    calendar_name = models.CharField(max_length=255, db_column='calendar_name')
    color = models.CharField(max_length=20, null=True, blank=True, db_column='color')
    is_visible = models.SmallIntegerField(default=1, db_column='is_visible')
    sort_order = models.IntegerField(default=0, db_column='sort_order')
    source_type = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.LOCAL,
        db_column='source_type',
    )
    external_id = models.CharField(max_length=255, null=True, blank=True, db_column='external_id')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')

    class Meta:
        db_table = 't_user_calendar'
        ordering = ['sort_order', 'created_at']
        verbose_name = '사용자 캘린더'
        verbose_name_plural = '사용자 캘린더들'

    def __str__(self):
        return self.calendar_name

    @property
    def visible(self):
        """is_visible을 boolean으로 변환"""
        return self.is_visible == 1

    @property
    def name(self):
        """calendar_name의 별칭"""
        return self.calendar_name

    @property
    def id(self):
        """calendar_sid의 별칭"""
        return self.calendar_sid


# ============================================================
# Google OAuth 자격증명
# ============================================================
class GoogleCredentials(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_credentials",
        db_column="user_id",
    )

    access_token = models.TextField(db_column="access_token")
    refresh_token = models.TextField(null=True, blank=True, db_column="refresh_token")

    client_id = models.TextField(db_column="client_id")
    client_secret = models.TextField(db_column="client_secret")
    scopes = models.TextField(db_column="scopes")

    expiry = models.DateTimeField(db_column="expiry")

    class Meta:
        db_table = "t_google_credentials"

    def __str__(self):
        return f"GoogleCredentials({self.user})"


# ============================================================
# ✅ 핵심: SyncedCalendar (구글 캘린더 + 색상)
# ============================================================
class SyncedCalendar(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="synced_calendars",
        db_column="user_id",
    )

    calendar_id = models.CharField(max_length=255, db_column="calendar_id")
    summary = models.CharField(max_length=255, db_column="summary")

    selected = models.BooleanField(default=True, db_column="selected")

    # ✅ 캘린더별 색상 (FullCalendar / Google 이벤트 공통)
    color = models.CharField(
        max_length=20,
        default="#3b82f6",
        blank=True,
        db_column="color",
    )

    class Meta:
        db_table = "t_synced_calendar"
        unique_together = ("user", "calendar_id")

    def __str__(self):
        return f"{self.summary}"


class GoogleSyncedEvent(models.Model):
    """
    구글 이벤트와 RDB 일정(Schedule)을 연결하는 캐시 테이블.
    실제 일정 데이터는 t_schedule에 저장하고 동기화 메타데이터만 별도로 관리한다.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_synced_events",
        db_column="user_id",
    )

    calendar = models.ForeignKey(
        SyncedCalendar,
        on_delete=models.CASCADE,
        related_name="synced_events",
        db_column="calendar_id",
    )

    schedule = models.OneToOneField(
        Schedule,
        on_delete=models.CASCADE,
        related_name="google_sync",
        db_column="schedule_sid",
    )

    event_id = models.CharField(max_length=255, db_column="event_id")
    status = models.CharField(max_length=20, default="active", db_column="status")
    etag = models.CharField(max_length=255, null=True, blank=True, db_column="etag")
    summary = models.CharField(max_length=255, null=True, blank=True, db_column="summary")
    raw_payload = models.JSONField(null=True, blank=True, db_column="raw_payload")
    google_updated = models.DateTimeField(null=True, blank=True, db_column="google_updated")

    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")
    updated_at = models.DateTimeField(auto_now=True, db_column="updated_at")

    class Meta:
        db_table = "t_google_synced_event"
        unique_together = ("user", "calendar", "event_id")

    def __str__(self):
        return f"{self.calendar.summary} / {self.event_id}"
