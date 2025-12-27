#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pgvector 임베딩 로더.

- article_section_embedding.csv
- protocol_embedding.csv

두 CSV를 읽어서 Postgres(pgvector) 테이블에 업서트한다.

외부 엔트리 포인트는 `run(embeddings_dir: str)` 하나만 사용한다.
"""

import os
import csv
from pathlib import Path
from typing import Set, Dict, Any, Generator, List

try:
    import psycopg2  # psycopg2가 설치된 환경(레거시) 우선 사용
    from psycopg2.extras import execute_batch

    def _pg_connect(**kwargs):
        return psycopg2.connect(**kwargs)

except ModuleNotFoundError:
    import psycopg  # psycopg v3 (requirements.txt 에 명시된 기본 드라이버)

    def execute_batch(cur, query: str, rows):
        """
        psycopg3에는 execute_batch helper가 없어 executemany로 대체한다.
        """
        cur.executemany(query, rows)

    def _pg_connect(**kwargs):
        return psycopg.connect(**kwargs)


# ─────────────────────────────────────
# 0) CSV 유틸
# ─────────────────────────────────────

def load_existing_chunk_ids(out_path: Path) -> Set[str]:
    """
    [공용 메타데이터 로드 함수]
    이미 생성된 CSV 파일에서 chunk_id를 모두 읽어서 반환합니다.
    (필요 없으면 안 써도 됨)
    """
    if not out_path.exists():
        return set()

    existing_ids: Set[str] = set()
    try:
        with out_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "chunk_id" not in reader.fieldnames:
                return set()
            for row in reader:
                cid = row.get("chunk_id")
                if cid:
                    existing_ids.add(str(cid))
    except Exception:
        return set()
    return existing_ids


def iter_chunk_csv_rows(csv_path: Path, required_cols: List[str]) -> Generator[Dict[str, Any], None, None]:
    """
    [임베딩 데이터 노드 함수]
    chunk CSV 파일을 row-by-row로 읽는 제너레이터입니다.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Chunk CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as inf:
        reader = csv.DictReader(inf)
        # 헤더 검증
        missing = [c for c in required_cols if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Chunk CSV에 필요한 컬럼이 없습니다: {missing}")

        for r in reader:
            yield r


def infer_vector_dim_from_str(vec_str: str) -> int:
    """
    "[0.1, 0.2, ...]" / "0.1,0.2,..." 같은 문자열에서 실제 원소 개수를 셉니다.
    """
    if vec_str is None:
        return 0
    s = vec_str.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    if not s.strip():
        return 0
    parts = s.split(",")
    parts = [p.strip() for p in parts if p.strip() != ""]
    return len(parts)


# ─────────────────────────────────────
# 1) DB 연결 헬퍼
# ─────────────────────────────────────

def get_pg_conn():
    """
    환경변수 기반 Postgres 연결.

    기본값:
      host=localhost, port=5432, db=sknfinaldb, user=root, password=root1234
    """
    conn = _pg_connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "sknfinaldb"),
        user=os.getenv("POSTGRES_USER", "root"),
        password=os.getenv("POSTGRES_PASSWORD", "root1234"),
    )
    conn.autocommit = False
    return conn


# ─────────────────────────────────────
# 2) article_section_embedding 로더
# ─────────────────────────────────────

def load_article_section_embedding(csv_path: Path, expected_dim: int, batch_size: int = 1000):
    """
    CSV (chunk_id, section_id, chunk_seq, start_char, end_char,
         emb_model, emb_dim, text_chunk, embedding)
    → article_section_embedding 테이블로 적재
    """
    required_cols = [
        "chunk_id",
        "section_id",
        "chunk_seq",
        "start_char",
        "end_char",
        "emb_model",
        "emb_dim",
        "text_chunk",
        "embedding",
    ]

    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        rows_buffer = []
        row_idx = 0

        for row in iter_chunk_csv_rows(csv_path, required_cols):
            row_idx += 1

            # CSV emb_dim 검증
            emb_dim_csv = int(row["emb_dim"])
            if emb_dim_csv != expected_dim:
                raise ValueError(
                    f"[article_section_embedding] CSV emb_dim({emb_dim_csv}) != expected_dim({expected_dim}) "
                    f"at row {row_idx} (chunk_id={row.get('chunk_id')})"
                )

            # embedding 문자열 길이 검증
            embedding_str = row["embedding"]
            vec_len = infer_vector_dim_from_str(embedding_str)
            if vec_len != expected_dim:
                raise ValueError(
                    f"[article_section_embedding] embedding vector length({vec_len}) != expected_dim({expected_dim}) "
                    f"at row {row_idx} (chunk_id={row.get('chunk_id')})"
                )

            # 타입 캐스팅
            section_id = row["section_id"]  # ← 더 이상 int()로 변환하지 않음
            chunk_seq = int(row["chunk_seq"])
            start_char = int(row["start_char"]) if row["start_char"] not in (None, "",) else None
            end_char = int(row["end_char"]) if row["end_char"] not in (None, "",) else None

            rows_buffer.append((
                row["chunk_id"],
                section_id,
                chunk_seq,
                start_char,
                end_char,
                row["emb_model"],
                emb_dim_csv,
                row["text_chunk"],
                embedding_str,
            ))


            if len(rows_buffer) >= batch_size:
                execute_batch(
                    cur,
                    """
                    INSERT INTO article_section_embedding (
                        chunk_id,
                        section_id,
                        chunk_seq,
                        start_char,
                        end_char,
                        emb_model,
                        emb_dim,
                        text_chunk,
                        embedding
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    rows_buffer,
                )
                rows_buffer.clear()

        if rows_buffer:
            execute_batch(
                cur,
                """
                INSERT INTO article_section_embedding (
                    chunk_id,
                    section_id,
                    chunk_seq,
                    start_char,
                    end_char,
                    emb_model,
                    emb_dim,
                    text_chunk,
                    embedding
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::vector
                )
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                rows_buffer,
            )

        conn.commit()
        print(f"[article_section_embedding] Load complete from {csv_path} (expected_dim={expected_dim})")

    except Exception as e:
        conn.rollback()
        print(f"[article_section_embedding] ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────
# 3) protocol_embedding 로더
# ─────────────────────────────────────

def load_protocol_embedding(csv_path: Path, expected_dim: int, batch_size: int = 1000):
    """
    CSV (protocol_id, url, title, chunking_id, text, embedding)
    → protocol_embedding 테이블로 적재
    """
    required_cols = [
        "protocol_id",
        "url",
        "title",
        "chunking_id",
        "text",
        "embedding",
    ]

    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        rows_buffer = []
        row_idx = 0

        for row in iter_chunk_csv_rows(csv_path, required_cols):
            row_idx += 1

            embedding_str = row["embedding"]
            vec_len = infer_vector_dim_from_str(embedding_str)
            if vec_len != expected_dim:
                raise ValueError(
                    f"[protocol_embedding] embedding vector length({vec_len}) != expected_dim({expected_dim}) "
                    f"at row {row_idx} (chunking_id={row.get('chunking_id')})"
                )

            protocol_id = int(row["protocol_id"])

            rows_buffer.append((
                protocol_id,
                row["url"],
                row["title"],
                row["chunking_id"],
                row["text"],
                embedding_str,
            ))

            if len(rows_buffer) >= batch_size:
                execute_batch(
                    cur,
                    """
                    INSERT INTO protocol_embedding (
                        protocol_id,
                        url,
                        title,
                        chunking_id,
                        text,
                        embedding
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (chunking_id) DO NOTHING
                    """,
                    rows_buffer,
                )
                rows_buffer.clear()

        if rows_buffer:
            execute_batch(
                cur,
                """
                INSERT INTO protocol_embedding (
                    protocol_id,
                    url,
                    title,
                    chunking_id,
                    text,
                    embedding
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s::vector
                )
                ON CONFLICT (chunking_id) DO NOTHING
                """,
                rows_buffer,
            )

        conn.commit()
        print(f"[protocol_embedding] Load complete from {csv_path} (expected_dim={expected_dim})")

    except Exception as e:
        conn.rollback()
        print(f"[protocol_embedding] ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────
# 4) 외부에서 호출할 엔트리 포인트
# ─────────────────────────────────────

def run(embeddings_dir: str) -> None:
    """
    ETL 파이프라인용 엔트리 포인트.

    현재는 embeddings_dir 인자를 실제로 쓰지 않고,
    고정된 CSV 경로를 사용한다.
    """

    # 네가 하드코딩해 둔 CSV 경로들
    article_csv = Path(
        r"C:\dev\study\skn18_fianl-2team\final_2team\SKN18-FINAL-2TEAM\data\embeddings\article_embeddig_v2.csv"
    )
    protocol_csv = Path(
        r"C:\dev\study\skn18_fianl-2team\final_2team\SKN18-FINAL-2TEAM\data\embeddings\protocol_embedding.csv"
    )

    # 각 CSV마다 dim 지정 (필요하면 환경변수로도 오버라이드 가능)
    expected_article_dim = int(os.getenv("ARTICLE_EMB_DIM", "1536"))
    expected_protocol_dim = int(os.getenv("PROTOCOL_EMB_DIM", "1024"))

    print(f"[pgvector.run] embeddings_dir(arg)={embeddings_dir}")
    print(f"  - article CSV:  {article_csv} (dim={expected_article_dim})")
    print(f"  - protocol CSV: {protocol_csv} (dim={expected_protocol_dim})")

    if article_csv.exists():
        load_article_section_embedding(article_csv, expected_dim=expected_article_dim)
    else:
        print(f"[WARN] article_section_embedding CSV not found at {article_csv}, skip.")

    if protocol_csv.exists():
        load_protocol_embedding(protocol_csv, expected_dim=expected_protocol_dim)
    else:
        print(f"[WARN] protocol_embedding CSV not found at {protocol_csv}, skip.")


# ─────────────────────────────────────
# 5) 스크립트 직접 실행용 엔트리
# ─────────────────────────────────────

if __name__ == "__main__":
    import sys
    # 기본값은 ./data, 인자를 하나 주면 그걸 사용 (지금은 로그용으로만 사용)
    embeddings_dir = sys.argv[1] if len(sys.argv) > 1 else "./data"
    run(embeddings_dir)
