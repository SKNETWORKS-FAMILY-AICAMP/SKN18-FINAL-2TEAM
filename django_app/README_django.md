# Django Application README

HelixOps Django 애플리케이션 개발 가이드입니다.

## 📋 목차

- [프로젝트 구조](#프로젝트-구조)
- [시작하기](#시작하기)
- [개발 환경 설정](#개발-환경-설정)
- [API 문서](#api-문서)
- [데이터베이스 스키마](#데이터베이스-스키마)
- [주의사항](#주의사항)

---

## 📁 프로젝트 구조

### Django 앱 구조
```
django_app/
├── apps/                    # Django 앱들
│   ├── account/             # 계정 관리
│   ├── chat/                # 채팅 기능
│   ├── dashboard/           # 대시보드
│   ├── experiments/         # 실험 관리
│   ├── notes/               # 노트 관리
│   ├── schedule/            # 일정 관리
│   ├── organization/        # 조직 관리
│   ├── bookmark/            # 북마크
│   └── ...
├── config/                  # Django 설정
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── static/                  # 정적 파일
│   ├── css/                # 스타일시트
│   ├── js/                 # JavaScript 파일
│   └── js-lib/             # Vite 빌드 결과물
├── templates/              # HTML 템플릿
└── manage.py               # Django 관리 스크립트
```

### Static 파일 구조
```
django_app/static/
├── js/                      # HTML 템플릿용 JavaScript
│   ├── components/         # 컴포넌트별 JS
│   │   ├── header.js
│   │   ├── sidebar.js
│   │   └── subsidebar.js
│   ├── pages/             # 페이지별 JS
│   │   ├── dashboard.js
│   │   ├── chat.js
│   │   ├── schedule.js
│   │   └── ...
│   └── utils/              # 유틸리티 함수들
│       ├── markdown_message.js
│       └── ...
└── js-lib/                 # npm 라이브러리 빌드 결과물 (Vite)
    ├── main.js            # Vite 빌드 결과물
    ├── chunk-*.js         # Vite 청크 파일들
    └── ...
```

---

## 🚀 시작하기

### 사전 요구사항

- **Python**: 3.12
- **Node.js**: 22 이상
- **PostgreSQL**: Docker로 실행 가능
- **Docker & Docker Compose**: 데이터베이스 실행용

### 1. 데이터베이스 실행 (Docker)

PostgreSQL 데이터베이스를 Docker로 실행합니다.

```bash
# Windows
docker-compose -f infra/docker-compose.yml up -d

# Mac / Linux
docker compose -f infra/docker-compose.yml up -d
```

### 2. 프론트엔드 빌드 (Vite)

**터미널 1**: Vite 개발 서버 실행

```bash
cd django_ui

# Node.js 버전 확인 (22+ 필요)
node --version

# 의존성 설치 (최초 1회)
npm install

# 빌드 실행
npm run build
```

> **참고**: `package.json`에 라이브러리를 추가할 때는 반드시 팀원들에게 공유하세요!

### 3. Django 서버 실행

**터미널 2**: Django 개발 서버 실행

```bash
# 마이그레이션 생성 (모델 변경 시)
python django_app/manage.py makemigrations

# 마이그레이션 적용
python django_app/manage.py migrate

# 관리자 계정 생성 (최초 1회)
python django_app/manage.py createsuperuser

# 개발 서버 실행
python django_app/manage.py runserver
```

### 4. 접속

브라우저에서 다음 URL로 접속합니다:

```
http://127.0.0.1:8000/
```

### 5. 더미 데이터 (선택사항)

테스트를 위해 더미 데이터를 사용할 수 있습니다:

- `dummy_data.sql` 파일 참고
- 데이터베이스에 직접 INSERT 후 테스트

---

## 📚 API 문서

### 접속 URL

- **Swagger UI**: http://127.0.0.1:8000/api/docs/
- **ReDoc**: http://127.0.0.1:8000/api/redoc/
- **OpenAPI Schema (JSON)**: http://127.0.0.1:8000/api/schema/

### 인증 설정

Swagger UI에서 API를 테스트하려면 인증이 필요합니다.

#### 방법 1: 브라우저 세션 쿠키 자동 사용 (권장)

1. 먼저 로그인 페이지에서 로그인
   ```
   http://127.0.0.1:8000/accounts/login/
   ```
2. 로그인 후 Swagger UI 접속
   ```
   http://127.0.0.1:8000/api/docs/
   ```
3. 브라우저가 세션 쿠키를 자동으로 전달하므로 별도 설정 불필요

#### 방법 2: 세션 쿠키 수동 입력

1. 브라우저 개발자 도구 열기 (F12)
2. **Application/Storage** 탭 → **Cookies** → `http://127.0.0.1:8000` 선택
3. `sessionid` 값 복사
4. Swagger UI 우측 상단의 **"Authorize"** 버튼 클릭
5. `sessionid` 필드에 붙여넣기
6. `csrftoken`도 동일하게 복사해 입력 (있는 경우)
7. **"Authorize"** 클릭

### 주요 API 엔드포인트

현재 Swagger에 등록된 API:

- `GET /api/notes/` - 노트 목록 조회
- `GET /api/experiments/` - 실험 목록 조회
- `POST /api/experiments/` - 실험 생성
- `GET /api/calendars/` - 캘린더 목록 조회
- `POST /api/calendars/` - 캘린더 생성
- `GET /api/schedules/` - 일정 목록 조회
- `POST /api/schedules/` - 일정 생성

---

## 🗄️ 데이터베이스 스키마

### Schedule 관련 테이블

일정 관리 시스템의 데이터베이스 테이블 구조입니다.

#### 1. `t_user_calendar` - 사용자 캘린더 그룹

사용자가 생성한 캘린더 그룹을 관리하는 테이블입니다.

**주요 필드**:
- `calendar_sid` (PK): 캘린더 ID
- `calendar_name`: 캘린더 이름
- `color`: 캘린더 색상 (HEX 코드)
- `is_visible`: 표시 여부 (1: 표시, 0: 숨김)
- `sort_order`: 정렬 순서 (드래그 앤 드롭으로 조정 가능)
- `source_type`: 소스 타입 (`local`: 로컬, `google`: Google Calendar)
- `external_id`: 외부 캘린더 ID (Google Calendar ID 등)
- `created_id`, `updated_id`: 생성자/수정자 ID
- `created_at`, `updated_at`: 생성/수정 시간

**관계**: `t_schedule` 테이블과 1:N 관계

**정렬**: `sort_order`, `created_at` 순으로 정렬

#### 2. `t_schedule` - 일정 메인 테이블

사용자가 생성한 일정을 저장하는 메인 테이블입니다.

**주요 필드**:
- `schedule_sid` (PK): 일정 ID
- `title`: 일정 제목
- `description`: 일정 설명
- `schedule_type`: 일정 타입
  - `E`: 실험
  - `M`: 미팅
  - `A`: 분석
  - `S`: 세미나
- `schedule_status`: 일정 상태
  - `E`: 예정
  - `R`: 진행중
  - `C`: 완료
- `start_date`, `end_date`: 시작/종료 일시
- `is_all_day`: 종일 일정 여부 (`Y`/`N`)
- `location`: 장소
- `color`: 일정 색상
- `linked_note_sid`: 연결된 노트 ID
- `calendar_sid` (FK): 소속 캘린더 → `t_user_calendar`
- `repeat_type`: 반복 타입
  - `N`: 반복 안 함
  - `D`: 매일
  - `W`: 매주
  - `M`: 매월
  - `Y`: 매년
- `use_yn`: 사용 여부 (`Y`/`N`)
- `created_id`, `updated_id`: 생성자/수정자 ID
- `created_at`, `updated_at`: 생성/수정 시간

**관계**:
- `t_user_calendar`와 N:1 관계
- `t_schedule_recurrence`와 1:1 관계
- `t_schedule_share`와 1:N 관계

#### 3. `t_schedule_recurrence` - 반복 규칙

반복 일정의 규칙을 저장하는 테이블입니다 (RRULE 기반).

**주요 필드**:
- `schedule_sid` (PK, FK): 일정 ID → `t_schedule`
- `freq`: 반복 주기
  - `DAILY`: 매일
  - `WEEKLY`: 매주
  - `MONTHLY`: 매월
  - `YEARLY`: 매년
- `interval`: 반복 간격
- `week_days`: 요일 배열 (JSON)
- `month_days`: 월의 일자 배열 (JSON)
- `count`: 반복 횟수
- `until`: 반복 종료 일시
- `timezone`: 타임존
- `metadata`: 추가 메타데이터 (JSON)
- `created_at`, `updated_at`: 생성/수정 시간

**관계**: `t_schedule`와 1:1 관계

#### 4. `t_schedule_exception` - 반복 예외

반복 일정의 예외를 처리하는 테이블입니다 (스킵/변경된 일정).

**주요 필드**:
- `recurrence_sid` (FK): 반복 규칙 ID → `t_schedule_recurrence`
- `exception_date`: 예외 날짜
- `note`: 예외 사유/메모
- `created_at`: 생성 시간

**관계**: `t_schedule_recurrence`와 N:1 관계

**제약조건**: `(recurrence_sid, exception_date)` 유니크 제약

#### 5. `t_schedule_share` - 일정 공유

일정을 다른 사용자와 공유하는 테이블입니다.

**주요 필드**:
- `schedule_share_sid` (PK): 공유 ID
- `schedule_sid` (FK): 일정 ID → `t_schedule`
- `user_id`: 공유받은 사용자 ID
- `created_id`: 공유한 사용자 ID
- `created_at`: 생성 시간

**관계**: `t_schedule`와 N:1 관계

**인덱스**: `(schedule_sid, user_id)` 복합 인덱스

#### 6. `t_google_credentials` - Google OAuth 자격증명

Google Calendar 연동을 위한 OAuth 토큰을 저장하는 테이블입니다.

**주요 필드**:
- `user_id` (PK, FK): 사용자 ID → User (1:1)
- `access_token`: 액세스 토큰
- `refresh_token`: 리프레시 토큰
- `client_id`, `client_secret`: OAuth 클라이언트 정보
- `scopes`: 권한 범위
- `expiry`: 토큰 만료 시간

**관계**: User와 1:1 관계

#### 7. `t_synced_calendar` - 동기화된 Google 캘린더

Google Calendar에서 동기화된 캘린더 목록을 관리하는 테이블입니다.

**주요 필드**:
- `user_id` (FK): 사용자 ID → User
- `calendar_id`: Google Calendar ID
- `summary`: 캘린더 이름
- `selected`: 선택 여부 (동기화 대상인지)
- `color`: 캘린더 색상 (HEX 코드)

**관계**: User와 N:1 관계

**제약조건**: `(user_id, calendar_id)` 유니크 제약

#### 8. `t_google_synced_event` - Google 이벤트 동기화 캐시

Google Calendar 이벤트와 로컬 일정(`t_schedule`)을 연결하는 메타데이터 테이블입니다.

**주요 필드**:
- `user_id` (FK): 사용자 ID → User
- `calendar_id` (FK): 동기화된 캘린더 ID → `t_synced_calendar`
- `schedule_sid` (FK): 로컬 일정 ID → `t_schedule` (1:1)
- `event_id`: Google Calendar 이벤트 ID
- `status`: 동기화 상태 (`active`, `deleted` 등)
- `etag`: Google API ETag (변경 감지용)
- `summary`: 이벤트 제목
- `raw_payload`: 원본 Google API 응답 (JSON)
- `google_updated`: Google에서 마지막 업데이트된 시간
- `created_at`, `updated_at`: 생성/수정 시간

**관계**:
- `t_schedule`와 1:1 관계
- `t_synced_calendar`와 N:1 관계

**제약조건**: `(user_id, calendar_id, event_id)` 유니크 제약

##### 데이터 저장 시점 및 플로우

`t_google_synced_event` 테이블에 데이터가 저장되는 시점과 로직은 다음과 같습니다:

**1. 트리거 시점**

- **API 호출**: `POST /schedule/api/google-events/sync/` 엔드포인트 호출 시
- **수동 동기화**: 사용자가 "최신 일정 불러오기" 버튼 클릭 시
- **자동 동기화**: Google Calendar 연동 후 초기 동기화 시

**2. 실행 플로우**

```
사용자 액션
    ↓
POST /schedule/api/google-events/sync/
    ↓
google_events_sync() 함수 (service.py:1254)
    ↓
_sync_google_events_to_db() 함수 (service.py:427)
    ↓
Google Calendar API 호출
    ↓
각 이벤트마다 _upsert_schedule_from_google_payload() 호출 (service.py:284)
    ↓
t_google_synced_event 테이블에 저장/업데이트
```

**3. 핵심 로직 (`_upsert_schedule_from_google_payload`)**

```python
# service.py:284-392

def _upsert_schedule_from_google_payload(...):
    """
    Google 이벤트 JSON을 Schedule + GoogleSyncedEvent에 저장/갱신.
    """
    event_id = event_payload.get("id")
    
    with transaction.atomic():
        # 1. 기존 GoogleSyncedEvent 조회 (event_id로)
        link = GoogleSyncedEvent.objects.select_for_update().filter(
            user=user, 
            calendar=calendar, 
            event_id=event_id
        ).select_related("schedule").first()
        
        # 2. 기존 일정이 있으면 재사용, 없으면 새로 생성
        if link and link.schedule:
            schedule = link.schedule
        else:
            # 새 Schedule 생성
            schedule = Schedule.objects.create(...)
            # 새 GoogleSyncedEvent 생성 (여기서 저장!)
            link = GoogleSyncedEvent.objects.create(
                user=user,
                calendar=calendar,
                schedule=schedule,
                event_id=event_id,
            )
        
        # 3. Schedule 정보 업데이트
        schedule.title = title
        schedule.description = description
        # ... 기타 필드 업데이트
        schedule.save()
        
        # 4. GoogleSyncedEvent 메타데이터 업데이트
        link.summary = title
        link.status = event_payload.get("status", "confirmed")
        link.etag = event_payload.get("etag")
        link.google_updated = parse_datetime(updated_raw)
        link.raw_payload = event_payload  # 전체 JSON 저장
        link.save()
```

**4. 저장 조건**

- **새 이벤트**: Google Calendar에서 가져온 이벤트가 `t_google_synced_event`에 없을 때
  - `GoogleSyncedEvent.objects.create()` 호출
  - `t_schedule` 테이블에도 새 일정 생성
- **기존 이벤트 업데이트**: 동일한 `event_id`가 이미 존재할 때
  - 기존 `GoogleSyncedEvent` 레코드의 메타데이터만 업데이트
  - 연결된 `Schedule` 레코드도 함께 업데이트

**5. 삭제 처리**

Google Calendar에서 삭제된 이벤트는 `_deactivate_missing_events()` 함수에서 처리:

```python
# service.py:395-424

def _deactivate_missing_events(...):
    """
    더 이상 Google에서 내려오지 않는 이벤트는 RDB에서 비활성화.
    """
    # 동기화된 이벤트 ID 목록과 비교
    qs = GoogleSyncedEvent.objects.filter(...)
    qs = qs.exclude(event_id__in=synced_ids)  # 동기화 목록에 없는 것
    
    for link in qs:
        # Schedule 비활성화
        link.schedule.use_yn = "N"
        link.schedule.save()
        # GoogleSyncedEvent 상태 변경
        link.status = "deleted"
        link.save()
```

**6. 주요 코드 위치**

- **동기화 엔드포인트**: `django_app/apps/schedule/urls.py:27`
- **동기화 함수**: `django_app/apps/schedule/service.py:1254` (`google_events_sync`)
- **이벤트 저장 함수**: `django_app/apps/schedule/service.py:284` (`_upsert_schedule_from_google_payload`)
- **일괄 동기화 함수**: `django_app/apps/schedule/service.py:427` (`_sync_google_events_to_db`)

**7. 사용 예시**

```python
# 프론트엔드에서 동기화 요청
POST /schedule/api/google-events/sync/
Content-Type: application/json

{
  "timeMin": "2024-01-01T00:00:00Z",
  "timeMax": "2024-12-31T23:59:59Z"
}

# 응답
{
  "synced": 150,      # 동기화된 이벤트 수
  "removed": 5,       # 삭제된 이벤트 수
  "status": "ok",     # 상태
  "calendars": 3      # 동기화된 캘린더 수
}
```

**8. 주의사항**

- **트랜잭션 처리**: `transaction.atomic()` 블록 내에서 처리되어 데이터 일관성 보장
- **중복 방지**: `(user_id, calendar_id, event_id)` 유니크 제약으로 중복 저장 방지
- **CASCADE 삭제**: `SyncedCalendar` 삭제 시 연결된 `GoogleSyncedEvent`도 함께 삭제됨
- **재연동 지원**: 연동 해제 후 재연동 시 `event_id`로 기존 일정을 찾아 업데이트 가능

### 테이블 관계도

```
User
  ├─ t_google_credentials (1:1) - OAuth 토큰
  ├─ t_synced_calendar (1:N) - 동기화된 Google 캘린더
  │   └─ t_google_synced_event (1:N) - Google 이벤트 동기화
  │       └─ t_schedule (1:1) - 실제 일정 데이터
  └─ t_user_calendar (1:N) - 사용자 캘린더 그룹
      └─ t_schedule (1:N) - 일정
          ├─ t_schedule_recurrence (1:1) - 반복 규칙
          │   └─ t_schedule_exception (1:N) - 반복 예외
          └─ t_schedule_share (1:N) - 일정 공유
```

### 주요 기능별 테이블

- **일정 관리**: `t_schedule`, `t_user_calendar`
- **반복 일정**: `t_schedule_recurrence`, `t_schedule_exception`
- **공유 기능**: `t_schedule_share`
- **Google 연동**: `t_google_credentials`, `t_synced_calendar`, `t_google_synced_event`

> **참고**: 모든 일정 데이터는 `t_schedule` 테이블에 저장되며, Google Calendar 이벤트도 동기화 후 이 테이블에 저장됩니다.

---

## ⚠️ 주의사항

### 개발 환경

- **CSRF 보호**: 개발 환경에서는 API 경로(`/api/`)의 CSRF 보호가 우회되도록 설정되어 있습니다.
- **Swagger UI**: API 테스트 시 로그인된 상태여야 합니다.

### 프로덕션 환경

- **보안**: 프로덕션 환경에서는 반드시 CSRF 보호를 다시 활성화해야 합니다.
- **DEBUG 모드**: `DEBUG = False`로 설정해야 합니다.
- **SECRET_KEY**: 환경 변수로 관리해야 합니다.

### 패키지 관리

- **npm 패키지 추가**: `django_ui/package.json`에 라이브러리를 추가할 때는 반드시 팀원들에게 공유하세요.
- **Python 패키지**: `requirements.txt`에 추가된 패키지는 모든 개발자가 동일하게 사용해야 합니다.

---

## 🔧 유용한 명령어

### Django

```bash
# 마이그레이션 생성
python django_app/manage.py makemigrations

# 마이그레이션 적용
python django_app/manage.py migrate

# 관리자 계정 생성
python django_app/manage.py createsuperuser

# 개발 서버 실행
python django_app/manage.py runserver

# Django Shell 실행
python django_app/manage.py shell
```

### Vite

```bash
# 개발 모드 (watch 모드)
cd django_ui
npm run dev

# 프로덕션 빌드
npm run build
```

### Docker

```bash
# 컨테이너 시작
docker compose -f infra/docker-compose.yml up -d

# 컨테이너 중지
docker compose -f infra/docker-compose.yml down

# 로그 확인
docker compose -f infra/docker-compose.yml logs -f
```

---

## 📝 추가 정보

- Django 공식 문서: https://docs.djangoproject.com/
- Django REST Framework: https://www.django-rest-framework.org/
- Vite 공식 문서: https://vitejs.dev/

---

## 🤝 기여하기

프로젝트에 기여하기 전에 다음 사항을 확인하세요:

1. 코드 스타일 가이드를 따르세요
2. 변경사항을 커밋하기 전에 테스트하세요
3. 새로운 패키지 추가 시 팀원들에게 공유하세요

