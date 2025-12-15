# SKN18-FINAL-2TEAM

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

.env.example 파일명을 .env 로 변경

- **터미널 1: npm 라이브러리 빌드**
```bash
# 터미널 1: npm 라이브러리 빌드
cd django_ui

# 노트 버전 확인 (node 22+)
node --version

# 설치 한번
npm install
npm run build
```

- **터미널 2: Django 서버 실행**
```bash
# 루트 폴더에서 실행
python django_app/manage.py makemigrations
python django_app/manage.py migrate

# 관리자 계정 생성 (로그인할 계정 생성)
python django_app/manage.py createsuperuser

# 실행
python django_app/manage.py runserver
```

- **접속**
```url
http://127.0.0.1:8000/
```

- **더미 데이터**
  - **dummy_data.sql** 파일 참고
  - 데이터 미리 insert 후 테스트

- **README_meta.md를 읽어주세요**


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
│  │  ├─ 02_normalize/                     # 2단계: 소스별 raw → 공통 포맷 및 데이터 클렌징
│  │  │  ├─ 01_normalize_pubmed.py         # PubMed raw → internal_doc_format (+ 클렌징)
│  │  │  ├─ 02_normalize_nih.py            # NIH raw → internal_doc_format (+ 클렌징)
│  │  │  └─ 03_normalize_protocols_io.py   # Protocols raw → internal_doc_format (+ 클렌징, 예: 중복/노이즈/빈값 정리)
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