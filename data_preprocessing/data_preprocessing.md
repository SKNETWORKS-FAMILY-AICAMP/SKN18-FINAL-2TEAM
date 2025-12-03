# data preprocessing 폴더
## extract -cleansing .py 파일 넣어주세요# data_preprocessing 사용 설명서

## 1. 폴더 구조 개요

- `data_preprocessing/`
  - `pmc_etl/` : PMC 원문 수집 · 파싱 · CSV 변환 파이프라인
  - `result_research_chunks_and_fig_tab.py` : Result 섹션 텍스트 청크 + 그림/표 매핑 최종 병합 스크립트
  - `final_result_data.csv` : 최종 병합된 결과(프로젝트 상황에 따라 이름/내용 다를 수 있음)

---

## 2. pmc_etl 파이프라인 개요

전반적인 처리 흐름:

1. `api_client.py`  
   → PubMed/PMC API로 카테고리별 논문 ID 수집 + OAI-PMH로 XML 원문 가져오기  
   → `parsing.py`의 `extract_article_info()`로 파싱해 카테고리별 article dict 리스트 생성 후 JSON 저장  
   (예: `pmc_articles_by_category32.json`)

2. `pmc_json_to_csv_main.py`  
   → 위 JSON을 읽어서 여러 CSV (`articles.csv`, `sections.csv`, `figures.csv`, `tables.csv`, `equations.csv`, `references.csv`)로 분리 저장

3. `preprocess_split.py`  
   → `sections.csv`에서
   - 메타 정보만 담은 `sections_meta.csv`
   - 청크 생성 전용 텍스트 `sections_for_chunk.csv`
   를 생성

4. (선택) 이후 `embedding` 폴더에서 청크 생성 및 임베딩 진행

5. `result_research_chunks_and_fig_tab.py`  
   → `sections.csv`, 청크 CSV, 그림/표 CSV들을 이용해 “연구 논문(Research) + Result 섹션”만 골라 텍스트 청크 + 그림 + 표를 하나의 최종 데이터셋으로 병합

---

## 3. pmc_etl 폴더 파일별 설명 및 사용법

### 3-1. `config.py`

- 역할
  - PMC API, PubMed E-utilities 엔드포인트 URL 정의
  - 기본 수집 기간 (`DEFAULT_FROM_DATE`, `DEFAULT_UNTIL_DATE`)
  - 주제 카테고리별 키워드 (`CATEGORY_KEYWORDS`)
- 사용
  - 직접 실행하는 스크립트가 아니라, 다른 모듈에서 import 해서 사용

---

### 3-2. `utils.py`

- 역할
  - 공통 유틸 함수 모음
    - `_local_name`: XML 태그에서 네임스페이스 제거
    - `_extract_caption_text`: figure/table에서 caption 텍스트 추출
    - `gen_random_fig_id`, `gen_random_table_id`: 랜덤 ID 생성
    - `parse_fig_label`, `normalize_fig_label`: Figure 라벨 파싱·정규화
    - `parse_table_label`, `normalize_table_label`: Table 라벨 파싱·정규화
    - `categorize_article`: 제목/초록 기반 논문 주제 카테고리 분류
    - `build_pubmed_term_for_category`: PubMed 검색용 term 문자열 구성
- 사용
  - `api_client.py`, `parsing.py`, `pmc_processing_utils.py` 등에서 공통으로 사용

---

### 3-3. `pmc_math.py`

- 역할
  - PMC NXML 내 `<math>`, `<disp-formula>`, `<inline-formula>` 등 수식 태그를 LaTeX 문자열로 변환
  - `extract_formula_text(formula_node, display=False)`:
    - `tex-math` 또는 MathML을 찾아 LaTeX 문자열로 변환
- 사용
  - `utils.py`, `parsing.py` 등에서 수식 텍스트 추출용으로 import

---

### 3-4. `html_scraper.py`

- 역할
  - `get_html_image_map(pmcid: str) -> Dict[str, str]`
    - Playwright로 PMC 아티클 HTML 로드
    - BeautifulSoup으로 blob 이미지 URL을 모두 파싱
    - 그림 파일 basename → 실제 이미지 URL 매핑 딕셔너리 반환
- 사용 예시
  ```python
  from html_scraper import get_html_image_map

  image_map = get_html_image_map("PMC1234567")
  url = image_map.get("some_blob_id")
  ```

---

### 3-5. `parsing.py`

- 역할
  - PMC XML Record를 파싱해 논문 단위 dict로 변환
  - 주요 기능
    - `extract_body_components(body_elem)`:
      - 본문 텍스트
      - figure/table caption
      - 수식 정보
      - 섹션 경로 등 추출
    - 참고문헌(Reference) 정보 추출
    - `extract_article_info(record)`:
      - 제목, 초록, 저널, 연도, PMCID/PMID/DOI
      - 섹션 리스트
      - 수식 리스트
      - 참고문헌 리스트
      등을 포함한 하나의 article dict 생성
- 사용
  - `api_client.py`에서 각 record 처리 시 호출

---

### 3-6. `pmc_processing_utils.py`

- 역할
  - 텍스트 정리, 레퍼런스 마커 처리, 섹션 카테고리 분류 등
- 대표 함수
  - `clean_content(text)`: 줄바꿈/탭 제거, 공백 정리
  - `normalize_title_spacing(text)`: 제목/섹션 타이틀 포맷 정리
  - `normalize_reference_spacing(text)`: 참고문헌 텍스트 포맷 정리
  - `extract_figure_table_markers(text)`: (Fig. 1), (Table S1) 같은 그림/표 참조 마커 추출
  - `extract_reference_markers(text)`: 본문 내 [1], (2–3) 등 인용 마커에서 번호 추출
  - `remove_reference_markers(text)`: 본문 내 인용 마커 제거
  - `gen_section_id()`: 섹션용 랜덤 정수 ID 생성
  - `annotate_section_categories(article)`: 섹션을 abstract/introduction/result/discussion/method/other 등으로 분류
  - `iter_articles(obj)`: JSON 구조를 순회하며 article dict들을 yield
- 사용
  - `pmc_json_to_csv_main.py`, `embedding/chunking.py` 등에서 공통으로 사용

---

### 3-7. `api_client.py`

- 역할
  - PubMed ESearch + PMC OAI-PMH를 사용해 카테고리별 논문을 수집하고 article dict로 구조화
- 주요 함수
  - `search_pmc_ids_for_category(category, keywords, max_ids, retstart)`:
    - 카테고리/키워드 기반 PMC ID 검색 (ESearch)
  - `fetch_pmc_records()`:
    - 날짜 범위 내 open-access 레코드 반복적으로 가져오기 (ListRecords)
  - `fetch_single_pmc_record(pmcid)`:
    - 특정 PMCID에 대한 Record 1개 가져오기 (GetRecord)
  - `collect_articles_per_category(max_per_category, batch_size)`:
    - 카테고리별로 최대 `MAX_PER_CATEGORY`만큼 논문 수집
    - `parsing.extract_article_info()`로 파싱
    - `categorize_article()`로 카테고리 매칭 확인 후 수집
  - `save_as_json(data, path)`:
    - 수집된 dict를 JSON 파일로 저장
- 실행 예시
  ```bash
  cd data_preprocessing/pmc_etl
  python api_client.py
  ```

---

### 3-8. `pmc_json_to_csv_main.py`

- 역할
  - `pmc_articles_by_category.json` 형식의 JSON을 여러 CSV로 분리
- 입력
  - `--input_json`: article dict들이 들어 있는 JSON 파일
- 출력 (예)
  - `articles.csv`:
    - `pmcid`, `pmid`, `topic_category`, `title`, `journal`, `year`, `doi`, `article_category`, `article_type_raw`, `abstract`, `n_sections`, `n_equations`, `n_figures`, `n_tables`, `n_references`
  - `sections.csv`:
    - `section_id`, `pmcid`, `pmid`, `topic_category`, `title`, `text`, `path`, `section_category`, `article_category`, `fig_ids`, `table_ids`
  - `equations.csv`:
    - `pmcid`, `pmid`, `equation_index`, `display`, `latex`, `image_url`
  - `figures.csv`:
    - `pmcid`, `pmid`, `fig_ids`, `fig_label`, `fig_caption`, `fig_url`
  - `tables.csv`:
    - `pmcid`, `pmid`, `table_index`, `table_ids`, `table_label`, `table_caption`, `table_url`
  - `references.csv`:
    - `pmcid`, `pmid`, `ref_index`, `title`, `journal`, `year`, `doi`, `ref_pmid`, `ref_url`
- 실행 예시
  ```bash
  cd data_preprocessing/pmc_etl
  python pmc_json_to_csv_main.py \
    --input_json ./pmc_articles_by_category32.json \
    --out_dir ./pmc_csv
  ```

---

### 3-9. `preprocess_split.py`

- 역할
  - `sections.csv`를
    - 메타 정보만 담은 CSV
    - 청크 생성을 위한 텍스트 CSV
    로 분리
- 입력
  - `--input`: `sections.csv` 경로
- 출력
  - `--meta-out`: 섹션 메타 정보 CSV (예: `sections_meta.csv`)
    - `section_id`, `pmcid`, `pmid`, `topic_category`, `path`, `section_category`, `article_category`, `fig_ids`, `table_ids`, `ref_ids`
  - `--chunk-out`: 청크 전처리용 텍스트 CSV (예: `sections_for_chunk.csv`)
    - `section_id`, `title`, `text`  
    - `title + text`를 합치고 정규화한 텍스트를 사용  
    - 너무 짧은 텍스트는 제외
- 실행 예시
  ```bash
  cd data_preprocessing/pmc_etl
  python preprocess_split.py \
    --input ./pmc_csv/sections.csv \
    --meta-out ./pmc_csv/sections_meta.csv \
    --chunk-out ./pmc_csv/sections_for_chunk.csv
  ```

---

## 4. result_research_chunks_and_fig_tab.py

- 역할
  - “연구 논문(Research)” 중 “Result 섹션”에 해당하는 데이터만 골라,
    - 텍스트 청크 (예: `chunks_new7.csv`)
    - 그림 정보 (`figures.csv`)
    - 표 정보 (`tables.csv`)
    를 하나의 최종 CSV로 병합
- 동작 개요
  1. `sections.csv`에서  
     - `section_category == "result"`  
     - `article_category == "research"`  
     인 섹션만 필터링
  2. 해당 섹션들의 `section_id`와 `pmid` 목록을 추출
  3. 청크 CSV(`chunks`)에서 `section_id` 기준으로 관련 청크를 필터링
  4. `figures.csv`, `tables.csv`에서 같은 PMID에 해당하는 figure/table을 필터링
  5. 모두 합쳐 하나의 DataFrame으로 만들고 CSV로 저장
- 인자
  - `--base-dir`: 입력 파일들의 기본 디렉터리 (기본값: 현재 디렉터리)
  - `--sections`: 섹션 CSV 파일명/경로 (기본값: `sections.csv`)
  - `--chunks`: 청크 CSV 파일명/경로 (기본값: `chunks_new7.csv`)
  - `--figures`: 그림 CSV 파일명/경로 (기본값: `figures.csv`)
  - `--tables`: 표 CSV 파일명/경로 (기본값: `tables.csv`)
  - `--output`: 최종 결과 CSV 파일명/경로 (기본값: `final_result_research_dataset.csv`)
- 실행 예시
  ```bash
  cd data_preprocessing
  python result_research_chunks_and_fig_tab.py \
    --base-dir ./pmc_etl/pmc_csv \
    --sections sections.csv \
    --chunks chunks_new7.csv \
    --figures figures.csv \
    --tables tables.csv \
    --output final_result_research_dataset.csv
  ```
- 결과
  - `final_result_research_dataset.csv` (또는 지정한 이름)
    - 예시 컬럼:
      - `pmid`
      - `data_type` (`text` / `figure` / `table`)
      - `chunk_id`, `text_chunk`
      - `fig_url`, `table_url`
      - 그 외 원본 CSV에서 온 메타 컬럼들
    - “연구 논문 Result 섹션 텍스트 + 관련 그림/표”가 한 파일로 모인 최종 데이터셋

