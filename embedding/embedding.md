# embedding 사용 설명서

## 1. 폴더 역할 개요

- 입력: `data_preprocessing/pmc_etl/preprocess_split.py` 에서 생성한 섹션 텍스트 CSV  
  (예: `sections_for_chunk.csv`)
- 처리 단계:
  1. 문장 단위 청크 생성 (`chunking.py`, `chunk_generator.py`, `run_chunk.py`)
  2. OpenAI 임베딩 생성 및 CSV/DB 저장 (`chunk_embedder.py`, `run_embed.py`)
  3. (선택) 섹션 메타 Postgres 업서트 (`load_pmc_meta.py`)
  4. (별도 프로젝트) 인터뷰 Q&A 벡터 검색 (`search_similar.py`)

---

## 2. 전체 파이프라인 (embedding 관점)

1. **청크 생성 단계**

   - 입력: 섹션 텍스트 CSV (예: `sections_for_chunk.csv`)
   - 스크립트:
     - `chunk_generator.py` (ChunkGenerator 클래스)
     - `run_chunk.py` (CLI 래퍼)
   - 출력: 청크 CSV (기본 `pmc_chunks.csv`)
     - 컬럼 예:  
       `chunk_id`, `section_id`, `chunk_seq`, `start_char`, `end_char`, `text_chunk`, `fig_ref_markers`, `ref_ids`

2. **임베딩 생성 단계**

   - 입력: 청크 CSV (`pmc_chunks.csv`)
   - 스크립트:
     - `chunk_embedder.py` (ChunkEmbedder 클래스)
     - `run_embed.py` (CLI 래퍼)
   - 출력:
     - CSV: 임베딩 CSV (기본 `pmc_vector.csv`)
       - `chunk_id`, `section_id`, `chunk_seq`, `start_char`, `end_char`, `emb_model`, `emb_dim`, `text_chunk`, `embedding`
     - (옵션) Postgres 테이블 `pmc_section_chunk`에 같은 정보 insert/upsert

3. **메타 업서트 (선택)**

   - 입력: 섹션 메타 CSV (`sections_meta.csv`)
   - 스크립트: `load_pmc_meta.py`
   - 출력:
     - Postgres 테이블 `pmc_section_meta`에 `section_id` 기준 upsert

---

## 3. 파일별 설명 및 사용법

### 3-1. `chunking.py`

- 역할
  - 청크 생성에 필요한 공통 유틸 제공
  - `.env` 로드 및 `OPENAI_API_KEY` 등 환경설정
- 주요 상수
  - `DEFAULT_EMBED_MODEL = "text-embedding-3-small"`
  - `DEFAULT_EMBED_DIM = 1536`
  - `DEFAULT_CHUNK_SIZE = 600` (문자 기준 청크 길이)
  - `DEFAULT_OVERLAP = 120` (청크 간 중첩 길이)
  - `RATE_LIMIT_DELAY`: 임베딩 호출 간 딜레이 (초)
- 주요 함수
  - `normalize_text(s: str) -> str`: 공백 정리
  - `make_chunk_id(section_id: str, seq: int) -> str`  
    - `SEC{section_id}_C{seq:02d}` 형식으로 청크 ID 생성
  - `process_section_text_for_chunking(raw_text: str) -> Dict[str, Any]`
    - `clean_content` 적용
    - `extract_figure_table_markers`로 그림/표 참조 마커 추출
    - `extract_reference_markers`로 참고문헌 인용 마커 ID 추출
    - `remove_reference_markers`로 본문에서 인용 마커 제거
    - 결과:
      - `clean_text`: 청크에 사용할 텍스트
      - `ref_ids`: 인용 마커 ID 목록 문자열
      - `fig_ref_markers`: 그림/표 참조 마커 문자열
  - `split_into_sentences(text: str) -> List[Tuple[int, int]]`
    - 약어, 괄호, 숫자 등 고려한 문장 분리
  - `sentence_chunks(text, max_len, overlap)`
    - 문장 단위로 묶어 청크 구간(start_char, end_char)과 텍스트 생성
  - `to_pgvector_literal(vec: List[float]) -> str`
    - `[0.1234567,0.2345678,...]` 형태 문자열 반환

---

### 3-2. `pmc_data_loader.py`

- 역할
  - 청크/임베딩 CSV를 읽는 유틸
- 주요 함수
  - `load_existing_chunk_ids(out_path: Path) -> Set[str]`
    - CSV의 `chunk_id` 컬럼을 모두 읽어 집합으로 반환
    - resume 모드에서 이미 처리된 청크 건너뛰기용
  - `iter_chunk_csv_rows(csv_path: Path, required_cols: List[str])`
    - CSV를 row-by-row로 제너레이터 형태로 반환
    - `required_cols`가 모두 존재하는지 검증

---

### 3-3. `chunk_generator.py`

- 역할
  - 섹션 CSV → 청크 CSV로 변환하는 `ChunkGenerator` 클래스 제공
- 생성자 인자
  - `input_csv: str`: 섹션 텍스트 CSV 경로 (`sections_for_chunk.csv` 등)
  - `chunk_csv: str`: 청크 CSV 출력 경로 (예: `pmc_chunks.csv`)
  - `chunk_size: int`: 청크 길이 (기본 `DEFAULT_CHUNK_SIZE`)
  - `overlap: int`: 청크 중첩 길이 (기본 `DEFAULT_OVERLAP`)
  - `batch_size: int`: 진행 바 추정용 (실제 로직에는 크게 영향 없음)
  - `meta_csv: str`: (옵션) 메타 CSV 출력 경로
  - `split_meta: bool`: True일 경우 메타 CSV 생성
- 메서드
  - `run(resume: bool = True)`
    - `input_csv`를 읽어서 섹션별로 청크 생성
    - `resume=True`일 경우 기존 `chunk_csv`에서 `chunk_id`를 읽어 이미 생성된 청크는 건너뜀
    - 결과를 `chunk_csv`에 append
- 청크 CSV 컬럼
  - `chunk_id`
  - `section_id`
  - `chunk_seq`
  - `start_char`
  - `end_char`
  - `text_chunk`
  - `fig_ref_markers`
  - `ref_ids`

---

### 3-4. `run_chunk.py`

- 역할
  - 청크 생성 CLI 엔트리 포인트
- 기본 사용 예 (PowerShell)
  ```bash
  cd embedding

  python run_chunk.py chunk `
    --input ../data_preprocessing/pmc_etl/pmc_csv/sections_for_chunk.csv `
    --chunk-out ./pmc_chunks.csv `
    --meta-out ./sections_meta.csv `
    --split-meta `
    --chunk 600 `
    --overlap 120
  ```
- 주요 옵션
  - `chunk` (서브커맨드): 청크 생성 (기본값이므로 생략 가능)
  - `--input`: 섹션 텍스트 CSV 경로 (필수)
  - `--chunk-out`: 청크 CSV 출력 경로 (기본 `pmc_chunks.csv`)
  - `--meta-out`: 메타 CSV 저장 경로 (선택)
  - `--split-meta`: 메타 CSV를 생성할지 여부
  - `--chunk`: 청크 길이
  - `--overlap`: 청크 중첩 길이
  - `--batch-size`: 진행 바 추정용
  - `--no-resume`: 기존 청크 CSV를 무시하고 처음부터 생성

- 결과
  - `pmc_chunks.csv`: 임베딩 입력용 텍스트 청크 목록
  - (옵션) `sections_meta.csv`: 섹션 메타 정보 CSV

---

### 3-5. `chunk_embedder.py`

- 역할
  - 청크 CSV를 읽어 OpenAI 임베딩을 생성하고 CSV/DB에 기록하는 `ChunkEmbedder` 클래스 제공
- 생성자 인자
  - `chunk_csv: str`: 청크 CSV 경로
  - `output_csv: str`: 임베딩 CSV 출력 경로 (예: `pmc_vector.csv`)
  - `embed_model: str`: 임베딩 모델 (기본 `DEFAULT_EMBED_MODEL`)
  - `embed_dim: int`: 임베딩 차원 (기본 `DEFAULT_EMBED_DIM`)
  - `pg_connect: Optional[dict]`: DB 연결 정보 (`host`, `port`, `dbname`, `user`, `password`)
  - `pg_table: str`: 타깃 테이블명 (기본 `"pmc_section_chunk"`)
  - `write_csv: bool`: CSV도 기록할지 여부 (기본 True)
  - `pg_batch_size: int`: DB 배치 insert 크기
- 메서드
  - `embed(text: str) -> List[float]`
    - OpenAI 임베딩 API 호출
  - `run(resume: bool = True)`
    - `chunk_csv`를 순회하며 청크마다 임베딩 생성
    - 이미 CSV/DB에 존재하는 `chunk_id`는 건너뜀
    - CSV 및 (선택) DB에 결과 기록
- 임베딩 CSV 컬럼
  - `chunk_id`
  - `section_id`
  - `chunk_seq`
  - `start_char`
  - `end_char`
  - `emb_model`
  - `emb_dim`
  - `text_chunk`
  - `embedding` (pgvector 형식 문자열)

---

### 3-6. `run_embed.py`

- 역할
  - 임베딩 생성 CLI 엔트리 포인트
- 기본 사용 예
  ```bash
  cd embedding

  python run_embed.py embed `
    --chunks ./pmc_chunks.csv `
    --output ./pmc_vector.csv `
    --model text-embedding-3-small `
    --pg-host localhost `
    --pg-port 5432 `
    --pg-user pmc `
    --pg-password pmc1234 `
    --pg-db pmc_db `
    --pg-table pmc_section_chunk
  ```
- 주요 옵션
  - `embed` (서브커맨드): 임베딩 생성 (기본값)
  - `--chunks`: 청크 CSV 경로 (필수)
  - `--output`: 임베딩 CSV 출력 경로 (기본 `pmc_vector.csv`)
  - `--model`: 임베딩 모델명 (기본 `DEFAULT_EMBED_MODEL`)
  - `--no-resume`: 기존 결과 무시하고 전부 재계산
  - `--no-csv`: CSV는 쓰지 않고 DB에만 삽입
  - `--pg-batch-size`: DB 배치 insert 크기 (기본 500)
  - `--pg-host`, `--pg-port`, `--pg-user`, `--pg-password`, `--pg-db`, `--pg-table`: Postgres 연결 정보
- 결과
  - CSV: `pmc_vector.csv`
  - DB: `pmc_section_chunk` 테이블에 벡터 삽입/업서트

---

### 3-7. `load_pmc_meta.py`

- 역할
  - 섹션 메타 CSV(`sections_meta.csv`)를 Postgres `pmc_section_meta` 테이블에 upsert
- 기본 사용 예
  ```bash
  cd embedding

  python load_pmc_meta.py \
    --input ../data_preprocessing/pmc_etl/pmc_csv/sections_meta.csv \
    --pg-host localhost \
    --pg-port 5432 \
    --pg-user pmc \
    --pg-password pmc1234 \
    --pg-db pmc_db \
    --table pmc_section_meta \
    --commit
  ```
- 옵션
  - `--input`: 섹션 메타 CSV 경로 (필수)
  - `--table`: 타깃 테이블명 (기본 `pmc_section_meta`)
  - `--batch-size`: 배치 크기 (기본 500)
  - `--commit`: 실제 DB에 반영 (없으면 dry-run으로 동작)
  - `--pg-*`: DB 연결 정보 (또는 환경변수 `POSTGRES_HOST`, `POSTGRES_DB` 등 사용)
- 결과
  - `section_id` 기준으로 메타 정보가 DB에 upsert



## 4. 최종 산출물 요약

- **data_preprocessing 쪽 결과**
  - JSON:
    - `pmc_articles_by_category*.json`
  - CSV:
    - `articles.csv`, `sections.csv`, `figures.csv`, `tables.csv`, `equations.csv`, `references.csv`
    - `sections_meta.csv`, `sections_for_chunk.csv`

- **embedding 쪽 결과**
  - CSV:
    - `pmc_chunks.csv`: 섹션 기반 텍스트 청크
    - `pmc_vector.csv`: 각 청크의 임베딩 및 텍스트
  - DB (선택):
    - `pmc_section_meta`: 섹션 메타 정보
    - `pmc_section_chunk`: 청크 + 임베딩 정보

이 흐름을 통해, PMC 원문 수집 → 구조화 → 섹션/청크 분할 → 임베딩 → 최종 Result 섹션+그림/표 데이터셋 및 벡터 검색까지 단계적으로 진행할 수 있습니다.

