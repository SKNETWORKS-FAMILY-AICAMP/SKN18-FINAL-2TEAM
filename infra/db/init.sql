-- 테이블/인덱스 초기 스키마

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tb_vector (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB NOT NULL
);

-- (선택) 기본 계정/권한
-- CREATE USER skn WITH PASSWORD 'sknpass';
-- GRANT ALL PRIVILEGES ON DATABASE skn_project TO skn;

