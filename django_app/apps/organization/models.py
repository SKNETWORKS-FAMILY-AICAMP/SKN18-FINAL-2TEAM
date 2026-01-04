from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Organization(models.Model):
    """
    조직 모델 (zs_organization 테이블)
    """
    class Status(models.TextChoices):
        ACTIVE = 'A', '활성'
        DELETED = 'R', '삭제됨'
    
    organization_sid = models.AutoField(primary_key=True, db_column='organization_sid')
    organization_name = models.CharField(max_length=255, db_column='organization_name', verbose_name='조직 이름')
    created_by_user_id = models.CharField(
        max_length=60,
        db_column='created_by_user_id',
        verbose_name='생성자 ID'
    )
    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_column='status',
        verbose_name='상태'
    )
    created_at = models.DateTimeField(default=timezone.now, db_column='created_at', verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at', verbose_name='수정일')

    class Meta:
        db_table = 'zs_organization'
        verbose_name = '조직'
        verbose_name_plural = '조직'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.organization_name

    @property
    def member_count(self):
        """조직 멤버 수"""
        return self.members.count()

    @property
    def owner(self):
        """조직 소유자 (생성자)"""
        try:
            from apps.account.models import CustomUser
            return CustomUser.objects.get(user_id=self.created_by_user_id)
        except:
            return None


class OrganizationMember(models.Model):
    """
    조직 멤버 모델 (zs_organization_member 테이블)
    """
    class Role(models.TextChoices):
        OWNER = 'owner', '소유자'
        MEMBER = 'member', '멤버'
        ADMIN = 'admin', '관리자'

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members',
        db_column='organization_sid',
        verbose_name='조직'
    )
    user_id = models.CharField(
        max_length=60,
        db_column='user_id',
        verbose_name='사용자 ID'
    )
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.MEMBER,
        db_column='role',
        verbose_name='역할'
    )
    joined_at = models.DateTimeField(
        default=timezone.now,
        db_column='joined_at',
        verbose_name='가입일'
    )

    class Meta:
        db_table = 'zs_organization_member'
        verbose_name = '조직 멤버'
        verbose_name_plural = '조직 멤버'
        unique_together = [['organization', 'user_id']]
        indexes = [
            models.Index(fields=['organization', 'user_id']),
        ]

    def __str__(self):
        return f"{self.organization.organization_name} - {self.user_id}"

    @property
    def user(self):
        """사용자 객체"""
        try:
            from apps.account.models import CustomUser
            return CustomUser.objects.get(user_id=self.user_id)
        except:
            return None


class OrganizationInvitation(models.Model):
    """
    조직 초대 모델 (화면에서 멤버 초대 기능을 위해 추가)
    """
    class Status(models.TextChoices):
        PENDING = 'pending', '대기중'
        ACCEPTED = 'accepted', '수락됨'
        REJECTED = 'rejected', '거절됨'
        EXPIRED = 'expired', '만료됨'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name='조직'
    )
    email = models.EmailField(verbose_name='초대 이메일')
    invited_by_user_id = models.CharField(
        max_length=60,
        verbose_name='초대한 사용자 ID'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='상태'
    )
    invited_at = models.DateTimeField(default=timezone.now, verbose_name='초대일')
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name='수락일')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='만료일')

    class Meta:
        db_table = 'zs_organization_invitation'
        verbose_name = '조직 초대'
        verbose_name_plural = '조직 초대'
        # unique_together 제거: 모든 상태값 히스토리를 보존하기 위해
        # pending 상태만 중복 체크는 애플리케이션 레벨에서 처리
        # (views.py의 organization_create_api, organization_add_member_api에서 체크)
        indexes = [
            models.Index(fields=['organization', 'email']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['organization', 'email', 'status']),  # 조회 성능 향상
        ]

    def __str__(self):
        return f"{self.organization.organization_name} - {self.email}"

    @property
    def is_expired(self):
        """만료 여부 확인"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def inviter(self):
        """초대한 사용자 객체"""
        try:
            from apps.account.models import CustomUser
            return CustomUser.objects.get(user_id=self.invited_by_user_id)
        except:
            return None
