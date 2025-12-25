## 📌 sim_tools에 들어갈 툴 종류 — 역할 중심 요약
### 1) AlphaFold 3
- 목적: 단백질 구조 예측 (structure prediction)
- 입력: FASTA 시퀀스 / MSA / templates
- 출력: PDB 구조, confidence, metrics
- 특성:
  - GPU 필요 (A100, H100급 권장)
  - 대형 모델 + 복잡한 파이프라인
  - 실행 시간 길고, 리소스 많이 먹음
- 플랫폼에서는:
  - “입력 시퀀스 → 구조 예측 → PDB 저장 → 시각화 링크 제공”
  - YAML로 하이퍼파라미터 지정 가능

### 1) ProteinMPNN
- 목적: 단백질 서열 생성(디자인)
- 입력: 구조(PDB) 또는 좌표 / 마스크 정보
- 출력: 디자인된 새로운 아미노산 서열
- 특성:
  - GPU 있어도 좋지만 CPU-only 실행도 가능 (빠름)
  - 알파폴드3 결과를 이어받아 “구조 → 시퀀스” 디자인 가능
- 플랫폼에서는:
  - AlphaFold 출력물을 가져와 “역설계(back-design)” 기능 제공

### 1) RFdiffusion
- 목적: 단백질 디자인 (diffusion 기반; de novo 디자인)
- 입력: 조건(constraints), hot-spot residue, motif 등
- 출력: 새 단백질 구조(PDB)
  - 연산량 중간~높음
- 특징:
  - 확률적 생성 모델
  - "모티프 기반 디자인"과 "de novo fold generation" 시나리오 가능

## 📦 sim_tools 폴더 구조 (추천 버전)
```text
sim_tools/
├─ base/                           # 공통 base image (python deps)
│  ├─ Dockerfile
│  └─ requirements.txt
│
├─ alphafold3/
│  ├─ Dockerfile
│  ├─ config.yml                   # 입력schema
│  ├─ run.sh                       # 실행 스크립트 (docker 내부)
│  ├─ src/
│  │  ├─ main.py                   # YAML → AlphaFold3 pipeline 실행
│  │  ├─ utils.py
│  │  └─ parsers.py
│  └─ tests/
│     └─ sample_input.yml
│
├─ protein_mpnn/
│  ├─ Dockerfile
│  ├─ config.yml
│  ├─ run.sh
│  ├─ src/
│  │  ├─ main.py
│  │  ├─ model_utils.py
│  │  └─ structure_loader.py
│  └─ tests/
│
├─ rfdiffusion/
│  ├─ Dockerfile
│  ├─ config.yml
│  ├─ run.sh
│  ├─ src/
│  │  ├─ main.py
│  │  ├─ diffusion_runner.py
│  │  └─ sampling_utils.py
│  └─ tests/
│
└─ common/
   ├─ io.py                         # 공용 파일 로딩, 경로 관리
   ├─ pdb_utils.py                  # 공용 구조 처리
   └─ types.py                      # 공용 데이터 클래스
```

## 🧬 각 툴별 config.yml 예시

### 1) AlphaFold3 config.yml
```yaml
model: "alphafold3"
input:
  sequence: "ACDEFGHIKLMNPQRSTVWY"
  msa: false
  templates: false
options:
  model_preset: "monomer"
  num_recycles: 3
  random_seed: 42
output:
  save_dir: "/output"
  save_pdb: true
  save_plddt: true
```

### 2) ProteinMPNN config.yml
```yaml
model: "proteinmpnn"
input:
  pdb_path: "/input/structure.pdb"
  chain_id: "A"
  design_only: true
options:
  num_sequences: 5
  temperature: 0.1
output:
  save_dir: "/output"
  save_fasta: true
```

### 3) RFdiffusion config.yml
```yaml
model: "rfdiffusion"
task: "motif_scaffolding"
input:
  fixed_motif: "/input/motif.pdb"
  hotspot_residues: [42, 43, 44]
options:
  inference_steps: 30
  num_samples: 10
  seed: 112358
output:
  save_dir: "/output"
  save_all_trajectories: false
```

## 🔥 실행 방식 (LangGraph → sim_tools 도커)
- LangGraph의 sim_launcher.py 노드에서 하는 동작은 동일:
```python
def launch_simulation(yaml_config_path: str, tool_name: str):
    docker_image = f"bio-med/{tool_name}:latest"
    cmd = [
        "docker", "run", "--gpus", "all",
        "-v", f"{yaml_config_path}:/app/config.yml",
        docker_image
    ]
    subprocess.run(cmd)
```
툴이 바뀌어도 동일하게 실행되니까 유지보수가 편해.

## 💡 왜 이렇게 구조화해야 하냐?
**✔ 1. 각 툴은 독립 환경이 필요**
- AlphaFold3는 CUDA + ColabFold + 대용량 deps 필요
- RFdiffusion은 PyTorch + 트랜스포머 + diffusion 추가 deps
- ProteinMPNN은 훨씬 가벼움
섞어 쓰면 Dockerfile이 지옥이 됨 → 독립 컨테이너가 답.

**✔ 2. 병렬 실행 / 스케일링 가능**
- EC2 하나에서 여러 컨테이너 동시에 실행
- 필요하면 AWS Batch / ECS GPU 노드로 분산

**✔ 3. YAML 기반 입력으로 자동화 가능**
- 웹 → LangGraph → YAML → 컨테이너
- 완전한 “Agentic Wet Lab Simulator” 패턴 구축 가능

## 🌟 정리
| Tool            | 목적          | 리소스        | 독립 컨테이너 권장 이유     |
| --------------- | ----------- | ---------- | ----------------- |
| **AlphaFold3**  | 구조 예측       | GPU 고필요    | 대형 모델 deps        |
| **ProteinMPNN** | 서열 디자인      | CPU/GPU 옵션 | 구조→서열 pipeline 연결 |
| **RFdiffusion** | de novo 디자인 | GPU 중간필요   | 확률 모델 + 별도 러너     |


sim_tools 안에 넣기 가장 적합하고,
각각을 1 컨테이너 = 1 기능으로 만드는 게 정답.

