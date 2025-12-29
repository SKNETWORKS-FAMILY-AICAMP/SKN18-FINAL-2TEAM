# RAG / LangGraph 변경 요약

> 기준 경로: `c:\dev\study\skn18_fianl-2team\SKN18-FINAL-2TEAM`

---

## 1. `graph/compile.py`

- LangGraph 전체 플로우 재구성:
  - `guardrail_input → classify_agent → memory_read → query_rewrite_agent → retriever_* → *_evaluate_chunk → web_search/evaluate_web → generate_answer → memory_write`.
- **rerank 노드 제거**:
  - 기존 `rerank` 노드를 그래프에서 삭제하고,
  - RAG 단계에서 바로 `*_evaluate_chunk_node`로 연결.


---

## 2. `graph/nodes/retriver.py`

- 역할: BIO/PROTOCOL 질문에 대한 **RAG + Cross-Encoder rerank**를 “retrieval 단계”에서 수행.
- 공통 처리:
  - `run_rag_retrieval_pipeline(question)` 호출로 `rewrite`, `retrieval_plan`, `embeddings`, `contexts` 등 수집.
  - `rewrite` 결과에서 엔티티를 추출해 `state["entities"]`에 저장.
  - `state["contexts"]`, `state["contexts_count"]`에 원본 컨텍스트 보관.
- Cross-Encoder 기반 rerank:
  - `rerank_with_cross_encoder(query=normalized_q, documents=contexts, top_k=min(20, len(contexts)) or 20)`.
  - rerank 결과를 `state["retrieval_results"]`에 저장.
  - 최고 score를 `state["retrieval_score"]`에 저장.
  - 실패 시에는 rerank 없이 `contexts`를 그대로 `retrieval_results`로 사용.
- 메타 정보:
  - `state["used_search_db"] = "graph_rag"`.
  - BIO/PROTOCOL 노드 각각 동일한 패턴으로 구현.

---

## 3. `graph/nodes/evaluate_chunk.py`

- BIO_Q / PROTOCOL_Q 공통 평가 로직 전면 정리.

### 3.1. 공통 헬퍼

- `_coarse_filter_prompt(question, entities)`:
  - 엔티티 등장 여부만 빠르게 보는 **Coarse Filter(Stage 1)** 프롬프트 생성.
- `_build_evaluation_prompt(question, context, entities=None)`:
  - 기전/전반적 관련성을 보는 **Stage 2 평가 프롬프트** 생성.
- `_parse_evaluation_result(result)`:
  - LLM 응답에서 `(is_relevant: bool, score: float, reason: str)` 추출.
  - 스코어가 없으면 `0.8/0.3` 기본값, 1.0 초과 시 0–1 스케일로 정규화.


### 3.2. `bio_evaluate_chunk_node`

- 입력:
  - `question`, `rewritten_query`, `retrieval_results`, `reranked_results`, `entities`.
- 로직:
  - `retrieval_results` 비어 있으면 관련성 `False`, 스코어 0.0, 선택 청크 없음.
  - 엔티티가 있으면 Coarse Filter Stage 1 실행:
    - 결과가 `"NO"`여도 **더 이상 early return 하지 않고** Stage 2를 계속 진행.
  - Stage 2:
    - rerank된 상위 N개(최대 5개)를 context로 묶어 LLM 평가.
    - 결과에 따라:
      - `state["chunk_is_relevant"]`
      - `state["chunk_relevance_score"]`
      - 관련성이 높을 때 상위 3개 청크 텍스트를 `state["selected_chunks"]`에 저장.


### 3.3. `protocol_evaluate_chunk_node`

- BIO 버전과 동일한 구조로 PROTOCOL_Q 전용 평가:
  - Coarse Filter Stage 1은 참고용만 사용 (엔티티 미등장이어도 Stage 2 계속).
  - Stage 2에서 상위 5개 컨텍스트 기반 평가 후, 관련 시 상위 3개 청크를 `selected_chunks`로 선택.

---



## 4. `graph/nodes/memory.py`

- 메모리 요약 및 DB 저장 로직 개선 + `chat_room_id` NOT NULL 오류 수정.

### 4.2. `memory_write_node(state)`

- 공통:
  - `conversation_id`를 가져와 **정수로 캐스팅하여** `chat_room_id`로 사용.
  - 변환 실패 또는 `None`이면:
    - 경고 로그 출력 후 **DB에 아무것도 쓰지 않고 반환** (NOT NULL 위반 방지).


---

## 5. `rag/retriver/rag_orchestrator.py`

- Hybrid/Entity RAG 오케스트레이션 튜닝.

### 5.1. Lucene 안전 문자열 변환

- `_to_safe_fulltext_query(text: str) -> str`:
  - Lucene fulltext 쿼리에서 문제되는 특수문자(`/ ? : { } [ ] ( ) ^ ~ *` 등)를 공백으로 치환.
  - `\`, `"`는 escape 처리.
  - 전체를 `"..."`로 감싸 **phrase query** 형태로 반환.
  - Neo4j `db.index.fulltext.queryNodes` 호출 시 사용.

### 5.2. Hybrid Search (`route_by_hybrid_search`)

- 입력: `question`, `embedding`, `domain="paper"` 등.
- 파라미터:
  - `k_seed` 기본값 **150**.
  - `k_final` 기본값 **100** (최종 chunk 수).
  - Hybrid용 내부 파라미터:
    - `k_vec=80`, `k_ft=80`, `rrf_k0=60`.
- 공통 Hybrid 파이프라인:
  - 각 도메인(paper/protocol/clinical)에 대해 `HY_*_CHUNK_DUAL_RRF` 쿼리 호출.
- **must_terms fallback** 추가:
  - 초기 검색 결과가 비어 있고 `must_terms`가 있으면:
    - `must_terms=[]`로 완화한 `relaxed_params`로 **한 번 더 HY 쿼리 실행**.
  - 두 번째도 없으면 빈 리스트 반환.

### 5.3. Entity 기반 Search (`route_by_entity`)

- `_to_safe_fulltext_query`로 엔티티 검색 문자열 정제.
- 도메인/트랙(T1/T3/T4)에 따라 PAPER/PROTOCOL/CLINICAL/KG 셀 쿼리 호출 (구조 정리).

---

## 6. `rag/retriver/rag_queries.py`

- Hybrid RRF 쿼리 및 LIMIT 상향 조정.

### 6.1. Hybrid RRF 쿼리 (`HY_*_CHUNK_DUAL_RRF`)

- `HY_PAPER_CHUNK_DUAL_RRF`, `HY_PROTOCOL_CHUNK_DUAL_RRF`, `HY_CLINICAL_CHUNK_DUAL_RRF`:
  - 벡터/풀텍스트 각각 상위 `k_vec`, `k_ft`까지 자른 뒤 rank/score를 합치는 구조.
  - 최종 `hy_score` 계산 로직 정리:
    - `(coalesce(vec_score, 0.0) + coalesce(ft_score, 0.0)) AS hy_score`.
- LIMIT 조정:
  - 세 쿼리 모두 `LIMIT coalesce($k, **120**)`로 상향 (기존 80 → 120 수준).

### 6.2. 기타 연관 쿼리

- Vector / Fulltext 단일 연산 쿼리는 그대로 두되, Hybrid 쿼리와 일관되게 `k` 관련 파라미터(80, 120 등)를 맞춤.

---

## 7. `graph/test/ask_v2.py`

- LangGraph 테스트 스크립트에 **질문별 CSV 로깅** 기능 추가.

### 7.1. CSV 헤더 정의 (`LOG_HEADER`)

- `timestamp, conversation_id, user_id, question`
- `case_type, final_answer`
- `used_search_db, used_web_search`
- `selected_chunks_count, web_selected_chunks_count`
- `entities`
- `rag_rerank_chunks_preview`
- `chunk_is_relevant, chunk_relevance_score`
- `evaluate_chunks_preview`
- `error`

### 7.2. 청크 프리뷰 유틸

- `_preview_chunks(chunks, max_items=3, max_len=120)`:
  - dict이면 `content → text → str(ch)` 순으로 텍스트 추출.
  - 최대 3개, 120자 제한, `" || "` 구분자로 한 줄 요약 문자열 생성.

### 7.3. 실행 결과 → 로그 레코드 변환

- `append_log_row(question, conversation_id, user_id, result, error="")`:
  - 정상 실행:
    - state에서 모든 필드 추출해 dict 구성.
    - `retrieval_results` 상위 3개로 `rag_rerank_chunks_preview`.
    - `selected_chunks` 상위 3개로 `evaluate_chunks_preview`.
    - `entities` 리스트는 `"|"` join.
    - `error`는 빈 문자열.
  - 예외:
    - `case_type="ERROR"`로 기록, 나머지는 기본값/빈값 + `error`에 메시지.

### 7.4. CSV 파일 기록

- `append_row_to_csv(row)`:
  - 파일 경로: `graph/test/ask_v2_logs.csv`.
  - 없으면 헤더 먼저 쓰고, 이후 질문마다 한 줄씩 append.
  - `encoding="utf-8"`, `newline=""`.

### 7.5. 워크플로 실행 루프 연동

- `run_workflow_test`:
  - `app.invoke(initial_state)` 실행 후 결과 요약 출력.
  - 성공/실패 모두 `append_log_row` → `append_row_to_csv` 호출로 로그 누적.
- 메인 루프:
  - 사용자가 입력하는 **각 질문마다** 하나의 CSV 레코드가 추가되도록 변경.

---
