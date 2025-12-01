-- db/init.sql

-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================
-- 1. 섹션 메타 정보 테이블
--    (section.csv 의 메타 컬럼 저장)
-- ===========================
CREATE TABLE IF NOT EXISTS pmc_section_meta (
    section_id      BIGINT PRIMARY KEY,  -- pmc_processing_utils.gen_section_id() 결과
    pmcid           TEXT NOT NULL,
    pmid            TEXT,
    topic_category  TEXT,
    path            TEXT,
    section_category TEXT,
    article_category TEXT,
    fig_ids         TEXT,
    table_ids       TEXT,
    ref_ids         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 (검색용)
CREATE INDEX IF NOT EXISTS idx_pmc_section_meta_pmcid
    ON pmc_section_meta (pmcid);
CREATE INDEX IF NOT EXISTS idx_pmc_section_meta_pmid
    ON pmc_section_meta (pmid);
CREATE INDEX IF NOT EXISTS idx_pmc_section_meta_topic
    ON pmc_section_meta (topic_category);


-- ===========================
-- 2. 섹션 청크 + 임베딩 테이블
--    (pmc_vector.csv 내용)
-- ===========================
CREATE TABLE IF NOT EXISTS pmc_section_chunk (
    chunk_id    TEXT PRIMARY KEY,             -- SEC{section_id}_Cxx
    section_id  BIGINT NOT NULL REFERENCES pmc_section_meta(section_id)
                    ON DELETE CASCADE,
    chunk_seq   INTEGER NOT NULL,             -- 청크 순번 (1,2,3…)
    start_char  INTEGER,
    end_char    INTEGER,
    emb_model   TEXT,
    emb_dim     INTEGER,
    text_chunk  TEXT,
    embedding   vector(1536)                  -- text-embedding-3-small
);

-- section_id + chunk_seq 인덱스
CREATE INDEX IF NOT EXISTS idx_pmc_section_chunk_section_seq
    ON pmc_section_chunk (section_id, chunk_seq);

-- 벡터 검색용 인덱스 (cosine distance, 필요 시 조정)
-- 대용량이면 lists 값 키워줘도 됨
CREATE INDEX IF NOT EXISTS idx_pmc_section_chunk_embedding
    ON pmc_section_chunk
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
