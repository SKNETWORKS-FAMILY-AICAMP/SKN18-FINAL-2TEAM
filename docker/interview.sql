-- file: vector_init.sql
-- Purpose: Initialize pgvector with separated meta_df and vector indexes

-- 1) Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2) Create dedicated schema
CREATE SCHEMA IF NOT EXISTS interview;

-- ============================================
-- META TABLE: meta_df (표시/필터용)
-- ============================================
CREATE TABLE IF NOT EXISTS interview.meta_df (
    doc_id INTEGER PRIMARY KEY,                    -- sample_id를 그대로 PK로
    occupation VARCHAR(50),
    gender VARCHAR(20),
    age_range VARCHAR(20),
    experience VARCHAR(20),
    answer_intent_category VARCHAR(100),
    answer_emotion_expression VARCHAR(100),
    answer_emotion_category VARCHAR(50),
    question_intent VARCHAR(100),
    question_text TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    content_combined TEXT NOT NULL,              
    tokens_answer INTEGER,
    tokens_combined INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interview.vector (
    chunk_id   VARCHAR(120) PRIMARY KEY,           -- 예: DOC000123_C01
    doc_id     INTEGER NOT NULL REFERENCES interview.meta_df(doc_id) ON DELETE CASCADE,
    chunk_seq  SMALLINT NOT NULL DEFAULT 1,        -- 1,2,... (문서 내 순서)
    start_char INTEGER,                            -- 선택: 원문 내 시작 위치
    end_char   INTEGER,                            -- 선택: 원문 내 끝 위치
    emb_model  TEXT NOT NULL,
    emb_dim    INT  NOT NULL,
    embedding  vector(3072) NOT NULL,              -- text-embedding-3-large
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (doc_id, chunk_seq),                    -- 문서 내 중복 방지
    CHECK (chunk_seq >= 1)
);


-- 메타 필터용 인덱스(있으면 좋음)
CREATE INDEX IF NOT EXISTS meta_df_occupation_idx ON interview.meta_df(occupation);
CREATE INDEX IF NOT EXISTS meta_df_question_intent_idx ON interview.meta_df(question_intent);

-- 조인/필터 최적화
CREATE INDEX IF NOT EXISTS vector_doc_id_idx ON interview.vector(doc_id);
CREATE INDEX IF NOT EXISTS vector_model_idx ON interview.vector(emb_model);

-- 벡터 인덱스
CREATE INDEX IF NOT EXISTS interview_vector_cosine_idx ON interview.vector
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- ============================================
-- PERMISSIONS
-- ============================================
-- Grant permissions to skn4th user (or create interview_user if needed)
GRANT USAGE ON SCHEMA qa TO skn4th;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA qa TO skn4th;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA qa TO skn4th;