"""
Django 프로젝트 초기화 파일

Celery 앱을 여기서 초기화하여 Django가 시작될 때 Celery가 로드되도록 합니다.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
