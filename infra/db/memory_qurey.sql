/* ===========================================
   MEMORY DB 조회용 통합 SQL 파일
   - 단순화된 3컬럼 구조 (case_type, full_response, summary)
   - chat_room_id 기준으로 메모리 조회
   =========================================== */

/* -------------------------------------------
   1) 특정 채팅방(chat_room_id)의 전체 Memory 조회
-------------------------------------------- */
SELECT *
FROM t_memory
WHERE chat_room_id = :chat_room_id
ORDER BY created_at DESC;


/* -------------------------------------------
   2) 특정 케이스 타입의 히스토리만 조회
      - 사용 예: classifier가 후속 질문인지 판단할 때
-------------------------------------------- */
-- SIMULATION_Q 대화만 조회
SELECT chat_sid, original_question, summary, full_response, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id 
  AND case_type = 'SIMULATION_Q'
ORDER BY created_at DESC;

-- INFERENCE_Q 대화만 조회
SELECT chat_sid, original_question, summary, full_response, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id 
  AND case_type = 'INFERENCE_Q'
ORDER BY created_at DESC;

-- BIO_Q 대화만 조회
SELECT chat_sid, original_question, summary, full_response, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id 
  AND case_type = 'BIO_Q'
ORDER BY created_at DESC;

-- PROTOCOL_Q 대화만 조회
SELECT chat_sid, original_question, summary, full_response, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id 
  AND case_type = 'PROTOCOL_Q'
ORDER BY created_at DESC;


/* -------------------------------------------
   3) 핵심 메타 정보만 조회
-------------------------------------------- */
SELECT 
    chat_sid,
    case_type,
    original_question,
    latest_keywords,
    topic,
    entities,
    referenced_memory_count,
    created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id
ORDER BY created_at DESC;


/* -------------------------------------------
   4) 가장 최근 N개의 대화만 조회
-------------------------------------------- */
-- 전체 최근 3개
SELECT chat_sid, case_type, original_question, summary, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id
ORDER BY created_at DESC
LIMIT 3;

-- 특정 케이스 타입의 최근 3개
SELECT chat_id, original_question, summary, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id 
  AND case_type = :case_type
ORDER BY created_at DESC
LIMIT 3;


/* -------------------------------------------
   5) 특정 user_id가 가진 모든 chat_room_id 조회
      - 해당 유저의 전체 대화방 Memory 리스트
-------------------------------------------- */
SELECT DISTINCT chat_room_id, MAX(updated_at) as last_updated
FROM t_memory
WHERE user_id = :user_id
GROUP BY chat_room_id
ORDER BY last_updated DESC;


/* -------------------------------------------
   6) Memory 존재 여부 확인 (대화 첫 메시지인지 판단)
-------------------------------------------- */
SELECT EXISTS (
    SELECT 1
    FROM t_memory
    WHERE chat_room_id = :chat_room_id
);


/* -------------------------------------------
   7) Memory 삭제 (예: 세션 초기화)
-------------------------------------------- */
-- 특정 채팅방의 모든 대화 삭제
DELETE FROM t_memory
WHERE chat_room_id = :chat_room_id;

-- 특정 대화(chat_sid) 하나만 삭제
DELETE FROM t_memory
WHERE chat_sid = :chat_sid;


/* -------------------------------------------
   8) 오래된 Memory 자동 삭제 (30일 이전 기록)
-------------------------------------------- */
DELETE FROM t_memory
WHERE updated_at < NOW() - INTERVAL '30 days';


/* -------------------------------------------
   9) 케이스 타입별 통계 조회
-------------------------------------------- */
SELECT 
    case_type,
    COUNT(*) as conversation_count,
    AVG(LENGTH(full_response)) as avg_response_length,
    MAX(created_at) as last_conversation
FROM t_memory
WHERE chat_room_id = :chat_room_id
GROUP BY case_type
ORDER BY conversation_count DESC;


/* -------------------------------------------
   10) 요약본만 조회 (메모리 효율적)
-------------------------------------------- */
SELECT chat_sid, case_type, original_question, summary, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id
ORDER BY created_at DESC;


/* -------------------------------------------
   11) 원본 답변 조회 (필요시에만)
-------------------------------------------- */
SELECT chat_sid, case_type, original_question, full_response, created_at
FROM t_memory
WHERE chat_sid = :chat_sid;


/* -------------------------------------------
   12) 메모리 참조 통계 조회
       - 답변 생성 시 얼마나 많은 이전 대화를 참고했는지 분석
-------------------------------------------- */
SELECT 
    case_type,
    AVG(referenced_memory_count) as avg_referenced,
    MAX(referenced_memory_count) as max_referenced,
    MIN(referenced_memory_count) as min_referenced
FROM t_memory
WHERE chat_room_id = :chat_room_id
GROUP BY case_type;


/* -------------------------------------------
   13) 메모리를 많이 참고한 대화 조회 (복잡한 질문 분석)
-------------------------------------------- */
SELECT chat_sid, case_type, original_question, referenced_memory_count, created_at
FROM t_memory
WHERE chat_room_id = :chat_room_id
  AND referenced_memory_count > 0
ORDER BY referenced_memory_count DESC, created_at DESC
LIMIT 10;
