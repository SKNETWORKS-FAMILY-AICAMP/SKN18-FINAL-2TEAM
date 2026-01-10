# 알림 시스템 구현 완료 요약

## 📋 개요

프로젝트에 종합적인 알림 시스템을 구현하여 사용자에게 다양한 이벤트에 대한 실시간 알림을 제공합니다. 총 6가지 주요 기능에 알림이 연동되었으며, 실험 진행 상황에 대한 상세한 알림도 포함됩니다.

---

## 🔧 주요 변경사항

### 1. 데이터베이스 모델

#### Notification 모델 생성
- **파일**: `django_app/apps/dashboard/models.py`
- **테이블**: `t_notification`
- **주요 필드**:
  - `notification_sid`: 알림 ID (Primary Key)
  - `user_id`: 수신자 사용자 ID
  - `notification_type`: 알림 타입 ('E': 실험, 'M': 미팅, 'N': 노트, 'SYS': 시스템)
  - `title`: 알림 제목
  - `message`: 알림 메시지
  - `read_yn`: 읽음 여부 ('Y'/'N')
  - `related_sid`: 관련 ID (experiment_sid, schedule_sid, note_sid 등)
  - `created_at`: 생성 일시

#### 인덱스 최적화
- `user_id` + `created_at` 복합 인덱스 (최신 알림 조회 최적화)
- `user_id` + `read_yn` 복합 인덱스 (읽지 않은 알림 조회 최적화)

### 2. 알림 유틸리티 함수

#### 파일: `django_app/apps/dashboard/notification_utils.py`

**기본 함수:**
- `create_notification()`: 기본 알림 생성 함수
- `get_user_display_name()`: 사용자 표시 이름 가져오기
- `bulk_create_notifications()`: 여러 알림 일괄 생성

**기능별 알림 함수:**
1. `create_schedule_share_notification()` - 일정 공유 알림
2. `create_organization_invitation_notification()` - 조직 초대 알림
3. `create_schedule_reminder_notification()` - 일정 리마인더 알림
4. `create_experiment_start_notification()` - 실험 시작 알림
5. `create_experiment_tool_complete_notification()` - 실험 도구 완료 알림
6. `create_experiment_final_tool_complete_notification()` - 마지막 도구 완료 및 실험 완료 통합 알림
7. `create_note_share_notification()` - 노트 공유 알림

### 3. 기능별 알림 연동

#### 일정 공유 알림
- **파일**: `django_app/apps/schedule/views.py`
- **함수**: 
  - `_invite_schedule_shared_users()` (라인 232-282)
  - `schedule_shared_users()` (라인 1359-1373)
- **발생 시점**: 일정 초대 생성 시
- **수신자**: 초대받은 사용자
- **메시지**: "{소유자명}님이 '{일정명}' 일정을 공유했습니다."

#### 조직 초대 알림
- **파일**: `django_app/apps/organization/views.py`
- **함수**:
  - `organization_create_api()` - 조직 생성 시 멤버 초대 알림
  - `organization_add_member_api()` - 조직 멤버 추가 시 알림
- **발생 시점**: 조직 초대 생성 시
- **수신자**: 초대받은 사용자
- **메시지**: "{초대자명}님이 '{조직명}' 조직에 초대했습니다."

#### 노트 공유 알림
- **파일**: `django_app/apps/notes/views.py`
- **함수**:
  - `note_create_api()` - 노트 생성 시 공유 멤버에게 알림
  - `note_share_api()` - 노트 공유 시 알림
- **발생 시점**: 노트 공유 시
- **수신자**: 공유받은 사용자
- **메시지**: "{소유자명}님이 '{노트명}' 노트를 공유했습니다."

#### 실험 알림
- **파일**: `messaging/consumers/simulation_consumer.py`
- **함수**: `handle_simulation_task()`

**실험 시작 알림:**
- **발생 시점**: 첫 번째 작업 처리 시작 시 (`current_sort_order == 0`)
- **수신자**: 실험 생성자
- **메시지**: "'{실험명}' 실험이 시작되었습니다."

**중간 도구 완료 알림:**
- **발생 시점**: 중간 단계 도구 완료 시 (`next_task_id`가 존재할 때)
- **수신자**: 실험 생성자
- **메시지**: "'{실험명}' 실험의 {도구명} 도구가 완료되었습니다."
- **예시**: RFdiffusion, ProteinMPNN 등

**마지막 도구 완료 및 실험 완료 통합 알림:**
- **발생 시점**: 마지막 단계 도구 완료 시 (`next_task_id`가 없을 때)
- **수신자**: 실험 생성자
- **메시지**: "'{실험명}' 실험의 {도구명} 도구가 완료되어 실험이 완료되었습니다."
- **특징**: 도구 완료와 실험 완료를 하나의 알림으로 통합

#### 일정 리마인더 알림
- **파일**: `django_app/apps/dashboard/management/commands/check_schedule_reminders.py`
- **타입**: Django 관리 명령어
- **발생 시점**: 일정 시작 전 (5분, 15분, 30분, 1시간 전)
- **수신자**: 일정 소유자
- **메시지**: "'{일정명}' 일정이 {시간} 시작됩니다."
- **실행 방법**: `python manage.py check_schedule_reminders`

### 4. 프론트엔드 연동

#### Context Processor
- **파일**: `django_app/apps/dashboard/context_processors.py`
- **기능**: 모든 템플릿에 알림 데이터 자동 주입
  - `unread_notifications_count`: 읽지 않은 알림 개수
  - `recent_notifications`: 최근 알림 목록 (최대 10개)

#### API 엔드포인트
- **파일**: `django_app/apps/dashboard/views.py`
- **엔드포인트**: `POST /api/notifications/<notification_id>/read/`
- **기능**: 알림 읽음 처리

#### URL 설정
- **파일**: `django_app/config/urls.py`
- **등록**: `api/notifications/<int:notification_id>/read/`

#### Admin 등록
- **파일**: `django_app/apps/dashboard/admin.py`
- **기능**: Django Admin에서 알림 관리 가능

---

## 🧪 테스트 목록

### 1. 통합 테스트 스크립트

#### 파일: `django_app/apps/dashboard/test_all_notifications.py`

**실행 방법:**
```bash
# 방법 1: 직접 실행
python django_app/manage.py shell < django_app/apps/dashboard/test_all_notifications.py

# 방법 2: shell에서 실행
python django_app/manage.py shell
>>> exec(open('django_app/apps/dashboard/test_all_notifications.py').read())
```

**테스트 항목:**
1. ✅ 일정 공유 알림 테스트
2. ✅ 조직 초대 알림 테스트
3. ✅ 일정 리마인더 알림 테스트
4. ✅ 실험 시작 알림 테스트
5. ✅ 실험 도구 완료 알림 테스트
6. ✅ 실험 완료 알림 테스트
7. ✅ 노트 공유 알림 테스트

**출력 정보:**
- 초기 알림 개수
- 각 테스트별 성공/실패 여부
- 최종 알림 개수 및 생성된 알림 목록

### 2. 테스트 사용자 생성 스크립트

#### 파일: `django_app/apps/dashboard/create_test_users.py`

**실행 방법:**
```bash
python django_app/manage.py shell < django_app/apps/dashboard/create_test_users.py
```

**생성되는 계정:**
- 사용자 A: `test_user_a@example.com` / `test1234!`
- 사용자 B: `test_user_b@example.com` / `test1234!`

### 3. 테스트 알림 생성 스크립트

#### 파일: `django_app/apps/dashboard/create_test_notifications.py`

**기능**: 다양한 타입의 테스트 알림 생성

### 4. 일정 리마인더 명령어 테스트

#### 실행 방법:
```bash
cd django_app
python manage.py check_schedule_reminders

# 옵션: 체크 시간 범위 지정
python manage.py check_schedule_reminders --check-minutes 120
```

**테스트 시나리오:**
1. 테스트 일정 생성 (10분 후 시작)
2. 리마인더 명령어 실행
3. 알림 생성 확인

### 5. 웹 UI 테스트

#### 시나리오 1: 일정 공유 알림
1. 사용자 A로 로그인
2. 일정 생성 또는 수정
3. 사용자 B에게 공유
4. 사용자 B로 로그인
5. 헤더 알림 아이콘 클릭 → 알림 확인

#### 시나리오 2: 노트 공유 알림
1. 사용자 A로 로그인
2. 노트 생성 또는 수정
3. 사용자 B에게 공유
4. 사용자 B로 로그인
5. 헤더 알림 아이콘 클릭 → 알림 확인

#### 시나리오 3: 조직 초대 알림
1. 사용자 A로 로그인
2. 조직 생성 또는 멤버 추가
3. 사용자 B 초대
4. 사용자 B로 로그인
5. 헤더 알림 아이콘 클릭 → 알림 확인

#### 시나리오 4: 실험 알림
1. 실험 생성 및 실행
2. 실험 시작 알림 확인
3. 각 도구 완료 알림 확인
4. 마지막 도구 완료 시 통합 알림 확인

---

## 📊 알림 타입별 상세 정보

| 알림 타입 | 발생 시점 | 수신자 | 메시지 형식 | 관련 ID |
|---------|---------|--------|-----------|---------|
| 일정 공유 | 일정 초대 생성 시 | 초대받은 사용자 | "{소유자명}님이 '{일정명}' 일정을 공유했습니다." | `schedule_sid` |
| 조직 초대 | 조직 초대 생성 시 | 초대받은 사용자 | "{초대자명}님이 '{조직명}' 조직에 초대했습니다." | `organization_sid` |
| 일정 리마인더 | 일정 시작 전 | 일정 소유자 | "'{일정명}' 일정이 {시간} 시작됩니다." | `schedule_sid` |
| 실험 시작 | 첫 번째 작업 처리 시작 | 실험 생성자 | "'{실험명}' 실험이 시작되었습니다." | `experiment_sid` |
| 도구 완료 | 중간 단계 도구 완료 | 실험 생성자 | "'{실험명}' 실험의 {도구명} 도구가 완료되었습니다." | `experiment_sid` |
| 실험 완료 | 마지막 도구 완료 | 실험 생성자 | "'{실험명}' 실험의 {도구명} 도구가 완료되어 실험이 완료되었습니다." | `experiment_sid` |
| 노트 공유 | 노트 공유 시 | 공유받은 사용자 | "{소유자명}님이 '{노트명}' 노트를 공유했습니다." | `note_sid` |

---

## 🚀 추가 개선 방향

### 1. 일정 리마인더 스케줄러 설정 (우선순위: 높음)

**현재 상태**: 수동 실행만 가능

**개선 방안:**
- **Cron 설정** (Linux/Mac):
  ```bash
  # crontab 편집
  crontab -e
  
  # 매 5분마다 실행
  */5 * * * * cd /path/to/project/django_app && python manage.py check_schedule_reminders
  ```

- **Celery Beat 사용** (권장):
  
  **설정 파일 위치:**
  - `django_app/config/celery.py` - Celery 앱 설정 (이미 생성됨)
  - `django_app/config/settings.py` - Celery Beat 스케줄 설정 (이미 추가됨)
  - `django_app/apps/dashboard/tasks.py` - Celery task 함수 (이미 생성됨)
  
  **실행 방법:**
  ```bash
  # 1. Celery worker 실행
  cd django_app
  celery -A config worker --loglevel=info
  
  # 2. Celery Beat 실행 (스케줄러)
  celery -A config beat --loglevel=info
  
  # 3. Worker + Beat 동시 실행 (개발 환경)
  celery -A config worker --beat --loglevel=info
  ```
  
  **스케줄 설정 변경:**
  `django_app/config/settings.py` 파일의 `CELERY_BEAT_SCHEDULE` 섹션에서 수정:
  ```python
  CELERY_BEAT_SCHEDULE = {
      'check-schedule-reminders': {
          'task': 'apps.dashboard.tasks.check_schedule_reminders',
          'schedule': 300.0,  # 5분마다 (초 단위)
          # 또는 crontab 사용:
          # 'schedule': crontab(minute='*/5'),  # 매 5분마다
      },
  }
  ```
  
  **주의사항:**
  - Celery를 사용하려면 `celery` 패키지 설치 필요: `pip install celery`
  - Redis 또는 RabbitMQ가 필요합니다 (기본값: Redis)
  - 환경변수 `CELERY_BROKER_URL`과 `CELERY_RESULT_BACKEND` 설정 필요

- **Windows Task Scheduler** (Windows 환경):
  - 작업 스케줄러에서 Python 스크립트를 주기적으로 실행

### 2. 이메일 알림 연동 (우선순위: 중간)

**개선 방안:**
- `UserSettings` 모델의 `email_alerts` 필드 확인
- 알림 생성 시 이메일 발송 옵션 추가
- SMTP 설정 및 이메일 템플릿 작성
- 알림 타입별 이메일 발송 여부 설정

**구현 예시:**
```python
def create_notification_with_email(...):
    notification = create_notification(...)
    
    # 사용자 설정 확인
    user_settings = UserSettings.objects.get(user_id=user_id)
    if user_settings.email_alerts == 'Y':
        send_notification_email(notification)
    
    return notification
```

### 3. 푸시 알림 연동 (우선순위: 중간)

**개선 방안:**
- **브라우저 푸시 알림**: Web Push API 사용
- **모바일 푸시 알림**: FCM (Firebase Cloud Messaging) 또는 APNS (Apple Push Notification Service)
- 사용자별 푸시 토큰 관리
- 알림 타입별 푸시 발송 여부 설정

### 4. 알림 설정 기능 (우선순위: 중간)

**개선 방안:**
- 사용자별 알림 설정 페이지 추가
- 알림 타입별 활성화/비활성화 옵션
- 알림 수신 시간대 설정
- 알림 그룹핑 설정 (예: 실험 알림만 받기)

**데이터베이스 스키마:**
```sql
CREATE TABLE t_user_notification_settings (
    user_id VARCHAR(60) PRIMARY KEY,
    schedule_share_enabled BOOLEAN DEFAULT TRUE,
    organization_invite_enabled BOOLEAN DEFAULT TRUE,
    schedule_reminder_enabled BOOLEAN DEFAULT TRUE,
    experiment_start_enabled BOOLEAN DEFAULT TRUE,
    experiment_tool_complete_enabled BOOLEAN DEFAULT TRUE,
    experiment_complete_enabled BOOLEAN DEFAULT TRUE,
    note_share_enabled BOOLEAN DEFAULT TRUE,
    email_enabled BOOLEAN DEFAULT FALSE,
    push_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME,
    quiet_hours_end TIME
);
```

### 5. 알림 필터링 및 검색 (우선순위: 낮음)

**개선 방안:**
- 알림 타입별 필터링
- 날짜 범위 필터링
- 읽음/읽지 않음 필터링
- 키워드 검색 기능

### 6. 알림 그룹핑 및 요약 (우선순위: 낮음)

**개선 방안:**
- 같은 타입의 알림을 시간대별로 그룹핑
- "5개의 새로운 실험 알림" 같은 요약 표시
- 알림 일괄 읽음 처리

### 7. 알림 성능 최적화 (우선순위: 중간)

**개선 방안:**
- 읽지 않은 알림 개수 캐싱 (Redis 사용)
- 알림 목록 페이지네이션
- 알림 생성 시 비동기 처리 (Celery 사용)
- 대량 알림 생성 시 `bulk_create_notifications()` 활용

### 8. 알림 통계 및 분석 (우선순위: 낮음)

**개선 방안:**
- 사용자별 알림 수신 통계
- 알림 타입별 클릭률 분석
- 알림 읽음 시간 분석
- 알림 효과성 측정

### 9. 알림 템플릿 커스터마이징 (우선순위: 낮음)

**개선 방안:**
- 관리자 페이지에서 알림 메시지 템플릿 수정
- 다국어 지원
- 사용자별 알림 메시지 형식 설정

### 10. 실험 알림 고도화 (우선순위: 낮음)

**개선 방안:**
- 실험 진행률 퍼센트 표시
- 예상 완료 시간 표시
- 실험 실패 시 오류 알림
- 실험 결과 요약 알림

---

## 📝 구현 파일 목록

### 핵심 파일
- `django_app/apps/dashboard/models.py` - Notification 모델
- `django_app/apps/dashboard/notification_utils.py` - 알림 유틸리티 함수
- `django_app/apps/dashboard/views.py` - 알림 읽음 API
- `django_app/apps/dashboard/context_processors.py` - 알림 데이터 주입
- `django_app/apps/dashboard/admin.py` - Admin 등록

### 연동 파일
- `django_app/apps/schedule/views.py` - 일정 공유 알림
- `django_app/apps/organization/views.py` - 조직 초대 알림
- `django_app/apps/notes/views.py` - 노트 공유 알림
- `django_app/apps/experiments/views.py` - 실험 생성 (알림 제거됨)
- `messaging/consumers/simulation_consumer.py` - 실험 진행 알림

### 관리 명령어
- `django_app/apps/dashboard/management/commands/check_schedule_reminders.py` - 일정 리마인더 체크

### 테스트 파일
- `django_app/apps/dashboard/test_all_notifications.py` - 통합 테스트
- `django_app/apps/dashboard/create_test_users.py` - 테스트 사용자 생성
- `django_app/apps/dashboard/create_test_notifications.py` - 테스트 알림 생성

### 설정 파일
- `django_app/config/urls.py` - URL 라우팅

---

## ✅ 체크리스트

### 구현 완료
- [x] Notification 모델 생성 및 마이그레이션
- [x] 알림 유틸리티 함수 구현
- [x] 일정 공유 알림 연동
- [x] 조직 초대 알림 연동
- [x] 노트 공유 알림 연동
- [x] 실험 시작 알림 연동
- [x] 실험 도구 완료 알림 연동
- [x] 실험 완료 알림 연동 (마지막 도구 통합)
- [x] 일정 리마인더 관리 명령어 생성
- [x] Context Processor 구현
- [x] 알림 읽음 API 구현
- [x] Admin 등록
- [x] 통합 테스트 스크립트 작성

### 향후 작업
- [ ] 일정 리마인더 스케줄러 설정 (Cron/Celery)
- [ ] 이메일 알림 연동
- [ ] 푸시 알림 연동
- [ ] 알림 설정 기능 구현
- [ ] 알림 필터링 및 검색 기능
- [ ] 알림 성능 최적화
- [ ] 알림 통계 및 분석

---

## 🔍 문제 해결 가이드

### 알림이 생성되지 않는 경우

1. **마이그레이션 확인**
   ```bash
   python manage.py showmigrations dashboard
   python manage.py migrate dashboard
   ```

2. **로그 확인**
   - Django 로그에서 `Failed to create notification` 에러 확인
   - 각 기능 파일의 로그 확인

3. **사용자 ID 확인**
   - 알림을 받을 사용자의 `user_id`가 올바른지 확인
   - 사용자가 존재하는지 확인

### 일정 리마인더가 작동하지 않는 경우

1. **관리 명령어 실행 확인**
   ```bash
   python manage.py check_schedule_reminders --check-minutes 60
   ```

2. **일정 데이터 확인**
   - `start_date`가 올바르게 설정되어 있는지
   - `use_yn='Y'`, `schedule_status='E'`인지 확인

3. **스케줄러 설정 확인**
   - Cron 또는 Celery Beat가 올바르게 설정되어 있는지 확인

### 실험 알림이 생성되지 않는 경우

1. **Django 설정 확인**
   - `simulation_consumer.py`에서 Django ORM 접근 가능한지 확인
   - `_ensure_django_setup()` 함수가 올바르게 작동하는지 확인

2. **실험 데이터 확인**
   - 실험이 올바르게 생성되었는지
   - `experiment.created_id`가 올바른지 확인

3. **로그 확인**
   - `simulation_consumer.py`의 로그에서 알림 생성 관련 에러 확인

---

## 📚 참고 자료

### 관련 문서
- `django_app/apps/dashboard/TEST_NOTIFICATION.md` - 초기 알림 테스트 가이드
- `assets/database_schema.sql` - 데이터베이스 스키마 (라인 490-499)

### Django 문서
- [Django Models](https://docs.djangoproject.com/en/stable/topics/db/models/)
- [Django Management Commands](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
- [Django Context Processors](https://docs.djangoproject.com/en/stable/ref/templates/api/#context-processors)

---

**작성일**: 2026년 1월  
**최종 업데이트**: 실험 알림 통합 기능 추가 후
