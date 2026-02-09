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
    embedding   vector(1536)   -- 코드에서 expected_article_dim = 1536
);

-- 필요하면 section_id + chunk_seq 인덱스
CREATE INDEX IF NOT EXISTS idx_article_section_embedding_section_seq
    ON article_section_embedding (section_id, chunk_seq);

-- 벡터 검색용 HNSW 인덱스 (cosine)
CREATE INDEX IF NOT EXISTS idx_article_section_embedding_hnsw
    ON article_section_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ===========================
-- 4. protocol_embedding (새 벡터 테이블)
-- ===========================
CREATE TABLE IF NOT EXISTS protocol_embedding (
    protocol_id BIGINT NOT NULL,
    url         TEXT,
    title       TEXT,
    chunking_id TEXT PRIMARY KEY,
    text        TEXT,
    embedding   vector(1024)   -- 코드에서 expected_protocol_dim = 1024
);

CREATE INDEX IF NOT EXISTS idx_protocol_embedding_protocol
    ON protocol_embedding (protocol_id);

-- 벡터 검색용 HNSW 인덱스 (cosine)
CREATE INDEX IF NOT EXISTS idx_protocol_embedding_hnsw
    ON protocol_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ===========================
-- 5. article_table_emb (테이블 캡션 임베딩)
-- ===========================
CREATE TABLE IF NOT EXISTS article_table_emb (
    table_id            TEXT PRIMARY KEY,
    pmcid               TEXT,
    pmid                TEXT,
    table_content       JSONB,
    table_caption       TEXT,
    table_url           TEXT,
    table_caption_emb   vector(1536)
);

-- pmcid 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_article_table_emb_pmcid
    ON article_table_emb (pmcid);

-- pmid 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_article_table_emb_pmid
    ON article_table_emb (pmid);

-- 벡터 검색용 HNSW 인덱스 (cosine)
CREATE INDEX IF NOT EXISTS idx_article_table_emb_hnsw
    ON article_table_emb
    USING hnsw (table_caption_emb vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
