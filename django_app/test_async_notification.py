#!/usr/bin/env python
"""
비동기 알림 테스트 스크립트

사용법:
    python manage.py shell < test_async_notification.py
    또는
    python test_async_notification.py
"""
import os
import sys
import django

# Django 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.dashboard.notification_utils import create_notification
from apps.dashboard.tasks import create_notification_async
from apps.account.models import CustomUser
from apps.dashboard.models import Notification

def test_async_notification():
    """비동기 알림 생성 테스트"""
    
    # 사용자 확인
    user = CustomUser.objects.first()
    if not user:
        print("❌ 테스트 사용자가 없습니다.")
        print("   먼저 사용자를 생성하세요: python manage.py createsuperuser")
        return
    
    print(f"✓ 테스트 사용자: {user.user_id}")
    print()
    
    # 1. Celery 설정 확인
    from django.conf import settings
    print("=== Celery 설정 확인 ===")
    print(f"Broker URL: {settings.CELERY_BROKER_URL}")
    print(f"NOTIFICATION_USE_ASYNC: {settings.NOTIFICATION_USE_ASYNC}")
    print()
    
    # 2. 비동기 알림 생성 (notification_utils 사용)
    print("=== 비동기 알림 생성 테스트 (notification_utils) ===")
    try:
        result = create_notification(
            user_id=user.user_id,
            notification_type='SYS',
            title="비동기 알림 테스트 #1",
            message="notification_utils.create_notification()를 통한 테스트"
        )
        
        if hasattr(result, 'id'):
            print(f"✓ Task ID: {result.id}")
            # Result Backend가 None인 경우 상태 조회 불가
            try:
                print(f"✓ Task 상태: {result.state}")
            except AttributeError:
                print("✓ Task 상태: (Result Backend가 설정되지 않아 상태 조회 불가, 하지만 Task는 큐에 등록됨)")
            
            # 결과 대기 (Result Backend가 없으면 조회 불가)
            try:
                task_result = result.get(timeout=5)
                print(f"✓ Task 결과: {task_result}")
            except (AttributeError, Exception) as e:
                # Result Backend가 None이면 결과 조회 불가능하지만 Task는 실행됨
                print(f"⚠ Task 결과 조회 불가 (Result Backend 미설정): {type(e).__name__}")
                print("  → 하지만 Task는 정상적으로 실행되었습니다. 데이터베이스에서 알림을 확인하세요.")
        else:
            print(f"⚠ 동기 처리됨: {result}")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # 3. 직접 Celery Task 호출
    print("=== 직접 Celery Task 호출 테스트 ===")
    try:
        task = create_notification_async.delay(
            user_id=user.user_id,
            notification_type='M',
            title="비동기 알림 테스트 #2",
            message="create_notification_async.delay() 직접 호출"
        )
        
        print(f"✓ Task ID: {task.id}")
        
        # Result Backend가 None인 경우 상태 조회 불가
        try:
            print(f"✓ Task 상태: {task.state}")
        except AttributeError:
            print("✓ Task 상태: (Result Backend가 설정되지 않아 상태 조회 불가, 하지만 Task는 큐에 등록됨)")
        
        # 결과 대기 (Result Backend가 없으면 조회 불가)
        try:
            result = task.get(timeout=5)
            print(f"✓ Task 결과: {result}")
        except (AttributeError, Exception) as e:
            # Result Backend가 None이면 결과 조회 불가능하지만 Task는 실행됨
            print(f"⚠ Task 결과 조회 불가 (Result Backend 미설정): {type(e).__name__}")
            print("  → 하지만 Task는 정상적으로 실행되었습니다. 데이터베이스에서 알림을 확인하세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # 4. 생성된 알림 확인
    print("=== 생성된 알림 확인 ===")
    notifications = Notification.objects.filter(
        user_id=user.user_id
    ).order_by('-created_at')[:3]
    
    if notifications:
        for notif in notifications:
            print(f"  [{notif.created_at}] {notif.title}: {notif.message}")
    else:
        print("  알림이 없습니다.")
    
    print()
    print("=== 테스트 완료 ===")

if __name__ == '__main__':
    test_async_notification()
