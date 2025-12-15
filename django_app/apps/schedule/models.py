from django.db import models


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
    schedule_type = models.CharField(max_length=50, choices=TYPE_CHOICES, db_column='schedule_type')
    schedule_status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='E', db_column='schedule_status')
    use_yn = models.CharField(max_length=1, default='Y', db_column='use_yn')
    start_date = models.DateTimeField(db_column='start_date')
    end_date = models.DateTimeField(db_column='end_date')
    is_all_day = models.CharField(max_length=1, default='N', db_column='is_all_day')
    location = models.CharField(max_length=255, null=True, blank=True, db_column='location')
    color = models.CharField(max_length=50, null=True, blank=True, db_column='color')
    # TODO: Note 모델 생성 후 ForeignKey로 변경
    # linked_note = models.ForeignKey('notes.Note', on_delete=models.SET_NULL, null=True, blank=True, db_column='linked_note_sid')
    linked_note_sid = models.IntegerField(null=True, blank=True, db_column='linked_note_sid')
    repeat_type = models.CharField(max_length=50, choices=REPEAT_CHOICES, default='N', db_column='repeat_type')
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


class ScheduleShare(models.Model):
    """
    일정 공유 모델
    """
    
    schedule_share_sid = models.AutoField(primary_key=True, db_column='schedule_share_sid')
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='shares',
        db_column='schedule_sid'
    )
    user_id = models.CharField(max_length=60, db_column='user_id')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_schedule_share'
        ordering = ['-created_at']
        verbose_name = '일정 공유'
        verbose_name_plural = '일정 공유들'
        indexes = [
            models.Index(fields=['schedule', 'user_id']),
        ]
    
    def __str__(self):
        return f"{self.schedule.title} - {self.user_id}"


class UserCalendar(models.Model):
    """
    사용자 캘린더 모델
    """
    
    calendar_sid = models.AutoField(primary_key=True, db_column='calendar_sid')
    calendar_name = models.CharField(max_length=255, db_column='calendar_name')
    color = models.CharField(max_length=50, null=True, blank=True, db_column='color')
    is_visible = models.SmallIntegerField(default=1, db_column='is_visible')
    sort_order = models.IntegerField(default=0, db_column='sort_order')
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


class GoogleCalendar(models.Model):
    """
    Google Calendar 연동 모델
    """
    
    google_calendar_id = models.AutoField(primary_key=True, db_column='google_calendar_id')
    calendar_name = models.CharField(max_length=255, db_column='calendar_name')
    calendar_email = models.CharField(max_length=255, null=True, blank=True, db_column='calendar_email')
    color = models.CharField(max_length=50, null=True, blank=True, db_column='color')
    is_connected = models.CharField(max_length=1, default='N', db_column='is_connected')
    is_selected = models.SmallIntegerField(default=0, db_column='is_selected')
    access_token = models.CharField(max_length=500, null=True, blank=True, db_column='access_token')
    refresh_token = models.CharField(max_length=500, null=True, blank=True, db_column='refresh_token')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_google_calendar'
        ordering = ['-created_at']
        verbose_name = 'Google 캘린더'
        verbose_name_plural = 'Google 캘린더들'
    
    def __str__(self):
        return self.calendar_name
    
    @property
    def connected(self):
        """is_connected를 boolean으로 변환"""
        return self.is_connected == 'Y'
    
    @property
    def selected(self):
        """is_selected를 boolean으로 변환"""
        return self.is_selected == 1
