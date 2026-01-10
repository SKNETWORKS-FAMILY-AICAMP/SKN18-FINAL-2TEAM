# 로컬 비동기 알림 테스트 가이드

## 📋 개요

로컬 환경에서 Celery를 통한 비동기 알림 처리가 제대로 동작하는지 확인하는 방법입니다.

---

## 🚀 준비 단계

### 1. RabbitMQ 실행 (Docker Compose)

```bash
# 프로젝트 루트에서
docker-compose up -d rabbitmq

# RabbitMQ Management UI 접속 확인
# http://localhost:15672
# 기본 계정: guest / guest
```

### 2. 환경변수 설정 (선택사항)

`.env` 파일에 RabbitMQ 설정이 없으면 기본값 사용:
- `RABBITMQ_HOST=localhost`
- `RABBITMQ_PORT=5672`
- `RABBITMQ_USER=guest`
- `RABBITMQ_PASSWORD=guest`

---

## 🔧 Celery Worker 실행

### 터미널 1: Celery Worker 실행

```bash
cd django_app

# Celery Worker 실행
celery -A config worker --loglevel=info

# 또는 더 자세한 로그
celery -A config worker --loglevel=debug
```

**정상 실행 시 출력 예시:**
```
[2026-01-XX XX:XX:XX,XXX: INFO/MainProcess] Connected to amqp://guest:**@127.0.0.1:5672//
[2026-01-XX XX:XX:XX,XXX: INFO/MainProcess] celery@hostname ready.
```

### 터미널 2: Celery Beat 실행 (일정 리마인더 테스트 시)

```bash
cd django_app

# Celery Beat 실행 (스케줄러)
celery -A config beat --loglevel=info
```

---

## 🧪 테스트 방법

### 방법 1: Django Shell에서 테스트

```bash
cd django_app
python manage.py shell
```

#### 1-1. Celery 설정 확인

```python
from django.conf import settings

# Celery Broker URL 확인
print(f"Celery Broker URL: {settings.CELERY_BROKER_URL}")
print(f"Celery Result Backend: {settings.CELERY_RESULT_BACKEND}")
print(f"NOTIFICATION_USE_ASYNC: {settings.NOTIFICATION_USE_ASYNC}")
```

**예상 출력:**
```
Celery Broker URL: amqp://guest:guest@localhost:5672//
Celery Result Backend: amqp://guest:guest@localhost:5672//
NOTIFICATION_USE_ASYNC: True
```

#### 1-2. 비동기 알림 생성 테스트

```python
from apps.dashboard.notification_utils import create_notification
from apps.account.models import CustomUser

# 테스트 사용자 가져오기 (실제 사용자 ID로 변경)
user = CustomUser.objects.first()
if not user:
    print("⚠ 사용자가 없습니다. 먼저 사용자를 생성하세요.")
else:
    print(f"테스트 사용자: {user.user_id}")
    
    # 비동기 알림 생성 (기본적으로 비동기 사용)
    result = create_notification(
        user_id=user.user_id,
        notification_type='SYS',
        title="비동기 알림 테스트",
        message="이 알림은 Celery Worker를 통해 비동기로 생성되었습니다."
    )
    
    # 결과 확인
    print(f"결과 타입: {type(result)}")
    
    # Task 객체인 경우 (비동기 처리됨)
    if hasattr(result, 'id'):
        print(f"✓ Task ID: {result.id}")
        print(f"✓ Task 상태: {result.state}")
        
        # 결과 대기 (최대 5초)
        try:
            task_result = result.get(timeout=5)
            print(f"✓ Task 결과: {task_result}")
        except Exception as e:
            print(f"⚠ Task 결과 조회 실패: {e}")
    
    # Notification 객체인 경우 (동기 처리됨)
    elif hasattr(result, 'notification_sid'):
        print(f"⚠ 동기 처리됨 (notification_sid: {result.notification_sid})")
        print("⚠ Celery Worker가 실행 중이지 않거나 연결에 실패했습니다.")
```

#### 1-3. 알림이 실제로 생성되었는지 확인

```python
from apps.dashboard.models import Notification

# 최근 알림 확인
recent_notifications = Notification.objects.filter(
    user_id=user.user_id
).order_by('-created_at')[:5]

for notif in recent_notifications:
    print(f"[{notif.created_at}] {notif.title}: {notif.message}")
```

#### 1-4. 직접 Celery Task 호출 테스트

```python
from apps.dashboard.tasks import create_notification_async

# 직접 Celery Task 호출
task = create_notification_async.delay(
    user_id=user.user_id,
    notification_type='M',
    title="직접 Task 호출 테스트",
    message="create_notification_async.delay()를 직접 호출했습니다."
)

print(f"Task ID: {task.id}")
print(f"Task 상태: {task.state}")

# 결과 대기
result = task.get(timeout=5)
print(f"Task 결과: {result}")
```

---

### 방법 2: 테스트 스크립트 실행

#### 2-1. 테스트 스크립트 생성

`django_app/test_async_notification.py` 파일 생성:

```python
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
            print(f"✓ Task 상태: {result.state}")
            
            # 결과 대기
            try:
                task_result = result.get(timeout=5)
                print(f"✓ Task 결과: {task_result}")
            except Exception as e:
                print(f"⚠ Task 결과 조회 실패: {e}")
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
        print(f"✓ Task 상태: {task.state}")
        
        result = task.get(timeout=5)
        print(f"✓ Task 결과: {result}")
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
```

#### 2-2. 스크립트 실행

```bash
cd django_app
python test_async_notification.py
```

---

## ✅ 성공 확인 기준

### 1. Celery Worker 로그에서 확인

Celery Worker 터미널에서 다음과 같은 로그가 보여야 합니다:

```
[2026-01-XX XX:XX:XX,XXX: INFO/MainProcess] Task apps.dashboard.tasks.create_notification_async[xxxxx-xxxx-xxxx] received
[2026-01-XX XX:XX:XX,XXX: INFO/ForkPoolWorker-1] Notification created: 123 for user test_user
[2026-01-XX XX:XX:XX,XXX: INFO/MainProcess] Task apps.dashboard.tasks.create_notification_async[xxxxx-xxxx-xxxx] succeeded in 0.123s
```

### 2. RabbitMQ Management UI에서 확인

1. http://localhost:15672 접속 (guest/guest)
2. **Queues** 탭에서 `celery` 큐 확인
3. **Connections** 탭에서 Celery Worker 연결 확인

### 3. 데이터베이스에서 확인

```python
from apps.dashboard.models import Notification

# 최근 알림 확인
notifications = Notification.objects.all().order_by('-created_at')[:5]
for n in notifications:
    print(f"{n.created_at} | {n.title} | {n.message}")
```

---

## 🐛 문제 해결

### 문제 1: "Task 객체가 아닌 Notification 객체 반환됨"

**원인:** Celery Worker가 실행되지 않았거나 연결 실패

**해결:**
1. Celery Worker가 실행 중인지 확인
2. RabbitMQ가 실행 중인지 확인: `docker ps | grep rabbitmq`
3. `CELERY_BROKER_URL` 설정 확인

### 문제 2: "Connection refused" 오류

**원인:** RabbitMQ에 연결할 수 없음

**해결:**
```bash
# RabbitMQ 컨테이너 확인
docker ps | grep rabbitmq

# RabbitMQ 재시작
docker-compose restart rabbitmq

# RabbitMQ 로그 확인
docker logs rabbitmq-final
```

### 문제 3: "ModuleNotFoundError: No module named 'celery'"

**원인:** Celery 패키지가 설치되지 않음

**해결:**
```bash
pip install celery
# 또는
pip install -r requirements.txt
```

### 문제 4: "Task가 실행되지 않음"

**원인:** Celery Worker가 Task를 인식하지 못함

**해결:**
1. Celery Worker 재시작
2. `django_app/config/__init__.py`에서 Celery 앱이 import되는지 확인
3. `apps.dashboard.tasks` 모듈이 올바른지 확인

---

## 📊 모니터링

### RabbitMQ Management UI

- **URL:** http://localhost:15672
- **계정:** guest / guest
- **확인 항목:**
  - Connections: Celery Worker 연결 상태
  - Queues: `celery` 큐의 메시지 수
  - Exchanges: Celery exchange 상태

### Celery Worker 로그

```bash
# 더 자세한 로그
celery -A config worker --loglevel=debug

# 특정 Task만 모니터링
celery -A config worker --loglevel=info --task=apps.dashboard.tasks.create_notification_async
```

---

## 🎯 다음 단계

로컬 테스트가 성공하면:

1. **프로덕션 배포:** GitHub Actions를 통해 자동 배포
2. **모니터링:** CloudWatch 로그에서 Celery Worker/Beat 상태 확인
3. **성능 테스트:** 대량 알림 생성 시 비동기 처리 효과 확인

---

**작성일:** 2026년 1월  
**참고:** `CELERY_RABBITMQ_SETUP.md` - 서버 환경 설정 가이드
