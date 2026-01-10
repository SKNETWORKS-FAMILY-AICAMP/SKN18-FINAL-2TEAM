# Celery + RabbitMQ 서버 설정 가이드

## 📋 개요

프로젝트의 RabbitMQ 설정을 서버 환경에 맞게 적용하는 방법을 설명합니다.
프로젝트는 이미 `messaging/config.py`에서 RabbitMQ 설정을 관리하고 있으며,
Celery도 동일한 RabbitMQ를 사용하도록 설정되어 있습니다.

---

## 🔧 설정 방법

### 방법 1: 환경변수 사용 (로컬 개발 / Docker)

#### `.env` 파일에 추가

```bash
# RabbitMQ 서버 연결 정보
RABBITMQ_HOST=43.201.55.197  # 서버 RabbitMQ IP 또는 호스트명
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=your_password_here
RABBITMQ_VHOST=/

# Celery 설정 (선택사항 - 자동으로 RABBITMQ_URL 사용)
# CELERY_BROKER_URL은 자동으로 messaging/config.py의 RABBITMQ_URL을 사용합니다.
# CELERY_RESULT_BACKEND도 동일하게 설정됩니다.

# 비동기 알림 설정 (선택사항)
# 기본값: True (비동기 알림 활성화)
# 동기 처리로 변경하려면 False로 설정
# NOTIFICATION_USE_ASYNC=False
```

#### Docker Compose 사용 시

`docker-compose.yml` 또는 `docker-compose.prod.yml`에 환경변수 추가:

```yaml
services:
  web:
    environment:
      RABBITMQ_HOST: ${RABBITMQ_HOST:-43.201.55.197}
      RABBITMQ_PORT: ${RABBITMQ_PORT:-5672}
      RABBITMQ_USER: ${RABBITMQ_USER:-admin}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST:-/}
      NOTIFICATION_USE_ASYNC: ${NOTIFICATION_USE_ASYNC:-True}  # 기본값: True
```

---

### 방법 2: AWS Parameter Store 사용 (프로덕션 권장)

프로젝트는 이미 AWS Parameter Store를 지원합니다.

#### Parameter Store에 설정 추가

AWS Systems Manager Parameter Store에 다음 파라미터를 추가:

```bash
# AWS CLI 사용
aws ssm put-parameter \
  --name "/skn18/rabbitmq-user" \
  --value "admin" \
  --type "String" \
  --region ap-northeast-2

aws ssm put-parameter \
  --name "/skn18/rabbitmq-password" \
  --value "your_secure_password" \
  --type "SecureString" \
  --region ap-northeast-2
```

#### 환경변수로 호스트 설정

Parameter Store에는 호스트 정보가 없으므로 환경변수로 설정:

```bash
# 환경변수
export RABBITMQ_HOST=43.201.55.197
export RABBITMQ_PORT=5672
export RABBITMQ_VHOST=/
```

또는 `docker-compose.prod.yml`에서:

```yaml
services:
  web:
    environment:
      RABBITMQ_HOST: ${RABBITMQ_HOST}  # GitHub Actions에서 주입
      RABBITMQ_PORT: ${RABBITMQ_PORT:-5672}
      # RABBITMQ_USER, RABBITMQ_PASSWORD는 Parameter Store에서 자동으로 가져옴
```

---

## 🔍 현재 설정 확인

### 1. RabbitMQ URL 확인

Django shell에서 확인:

```python
python manage.py shell

from messaging.config import RABBITMQ_URL
print(f"RabbitMQ URL: {RABBITMQ_URL}")
```

### 2. Celery 설정 확인

```python
from django.conf import settings
print(f"Celery Broker URL: {settings.CELERY_BROKER_URL}")
print(f"Celery Result Backend: {settings.CELERY_RESULT_BACKEND}")
```

### 3. RabbitMQ 연결 테스트

```python
from messaging.connection import RabbitMQConnection

connection = RabbitMQConnection()
conn = connection.get_connection()
print(f"Connected: {connection.is_connected()}")
connection.close()
```

---

## 🚀 서버 RabbitMQ 적용 단계

### Step 1: 환경변수 설정

**로컬 개발 환경:**
```bash
# .env 파일 생성 또는 수정
RABBITMQ_HOST=43.201.55.197
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=your_password
RABBITMQ_VHOST=/
```

**프로덕션 환경 (AWS):**
- Parameter Store에 `/skn18/rabbitmq-user`, `/skn18/rabbitmq-password` 설정
- 환경변수로 `RABBITMQ_HOST` 설정

### Step 2: Celery Worker 실행

```bash
cd django_app

# Worker 실행
celery -A config worker --loglevel=info

# Beat 실행 (스케줄러)
celery -A config beat --loglevel=info

# 또는 동시 실행
celery -A config worker --beat --loglevel=info
```

### Step 3: 연결 확인

**RabbitMQ Management UI 접속:**
```
http://43.201.55.197:15672
```

**Celery 연결 확인:**
```bash
# Celery inspect로 worker 상태 확인
celery -A config inspect active
celery -A config inspect registered
```

---

## 📝 설정 파일 위치

### 자동 설정 (권장)

프로젝트는 이미 다음 파일에서 자동으로 RabbitMQ를 사용하도록 설정되어 있습니다:

1. **`messaging/config.py`**
   - RabbitMQ 연결 정보 관리
   - 환경변수 → Parameter Store → 기본값 순서로 읽음
   - `RABBITMQ_URL` 생성

2. **`django_app/config/settings.py`**
   - Celery 설정
   - `CELERY_BROKER_URL`과 `CELERY_RESULT_BACKEND`가 자동으로 `RABBITMQ_URL` 사용

3. **`django_app/config/celery.py`**
   - Celery 앱 초기화
   - Django 설정에서 자동으로 RabbitMQ URL 로드

### 수동 설정 (필요 시)

환경변수로 직접 지정하려면:

```bash
# .env 파일
CELERY_BROKER_URL=amqp://admin:password@43.201.55.197:5672//
CELERY_RESULT_BACKEND=amqp://admin:password@43.201.55.197:5672//
```

**주의:** 비밀번호에 특수문자가 있으면 URL 인코딩 필요:
```python
from urllib.parse import quote_plus
password_encoded = quote_plus("your@password#123")
url = f"amqp://admin:{password_encoded}@43.201.55.197:5672//"
```

---

## 🔐 보안 고려사항

### 1. 비밀번호 관리

**로컬 개발:**
- `.env` 파일 사용 (`.gitignore`에 포함되어야 함)
- 절대 Git에 커밋하지 않기

**프로덕션:**
- AWS Parameter Store의 `SecureString` 타입 사용
- IAM 역할로 접근 제어

### 2. 네트워크 보안

- RabbitMQ 서버 방화벽 설정
- VPC 내부 통신 권장
- SSL/TLS 사용 고려 (프로덕션)

### 3. 접근 제어

- RabbitMQ 사용자별 권한 설정
- VHost별 접근 제어

---

## 🧪 테스트

### 1. RabbitMQ 연결 테스트

```python
python manage.py shell

from messaging.connection import RabbitMQConnection
conn = RabbitMQConnection()
print(f"Connected: {conn.is_connected()}")
```

### 2. Celery Task 테스트

```python
from apps.dashboard.tasks import check_schedule_reminders

# 동기 실행 (테스트)
result = check_schedule_reminders(check_minutes=60)
print(result)

# 비동기 실행 (실제 사용)
task = check_schedule_reminders.delay(check_minutes=60)
print(f"Task ID: {task.id}")
print(f"Result: {task.get(timeout=10)}")
```

### 3. 알림 생성 테스트

```python
from apps.dashboard.tasks import create_notification_async

task = create_notification_async.delay(
    user_id="test_user",
    notification_type='M',
    title="테스트 알림",
    message="RabbitMQ를 통한 비동기 알림 테스트"
)

print(f"Task ID: {task.id}")
print(f"Result: {task.get(timeout=5)}")
```

---

## 🐛 문제 해결

### RabbitMQ 연결 실패

1. **호스트 확인**
   ```bash
   ping 43.201.55.197
   telnet 43.201.55.197 5672
   ```

2. **방화벽 확인**
   - 포트 5672 (AMQP) 열려있는지 확인
   - 포트 15672 (Management UI) 열려있는지 확인

3. **인증 정보 확인**
   ```python
   from messaging.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
   print(f"Host: {RABBITMQ_HOST}")
   print(f"User: {RABBITMQ_USER}")
   print(f"Password: {'*' * len(RABBITMQ_PASSWORD) if RABBITMQ_PASSWORD else 'None'}")
   ```

### Celery Worker 연결 실패

1. **Broker URL 확인**
   ```python
   from django.conf import settings
   print(settings.CELERY_BROKER_URL)
   ```

2. **Worker 로그 확인**
   ```bash
   celery -A config worker --loglevel=debug
   ```

3. **RabbitMQ Management UI 확인**
   - Connections 탭에서 연결 상태 확인
   - Queues 탭에서 Celery 큐 확인

---

## 📊 모니터링

### RabbitMQ Management UI

```
http://43.201.55.197:15672
```

**확인 항목:**
- Connections: Celery worker 연결 상태
- Queues: Celery 큐 상태 (celery, celerybeat 등)
- Exchanges: Celery exchange 상태

### Celery Flower (선택사항)

```bash
pip install flower
celery -A config flower
```

```
http://localhost:5555
```

---

## ✅ 체크리스트

### 서버 RabbitMQ 적용 전

- [ ] RabbitMQ 서버 접근 가능 (포트 5672, 15672)
- [ ] RabbitMQ 사용자 계정 생성 및 권한 설정
- [ ] 방화벽 규칙 확인

### 환경변수 설정

- [ ] `.env` 파일에 RabbitMQ 정보 추가 (로컬)
- [ ] AWS Parameter Store에 설정 추가 (프로덕션)
- [ ] `RABBITMQ_HOST` 환경변수 설정

### Celery 설정 확인

- [ ] `CELERY_BROKER_URL`이 올바른 RabbitMQ URL 사용
- [ ] `CELERY_RESULT_BACKEND` 설정 확인
- [ ] Celery worker 실행 테스트

### 테스트

- [ ] RabbitMQ 연결 테스트
- [ ] Celery task 실행 테스트
- [ ] 알림 생성 테스트 (동기/비동기)

---

## 📚 참고 자료

- **프로젝트 RabbitMQ 설정**: `messaging/config.py`
- **Celery 설정**: `django_app/config/celery.py`, `django_app/config/settings.py`
- **Celery Tasks**: `django_app/apps/dashboard/tasks.py`
- **Docker Compose**: `docker-compose.yml`, `docker-compose.prod.yml`

---

**작성일**: 2026년 1월  
**서버 RabbitMQ**: 43.201.55.197:5672
