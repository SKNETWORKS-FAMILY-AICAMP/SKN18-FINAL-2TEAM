-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;


-- ===========================
-- 3. article_section_embedding (새 벡터 테이블)
-- ===========================
CREATE TABLE IF NOT EXISTS article_section_embedding (
    chunk_id    TEXT PRIMARY KEY,
    section_id  TEXT NOT NULL,
    chunk_seq   INTEGER NOT NULL,
    start_char  INTEGER,
    end_char    INTEGER,
    emb_model   TEXT,
    emb_dim     INTEGER,
    text_chunk  TEXT,
    embedding   vector(1536)   -- 코드에서 expected_article_dim=1536
);

-- 필요하면 section_id + chunk_seq 인덱스
CREATE INDEX IF NOT EXISTS idx_article_section_embedding_section_seq
    ON article_section_embedding (section_id, chunk_seq);

-- 벡터 검색용 인덱스
CREATE INDEX IF NOT EXISTS idx_article_section_embedding_embedding
    ON article_section_embedding
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ===========================
-- 4. protocol_embedding (새 벡터 테이블)
-- ===========================
CREATE TABLE IF NOT EXISTS protocol_embedding (
    protocol_id BIGINT NOT NULL,
    url         TEXT,
    title       TEXT,
    chunking_id TEXT PRIMARY KEY,
    text        TEXT,
    embedding   vector(1024)   -- 코드에서 expected_protocol_dim=1024
);

CREATE INDEX IF NOT EXISTS idx_protocol_embedding_protocol
    ON protocol_embedding (protocol_id);

CREATE INDEX IF NOT EXISTS idx_protocol_embedding_embedding
    ON protocol_embedding
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
