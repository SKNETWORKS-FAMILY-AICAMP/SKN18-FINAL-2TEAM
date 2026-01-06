import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """Custom user manager for CustomUser model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('이메일은 필수입니다.')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with an email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'A')  # Admin status
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    사용자 기본 정보 모델 (zs_user 테이블)
    Django의 AbstractBaseUser를 확장하여 커스텀 인증 지원
    """
    
    class Status(models.TextChoices):
        """사용자 상태"""
        ENABLED = 'E', '활성'
        DISABLED = 'D', '비활성'
        SUSPENDED = 'S', '정지'
        ADMIN = 'A', '관리자'
    
    # Primary Key - UUID 기반
    user_id = models.CharField(
        max_length=60,
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='사용자 ID'
    )
    
    # 인증 정보
    email = models.EmailField(
        max_length=255,
        unique=True,
        verbose_name='이메일'
    )
    # password는 AbstractBaseUser에서 제공 (password_hash 역할)
    
    # 프로필 정보
    full_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='이름'
    )
    phone_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='전화번호'
    )
    company = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='회사/소속'
    )
    img_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='프로필 이미지 URL'
    )
    
    # 상태 및 일시
    join_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='가입일'
    )
    last_login = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='마지막 로그인'
    )
    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.ENABLED,
        verbose_name='상태'
    )
    
    # Django 권한 관련 필드
    is_staff = models.BooleanField(
        default=False,
        verbose_name='관리자 여부'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='활성 여부'
    )
    
    # 타임스탬프
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정일시'
    )
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'zs_user'
        verbose_name = '사용자'
        verbose_name_plural = '사용자 목록'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return self.full_name or self.email
    
    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email.split('@')[0]


class UserSettings(models.Model):
    """
    사용자 설정 모델 (zs_user_settings 테이블)
    각 사용자에 대한 개인 설정 저장
    """
    
    class YesNo(models.TextChoices):
        YES = 'Y', '예'
        NO = 'N', '아니오'
    
    class Language(models.TextChoices):
        KOREAN = 'ko', '한국어'
        ENGLISH = 'en', 'English'
        JAPANESE = 'ja', '日本語'
        CHINESE = 'zh', '中文'
    
    class NotesViewMode(models.TextChoices):
        CARD = 'card', '카드 보기'
        TABLE = 'table', '테이블 보기'
    
    settings_sid = models.AutoField(
        primary_key=True,
        verbose_name='설정 ID'
    )
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='settings',
        to_field='user_id',
        db_column='user_id',
        verbose_name='사용자'
    )
    
    # 알림 설정
    notifications = models.CharField(
        max_length=1,
        choices=YesNo.choices,
        default=YesNo.YES,
        verbose_name='알림'
    )
    email_alerts = models.CharField(
        max_length=1,
        choices=YesNo.choices,
        default=YesNo.YES,
        verbose_name='이메일 알림'
    )
    
    # UI 설정
    dark_mode = models.CharField(
        max_length=1,
        choices=YesNo.choices,
        default=YesNo.NO,
        verbose_name='다크 모드'
    )
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.KOREAN,
        verbose_name='언어'
    )
    notes_view_mode = models.CharField(
        max_length=10,
        choices=NotesViewMode.choices,
        default=NotesViewMode.CARD,
        verbose_name='노트 보기 모드'
    )
    
    # 타임스탬프
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정일시'
    )
    
    class Meta:
        db_table = 'zs_user_settings'
        verbose_name = '사용자 설정'
        verbose_name_plural = '사용자 설정 목록'
    
    def __str__(self):
        return f'{self.user.email} 설정'


class LinkedAccount(models.Model):
    """
    연동된 계정 모델 (zs_linked_account 테이블)
    Google, GitHub 등 OAuth 제공자 계정 연동 정보 저장
    
    분리 이유:
    1. One-to-Many 관계: 한 사용자가 여러 OAuth 제공자 연동 가능
    2. 확장성: 새로운 OAuth 제공자 추가가 용이
    3. 보안: 토큰 관리를 별도로 처리 가능
    4. 단순성: 메인 User 모델이 깔끔하게 유지됨
    """
    
    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        GITHUB = 'github', 'GitHub'
        KAKAO = 'kakao', 'Kakao'
        NAVER = 'naver', 'Naver'
    
    linked_account_sid = models.AutoField(
        primary_key=True,
        verbose_name='연동 계정 ID'
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='linked_accounts',
        to_field='user_id',
        db_column='user_id',
        verbose_name='사용자'
    )
    
    # OAuth 제공자 정보
    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
        verbose_name='제공자',
        help_text='google, github, kakao, naver 등'
    )
    provider_user_id = models.CharField(
        max_length=255,
        verbose_name='제공자 사용자 ID',
        help_text='OAuth 제공자에서의 고유 사용자 ID'
    )
    
    # OAuth 토큰 (암호화 저장 권장)
    access_token = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='액세스 토큰'
    )
    refresh_token = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='리프레시 토큰'
    )
    
    # 토큰 만료 시간 (추가 필드 - 실용적)
    token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='토큰 만료 시간'
    )
    
    # OAuth 권한 범위 (scope)
    scope = models.TextField(
        blank=True,
        null=True,
        verbose_name='권한 범위',
        help_text='OAuth 제공자에서 부여된 권한 목록 (공백으로 구분)'
    )
    
    # 타임스탬프
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정일시'
    )
    
    class Meta:
        db_table = 'zs_linked_account'
        verbose_name = '연동 계정'
        verbose_name_plural = '연동 계정 목록'
        # 사용자당 제공자별 하나의 계정만 허용
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'provider'],
                name='uk_provider_user'
            )
        ]
    
    def __str__(self):
        return f'{self.user.email} - {self.provider}'
    
    def is_token_expired(self):
        """토큰 만료 여부 확인"""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at
    
    def refresh_access_token(self):
        """
        refresh_token을 사용하여 access_token 갱신
        Google OAuth 전용 (다른 제공자는 필요시 확장)
        """
        if self.provider != 'google':
            return False
        
        if not self.refresh_token:
            return False
        
        from django.conf import settings
        import requests
        from datetime import timedelta
        
        try:
            data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            
            res = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
            res.raise_for_status()
            token_info = res.json()
            
            new_access_token = token_info.get("access_token")
            expires_in = token_info.get("expires_in", 3600)
            
            if new_access_token:
                self.access_token = new_access_token
                self.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                # refresh_token은 Google이 새로 발급하지 않으므로 유지
                self.save(update_fields=['access_token', 'token_expires_at'])
                return True
            
            return False
        except Exception as e:
            # 로깅은 필요시 추가
            return False
    
    def get_valid_access_token(self):
        """
        유효한 access_token 반환
        만료되었으면 자동으로 갱신 시도
        """
        if self.is_token_expired():
            if self.refresh_access_token():
                return self.access_token
            else:
                return None
        return self.access_token


class UserActivityLog(models.Model):
    """
    인증된 사용자의 요청 활동을 단순히 기록한다.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="activity_logs",
        to_field='user_id',
        db_column='user_id',
        verbose_name='사용자'
    )
    path = models.CharField(max_length=512, verbose_name='경로')
    method = models.CharField(max_length=10, verbose_name='HTTP 메서드')
    user_agent = models.CharField(max_length=512, blank=True, verbose_name='User Agent')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP 주소')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        db_table = 'zh_user_activity_logs'
        ordering = ["-created_at"]
        verbose_name = '사용자 활동 로그'
        verbose_name_plural = '사용자 활동 로그 목록'

    def __str__(self):
        return f"{self.user.get_full_name()} @ {self.path}"
