#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI runner for the embedding step only.
"""
import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Add embedding directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Now import local modules
from chunk_embedder_v2 import ChunkEmbedder
from chunking import DEFAULT_EMBED_MODEL
import load.load_pmc_meta as load_pmc_meta


def get_pg_connect_info(args):
    """
    커맨드라인 인자(args)와 환경변수(.env)를 조합하여 DB 연결 정보를 생성합니다.
    (run.py와 동일 로직)
    """
    env_host = os.getenv("POSTGRES_HOST") 
    env_port = os.getenv("POSTGRES_PORT") 
    env_user = os.getenv("POSTGRES_USER")
    env_password = os.getenv("POSTGRES_PASSWORD")
    env_db = os.getenv("POSTGRES_DB")

    host = args.pg_host or env_host or "localhost"
    port = args.pg_port or (int(env_port) if env_port else 5432)
    dbname = args.pg_db or env_db
    user = args.pg_user or env_user
    password = args.pg_password or env_password

    if not dbname or not user:
        return None

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="[STEP 2/2] Embed chunks CSV and insert into DB/CSV")
    sub = ap.add_subparsers(dest="cmd", required=False)

    # --- EMBED ---
    p_embed = sub.add_parser("embed", help="Embed chunks CSV and produce embedding CSV")
    p_embed.add_argument("--chunks", required=True, help="chunk CSV path")
    p_embed.add_argument("--output", default="pmc_vector.csv", help="embedding output CSV path")
    p_embed.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="embedding model")
    p_embed.add_argument("--no-resume", action="store_true", help="re-embed from scratch")
    p_embed.add_argument("--no-csv", action="store_true", help="do not write output CSV; insert only into Postgres")
    p_embed.add_argument("--pg-batch-size", type=int, default=500, help="Postgres batch insert size")
    
    # DB Args
    p_embed.add_argument("--pg-host", help="Postgres host")
    p_embed.add_argument("--pg-port", type=int, help="Postgres port")
    p_embed.add_argument("--pg-user", help="Postgres user")
    p_embed.add_argument("--pg-password", help="Postgres password")
    p_embed.add_argument("--pg-db", help="Postgres database name")
    p_embed.add_argument("--pg-table", default="pmc_section_chunk", help="Postgres target table name")

    args = ap.parse_args(argv)
    cmd = args.cmd or "embed" # 기본 명령을 embed로 설정

    # 실행 로직
    if cmd == "embed":
        print("[START] Embedding process started.")
        pg_connect = get_pg_connect_info(args)
        
        if pg_connect:
            print(f"[INFO] DB 연결 설정됨: {pg_connect['host']}/{pg_connect['dbname']}")
        else:
            print("[INFO] DB 연결 설정 없음 (CSV만 저장)")

        emb = ChunkEmbedder(
            chunk_csv=args.chunks,
            output_csv=args.output,
            embed_model=args.model,
            pg_connect=pg_connect,
            pg_table=args.pg_table,
            write_csv=(not args.no_csv),
            pg_batch_size=getattr(args, "pg_batch_size", 500),
        )
        emb.run(resume=(not args.no_resume))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()