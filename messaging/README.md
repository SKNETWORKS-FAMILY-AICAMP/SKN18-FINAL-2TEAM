# Messaging Module

RabbitMQ 기반 메시지 큐 모듈 - 시뮬레이션 및 비동기 작업 처리

## 구조

```
messaging/
├── __init__.py
├── config.py              # RabbitMQ 설정 및 큐/익스체인지 정의
├── connection.py           # 연결 관리 (싱글톤)
├── schemas/               # 메시지 스키마
│   ├── __init__.py
│   └── base.py
├── producers/             # Producer 모듈
│   ├── __init__.py
│   ├── base.py
│   └── simulation_producer.py
├── consumers/             # Consumer 모듈
│   ├── __init__.py
│   ├── base.py
│   └── simulation_consumer.py
└── workers/              # Worker 진입점
    ├── __init__.py
    └── main.py
```

## 사용법

### Django에서 시뮬레이션 작업 발행

```python
from django_app.apps.core.queue import publish_simulation

# 시뮬레이션 작업 큐에 추가
task_id = publish_simulation(
    tool_name="alphafold3",
    experiment_sid=123,
    payload={
        "protein_sequence": "ACDEFGHIKLMNPQRSTVWY",
        "protein_name": "Test Protein",
        "tool_selections": [...],
    },
    user_id=request.user.id
)
```

### Worker 실행

```bash
# 시뮬레이션 Consumer 실행
python -m messaging.workers.main
```

## 큐 구조

### 토픽 익스체인지 기반

- **Exchange**: `tasks.topic` (토픽 타입)
- **라우팅 키 패턴**: `domain.entity.action`
  - `sim.run.alphafold3`
  - `sim.run.protein_mpnn`
  - `sim.run.rfdiffusion`

### 상태 피드백

- **Exchange**: `status.topic`
- **라우팅 키**: `sim.status`

## 확장 가능성

향후 다른 작업 타입 추가 시:

1. `messaging/config.py`에 라우팅 키 추가
2. `messaging/producers/`에 새로운 Producer 추가
3. `messaging/consumers/`에 새로운 Consumer 추가
4. `django_app/apps/core/queue.py`에 발행 함수 추가

예시:
- `rag.etl.pubmed` - RAG ETL 작업
- `kg.sync.entities` - KG 동기화 작업
- `notify.email` - 이메일 발송 작업

## 배포

### docker-compose.prod.yml

- RabbitMQ 서비스 추가 (인프라 레이어)
- Web 서비스에 RabbitMQ 의존성 추가
- Worker 서비스에 Consumer 실행 명령 추가

### Dockerfile

- `Dockerfile.django`: Producer 모듈 포함
- `Dockerfile.worker`: Consumer 모듈 포함

