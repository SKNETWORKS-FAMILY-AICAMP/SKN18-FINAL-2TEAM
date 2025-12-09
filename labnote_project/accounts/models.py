# accounts/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class User(AbstractUser):
    # 추가 필드
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)

    # 강제: username 대신 email 로그인 가능 시
    # USERNAME_FIELD = "email"
    # REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.username} ({self.email})"