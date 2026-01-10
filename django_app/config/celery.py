"""
Celery 설정 파일

사용법:
    1. Celery worker 실행:
       celery -A config worker --loglevel=info
    
    2. Celery Beat 실행 (스케줄러):
       celery -A config beat --loglevel=info
    
    3. Celery worker + Beat 동시 실행:
       celery -A config worker --beat --loglevel=info

주의사항:
    - Celery를 사용하려면 RabbitMQ 또는 Redis가 필요합니다.
    - 프로젝트에 이미 RabbitMQ가 설정되어 있으므로 RabbitMQ를 사용합니다.
    - 환경변수 CELERY_BROKER_URL을 설정하여 다른 브로커를 사용할 수 있습니다.
"""
import os
from celery import Celery
from django.conf import settings

# Django 설정 모듈 경로 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Celery 앱 생성
app = Celery('config')

# Django 설정에서 Celery 설정 로드
# namespace='CELERY'는 settings.py에서 CELERY_로 시작하는 모든 설정을 로드합니다
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 앱에서 task 자동 발견
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """디버그용 테스트 task"""
    print(f'Request: {self.request!r}')
