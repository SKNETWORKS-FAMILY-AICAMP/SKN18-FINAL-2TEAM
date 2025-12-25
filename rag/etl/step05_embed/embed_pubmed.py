"""
테스트용 임베딩 스텁.
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI runner for the embedding step only.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Add embedding directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Now import local modules
from rag.etl.step05_embed.pmc_embed_common.chunk_embedder_v2 import ChunkEmbedder
from rag.etl.step04_chunk.pmc_chunk_common.chunking import DEFAULT_EMBED_MODEL

def run_for_files(
    chunks: str,
    output: str = "pmc_vector.csv",
    model: str = DEFAULT_EMBED_MODEL,
    resume: bool = True,
    write_csv: bool = True,
    pg_batch_size: int = 500,
) -> None:
    logger.info(
        "[EMBED:PubMed] run_for_files() chunks=%s, output=%s, model=%s, "
        "resume=%s, write_csv=%s, pg_batch_size=%d",
        chunks,
        output,
        model,
        resume,
        write_csv,
        pg_batch_size,
    )

    logger.info("[EMBED:PubMed] pgvector(Postgres) 비활성화 (CSV만 생성).")

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    emb = ChunkEmbedder(
        chunk_csv=chunks,
        output_csv=output,
        embed_model=model,
        pg_connect=None,
        pg_table="pmc_section_chunk",
        write_csv=write_csv,
        pg_batch_size=pg_batch_size,
    )

    emb.run(resume=resume)
    logger.info("[EMBED:PubMed] embedding finished: %s", output)



def run(chunks_dir: str, embeddings_dir: str) -> None:
    """
    pipeline_runner.run_embed 에서 사용하는 엔트리포인트.

    - 입력:  {chunks_dir}/pubmed/pmc_chunks.csv
    - 출력:  {embeddings_dir}/pubmed/pmc_vector.csv
    """
    chunks_base = Path(chunks_dir)
    embeds_base = Path(embeddings_dir)

    chunk_csv = chunks_base / "pubmed" / "pmc_chunks.csv"
    output_csv = embeds_base / "pubmed" / "pmc_vector.csv"

    logger.info(
        "[EMBED:PubMed] run() called with chunks_dir=%s, embeddings_dir=%s",
        chunks_dir,
        embeddings_dir,
    )
    logger.info(
        "[EMBED:PubMed] resolved paths: chunk_csv=%s, output_csv=%s",
        chunk_csv,
        output_csv,
    )

    if not chunk_csv.exists():
        logger.error("[EMBED:PubMed] chunk CSV not found: %s", chunk_csv)
        return

    run_for_files(
        chunks=str(chunk_csv),
        output=str(output_csv),
        model=DEFAULT_EMBED_MODEL,
        resume=True,
        write_csv=True,
        pg_batch_size=500,
    )


def main(argv=None) -> None:
    """직접 실행용 CLI 엔트리포인트."""
    ap = argparse.ArgumentParser(
        description="[STEP 2/2] Embed chunks CSV and (optionally) produce embedding CSV"
    )
    sub = ap.add_subparsers(dest="cmd", required=False)

    # --- EMBED ---
    p_embed = sub.add_parser("embed", help="Embed chunks CSV and produce embedding CSV")
    p_embed.add_argument("--chunks", required=True, help="chunk CSV path")
    p_embed.add_argument(
        "--output",
        default="pmc_vector.csv",
        help="embedding output CSV path",
    )
    p_embed.add_argument(
        "--model",
        default=DEFAULT_EMBED_MODEL,
        help="embedding model",
    )
    p_embed.add_argument(
        "--no-resume",
        action="store_true",
        help="re-embed from scratch",
    )
    p_embed.add_argument(
        "--no-csv",
        action="store_true",
        help="(무시 가능) CSV를 쓰지 않고 싶을 때 사용. 현재는 DB 비활성화 상태.",
    )
    p_embed.add_argument(
        "--pg-batch-size",
        type=int,
        default=500,
        help="(DB 비활성화 상태이지만) 배치 크기 설정 값",
    )

    # DB Args (현재는 파싱만 하고 실제로는 사용하지 않음)
    p_embed.add_argument("--pg-host", help="Postgres host (현재 무시됨)")
    p_embed.add_argument("--pg-port", type=int, help="Postgres port (현재 무시됨)")
    p_embed.add_argument("--pg-user", help="Postgres user (현재 무시됨)")
    p_embed.add_argument("--pg-password", help="Postgres password (현재 무시됨)")
    p_embed.add_argument("--pg-db", help="Postgres database name (현재 무시됨)")
    p_embed.add_argument(
        "--pg-table",
        default="pmc_section_chunk",
        help="Postgres target table name (현재 무시됨)",
    )

    args = ap.parse_args(argv)
    cmd = args.cmd or "embed"  # 기본 명령을 embed로 설정

    if cmd == "embed":
        write_csv = not args.no_csv

        logger.info(
            "[EMBED][CLI] chunks=%s, output=%s, model=%s, no_resume=%s, "
            "no_csv=%s, pg_batch_size=%d",
            args.chunks,
            args.output,
            args.model,
            args.no_resume,
            args.no_csv,
            args.pg_batch_size,
        )

        run_for_files(
            chunks=args.chunks,
            output=args.output,
            model=args.model,
            resume=not args.no_resume,
            write_csv=write_csv,
            pg_batch_size=args.pg_batch_size,
        )

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
