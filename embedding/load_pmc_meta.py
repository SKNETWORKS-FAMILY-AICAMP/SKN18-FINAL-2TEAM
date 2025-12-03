#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upsert PMC section metadata into Postgres `pmc_section_meta` table.

Usage examples (PowerShell):
    # Dry-run (no DB changes) - show counts
    python ./embedding/upsert_meta.py --input ./data/pmc_csv18/sections.csv

    # Execute upsert into local Postgres
    python ./embedding/upsert_meta.py --input ./data/pmc_csv18/sections.csv --pg-host localhost --pg-port 5432 --pg-db pmc_db --pg-user pmc --pg-password pmc1234 --commit

Options:
  --batch-size: number of rows per batch insert (default 500)
  --table: target table name (default: pmc_section_meta)
  --commit: actually execute DB writes; without it the script runs in dry-run mode

The script will look for these columns in the input CSV (case-sensitive):
  section_id, pmcid, pmid, topic_category, path, section_category, article_category,
  fig_ids, table_ids, ref_ids
Any missing columns will be treated as NULL.
"""
from pathlib import Path
import argparse
import csv
from typing import List, Dict, Any
import os

try:
    import psycopg2
    from psycopg2.extras import execute_values
except Exception:
    psycopg2 = None
try:
    # optional: load .env if present
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def read_rows(csv_path: Path) -> List[Dict[str, Any]]:
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def build_values_tuple(r: Dict[str, Any]) -> tuple:
    # Map expected columns. Convert section_id to int if possible.
    def get(k):
        v = r.get(k)
        if v is None or v == "":
            return None
        return v

    section_id_raw = get("section_id")
    try:
        section_id = int(section_id_raw) if section_id_raw is not None else None
    except Exception:
        section_id = section_id_raw

    return (
        section_id,
        get("pmcid"),
        get("pmid"),
        get("topic_category"),
        get("path"),
        get("section_category"),
        get("article_category"),
        get("fig_ids"),
        get("table_ids"),
        get("ref_ids"),
    )


def upsert_batches(conn, table: str, rows_tuples: List[tuple], batch_size: int = 500):
    cur = conn.cursor()
    insert_sql = f"""
    INSERT INTO {table}
      (section_id, pmcid, pmid, topic_category, path, section_category, article_category, fig_ids, table_ids, ref_ids)
    VALUES %s
    ON CONFLICT (section_id) DO UPDATE SET
      pmcid = EXCLUDED.pmcid,
      pmid = EXCLUDED.pmid,
      topic_category = EXCLUDED.topic_category,
      path = EXCLUDED.path,
      section_category = EXCLUDED.section_category,
      article_category = EXCLUDED.article_category,
      fig_ids = EXCLUDED.fig_ids,
      table_ids = EXCLUDED.table_ids,
      ref_ids = EXCLUDED.ref_ids
    """

    for i in range(0, len(rows_tuples), batch_size):
        batch = rows_tuples[i : i + batch_size]
        try:
            execute_values(cur, insert_sql, batch, page_size=batch_size)
            conn.commit()
        except Exception as e:
            print(f"Batch upsert failed: {e}")
            # fallback to per-row upsert to report problems
            per_sql = f"""
            INSERT INTO {table}
            (section_id, pmcid, pmid, topic_category, path, section_category, article_category, fig_ids, table_ids, ref_ids)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (section_id) DO UPDATE SET
            pmcid = EXCLUDED.pmcid,
            pmid = EXCLUDED.pmid,
            topic_category = EXCLUDED.topic_category,
            path = EXCLUDED.path,
            section_category = EXCLUDED.section_category,
            article_category = EXCLUDED.article_category,
            fig_ids = EXCLUDED.fig_ids,
            table_ids = EXCLUDED.table_ids,
            ref_ids = EXCLUDED.ref_ids
            """
            for t in batch:
                try:
                    cur.execute(per_sql, t)
                    conn.commit()
                except Exception as e2:
                    print(f"Row upsert failed for section_id={t[0]}: {e2}")
    cur.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="sections CSV path")
    ap.add_argument("--pg-host", help="Postgres host")
    ap.add_argument("--pg-port", type=int, help="Postgres port")
    ap.add_argument("--pg-user", help="Postgres user")
    ap.add_argument("--pg-password", help="Postgres password")
    ap.add_argument("--pg-db", help="Postgres database name")
    ap.add_argument("--table", default="pmc_section_meta", help="target table name")
    ap.add_argument("--batch-size", type=int, default=500, help="batch size for upsert")
    ap.add_argument("--commit", action="store_true", help="actually write to DB (default is dry-run)")

    args = ap.parse_args()

    # Allow reading Postgres connection info from environment variables
    # If user didn't pass --pg-* flags, we will look for: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    # First prefer PG* environment variables, then POSTGRES_* variables (common in .env files)
    env_pg_host = os.getenv("POSTGRES_HOST")
    env_pg_port = os.getenv("POSTGRES_PORT")
    env_pg_user = os.getenv("POSTGRES_USER")
    env_pg_password = os.getenv("POSTGRES_PASSWORD")
    env_pg_db = os.getenv("POSTGRES_DB")

    pg_host = args.pg_host or env_pg_host
    pg_port = args.pg_port or (int(env_pg_port) if env_pg_port else None)
    pg_user = args.pg_user or env_pg_user
    pg_password = args.pg_password or env_pg_password
    pg_db = args.pg_db or env_pg_db

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"Input CSV not found: {csv_path}")
        return

    rows = read_rows(csv_path)
    print(f"Read {len(rows)} rows from {csv_path}")

    tuples = [build_values_tuple(r) for r in rows]

    if not args.commit:
        print("Dry-run mode (no DB writes). Sample tuples:")
        for i, t in enumerate(tuples[:5]):
            print(i, t)
        print("Use --commit and provide Postgres connection options to execute upsert.")
        return

    # commit mode: require psycopg2 and DB params
    if psycopg2 is None:
        print("psycopg2 is not installed. Install psycopg2-binary to enable DB writes.")
        return

    if not (pg_db and (pg_user or pg_host)):
        print("Please provide Postgres connection info via flags or environment variables (PGHOST/PGUSER/PGDATABASE) or POSTGRES_HOST/POSTGRES_USER/POSTGRES_DB.")
        return

    try:
        conn = psycopg2.connect(
            host=pg_host or "localhost",
            port=pg_port or 5432,
            dbname=pg_db,
            user=pg_user,
            password=pg_password,
        )
    except Exception as e:
        print(f"Failed to connect to Postgres: {e}")
        return

    try:
        upsert_batches(conn, args.table, tuples, batch_size=args.batch_size)
        print(f"Upsert completed into {args.table} (rows: {len(tuples)})")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()


def upsert_file(
    csv_path: Path,
    pg_connect: dict,
    table: str = "pmc_section_meta",
    batch_size: int = 500,
    commit: bool = False,
) -> int:
    """Programmatic helper: read CSV and upsert into Postgres.

    Returns number of rows processed.
    If commit=False, runs in dry-run mode and does not write to DB.
    """
    rows = read_rows(csv_path)
    tuples = [build_values_tuple(r) for r in rows]

    if not commit:
        # dry-run
        print(f"Dry-run upsert: read {len(tuples)} rows from {csv_path}")
        for i, t in enumerate(tuples[:5]):
            print(i, t)
        return len(tuples)

    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for DB writes but is not installed")

    conn = psycopg2.connect(
        host=pg_connect.get("host", "localhost"),
        port=pg_connect.get("port", 5432),
        dbname=pg_connect.get("dbname"),
        user=pg_connect.get("user"),
        password=pg_connect.get("password"),
    )
    try:
        upsert_batches(conn, table, tuples, batch_size=batch_size)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return len(tuples)
