
## 주의
- 배포 전 계정 변경 & 확인


## 배포
- **ECR 이미지 기준:**
  - web 이미지
    → django_app/, graph/, rag/kg/sllm 중 런타임에 필요한 부분

  - worker 이미지
    → rag/, kg/, jobs/, (필요 시 graph/ 일부)

  - sim_tools 이미지들
    → 각 디렉터리(alphafold3/, protein_mpnn/, rfdiffusion/) + sim_tools/common/

  - sllm_server 이미지
    → sllm/inference/, sllm/configs/ 등

- **GitHub → ECR → EC2 패턴**
  - 폴더별 배포 - X 
  - 각 Dockerfile이 COPY하는 폴더가 배포 범위


## docker-compose.prod

설치·영구 데이터
→ db, neo4j (volume 있음)

앱 레이어
→ web, worker, sllm-server (이미지 교체/업데이트 대상)

프록시 레이어 (옵션)
→ nginx


