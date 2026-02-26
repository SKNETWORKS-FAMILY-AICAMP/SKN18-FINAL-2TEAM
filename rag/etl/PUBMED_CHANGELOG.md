# PubMed ETL 변경사항 (2026-01-13 이후)

## 개요

PubMed 전용 파이프라인 구축 및 step01~05 기능 보완.
파이프라인 진입점: `rag/etl/pipeline_runner_01245.py`

---

## Step 01 — Ingest (`step01_ingest/ingest_pubmed.py`)

### 테이블 / 피겨 ID 정립
- PMCID를 기준으로 테이블·피겨 ID 체계 통일

### 테이블 정보 파싱 강화
- XML API 응답 데이터를 BeautifulSoup으로 한 번 더 파싱
- 테이블 본문 텍스트 추출 및 저장
- 테이블이 이미지로 제공되는 경우: 이미지 URL 저장
- 출력 경로: `data/processed/pubmed/pmc_csv_*/tables.csv`

### 수식(Equation) 이미지 URL 파싱
- 수식이 이미지로 제공되는 경우 이미지 URL을 파싱하여 저장

#### 이미지 URL 파싱 의존성
- `curl_cffi` 설치 필요 (미설치 시 이미지 URL 파싱 불가)

```bash
uv pip install curl_cffi
```

---

## Step 02 — Normalize (`step02_normalize/normalize_pubmed.py`)

- raw JSON → CSV 변환 파이프라인 유지
- 출력: `data/processed/pubmed/pmc_csv_{MMDD_HHMM}/`
  - `articles.csv`, `sections.csv`, `sections_meta.csv`, `sections_for_chunk.csv`
  - `equations.csv`, `figures.csv`, `tables.csv`, `references.csv`

---

## Step 04 — Chunk (`step04_chunk/`)

### 대형 청크 재귀 분할 (`pmc_chunk_common/chunking.py`)
- 청크가 **2,000자 초과** 시 문장 단위 재귀 분할 적용
  - 문장 수 `n`의 절반(`n/2`)씩 `part1` / `part2`로 분리
  - 오버랩: 기존과 동일하게 **120자** 유지
- **무한 재귀 방지** 추가
  - 문장이 1개뿐인 경우 → 글자 수 기준 fallback 분할
  - 분할 후 크기가 원문과 동일한 경우 → 글자 수 기준 fallback 분할

### 출력 경로 타임스탬프 지원 (`step04_chunk/chunker_pubmed.py`)
- `run()` · `_run_internal()` 에 `output_csv` 파라미터 추가
- 파이프라인에서 `pmc_chunks_{MMDD_HHMM}.csv` 형태로 출력

---

## Step 05 — Embed (`step05_embed/embed_pubmed.py`)

### 청크 데이터만 임베딩
- 입력: `data/chunks/pubmed/pmc_chunks_{MMDD_HHMM}.csv`
- 출력: `data/embeddings/pubmed/pmc_vector_{MMDD_HHMM}.csv`
- 섹션 청크만 임베딩 (`run_for_files()` 직접 호출)
- 테이블 캡션 임베딩은 파이프라인에서 별도 제어 (테이블의 캡션데이터를 임베딩할 필요성 있으면 활용하기)

### 버그 수정 (`pmc_embed_common/chunk_embedder_v2.py`)
- `OPENAI_API_KEY` → `OPENAI_AZURE_API_KEY` 변수명 불일치 수정
  - `chunking.py` 변수 리네임에 맞춰 `chunk_embedder_v2.py` 동기화

---

## 파이프라인 (`pipeline_runner_01245.py`)

### 주요 특징
- **PubMed 전용** (NIH / Protocols 제외)
- 실행 단계: `INGEST → NORMALIZE → CHUNK → EMBED`
- 각 단계 출력 파일에 **동일 타임스탬프** (`MMDD_HHMM`) 적용

### 상단 컨피그 블록
```python
PUBMED_FROM_YEAR: int = 2024   # 수집 시작 연도
PUBMED_TO_YEAR:   int = 2024   # 수집 종료 연도
PUBMED_TARGET_COUNT: int = 10  # 카테고리당 수집 목표 논문 수
PUBMED_BATCH_SIZE:   int = 50  # API 배치 크기

SKIP_INGEST:    bool = False
SKIP_NORMALIZE: bool = False
SKIP_CHUNK:     bool = False
SKIP_EMBED:     bool = False
```

### 출력 파일 구조
```
data/raw/pubmed/
  └── pubmed_new_{MMDD_HHMM}.json

data/processed/pubmed/
  └── pmc_csv_{MMDD_HHMM}/
        ├── articles.csv
        ├── sections.csv
        ├── sections_meta.csv
        ├── sections_for_chunk.csv
        ├── equations.csv
        ├── figures.csv
        ├── tables.csv
        └── references.csv

data/chunks/pubmed/
  └── pmc_chunks_{MMDD_HHMM}.csv

data/embeddings/pubmed/
  └── pmc_vector_{MMDD_HHMM}.csv
```

### 실행
```bash
source .venv/bin/activate
python rag/etl/pipeline_runner_01245.py
```
