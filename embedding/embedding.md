# Interview Q&A Embedding System

OpenAI text-embedding-3-large 모델을 사용한 면접 질의응답 임베딩 시스템입니다.
메타데이터와 벡터 인덱스가 분리된 구조로 설계되었습니다.

## 📋 시스템 구성

- **Vector Database**: PostgreSQL + pgvector
- **Embedding Model**: OpenAI text-embedding-3-large (3072 dimensions)
- **Schema**: qa (meta_df, vec_q_index, vec_a_index)
- **데이터**: 68,074개의 면접 Q&A 쌍

## 🏗️ 테이블 구조

### 1. meta_df (메타데이터 테이블)
표시 및 필터링용 메타데이터를 저장합니다.

```sql
- chunk_id (PK)
- doc_id (sample_id)
- occupation, gender, age_range, experience
- question_intent, answer_intent_category
- answer_emotion_expression, answer_emotion_category
- question_text, question_text_norm
- answer_text, content_combined
- tokens_answer, tokens_combined
- group_id (같은 질문에 대한 다수 답변 묶기)
```

### 2. vec_q_index (질문 전용 Q-Index)
정규화된 질문 텍스트의 임베딩을 저장합니다.

```sql
- chunk_id_q (PK, 예: DOC000001_Q)
- chunk_id (FK → meta_df)
- emb_model, emb_dim (3072)
- embedding vector(3072)
```

### 3. vec_a_index (답변 전용 A-Index)
답변 텍스트의 임베딩을 저장합니다.

```sql
- id (PK, auto increment)
- chunk_id (FK → meta_df)
- emb_model, emb_dim (3072)
- embedding vector(3072)
```

## 🚀 시작하기

### 1. Docker 컨테이너 시작

```bash
cd docker
docker-compose up -d
```

데이터베이스가 준비되면:
- PostgreSQL: `localhost:5432`
- Database: `interview_db`
- Schema: `qa`
- User: `interview_user`
- Password: `interview_pass`

### 2. Python 패키지 설치

```bash
cd embedding
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일에 OpenAI API 키가 있는지 확인:

```env
OPENAI_API_KEY=your_api_key_here

# Optional: Override default DB settings
DB_HOST=localhost
DB_PORT=5432
DB_NAME=interview_db
DB_USER=interview_user
DB_PASSWORD=interview_pass
```

### 4. 임베딩 생성

```bash
python embed_data.py --input ../dataset/train_detailed_all.csv
```

**프로세스**:
1. CSV 데이터 로드
2. 메타데이터 생성 (meta_df에 삽입)
3. Q-Index 임베딩 생성 (정규화된 질문 텍스트)
4. A-Index 임베딩 생성 (답변 텍스트)
5. 배치 단위로 데이터베이스에 삽입

**예상 소요**:
- 시간: ~3-4시간 (68,074개 레코드)
- 비용: ~$28 USD (질문 + 답변 각각 임베딩)
- 배치: 50개씩 처리
- Rate limit: 0.2초 지연

## 🔍 유사도 검색

### 기본 검색 (Hybrid 모드)

```bash
python search_similar.py --query "팀 프로젝트에서 갈등을 해결한 경험"
```

### Q-Index 검색 (질문 기반)

```bash
python search_similar.py --query "리더십 경험" --mode q --top-k 5
```

### A-Index 검색 (답변 기반)

```bash
python search_similar.py --query "어려운 문제 해결 방법" --mode a --top-k 10
```

### Hybrid 검색 (Q + A 조합)

```bash
python search_similar.py --query "창의적인 아이디어" --mode hybrid --top-k 10 --k-q 3
```
- `--top-k 10`: 총 10개 결과
- `--k-q 3`: Q-Index에서 3개, A-Index에서 7개

### 필터링 검색

직업으로 필터링:
```bash
python search_similar.py --query "디자인 프로세스" --occupation ARD
```

질문 의도로 필터링 (Q-Index):
```bash
python search_similar.py --query "문제 해결" --mode q --q-intent behavioral_star
```

답변 의도로 필터링 (A-Index):
```bash
python search_similar.py --query "업무 태도" --mode a --a-intent attitude
```

복합 필터:
```bash
python search_similar.py --query "협업 경험" --occupation ARD --mode hybrid
```

## 📊 데이터베이스 스키마

```sql
-- 메타데이터 테이블
CREATE TABLE qa.meta_df (
    chunk_id VARCHAR(100) PRIMARY KEY,
    doc_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    content_combined TEXT NOT NULL,
    ...
);

-- Q-Index (질문 임베딩)
CREATE TABLE qa.vec_q_index (
    chunk_id_q VARCHAR(100) PRIMARY KEY,
    chunk_id VARCHAR(100) NOT NULL,
    embedding vector(3072) NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES qa.meta_df(chunk_id)
);

-- A-Index (답변 임베딩)
CREATE TABLE qa.vec_a_index (
    id BIGSERIAL PRIMARY KEY,
    chunk_id VARCHAR(100) NOT NULL,
    embedding vector(3072) NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES qa.meta_df(chunk_id)
);
```

## 🎯 검색 함수

데이터베이스에 내장된 검색 함수들:

### 1. qa.search_questions()
Q-Index 검색 - 질문 유사도 기반

```sql
SELECT * FROM qa.search_questions(
    $1::vector(3072),  -- query embedding
    10,                -- top_k
    'ARD',             -- occupation filter
    'behavioral_star'  -- question_intent filter
);
```

### 2. qa.search_answers()
A-Index 검색 - 답변 유사도 기반

```sql
SELECT * FROM qa.search_answers(
    $1::vector(3072),
    10,
    'ARD',
    'attitude'
);
```

### 3. qa.search_hybrid()
Hybrid 검색 - Q + A 조합

```sql
SELECT * FROM qa.search_hybrid(
    $1::vector(3072),
    10,  -- total results
    3,   -- Q-Index results
    'ARD'
);
```

## 💡 Python에서 직접 사용

```python
from search_similar import VectorSearch

searcher = VectorSearch()
searcher.connect_db()

# Q-Index 검색
q_results = searcher.search_questions(
    query="프로젝트 실패 경험",
    top_k=5,
    filters={'question_intent': 'behavioral_star'}
)

# A-Index 검색
a_results = searcher.search_answers(
    query="문제 해결 능력",
    top_k=5,
    filters={'occupation': 'ARD'}
)

# Hybrid 검색
hybrid_results = searcher.search_hybrid(
    query="협업과 리더십",
    top_k=10,
    k_q=3,
    filters={'occupation': 'ARD'}
)

for result in hybrid_results:
    print(f"Similarity: {result['similarity']:.4f}")
    print(f"Source: {result['source_index']}-Index")
    print(f"Question: {result['question_text']}")
    print()

searcher.close_db()
```

## 🛠️ 트러블슈팅

### Docker 컨테이너 상태 확인

```bash
docker ps
docker logs interview_vectordb
```

### 데이터베이스 연결 테스트

```bash
docker exec -it interview_vectordb psql -U interview_user -d interview_db
```

### 테이블 및 레코드 확인

```sql
-- 스키마 확인
\dt qa.*

-- 레코드 수 확인
SELECT COUNT(*) FROM qa.meta_df;
SELECT COUNT(*) FROM qa.vec_q_index;
SELECT COUNT(*) FROM qa.vec_a_index;

-- 직업별 분포
SELECT occupation, COUNT(*) 
FROM qa.meta_df 
GROUP BY occupation 
ORDER BY COUNT(*) DESC;

-- Question Intent 분포
SELECT question_intent, COUNT(*) 
FROM qa.meta_df 
GROUP BY question_intent 
ORDER BY COUNT(*) DESC 
LIMIT 10;
```

### 인덱스 상태 확인

```sql
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'qa';
```

## 📝 주요 특징

✅ **분리된 테이블 구조**: 메타데이터와 벡터 인덱스 분리로 유연한 검색  
✅ **Q-Index & A-Index**: 질문/답변 별도 임베딩으로 정확한 검색  
✅ **Hybrid Search**: 두 인덱스 조합으로 최적의 검색 결과  
✅ **텍스트 정규화**: 소문자/공백/기호 처리로 검색 정확도 향상  
✅ **Token 카운팅**: tiktoken을 사용한 정확한 토큰 수 계산  
✅ **필터링 지원**: occupation, intent 등 메타데이터 필터링  
✅ **Batch Processing**: 메모리 효율적인 배치 처리  
✅ **Foreign Key**: 데이터 무결성 보장  

## 🔄 데이터 재생성

기존 데이터 삭제 후 재생성:

```bash
# 데이터베이스 직접 삭제
docker exec -it interview_vectordb psql -U interview_user -d interview_db -c "
TRUNCATE TABLE qa.vec_a_index CASCADE;
TRUNCATE TABLE qa.vec_q_index CASCADE;
TRUNCATE TABLE qa.meta_df CASCADE;
"

# 재생성
python embed_data.py --input ../dataset/train_detailed_all.csv
```

## 📌 참고사항

- **임베딩 차원**: 3,072 (OpenAI text-embedding-3-large)
- **벡터 유사도**: Cosine similarity (`<=>` operator)
- **인덱스 타입**: IVFFlat (Q-Index: lists=50, A-Index: lists=200)
- **chunk_id 형식**: `DOC{doc_id:06d}` (예: DOC000001)
- **chunk_id_q 형식**: `DOC{doc_id:06d}_Q` (예: DOC000001_Q)
