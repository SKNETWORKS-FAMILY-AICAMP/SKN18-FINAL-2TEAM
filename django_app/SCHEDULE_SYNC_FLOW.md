## 일정 편집 동기화 전략 가이드

### 1. 배경
- 현재 HelixOps 스케줄 화면에서는 `/schedule/api/schedules/:id/` API를 통해 로컬 DB(`t_schedule`)만 수정합니다.
- Google Calendar와의 동기화를 담당하는 엔드포인트(`google_event_update`, `google_event_delete` 등)는 존재하지만, 화면 편집 플로우와 연결되어 있지 않습니다.
- 사용자 경험을 고려하면 “화면에서 편집 → 즉시 Google과 동기화”가 먼저 필요하고, 이후에는 오프라인 편집·큐 처리를 도입할 수 있습니다.

본 문서는 **플로우 2 (즉시 동기화)**를 우선 도입하면서, 향후 **플로우 3 (비동기/큐 기반)**로 확장할 때 고려해야 할 사항을 정리합니다.

---

### 2. 플로우 2: 로컬 수정 즉시 Google 반영
#### 2.1 처리 순서
1. 화면에서 일정 수정 → 기존대로 `/schedule/api/schedules/:id/` PATCH 요청.
2. 서버(`schedule_detail` 뷰)에서 요청을 수신하면,
   - 대상 일정에 `google_sync`(= `GoogleSyncedEvent`)가 연결되어 있는지 확인.
   - 있으면 Google Calendar API를 먼저 호출하여 event를 PATCH.
   - Google API가 성공하면 로컬 DB(`Schedule`, `ScheduleRecurrence`, 공유 복사본 등)를 업데이트.
   - Google API가 실패하면 DB 업데이트를 수행하지 않고 오류를 사용자에게 반환.
3. 응답 성공 시: 프런트는 기존 로직을 그대로 유지하고, 로컬 목록/캘린더를 리프레시.

#### 2.2 상세 구현 포인트
- **API 구조**
  - `schedule_detail` PATCH 내에서 `_update_google_event(schedule, payload)` 헬퍼 호출.
  - 헬퍼는 `schedule.google_sync`에 저장된 `calendar`와 `event_id`를 이용해 `service.google_event_update`와 동일한 로직을 재사용 또는 직접 호출.
  - Google API 호출이 성공하면 DB 트랜잭션을 커밋, 실패 시 `JsonResponse({'error': 'google_sync_failed', ...}, status=400)` 반환.
- **데이터 매핑**
  - Google 측의 all_day, recurrence, reminders 등은 이미 `_build_event_datetime_payload`, `_build_rrule_from_payload`로 처리하므로 재활용.
  - 로컬에서 사용하는 status/type/notification → Google 이벤트 속성 변환 규칙을 명시적으로 관리.
- **에러 처리**
  - 네트워크/권한 오류 시: 사용자에게 “Google 동기화 실패. Google 계정을 다시 연동하거나 잠시 후 시도해 주세요.” 메시지.
  - Google 인증 만료 시: `google_login` 리다이렉트 링크를 응답에 포함해 재연동 유도.
- **롤백 전략**
  - Google API 성공 시에만 DB 저장. 즉, `google_event_update` 성공 → DB 저장 (트랜잭션 내).
  - Google API 실패 시에는 로컬 변경이 반영되지 않으므로 사용자 데이터 일관성을 유지.
- **테스트**
  - 단위 테스트: `schedule_detail` PATCH 호출 시 Google API 모킹 → 성공/실패 케이스 검증.
  - 통합 테스트: 실제 Google 계정 샌드박스에서 한 일정 수정 → 실시간 반영 여부 확인.

#### 2.3 README/문서에 포함할 내용
- 기능 개요, 시퀀스 다이어그램, API 요청/응답 예시.
- 개발자가 로컬에서 Google API 테스트할 때 필요한 환경 변수(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 등).
- 실패 시 사용자 메시지를 통일하기 위한 문구 표준.

---

### 3. 플로우 3: 로컬 우선(비동기) 동기화로 전환할 때
향후 큐/워커 기반으로 전환할 경우를 대비해 아래 사항을 미리 고려합니다.

#### 3.1 개념
1. 화면에서 편집 시 즉시 로컬 DB 반영 → 응답 빠르게 반환.
2. 일정이 “동기화 대기” 상태(`sync_status = pending`)로 표시됨.
3. 백그라운드 워커(예: Celery, SQS worker)가 Google API에 PATCH/POST/DELETE 요청.
4. 성공 시 `sync_status = synced`. 실패 시 재시도 카운트 증가, 일정 카드에 “동기화 실패” 배지 노출.

#### 3.2 미리 설계해 둘 것
- **모델 필드**: `Schedule.sync_status`, `Schedule.sync_retry_count`, `Schedule.sync_error_message` 등.
- **워커 큐 메시지 스키마**: `{ "schedule_id": 123, "action": "update", "payload": {...} }`.
- **재시도 전략**: 지수 백오프, 최대 시도 횟수 후 관리자 알림.
- **충돌 해결 UI**: Google 측에서 별도로 수정된 일정과 충돌 시 diff/merge UI 제공.
- **모니터링**: 동기화 대기 건수, 실패율, 마지막 성공 시간 등을 Grafana/Slack으로 알림.

#### 3.3 전환 시 마이그레이션 플랜
1. 플로우 2 로직에 “즉시 동기화” 옵션 플래그 추가 (예: `settings.SCHEDULE_SYNC_MODE = 'realtime' | 'async'`).
2. 큐/워커 도입 후 플래그를 `async`로 전환.
3. README에 “비동기 모드” 활성화 방법, 워커 실행 커맨드, 장애 대응 방법을 문서화.
4. 실시간 모드와 비동기 모드를 동시에 운영할 수 있도록 코드 분기 유지(AB 테스트 가능).

---

### 4. README 구성 가이드
이 문서를 기반으로 프로젝트 README(예: `docs/schedule_sync_flow.md`)에 다음 내용을 포함하십시오.
1. **개요**: 플로우 2/3 정의, 도입 이유.
2. **현재 모드(플로우 2)**: 시퀀스, API, 필요한 환경설정, 테스트 방법.
3. **문제 해결**: Google API 실패 시 시나리오, 사용자 알림 메시지.
4. **향후 모드(플로우 3)**: 아키텍처, 모델 변경, 큐 설계, UI 요구사항.
5. **모드 전환 방법**: 설정 플래그, 배포 체크리스트.

위와 같이 README를 정비해 두면, 지금은 플로우 2를 안정적으로 구현하면서도 추후 플로우 3로 확장하는 데 필요한 정보와 기준을 팀 전체가 공유할 수 있습니다.
