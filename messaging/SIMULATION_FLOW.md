# 시뮬레이션 파이프라인 전체 플로우

## 📋 개요

사용자가 Django UI에서 시뮬레이션 파이프라인을 구성하고 실행하는 전체 프로세스입니다.
상태 업데이트부터 결과 저장까지의 모든 단계를 설명합니다.

## 🔄 전체 플로우 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. 사용자 UI (Django Frontend)                                  │
│    - 파이프라인 구성 (도구 선택, 파라미터 설정)                  │
│    - 시뮬레이션 실행 요청                                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Django View (django_app/apps/experiments/views.py)          │
│    - 실험 생성 (t_experiment 테이블)                            │
│    - 상태: 'E' (준비), progress: 0                              │
│    - 메시지 큐에 작업 발행                                       │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. RabbitMQ (tasks.topic Exchange)                              │
│    - 라우팅 키: sim.run.{tool_name}                             │
│    - 큐: sim.run.alphafold3 / sim.run.protein_mpnn / ...       │
│    - 메시지 영속화 (durable)                                    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Worker Consumer (messaging/consumers/simulation_consumer.py) │
│    - 메시지 소비                                                │
│    - 시뮬레이션 실행                                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│ 5-1. 상태 업데이트│          │ 5-2. 상태 피드백 │
│ (PostgreSQL)     │          │ (RabbitMQ)       │
│ - t_experiment   │          │ - status.topic   │
│ - status, progress│          │ - sim.status     │
└──────────────────┘          └──────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. 시뮬레이션 실행 (Docker Container)                          │
│    - Docker 컨테이너 실행                                        │
│    - 결과 파일 생성                                              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. 결과 저장 (PostgreSQL)                                       │
│    - t_experiment_result 테이블                                  │
│    - 파일 경로, 메타데이터 저장                                  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. 최종 상태 업데이트                                           │
│    - 상태: 'C' (완료), progress: 100                             │
│    - 상태 피드백 발행                                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. 사용자 UI 업데이트                                           │
│    - 실시간 상태 조회 (Polling 또는 WebSocket)                   │
│    - 결과 파일 다운로드                                          │
└─────────────────────────────────────────────────────────────────┘
```

## 📝 단계별 상세 설명

### 1단계: 사용자 UI에서 파이프라인 구성

**위치**: `django_app/templates/experiments/experiment.html`

```javascript
// 사용자가 시뮬레이션 파이프라인 구성
const pipeline = {
    tools: [
        { name: "alphafold3", order: 1, options: {...} },
        { name: "protein_mpnn", order: 2, options: {...} }
    ],
    protein_sequence: "ACDEFGHIKLMNPQRSTVWY",
    protein_name: "Test Protein"
};

// 시뮬레이션 실행 요청
fetch('/api/experiments/run/', {
    method: 'POST',
    body: JSON.stringify(pipeline)
});
```

**사용자 입력**:
- 단백질 시퀀스
- 단백질 이름
- 사용할 도구 선택 (AlphaFold3, ProteinMPNN, RFdiffusion)
- 각 도구별 파라미터 설정

---

### 2단계: Django View에서 실험 생성 및 메시지 발행

**위치**: `django_app/apps/experiments/views.py`

```python
@login_required
@require_http_methods(["POST"])
def run_simulation(request):
    """시뮬레이션 실행 요청"""
    
    # 2-1. 실험 레코드 생성 (t_experiment 테이블)
    experiment = Experiment.objects.create(
        pipeline_name=request.POST.get("tool_name"),
        status='E',  # 준비 상태
        progress=0,
        protein_sequence=request.POST.get("protein_sequence"),
        protein_name=request.POST.get("protein_name"),
        created_id=str(request.user.id),
        updated_id=str(request.user.id)
    )
    
    # 2-2. 도구 선택 저장 (t_experiment_tool_selection 테이블)
    for tool in request.POST.get("tools", []):
        ExperimentToolSelection.objects.create(
            experiment_sid=experiment.experiment_sid,
            tool_sid=tool["tool_sid"],
            sort_order=tool["order"],
            tool_options_json=json.dumps(tool["options"]),
            created_id=str(request.user.id),
            updated_id=str(request.user.id)
        )
    
    # 2-3. 메시지 큐에 작업 발행
    from django_app.apps.core.queue import publish_simulation
    
    task_id = publish_simulation(
        tool_name=request.POST.get("tool_name"),
        experiment_sid=experiment.experiment_sid,
        payload={
            "protein_sequence": experiment.protein_sequence,
            "protein_name": experiment.protein_name,
            "tool_selections": get_tool_selections(experiment.experiment_sid),
        },
        user_id=request.user.id
    )
    
    # 2-4. 상태를 'R' (진행중)로 업데이트
    from django_app.apps.experiments.utils import update_experiment_status
    update_experiment_status(experiment.experiment_sid, 'R', 0)
    
    # 2-5. 즉시 응답 (작업은 백그라운드에서 처리)
    return JsonResponse({
        "status": "queued",
        "experiment_sid": experiment.experiment_sid,
        "task_id": task_id,
        "message": "Simulation task has been queued"
    })
```

**데이터베이스 상태**:
```sql
-- t_experiment 테이블
experiment_sid: 123
pipeline_name: "alphafold3"
status: 'R'  -- 진행중으로 변경
progress: 0
protein_sequence: "ACDEFGHIKLMNPQRSTVWY"
protein_name: "Test Protein"
created_at: 2025-01-20 10:00:00
```

**메시지 큐 메시지**:
```json
{
    "task_id": "uuid-1234-5678",
    "requested_by": 1,
    "resource_uri": "/api/experiments/123/",
    "timestamp": "2025-01-20T10:00:00Z",
    "payload": {
        "experiment_sid": 123,
        "tool_name": "alphafold3",
        "protein_sequence": "ACDEFGHIKLMNPQRSTVWY",
        "protein_name": "Test Protein",
        "tool_selections": [...]
    }
}
```

---

### 3단계: RabbitMQ 메시지 큐잉

**위치**: `messaging/producers/simulation_producer.py`

```python
# 토픽 익스체인지로 메시지 발행
Exchange: tasks.topic (topic type)
Routing Key: sim.run.alphafold3
Queue: sim.run.alphafold3
```

**특징**:
- 메시지 영속화 (durable)
- DLX 설정 (실패 시 Dead Letter Queue로 이동)
- 우선순위 설정 (priority: 5)

---

### 4단계: Worker Consumer가 메시지 소비

**위치**: `messaging/consumers/simulation_consumer.py`

```python
def handle_simulation_task(message: Dict[str, Any]):
    task_id = message.get("task_id")
    payload = message.get("payload", {})
    experiment_sid = payload.get("experiment_sid")
    tool_name = payload.get("tool_name")
    
    # 4-1. 시작: 상태 업데이트 + 피드백 발행
    update_experiment_status(experiment_sid, 'R', 0)
    publish_status(task_id, experiment_sid, 'R', 0)
    
    # 4-2. 시뮬레이션 실행 준비
    # - YAML 설정 파일 생성
    # - 출력 디렉토리 생성
    
    # 4-3. 진행률 업데이트: 25%
    update_experiment_status(experiment_sid, 'R', 25)
    publish_status(task_id, experiment_sid, 'R', 25)
    
    # 4-4. 시뮬레이션 실행 (Docker)
    result = launch_simulation_docker(tool_name, config_path, output_dir)
    
    # 4-5. 결과 처리
    if result["success"]:
        # 완료 처리
        update_experiment_status(experiment_sid, 'C', 100)
        publish_status(task_id, experiment_sid, 'C', 100, result)
    else:
        # 실패 처리
        update_experiment_status(experiment_sid, 'F', 0, error_msg)
        publish_status(task_id, experiment_sid, 'F', 0, {"error": error_msg})
```

---

### 5단계: 상태 업데이트 (병렬 처리)

#### 5-1. PostgreSQL 상태 업데이트

**위치**: `django_app/apps/experiments/utils.py`

```python
def update_experiment_status(experiment_sid, status, progress, error_message=None):
    with transaction.atomic():
        # SELECT FOR UPDATE로 동시성 제어
        experiment = Experiment.objects.select_for_update().get(
            experiment_sid=experiment_sid
        )
        
        # 상태 전이 검증
        valid_transitions = {
            'E': ['R', 'F'],  # 준비 → 진행중/실패
            'R': ['C', 'F'],  # 진행중 → 완료/실패
            'C': [],  # 완료는 최종 상태
            'F': [],  # 실패는 최종 상태
        }
        
        # 업데이트
        experiment.status = status
        experiment.progress = progress
        experiment.updated_at = timezone.now()
        experiment.save()
```

**상태 전이**:
```
E (준비) → R (진행중) → C (완료)
         ↘ F (실패)
```

#### 5-2. 상태 피드백 발행 (RabbitMQ)

**위치**: `messaging/consumers/simulation_consumer.py`

```python
def publish_status(task_id, experiment_sid, status, progress, data=None):
    status_producer = TopicProducer(exchange="status.topic")
    status_message = StatusMessage(
        task_id=task_id,
        experiment_sid=experiment_sid,
        status=status,
        progress=progress,
        data=data or {}
    )
    status_producer.publish("sim.status", status_message.to_dict())
```

**상태 피드백 메시지**:
```json
{
    "task_id": "uuid-1234-5678",
    "experiment_sid": 123,
    "status": "R",
    "progress": 25,
    "data": {},
    "timestamp": "2025-01-20T10:00:30Z"
}
```

---

### 6단계: 시뮬레이션 실행 (Docker)

**위치**: `messaging/consumers/simulation_consumer.py`

```python
def launch_simulation_docker(tool_name, config_path, output_dir):
    docker_image = f"bio-med/{tool_name}:latest"
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{config_path}:/app/config.yml:ro",
        "-v", f"{output_dir}:/output",
        docker_image
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    return result
```

**실행 과정**:
1. Docker 컨테이너 실행
2. 설정 파일 마운트 (`/app/config.yml`)
3. 출력 디렉토리 마운트 (`/output`)
4. 시뮬레이션 실행 (예: AlphaFold3 구조 예측)
5. 결과 파일 생성 (PDB, FASTA 등)

**결과 파일**:
```
/data/sim_results/123/
├── model_1.pdb
├── model_2.pdb
├── confidence_scores.json
└── log.txt
```

---

### 7단계: 결과 저장

**위치**: `messaging/consumers/simulation_consumer.py` (TODO 구현 필요)

```python
# 결과 파일을 t_experiment_result 테이블에 저장
def save_experiment_results(experiment_sid, output_dir):
    import os
    from django_app.apps.experiments.models import ExperimentResult
    
    for file_name in os.listdir(output_dir):
        file_path = os.path.join(output_dir, file_name)
        file_size = os.path.getsize(file_path)
        
        # 파일 타입 결정
        if file_name.endswith('.pdb'):
            result_type = 'P'
        elif file_name.endswith('.fasta'):
            result_type = 'F'
        else:
            result_type = 'T'
        
        ExperimentResult.objects.create(
            experiment_sid=experiment_sid,
            result_name=file_name,
            result_type=result_type,
            file_size=file_size,
            file_path=file_path
        )
```

**데이터베이스 상태**:
```sql
-- t_experiment_result 테이블
result_sid: 1
experiment_sid: 123
result_name: "model_1.pdb"
result_type: 'P'  -- PDB 파일
file_size: 123456
file_path: "/data/sim_results/123/model_1.pdb"
created_at: 2025-01-20 10:05:00
```

---

### 8단계: 최종 상태 업데이트

**위치**: `messaging/consumers/simulation_consumer.py`

```python
# 완료 처리
update_experiment_status(experiment_sid, 'C', 100)
publish_status(
    task_id,
    experiment_sid,
    'C',
    100,
    {
        "output_dir": output_dir,
        "result": result,
        "result_files": result_files
    }
)
```

**최종 데이터베이스 상태**:
```sql
-- t_experiment 테이블
experiment_sid: 123
status: 'C'  -- 완료
progress: 100
updated_at: 2025-01-20 10:05:00
```

---

### 9단계: 사용자 UI 업데이트

**위치**: `django_app/static/js/pages/experiment.js`

```javascript
// 실시간 상태 조회 (Polling)
function pollExperimentStatus(experimentId) {
    setInterval(async () => {
        const response = await fetch(`/api/experiments/${experimentId}/status/`);
        const data = await response.json();
        
        // UI 업데이트
        updateProgressBar(data.progress);
        updateStatusBadge(data.status);
        
        // 완료 시 결과 표시
        if (data.status === 'C') {
            loadExperimentResults(experimentId);
            clearInterval(pollInterval);
        }
    }, 2000);  // 2초마다 조회
}

// 결과 파일 다운로드
function downloadResultFile(resultId) {
    window.location.href = `/api/experiments/results/${resultId}/download/`;
}
```

---

## 📊 상태 전이 다이어그램

```
┌─────────┐
│   E     │  준비 (Ready)
│ (Ready) │
└────┬────┘
     │
     │ 사용자 실행 요청
     ▼
┌─────────┐
│   R     │  진행중 (Running)
│(Running)│
└────┬────┘
     │
     ├─────────────────┐
     │                 │
     │ 성공            │ 실패
     ▼                 ▼
┌─────────┐        ┌─────────┐
│   C     │        │   F     │
│(Complete)│        │ (Failed)│
└─────────┘        └─────────┘
```

## 🔍 주요 데이터 흐름

### 1. 실험 생성 시
```
Django View → t_experiment (status='E', progress=0)
           → t_experiment_tool_selection
           → RabbitMQ (sim.run.{tool_name})
```

### 2. 시뮬레이션 실행 중
```
Worker Consumer → t_experiment (status='R', progress=0→25→50→75)
               → RabbitMQ (sim.status)
               → Docker Container 실행
```

### 3. 결과 저장 시
```
Worker Consumer → t_experiment_result (결과 파일 메타데이터)
               → t_experiment (status='C', progress=100)
               → RabbitMQ (sim.status, 완료 알림)
```

## 🛡️ 에러 처리

### 실패 시나리오

1. **시뮬레이션 실행 실패**
   ```python
   update_experiment_status(experiment_sid, 'F', 0, error_msg)
   publish_status(task_id, experiment_sid, 'F', 0, {"error": error_msg})
   ```

2. **타임아웃**
   ```python
   except subprocess.TimeoutExpired:
       update_experiment_status(experiment_sid, 'F', 0, "Simulation timeout")
   ```

3. **메시지 처리 실패**
   - DLX (Dead Letter Exchange)로 이동
   - 재시도 또는 수동 처리

## 📈 모니터링 포인트

1. **RabbitMQ Management UI** (`http://localhost:15672`)
   - 큐 길이 확인
   - 메시지 처리 속도
   - Consumer 상태

2. **데이터베이스 쿼리**
   ```sql
   -- 진행 중인 실험 조회
   SELECT * FROM t_experiment WHERE status = 'R';
   
   -- 실패한 실험 조회
   SELECT * FROM t_experiment WHERE status = 'F';
   ```

3. **로그 확인**
   - Django 로그: 실험 생성, 메시지 발행
   - Worker 로그: 시뮬레이션 실행, 상태 업데이트
   - Docker 로그: 시뮬레이션 컨테이너 실행

## 🚀 성능 최적화

1. **비동기 처리**: Django는 즉시 응답, Worker가 백그라운드 처리
2. **상태 피드백**: 실시간 상태 업데이트로 사용자 경험 향상
3. **멱등성 보장**: 상태 전이 검증으로 중복 실행 방지
4. **확장성**: Worker 인스턴스 추가로 처리량 증가 가능

