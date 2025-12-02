#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI runner for chunking + embedding pipeline.
"""
import argparse
import sys
from pathlib import Path

# Add embedding directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Now import local modules
from chunk_generator import ChunkGenerator
from chunk_embedder import ChunkEmbedder
from chunking import DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP, DEFAULT_EMBED_MODEL
import upsert_meta 


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chunk and embed PMC sections")
    sub = ap.add_subparsers(dest="cmd", required=False)

    p_chunk = sub.add_parser("chunk", help="Create chunk CSV from sections CSV")
    p_chunk.add_argument("--input", required=True, help="sections CSV path")
    p_chunk.add_argument(
        "--chunk-out",
        default="pmc_chunks.csv",
        help="output chunk CSV path (default: pmc_chunks.csv)",
    )
    p_chunk.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="chunk char length")
    p_chunk.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP, help="overlap char length")
    p_chunk.add_argument("--batch-size", type=int, default=100, help="batch size for reading input CSV (default: 100)")
    p_chunk.add_argument("--no-resume", action="store_true", help="regenerate chunks from scratch")

    p_embed = sub.add_parser("embed", help="Embed chunks CSV and produce embedding CSV")
    p_embed.add_argument("--chunks", required=True, help="chunk CSV path (from 'chunk' step)")
    p_embed.add_argument(
        "--output",
        default="pmc_vector.csv",
        help="embedding output CSV path (default: pmc_vector.csv)",
    )
    p_embed.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="embedding model")
    p_embed.add_argument("--no-resume", action="store_true", help="re-embed from scratch")
    p_embed.add_argument("--no-csv", action="store_true", help="do not write output CSV; insert only into Postgres")
    p_embed.add_argument("--pg-batch-size", type=int, default=500, help="Postgres batch insert size (execute_values)")
    # Postgres connection options (optional)
    p_embed.add_argument("--pg-host", help="Postgres host")
    p_embed.add_argument("--pg-port", type=int, help="Postgres port")
    p_embed.add_argument("--pg-user", help="Postgres user")
    p_embed.add_argument("--pg-password", help="Postgres password")
    p_embed.add_argument("--pg-db", help="Postgres database name")
    p_embed.add_argument("--pg-table", default="pmc_section_chunk", help="Postgres target table name")

    p_all = sub.add_parser("all", help="Run chunk then embed (one-shot)")
    p_all.add_argument("--input", required=True, help="sections CSV path")
    p_all.add_argument(
        "--chunks-out",
        default="pmc_chunks.csv",
        help="intermediate chunk CSV path",
    )
    p_all.add_argument(
        "--output",
        default="pmc_vector.csv",
        help="final embedding output CSV path",
    )
    p_all.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="chunk char length")
    p_all.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP, help="overlap char length")
    p_all.add_argument("--batch-size", type=int, default=100, help="batch size for reading input CSV (default: 100)")
    p_all.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="embedding model")
    p_all.add_argument("--no-resume", action="store_true", help="do not resume; start fresh")
    p_all.add_argument("--no-csv", action="store_true", help="do not write output CSV; insert only into Postgres")
    p_all.add_argument("--pg-batch-size", type=int, default=500, help="Postgres batch insert size (execute_values)")
    p_all.add_argument("--pg-host", help="Postgres host")
    p_all.add_argument("--pg-port", type=int, help="Postgres port")
    p_all.add_argument("--pg-user", help="Postgres user")
    p_all.add_argument("--pg-password", help="Postgres password")
    p_all.add_argument("--pg-db", help="Postgres database name")
    p_all.add_argument("--pg-table", default="pmc_section_chunk", help="Postgres target table name")
    p_all.add_argument("--upsert-meta", action="store_true", help="Upsert section metadata into pmc_section_meta before chunking")
    p_all.add_argument("--meta-table", default="pmc_section_meta", help="Target table for metadata upsert")
    p_all.add_argument("--meta-batch-size", type=int, default=500, help="Batch size for meta upsert")
    p_all.add_argument("--meta-commit", action="store_true", help="Actually commit metadata upsert (default is dry-run)")

    args = ap.parse_args(argv)
    cmd = args.cmd or "all"

    if cmd == "chunk":
        gen = ChunkGenerator(input_csv=args.input, chunk_csv=args.chunk_out, chunk_size=args.chunk, overlap=args.overlap, batch_size=args.batch_size)
        gen.run(resume=(not args.no_resume))
    elif cmd == "embed":
        pg_connect = None
        if args.pg_db or args.pg_host or args.pg_user:
            pg_connect = {
                "host": args.pg_host or "localhost",
                "port": args.pg_port or 5432,
                "dbname": args.pg_db,
                "user": args.pg_user,
                "password": args.pg_password,
            }
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
    elif cmd == "all":
        gen = ChunkGenerator(input_csv=args.input, chunk_csv=args.chunks_out, chunk_size=args.chunk, overlap=args.overlap, batch_size=args.batch_size)
        gen.run(resume=(not args.no_resume))
        pg_connect = None
        if args.pg_db or args.pg_host or args.pg_user:
            pg_connect = {
                "host": args.pg_host or "localhost",
                "port": args.pg_port or 5432,
                "dbname": args.pg_db,
                "user": args.pg_user,
                "password": args.pg_password,
            }
            # optionally upsert metadata first
            if getattr(args, "upsert_meta", False):
                if pg_connect is None:
                    print("--upsert-meta requested but no Postgres connection info provided; skipping meta upsert")
                else:
                    print("Running metadata upsert (pmc_section_meta)")
                    upsert_meta.upsert_file(
                        csv_path=Path(args.input),
                        pg_connect=pg_connect,
                        table=args.meta_table,
                        batch_size=args.meta_batch_size,
                        commit=args.meta_commit,
                    )
        emb = ChunkEmbedder(
            chunk_csv=args.chunks_out,
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
