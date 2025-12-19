# SKN18-FINAL-2TEAM

## 폴더 구조
```text
SKN18-FINAL-2TEAM/
├─ README.md
├─ README_DEPLOY.md
├─ docker-compose.yml               # postgreSQL, pgvector (infra/db/init.sql)
├─ docker-compose.prod.yml
├─ requirements.txt
├─ .env.example
│
├─ .github/
│  └─ workflows/
│     ├─ deploy.yml                 # 🔹 GitHub → ECR → EC2 자동배포
│     ├─ test.yml                   # (옵션) Django/LangGraph 테스트 CI
│     ├─ build_sllm.yml             # (옵션) sLLM 도커 이미지 빌드
│     └─ build_simtools.yml         # (옵션) sim_tools 개별 빌드
│
├─ infra/                           # 인프라/배포 관련
│  ├─ docker/
│  │  ├─ Dockerfile.django          # Django + LangGraph 서버
│  │  ├─ Dockerfile.worker          # ETL/Jobs Worker
│  │  ├─ Dockerfile.sim_base        # 시뮬 도커 공통 베이스
│  │  └─ Dockerfile.sllm_server     # vLLM or Ollama 서버
│  ├─ aws/
│  │  ├─ lambda_functions/
│  │  │  ├─ trigger_etl/
│  │  │  ├─ trigger_sim/
│  │  │  └─ daily_report/
│  │  ├─ cloudformation/
│  │  └─ terraform/
│  ├─ nginx/
│  │  └─ nginx.conf
│  ├─ neo4j/                       # Neo4j 설정
│  │  ├─ neo4j.conf
│  │  └─ init.cypher
│  └─ cicd/                        # 🔹 CI/CD 부가 스크립트
│     ├─ ec2_deploy.sh             # EC2에서 실행될 배포 스크립트
│     ├─ prune_old_images.sh       # ECR/로컬 이미지 정리(옵션)
│     ├─ generate_env.py           # 필요 시 환경변수 템플릿 생성
│     └─ README_CICD.md            # IAM, ECR, Secrets 설정 가이드
│
├─ django_app/                      # Django SSR + API
│  ├─ manage.py
│  ├─ config/                       # settings, urls, wsgi, asgi
│  ├─ apps/
│  │  ├─ accounts/                  # 로그인/회원가입
│  │  ├─ core/
│  │  ├─ dashboard/                 # 메인 대시보드
│  │  ├─ chat/                      # LangGraph 기반 챗봇
│  │  ├─ docs/                      # 문서 관리
│  │  ├─ experiments/               # 실험 시뮬레이션(YAML) 저장/관리
│  │  ├─ notifications/             # 이메일/푸시
│  │  └─ api/                       # REST API (선택)
│  ├─ templates/
│  │  ├─ base.html
│  │  ├─ dashboard/
│  │  ├─ chat/
│  │  ├─ docs/
│  │  └─ experiments/
│  ├─ static/
│  └─ tests/
│
├─ graph/                           # LangGraph 오케스트레이션
│  ├─ state.py
│  ├─ nodes/
│  │  ├─ classifier.py              # 질문 분류
│  │  ├─ medical_check.py
│  │  ├─ retrieval.py               # pgvector RAG
│  │  ├─ web_search.py
│  │  ├─ kg_query.py                # Neo4j 쿼리 (KAG)
│  │  ├─ evaluate_chunk.py
│  │  ├─ rewrite_query.py
│  │  ├─ sim_launcher.py            # 시뮬 도커 실행
│  │  ├─ notify_user.py
│  │  └─ generate_answer.py
│  ├─ flows/
│  │  ├─ med_research_rag.py        # RAG 중심 플로우
│  │  ├─ med_research_kag.py        # RAG + Neo4j KAG 하이브리드
│  │  ├─ experiment_copilot.py
│  │  └─ __init__.py
│  └─ entrypoints/
│     ├─ chat_flow.py
│     └─ batch_flow.py
│
├─ rag/                             # RAG + pgvector (문서/논문 기반)
│  ├─ config/
│  │  ├─ db_pgvector.sql
│  │  └─ schema_diagram.md
│  │  
│  ├─ etl/
│  │  ├─ 01_ingest/                         # 1단계: 데이터 "긁어오기"
│  │  │  ├─ 01_ingest_pubmed.py            # PubMed API 호출
│  │  │  ├─ 02_ingest_nih.py               # NIH API 호출
│  │  │  └─ 03_ingest_protocols_io.py      # Protocols.io API 호출
│  │  │
│  │  ├─ 02_normalize/                     # 2단계: 소스별 raw → 공통 포맷
│  │  │  ├─ 01_normalize_pubmed.py         # PubMed raw → internal_doc_format
│  │  │  ├─ 02_normalize_nih.py            # NIH raw → internal_doc_format
│  │  │  └─ 03_normalize_protocols_io.py   # Protocols raw → internal_doc_format
│  │  │
│  │  ├─ 03_extract/                       # 3단계: 엔터티/관계 추출 (KG용, 선택이지만 중요)
│  │  │  ├─ 01_entity_extraction.py        # 텍스트 → Protein / Disease / Drug / Trial 등
│  │  │  └─ 02_relation_extraction.py      # 엔터티 사이 관계 추출 (옵션)
│  │  │
│  │  ├─ 04_chunk/                         # 4단계: 청킹
│  │  │  └─ 01_chunker.py                  # 섹션/토큰 기준 chunk + overlap
│  │  │
│  │  ├─ 05_embed/                         # 5단계: 임베딩
│  │  │  └─ 01_embed_texts.py              # chunk 텍스트 → vector
│  │  │
│  │  ├─ 06_upsert/                        # 6단계: DB 적재
│  │  │  └─ 01_upsert_pgvector.py          # t_document / t_chunk / t_chunk_vec 업서트
│  │  │
│  │  ├─ common/                           # ETL 공통 util 모음
│  │  │  ├─ loaders.py                     # raw/processed 파일 로드/저장
│  │  │  ├─ schema.py                      # internal_doc_format, chunk schema 정의
│  │  │  ├─ text_cleaning.py               # 공통 전처리(HTML 태그 제거, 공백 정리 등)
│  │  │  └─ logging_utils.py               # 로깅 공통
│  │  │
│  │  └─ pipeline_runner.py                # 전체 ETL 실행 entrypoint
│  │
│  ├─ embeddings/
│  │  ├─ embed_texts.py
│  │  ├─ upsert_pgvector.py
│  │  └─ rebuild_index.sh
│  ├─ jobs/
│  │  ├─ cron_daily_ingest.sh
│  │  └─ cron_rebuild_index.sh
│  └─ tests/
│
├─ kg/                              # Neo4j 기반 Knowledge Graph
│  ├─ schema/
│  │  ├─ nodes.md                   # Protein / Disease / Experiment …
│  │  ├─ relationships.md
│  │  └─ constraints.cypher
│  ├─ etl/
│  │  ├─ from_rag_chunks.py         # RAG → KG 연동
│  │  ├─ from_sim_results.py        # AlphaFold3 → KG
│  │  ├─ from_experiments.py        # 실험 → KG
│  │  └─ sync_graph.py
│  │
│  ├─ etl/
│  │  ├─ 01_from_rag_docs/                   # rag/etl 결과를 입력으로 받는 단계
│  │  │  ├─ 01_load_normalized_docs.py      # rag/etl/02_normalize 결과 로딩
│  │  │  └─ 02_build_base_nodes.py          # Paper / Trial / Protocol 노드 생성
│  │  │
│  │  ├─ 02_from_rag_entities/              # rag/etl/03_extract 결과를 Graph로
│  │  │  ├─ 01_load_entities.py             # _entities.json 로딩
│  │  │  └─ 02_upsert_entities_relations.py # Protein, Disease, 관계 upsert
│  │  │
│  │  ├─ 03_from_sim_results/               # 시뮬레이션 결과 → KG 반영
│  │  │  ├─ 01_load_sim_results.py          # sim_tools 결과 로딩
│  │  │  └─ 02_link_protein_experiment.py   # (Protein)-[HAS_SIM_RESULT]->(Experiment)
│  │  │
│  │  ├─ 04_maintenance/                    # 그래프 유지보수/정리
│  │  │  ├─ 01_apply_constraints.py         # constraints.cypher 실행
│  │  │  └─ 02_recompute_graph_metrics.py   # centrality, degree 등 (선택)
│  │  │
│  │  ├─ common/
│  │  │  ├─ neo4j_client.py                 # Bolt 연결, 세션 관리
│  │  │  ├─ cypher_templates.py             # MERGE, MATCH 쿼리 템플릿
│  │  │  └─ mapping.py                      # internal_doc_format → node schema 매핑
│  │  │
│  │  └─ kg_pipeline_runner.py              # KG용 전체 파이프 entrypoint
│  │
│  ├─ queries/
│  │  ├─ path_queries.cypher
│  │  ├─ analytics.cypher
│  │  └─ graph_analytics.py
│  └─ tests/
│
├─ sim_tools/                       # 시뮬레이션 도커 툴
│  ├─ base/
│  │  ├─ Dockerfile
│  │  └─ requirements.txt
│  │
│  ├─ alphafold3/
│  │  ├─ Dockerfile
│  │  ├─ config.yml
│  │  ├─ run.sh
│  │  └─ src/main.py
│  │
│  ├─ protein_mpnn/
│  │  ├─ Dockerfile
│  │  ├─ config.yml
│  │  ├─ run.sh
│  │  └─ src/main.py
│  │
│  ├─ rfdiffusion/
│  │  ├─ Dockerfile
│  │  ├─ config.yml
│  │  ├─ run.sh
│  │  └─ src/main.py
│  │
│  └─ common/
│     ├─ io.py
│     ├─ pdb_utils.py
│     └─ types.py
│
├─ sllm/                            # 도메인 특화 LLM (sLLM)
│  ├─ configs/
│  │  ├─ finetune_bio_med.yaml
│  │  └─ inference.yaml
│  ├─ datasets/                     # SFT 멀티턴 QA / 실험 시나리오
│  │  ├─ train/
│  │  └─ eval/
│  ├─ training/
│  │  ├─ preprocess_to_sft.py
│  │  ├─ run_finetune.py
│  │  └─ experiment.ipynb
│  ├─ inference/
│  │  ├─ client_vllm.py
│  │  ├─ client_ollama.py
│  │  └─ router.py
│  └─ tests/
│
├─ jobs/                             # 백그라운드/배치 작업 (서버 사이드)
│  ├─ manage_etl.py                  # Django context + ETL 호출
│  ├─ check_sim_status.py            # 시뮬레이션 컨테이너 상태 체크 후 RDB 업데이트
│  └─ send_notifications.py          # 이메일/푸시 발송 (Lambda에서 호출 가능)
│
├─ scripts/                          # 개발 편의 스크립트
│  ├─ dev_up.sh                      # docker-compose up + migrate
│  ├─ prune_images.sh
│  └─ migrate.sh
│
├─ data/                             # 원천/가공 데이터, 로컬만 (운영에서는 S3)
│  ├─ raw/
│  └─ processed/
│
└─ assets/                           # ERD, Mermaid, 아키텍처 이미지
   └─ architecture/

```

## requirements

| 파일                                | 용도                  | 로컬 설치 필요 |
| --------------------------------- | ------------------- | -------- |
| requirements.txt                  | 로컬 개발 환경            | 필요       |
| requirements-lambda-nih.txt       | Lambda NIH 배포       | 불필요      |
| requirements-lambda-protocols.txt | Lambda Protocols 배포 | 불필요      |

requirements-lambda*.txt 이 파일들은 Lambda 배포 전용입니다.
1. 사용 위치:
   - CloudFormation BuildCommand에서만 사용
   - sam build 또는 sam deploy 시 자동으로 사용됨
   - 로컬 개발 환경에서는 사용되지 않음
2. 로컬 개발 환경:
   - requirements.txt만 사용
   - Lambda 전용 파일은 설치 불필요

## ETL 분리

### 전략
- **책임 분리 (가장 중요)**
  - 클렌징 등의 버그가 embedding에 영향 없이 수정 가능
- **재처리 비용 최소화**
  - chunk → embedding만 다시 할 수도 있음
- **병렬 처리**
  - 1~3단계는 CPU
  - 5단계는 GPU
- **장기 유지보수 / 확장성**
  - PubMed ingest 추가해도 기존 chunker.py는 그대로 사용
- **CI/CD & Airflow/Lambda와 바로 연동 가능**

### 구분
- **01_ingest/**
  - 각 API에서 긁어오기만 하기
  - PubMed / NIH / Protocols.io 각각 파일
- **02_normalize/**
  - 소스 제각각 포맷 👉 우리 통일 포맷으로 갈아입히기
  - 소스별로 다른 파일이지만, 출력 스키마는 동일
- **03_extract/**
  - KG(Neo4j)용 뇌 수술: 엔터티/관계 뽑기
- **04_chunk ~ 06_upsert**
  - 여기부터는 소스 구분 X, 공통 파이프라인
  - chunk → embed → pgvector upsert
- **common/**
  - ETL 공통 라이브러리 (loader, schema, text_cleaning)
- **pipeline_runner.py**
  - → python pipeline_runner.py --source=pubmed
  - 이런 식으로 전체 파이프 orchestrator

### RAG와 KG
- **kg/etl은 rag의 output을 소비하는 쪽**
  - rag/etl/02_normalize 결과 → 01_from_rag_docs
  - rag/etl/03_extract 결과 → 02_from_rag_entities
- 텍스트 전처리, 엔터티 추출 로직 자체를 kg 안에서 또 돌리지 않고,
- 이미 rag에서 만들어 놓은 파일들을 읽어서 Neo4j에 반영만 한다.

### Neo4J Conf

🔍 주요 설정 설명 (필요한 만큼만 쉽게)
1) dbms.default_database=neo4j
Community Edition은 DB 이름이 neo4j로 고정
KAG/RAG에서 기본적으로 여기에 데이터를 넣음

2) listen_address=0.0.0.0
EC2 환경에서 외부 접속을 위해 필요
  `Browser(7474)`
  `Bolt(7687)`
둘 다 외부에서 접속 가능.

3) 메모리 최적화
현재 EC2 기준:
 `pagecache: 2G`
 `heap: 1G → 2G`
Neo4j는 pagecache가 가장 중요한 요소.

4) 절대 필요한 튜닝
```ini
dbms.security.procedures.unrestricted=apoc.*,gds.*
```

APOC 사용하려면 반드시 필요.

5) 로그 디렉토리 경로

Docker compose에서:
```yml
- neo4j-data:/data
- neo4j-logs:/logs
```
이에 따라:
```ini
server.logs.dir=/logs
```

## 실행

- ENV
> .env.example 복사하여 .env 생성

- Python
```bash
uv venv .venv --python=3.12
source ./.venv/bin/activate
uv pip install -r requirements.txt
```

- Docker
```bash
# Window
docker-compoe up -d
# Mac
docker compoe up -d
```