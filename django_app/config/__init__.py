"""
Django 프로젝트 초기화 파일

Celery 앱을 여기서 초기화하여 Django가 시작될 때 Celery가 로드되도록 합니다.
Worker 환경에서는 celery가 설치되지 않을 수 있으므로 선택적으로 import합니다.
"""
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # celery가 설치되지 않은 환경 (예: rabbitmq-worker)에서는 celery_app 없이 실행
    celery_app = None
    __all__ = ()
