"""
Protocols.io table metadata CSV를 PostgreSQL에 업서트한다.

입력:
  data/entities/protocols/success/protocol_table_{keyword}.csv

출력:
  PostgreSQL ts_protocol_table_metadata
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Generator
from datetime import datetime

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.etl.common.db_connection import get_connection
from rag.etl.step01_ingest.modules import schedule_store

# =========================
# 설정
# =========================

TABLE_NAME = "ts_protocol_table_metadata"
BATCH_SIZE = int(os.getenv("PROTOCOL_TABLE_UPSERT_BATCH_SIZE", "1000"))


# =========================
# DB
# =========================

def ensure_table() -> None:
    """table metadata 테이블 생성"""
    with get_connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    table_id TEXT UNIQUE NOT NULL,
                    chunk_id TEXT NOT NULL,
                    table_json JSONB NOT NULL
                );
            """)
        conn.commit()

    print(f"[UPSERT][TableMetadata] 테이블 확인 완료: {TABLE_NAME}")


# =========================
# CSV Loader
# =========================

def iter_table_rows(csv_path: Path) -> Generator[dict, None, None]:
    required_cols = {"table_id", "chunk_id", "table_json"}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"CSV 헤더 없음: {csv_path}")

        missing = required_cols - set(reader.fieldnames)
        if missing:
            raise ValueError(f"필수 컬럼 누락: {missing}")

        for row in reader:
            yield row


# =========================
# UPSERT
# =========================

def upsert_table_csv(csv_path: Path) -> None:
    print(f"[UPSERT][TableMetadata] CSV 처리 시작: {csv_path}")

    with get_connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            buffer = []
            total = 0

            for row in iter_table_rows(csv_path):
                table_id = row["table_id"]
                chunk_id = row["chunk_id"]
                table_json = json.loads(row["table_json"])

                buffer.append((
                    table_id,
                    chunk_id,
                    json.dumps(table_json, ensure_ascii=False),
                ))

                if len(buffer) >= BATCH_SIZE:
                    _execute_batch(cur, buffer)
                    total += len(buffer)
                    buffer.clear()
                    print(f"[UPSERT][TableMetadata] {total} rows upserted", flush=True)

            if buffer:
                _execute_batch(cur, buffer)
                total += len(buffer)

            conn.commit()

    print(f"[UPSERT][TableMetadata] ✅ 업서트 완료: {total} rows")

def get_today_table_dir() -> Path:
    now = datetime.now()
    return (
        Path(__file__).resolve().parents[3]
        / "data/entities/protocols/success"
        / f"year={now.year:04d}"
        / f"month={now.month:02d}"
        / f"day={now.day:02d}"
        / "stage=table_metadata"
    )

def _execute_batch(cur, rows: list[tuple]) -> None:
    cur.executemany(
        f"""
        INSERT INTO {TABLE_NAME} (
            table_id,
            chunk_id,
            table_json
        )
        VALUES (%s, %s, %s::jsonb)
        ON CONFLICT (table_id)
        DO UPDATE SET
            chunk_id = EXCLUDED.chunk_id,
            table_json = EXCLUDED.table_json;
        """,
        rows,
    )


# =========================
# Runner
# =========================

def run() -> None:
    ensure_table()

    schedule_store.ensure_table()
    keywords = schedule_store.get_embedded_keywords()

    base_dir = get_today_table_dir()

    if not base_dir.exists():
        print(f"[UPSERT][TableMetadata] ⚠️ table 디렉토리가 없습니다: {base_dir}")
        return

    for keyword in keywords:
        csv_path = base_dir / f"protocol_tables_{keyword}.csv"

        if not csv_path.exists():
            print(f"[UPSERT][TableMetadata] ⚠️ 파일 없음: {csv_path}")
            continue

        upsert_table_csv(csv_path)

    print("[UPSERT][TableMetadata] 🎉 모든 table metadata 처리 완료!")


if __name__ == "__main__":
    run()