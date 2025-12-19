# RAG/ETL

## 로컬 파이프라인 실행 예시

- NIH 한 번에 실행 
```bash
python -m rag.etl.pipeline_runner --source nih
python -m rag.etl.pipeline_runner --source nih --skip-ingest --skip-normalize
```
- Protocols 한 번에 실행
```bash
python -m rag.etl.pipeline_runner --source protocols
```

## AWS Lambda 유의사항

- AWS Lambda 실행 제한 시간 = **15분**

## CloudFormation

- 폴더 : `infra/aws/cloudformation/skn18-final-infra-cf.yaml`
- 설치 필요
	- aws cli : 
		- https://docs.aws.amazon.com/ko_kr/cli/latest/userguide/getting-started-install.html
	- aws sam : 
		```bash
		# macOS
		brew install aws-sam-cli
		# 또는 pip
		pip install aws-sam-cli
		```

### **주의**
- skn18-final-infra-cf.yaml 변경 사항 있을 경우에만 재배포 한다
- 키페어를 구글 드라이브에서 다운받아서 내 로컬 ssh 폴더에 저장한다
	- **skn18-final-2team-key.pem**
	- https://drive.google.com/drive/u/1/folders/1Qi2RB2D4cwQnuu9EsbT92e-O1UvHlWoW

### 실행
- CF 업데이트 후 재배포 프로세스
- **주의 : skn18-final-infra-cf.yaml 변경 사항 있을 경우에만 재배포 한다 !!!**
```bash
# 1. 빌드 디렉토리 준비
cd infra/aws/lambda_build
./prepare_build.sh

# SAM
rm -rf .aws-sam
sam build -t infra/aws/cloudformation/skn18-final-infra-cf.yaml

# samconfig.toml 파일 없을때
sam deploy --guided

# samconfig.toml이 설정되어 있으면 다음 명령어로 업데이트
sam deploy
```

- 람다만 배포 
```bash
# 빌드 파일 모으기
./prepare_build.sh

# aws 서버 설정에 맞춰서 pip install
docker run -it --rm \
	-v "$PWD":/var/task \
	-w /var/task \
	--entrypoint bash \
	public.ecr.aws/lambda/python:3.12

# [docker] 안에서
cd infra/aws/lambda_build/nih/
pwd
pip install -r requirements.txt -t .


# [내 로컬에서] 람다 zip 파일 만들기
cd infra/aws/lambda_build/nih/
zip -r ../lambda_nih.zip . -x "*.pyc" "__pycache__/*" "*.bak" ".git/*"


# NIH ingest - 배포
aws lambda update-function-code --function-name skn18-nih-ingest --zip-file fileb:///Users/hjhwang/Documents/ai-camp/SKN18-FINAL-2TEAM/infra/aws/lambda_build/lambda_nih.zip
# NIH ingest - 강제실행
aws lambda invoke \
	--function-name skn18-nih-etl \
	--payload '{}' \
	output.json
# NIH ingest - 로그
aws logs tail /aws/lambda/skn18-nih-etl --follow


# NIH clean/chunk - 배포
aws lambda update-function-code --function-name skn18-nih-cleanse-chunk --zip-file fileb:///Users/hjhwang/Documents/ai-camp/SKN18-FINAL-2TEAM/infra/aws/lambda_build/lambda_nih.zip
# NIH clean/chunk - 강제실행
aws lambda invoke \
	--function-name skn18-nih-cleanse-chunk \
	--payload '{}' \
	output.json
# 로그
aws logs tail /aws/lambda/skn18-nih-cleanse-chunk --follow
```

- ec2 접속
```bash
# 키페어 필요 (EC2 Public IP 확인)
ssh -i ./skn18-final-2team-key.pem ec2-user@13.125.184.220

docker ps
```
  
- 로컬에서 postgresql 접속 
	- EC2 Public IP or 고정 IP 확인
  - Host: EC2 IP 
  - Post: 5432
  - Database: sknfinaldb
  - 계정
  
---
## 1. PubMed


---
## 2. NIH

### 전체 프로세스 흐름

```
1. Ingest (수집)
   → data/raw/nih/{YYYYMMDD}/*.json

2. Normalize (정규화)
   → data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=cleaned/cleaned_data_*.json

3. Chunk (청킹)
   → data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=chunked/chunk.csv
   → data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=chunked/metadata.csv

4. Embed (임베딩)
   → data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=embed/{HHMMSS}_nih_embeddings.csv

5. Upsert (DB 저장)
   → PostgreSQL (pgvector)
```

### 각 단계별 특징

#### 1. Ingest (수집)
- **입력**: ClinicalTrials.gov API
- **출력**: `data/raw/nih/{YYYYMMDD}/*.json`
- **특징**:
  - 조건(condition) 및 국가(country)별로 데이터 수집
  - 페이지 단위로 JSON 파일 저장
  - Rate limiting 적용

#### 2. Normalize (정규화)
- **입력**: `data/raw/nih/{YYYYMMDD}/*.json`
- **출력**: `data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=cleaned/cleaned_data_*.json`
- **특징**:
  - 메타데이터 추출 (`extract_metadata`)
  - 핵심 필드 추출 (`extract_core_fields`):
    - `detailedDescription`: 자세한 설명
    - `armGroups`: 치료군 설명
    - `primaryOutcomes`: 주요 결과
    - `secondaryOutcomes`: 부가 결과 (중복 제거 적용, " ||| " 구분자로 연결)
    - `eligibilityCriteria`: 참가 자격 기준
  - 텍스트 클렌징 (`clean_text`)
  - 파일 분할: 큰 파일은 여러 part로 분할 (`cleaned_data_*_part000.json`)

#### 3. Chunk (청킹)
- **입력**: `stage=cleaned/cleaned_data_*.json` (최신 파일 1개만 선택)
- **출력**: 
  - `stage=chunked/chunk.csv` (덮어쓰기 방식)
  - `stage=chunked/metadata.csv` (덮어쓰기 방식)
- **특징**:
  - **필드별 개별 청킹**: 각 필드를 독립적으로 청킹하여 `{"필드명": "청크 텍스트"}` 형태로 저장
  - **필드별 오버랩 설정**:
    - `detailedDescription`, `armGroups`, `primaryOutcomes`: 오버랩 적용 (문맥 중요)
    - `secondaryOutcomes`, `eligibilityCriteria`: 오버랩 미적용 (독립적인 항목)
  - **중복 제거**:
    - `secondaryOutcomes`: 원본 데이터에서 중복 description 제거
    - 청킹 단계에서도 part 간 중복 제거 (이중 안전장치)
  - **특수 처리**:
    - `secondaryOutcomes`: " ||| " 구분자로 나눈 후 각 part를 독립적으로 청킹
    - `eligibilityCriteria`: 섹션 구분자(Inclusion/Exclusion Criteria)로 나눈 후 각 섹션을 독립적으로 청킹
  - **청킹 설정**:
    - 청크 크기: 600 토큰
    - 오버랩 크기: 120 토큰 (적용되는 필드만)
  - **시맨틱 청킹**: 문장 단위로 분리 후 오버랩 적용 (NLTK 사용)

#### 4. Embed (임베딩)
- **입력**: `stage=chunked/chunk.csv` (최신 파일 1개만 선택)
- **출력**: `stage=embed/{HHMMSS}_nih_embeddings.csv` (타임스탬프 포함 새 파일 생성)
- **특징**:
  - **새 파일 생성 방식**: 타임스탬프를 포함한 파일명으로 매번 새 파일 생성
  - **배치 처리**: 배치 단위로 저장하여 중간에 끊겨도 데이터 보존
  - **모델**: OpenAI `text-embedding-3-small` (기본값)
  - **임베딩 차원**: 1536
  - **중복 제거 없음**: 모든 청크를 그대로 임베딩 (오버랩된 청크도 모두 임베딩)

#### 5. Upsert (DB 저장)
- **입력**: `stage=embed/{HHMMSS}_nih_embeddings.csv`
- **출력**: PostgreSQL (pgvector)
- **특징**:
  - 벡터 DB에 임베딩 저장
  - 중복 체크 및 업데이트

### 데이터 구조

#### Core Fields 구조
```json
{
  "detailedDescription": "자세한 설명 텍스트",
  "armGroups": "치료군 설명 텍스트",
  "primaryOutcomes": "주요 결과 텍스트",
  "secondaryOutcomes": "결과1 ||| 결과2 ||| 결과3",
  "eligibilityCriteria": "Inclusion Criteria: ... Exclusion Criteria: ..."
}
```

#### Chunk CSV 구조
```csv
nctid,chunk_id,chunk
NCT12345,chi_1,"{\"secondaryOutcomes\": \"Measured in minutes.\"}"
NCT12345,chi_2,"{\"eligibilityCriteria\": \"Inclusion Criteria: Age 18-75.\"}"
```

#### Embedding CSV 구조
```csv
nctid,chunk_id,text,embedding_model,embedding_dim,embedding
NCT12345,chi_1,"Secondary Outcomes: Measured in minutes.",text-embedding-3-small,1536,"[0.123, 0.456, ...]"
```

### 파일 처리 방식

| 단계 | 파일 처리 방식 | 기존 파일 처리 |
|------|---------------|----------------|
| **Normalize** | 새 파일 생성 (타임스탬프) | 기존 파일 유지 |
| **Chunk** | 덮어쓰기 (`'w'` 모드) | 삭제 후 재생성 |
| **Embed** | 새 파일 생성 (타임스탬프) | 기존 파일 유지 |

### 청킹 프로세스 상세

#### 1. 시맨틱 청킹 (문장 단위 분리)
- NLTK `sent_tokenize` 사용
- 약어 처리: "Fig.", "No." 등 자동 인식
- 문장 경계를 기준으로 분리

#### 2. 오버랩 적용 (필드별)
- **오버랩 적용 필드**: 문장 단위로 오버랩
  - 예: 청크1 = "문장1. 문장2. 문장3."
  - 청크2 = "문장2. 문장3. 문장4." (문장2, 문장3 오버랩)
- **오버랩 미적용 필드**: 각 항목을 독립 청크로
  - 예: `secondaryOutcomes`의 각 outcome이 독립 청크

#### 3. 중복 제거
- **Normalize 단계**: 원본 데이터에서 중복 description 제거
- **Chunk 단계**: part 간 중복 제거 (이중 안전장치)

### 주요 설정

- **청크 크기**: 600 토큰 (CHUNK_SIZE_MIN/MAX)
- **오버랩 크기**: 120 토큰 (OVERLAP_MIN/MAX, 적용되는 필드만)
- **배치 크기**: 로컬 200개, Lambda 70개
- **파일 분할**: Normalize 단계에서 100개 study마다 파일 분할

---
## 3. Protocols

### Keyword
- Protein
- Cell
- DNA
- RNA
- vivo
- mouse
  
### protocol etl 수정 사항

- api
  - 03_ingest_protocols_io.py 
  - CLIENT_ACCESS_TOKEN .env로 이동
  - 한 번에 메모리에 쌓았다가 CSV 저장 방식에서 -> 페이지마다 append 저장하는 방식으로 변경 
  - 스케줄 히스토리 저장 : schedule_store.py
  - raw 데이터 저장 경로 : data/raw/protocols
  - keyword 종류별로 api 병렬로 실행하도록 변경
    - MAX_PARALLEL_WORKERS = 2  # 동시에 돌릴 최대 키워드 수
    - 요청 간 time.sleep(0.6) 추가
  - page_size=30으로 변경 (람다 수행 제한 시간 고려)
  - 429/504 응답 시 exponential backoff 재시도 추가
    - MAX_RETRIES = int(os.getenv("PROTOCOLS_IO_MAX_RETRIES", "3"))
- clean
  -  03_normalize_protocols.py
  -  input, output 경로 변경
- chunk : 
  - 03_embed_protocols.py
  - input, output 경로 변경
  - 오버랩이 문장 단위로 붙도록 변경

### Raw data column 분석
- 컬럼 구성: url, title, abstract, step_content, reference, guidelines, materials
- `<no data>`: 해당 url에서 관련 데이터가 없을 경우 저장
- url 중복: url은 각 프로토콜의 고유 값이므로 중복 제거함
- url 중복 제거 후 title 중복: 본문 내용이 대부분 비슷하나 일부 차이가 있어 중복 title도 보존함
- 컬럼 값이 dict(string) 형태로 저장된 경우가 있음
    - 일반적으로 ast.literal_eval로 변환하여 파싱을 시도
    - 변환 오류 시 string 그대로 남아 dict 내부의 값 추출 필요(예: `{""blocks"": ... }`)
    - 오류 없이 파싱되면 텍스트 형태로 정리
- materials 컬럼(dict 형태 string)의 경우, dict 파싱 에러 발생 시 `"name"` 키 값만 추출하도록 split과 for문으로 처리
    - split('"name": ') 결과 enumerate하여 index=0(첫 요소)은 제외
    - 각 요소에서 name 값을 추출: `i.split(",")[0]`
- 프로토콜 별 고유 ID 재부여
- title 중복 + reference가 없을 때: reference가 없는 경우 해당 row는 제거

#### DB에 필요한 컬럼 구성 -json : cs
- RDB:
    - protocol_id (uuid, pk)
    - url (정확한 url 필요)
    - title (LIKE 쿼리로 검색 지원)
    - reference (정확한 이름 필요)
    - materials (reference와 유사)
    - abstract
- VectorDB V1:
    - protocol_id (uuid, fk)
    - chunking_id (pk)
    - text: [abstract, step_content, guidelines]
- VectorDB V2(원본):
    - protocol_id (uuid, fk)
    - chunking_id (pk)
    - abstract
    - step_content
    - guidelines
  

