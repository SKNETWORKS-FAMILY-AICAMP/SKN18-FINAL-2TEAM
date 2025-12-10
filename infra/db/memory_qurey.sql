/* ===========================================
   MEMORY DB 조회용 통합 SQL 파일
   - Bio RAG / Simulation / Protocol 등 CASE 기반 메모리 구조
   - conversation_id 기준으로 메모리 조회
   =========================================== */

/* -------------------------------------------
   1) 특정 채팅방(conversation_id)의 전체 Memory 조회
-------------------------------------------- */
SELECT *
FROM conversation_memory
WHERE conversation_id = :conversation_id;


/* -------------------------------------------
   2) 특정 CASE의 히스토리만 조회
      - 사용 예: classifier가 후속 질문인지 판단할 때
-------------------------------------------- */
SELECT no_relation
FROM conversation_memory
WHERE conversation_id = :conversation_id;

SELECT simulation_q
FROM conversation_memory
WHERE conversation_id = :conversation_id;

SELECT inference_q
FROM conversation_memory
WHERE conversation_id = :conversation_id;

SELECT bio_q
FROM conversation_memory
WHERE conversation_id = :conversation_id;

SELECT protocal_q
FROM conversation_memory
WHERE conversation_id = :conversation_id;


/* -------------------------------------------
   3) Slot Memory(핵심 구조화 정보)만 조회
-------------------------------------------- */
SELECT 
    last_case,
    last_question,
    latest_keywords,
    topic,
    entities,
    context_window
FROM conversation_memory
WHERE conversation_id = :conversation_id;


/* -------------------------------------------
   4) 가장 최근 업데이트된 대화  N개만 조회
      - 리턴된 JSON 배열의 끝쪽 요소(가장 최근)에서 추출
-------------------------------------------- */
SELECT jsonb_array_elements(no_relation) AS history
FROM conversation_memory
WHERE conversation_id = :conversation_id;

SELECT jsonb_array_elements(bio_q) AS history
FROM conversation_memory
WHERE conversation_id = :conversation_id;


/* -------------------------------------------
   5) 특정 user_id가 가진 모든 conversation_id 조회
      - 해당 유저의 전체 대화방 Memory 리스트
-------------------------------------------- */
SELECT conversation_id, updated_at
FROM conversation_memory
WHERE user_id = :user_id
ORDER BY updated_at DESC;


/* -------------------------------------------
   6) Memory 존재 여부 확인 (대화 첫 메시지인지 판단)
-------------------------------------------- */
SELECT EXISTS (
    SELECT 1
    FROM conversation_memory
    WHERE conversation_id = :conversation_id
);


/* -------------------------------------------
   7) Memory 삭제 (예: 세션 초기화)
-------------------------------------------- */
DELETE FROM conversation_memory
WHERE conversation_id = :conversation_id;


/* -------------------------------------------
   8) 오래된 Memory 자동 삭제 (30일 이전 기록)
-------------------------------------------- */
DELETE FROM conversation_memory
WHERE updated_at < NOW() - INTERVAL '30 days';
