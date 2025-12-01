## 1. 기본 설정
- `CREATE EXTENSION IF NOT EXISTS vector;` → pgvector 확장 활성화
- `CREATE SCHEMA IF NOT EXISTS qa;` → 모든 객체가 위치할 스키마 생성

---

## 2. 메타데이터 계층 (텍스트 + 라벨)
질문/답변 텍스트와 의도·감정 라벨 등 사람이 읽을 수 있는 정보를 관리합니다.

### 2.1 주요 테이블: `qa.meta_df`
| 컬럼 | 설명 |
|------|------|
| `chunk_id` (PK) | 질문/답변 조각마다 부여하는 유니크 ID (예: `DOC123_A_0001`) |
| `doc_id` | 원본 문서/샘플 ID (`sample_id`와 동일) |
| `occupation`, `gender`, `age_range`, `experience` | 화자 프로필 정보 |
| `question_text`, `question_text_norm` | 질문 원문 및 정규화 텍스트 |
| `answer_text` | 답변 원문 |
| `question_intent` | 질문 의도 라벨 |
| `answer_intent_category`, `answer_emotion_expression`, `answer_emotion_category` | 답변 의도/감정 라벨 |
| `content_combined` | 질문+답변 결합 텍스트 (선택) |
| `tokens_answer`, `tokens_combined` | 토큰 수 (선택) |
| `group_id` | 원하는 그룹핑 키 (선택) |

### 2.2 메타 함수
- `qa.upsert_metadata(...)` → `chunk_id` 기준으로 메타 정보를 insert/update

---

## 3. 임베딩 계층 (벡터 + 검색)
고차원 임베딩 벡터와 벡터 인덱스를 관리합니다.

### 3.1 통합 테이블: `qa.interview_embeddings`
| 컬럼 | 설명 |
|------|------|
| `id` (PK) | 내부 일련번호 |
| `doc_id`, `chunk_id` (UNIQUE) | 메타 정보와 연결되는 키 |
| `part` | `'Q'`, `'A'`, `'QA'` 중 하나 |
| `text` | 임베딩 대상 텍스트 |
| `occupation`, `gender`, `age_range`, `experience` | 화자 프로필 |
| `question_intent`, `answer_intent_category` | 라벨 |
| `answer_emotion_expression`, `answer_emotion_category` | 감정 라벨 |
| `embedding vector(3072)` | 텍스트 임베딩 (예: text-embedding-3-large 기준 3072차원) |
| `created_at` | 생성 시각 |

**인덱스**
- embedding 컬럼에 대한 IVFFLAT 인덱스 (전역 + Q/A 파트별)
- 필터용 B-tree 인덱스: `(doc_id, part)`, `occupation`, `question_intent`, `answer_intent_category`
- (선택) HNSW 인덱스

### 3.2 Q/A 분리 테이블
- `qa.vec_q_index`: 질문 벡터 저장 (`chunk_id_q`, `chunk_id`, `emb_model`, `embedding` 등)
- `qa.vec_a_index`: 답변 벡터 저장 (`chunk_id`, `emb_model`, `embedding` 등)

### 3.3 임베딩 함수
| 함수 | 설명 |
|------|------|
| `qa.upsert_q_embedding(...)` | 질문 벡터 upsert (`qa.vec_q_index`)
| `qa.insert_a_embedding(...)` | 답변 벡터 insert (`qa.vec_a_index`)

### 3.4 검색 함수
| 함수 | 기능 |
|------|------|
| `qa.search_questions(...)` | 질문 임베딩 + 메타 필터 검색 (occupation, question_intent)
| `qa.search_answers(...)` | 답변 임베딩 + 메타 필터 검색 (occupation, answer_intent_category)
| `qa.search_hybrid(...)` | 질문/답변 결과를 혼합하여 반환

---

## 4. 인덱스 & 튜닝 팁
- IVFFLAT 인덱스: 전역/파트별 리스트 수(lists) 조절
- B-tree 인덱스: 메타 필터 최적화
- 런타임 옵션 예: `SET ivfflat.probes = 10;`

---

## 5. 권한 & 유지보수
- 스키마/테이블 권한 부여 예시는 주석 참고
- `ANALYZE qa.meta_df`, `ANALYZE qa.vec_q_index`, `ANALYZE qa.vec_a_index` 권장
- 주기적으로 벡터 인덱스/통계 재생성

---

## 6. 전체 흐름 요약
1. 메타 정보 -> `qa.meta_df` upsert
2. 임베딩 -> `qa.interview_embeddings` 또는 질문/답변 전용 인덱스에 적재
3. 검색 -> 제공된 함수로 벡터 검색 + 메타 필터링 수행
