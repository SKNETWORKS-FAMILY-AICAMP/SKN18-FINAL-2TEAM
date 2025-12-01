-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS major_vector_chunks (
    id BIGSERIAL PRIMARY KEY,
    major_seq TEXT NOT NULL,
    major TEXT NOT NULL,
    salary TEXT,
    employment TEXT,
    job TEXT,
    qualifications TEXT,
    universities TEXT,
    embedding VECTOR(3072) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);