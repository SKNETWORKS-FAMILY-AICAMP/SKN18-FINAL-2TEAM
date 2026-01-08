
## 주의
- 배포 전 계정 변경 & 확인


## 배포
- **ECR 이미지 기준:**
  - web 이미지
    → django_app/, graph/, rag/kg/sllm 중 런타임에 필요한 부분
    → messaging/ (Producer 모듈 포함)

  - worker 이미지
    → rag/, kg/, jobs/, (필요 시 graph/ 일부)
    → messaging/ (Consumer 모듈 포함)
    → sim_tools/common/ (시뮬레이션 공통 유틸)

  - sim_tools 이미지들
    → 각 디렉터리(alphafold3/, protein_mpnn/, rfdiffusion/) + sim_tools/common/

  - sllm_server 이미지
    → sllm/inference/, sllm/configs/ 등

- **GitHub → ECR → EC2 패턴**
  - 폴더별 배포 - X 
  - 각 Dockerfile이 COPY하는 폴더가 배포 범위

- **메시지 큐 (RabbitMQ) 배포:**
  - RabbitMQ는 인프라 레이어로 분류 (db, neo4j와 동일)
  - 공식 이미지 직접 사용 (ECR 불필요): `rabbitmq:3.13-management-alpine`
  - Volume으로 데이터 영속성 보장
  - Producer는 web 이미지에 포함
  - Consumer는 worker 이미지에 포함


## docker-compose.prod

설치·영구 데이터 (인프라 레이어)
→ db, neo4j, rabbitmq (volume 있음, 공식 이미지 사용)

앱 레이어 (ECR 이미지)
→ web (Producer 포함), worker (Consumer 포함), sllm-server (이미지 교체/업데이트 대상)

프록시 레이어 (옵션)
→ nginx


## 메세지 큐 (RabbitMQ) 구조
```text
┌─────────────────────────────────────────┐
│  RabbitMQ EC2 (Broker)                  │
│  └─ RabbitMQ Server                     │
│     └─ 큐: sim.run.alphafold3 등       │
└─────────────────────────────────────────┘
              ▲                    ▼
              │                    │
     [발행]   │                    │   [소비]
              │                    │
┌─────────────┴────────────────────┴─────────────┐
│  App EC2                                        │
│  ├─ web (Producer)                             │
│  │  └─ Django → publish_simulation()           │
│  │     └─ messaging/producers/                 │
│  │                                             │
│  └─ worker (Consumer)                          │
│     └─ messaging/workers/main.py               │
│        └─ messaging/consumers/                 │
└─────────────────────────────────────────────────┘
```

### 요약

|용어|역할|위치|코드 위치|
|---|---|---|---|
|Broker|메시지 중개 서버|RabbitMQ EC2|RabbitMQ 서버|
|Producer|메시지 발행|App EC2 (web)|django_app/apps/core/queue.py|
|Consumer/Worker|메시지 소비 및 처리|App EC2 (worker)|messaging/workers/main.py|

- 결론: 브로커는 서버, Producer는 클라이언트입니다. Worker는 Consumer가 맞습니다.


## 메시지 큐 (RabbitMQ) 배포

### 서비스 구성

- **RabbitMQ 서비스**
  - 이미지: `rabbitmq:3.13-management-alpine`
  - 포트: `5672` (AMQP), `15672` (Management UI)
  - Volume: `rabbitmq-data`, `rabbitmq-logs`
  - 헬스체크: `rabbitmq-diagnostics ping`

- **의존성**
  - `web` 서비스: RabbitMQ 의존 (Producer 사용)
  - `worker` 서비스: RabbitMQ 의존 (Consumer 사용)

### 환경 변수 설정

`.env` 파일에 다음 변수 추가:

```bash
# RabbitMQ 연결 정보
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest  # 운영 환경에서는 강력한 비밀번호 사용
RABBITMQ_PASSWORD=guest  # 운영 환경에서는 강력한 비밀번호 사용
RABBITMQ_VHOST=/
```

### 배포 전 체크리스트

- [ ] `.env`에 RabbitMQ 연결 정보 설정
- [ ] RabbitMQ volume 경로 확인 (`/var/lib/rabbitmq`)
- [ ] Management UI 접근 제한 (방화벽/보안 그룹)
- [ ] 운영 환경에서는 기본 계정(`guest`) 변경

### 배포 후 확인

1. **RabbitMQ 헬스체크**
   ```bash
   docker exec rabbitmq-final rabbitmq-diagnostics ping
   ```

2. **Management UI 접속**
   - URL: `http://EC2_IP:15672`
   - 기본 계정: `guest` / `guest` (운영 환경에서는 변경 권장)
   - 확인 항목:
     - 큐 상태 (메시지 수, 처리 속도)
     - 연결 상태 (web, worker)
     - 메모리/디스크 사용량

3. **큐 생성 확인**
   - Consumer 실행 시 자동 생성
   - 큐 목록: `sim.run.alphafold3`, `sim.run.protein_mpnn`, `sim.run.rfdiffusion`, `sim.status`

4. **로그 확인**
   ```bash
   # RabbitMQ 로그
   docker logs rabbitmq-final
   
   # Worker 로그 (Consumer)
   docker logs etl-worker
   
   # Web 로그 (Producer)
   docker logs web-app
   ```

### 보안 고려사항

#### 운영 환경 권장 설정

```yaml
# docker-compose.prod.yml
rabbitmq:
  environment:
    RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}  # 강력한 비밀번호 사용
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
```

#### AWS 보안 그룹

- `5672` (AMQP): 내부 네트워크만 허용
- `15672` (Management UI): 특정 IP만 허용 또는 VPN 통해서만 접근

### 모니터링

- **RabbitMQ Management UI**: 큐 상태, 메시지 처리 속도, Consumer 상태
- **로그**: Django 로그 (Producer), Worker 로그 (Consumer), RabbitMQ 로그
- **메트릭**: 큐 길이, 메시지 처리 속도, 메모리 사용량

### 확장성

- **Worker 인스턴스 추가**: 처리량 증가를 위해 worker 컨테이너 추가 가능
- **큐 분리**: 도구별로 큐를 분리하여 독립적 스케일링 가능
- **우선순위 큐**: 중요 작업에 높은 우선순위 부여 가능

### 트러블슈팅

1. **연결 실패**
   - RabbitMQ 서비스가 실행 중인지 확인
   - 환경 변수 (`RABBITMQ_HOST`, `RABBITMQ_PORT`) 확인
   - 네트워크 연결 확인

2. **메시지 누적**
   - Consumer가 정상 실행 중인지 확인
   - Worker 로그 확인
   - 큐 길이 모니터링

3. **메시지 손실**
   - DLX (Dead Letter Exchange) 확인
   - 메시지 영속화 설정 확인
   - 재시도 로직 확인




