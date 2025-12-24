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


def run(
    chunks: str,
    output: str = "pmc_vector.csv",
    model: str = DEFAULT_EMBED_MODEL,
    resume: bool = True,
    write_csv: bool = True,
    pg_batch_size: int = 500,
) -> None:
    """파이프라인/외부에서 직접 호출할 때 사용하는 엔트리포인트."""
    logger.info(
        "[EMBED] run() called with chunks=%s, output=%s, model=%s, "
        "resume=%s, write_csv=%s, pg_batch_size=%d",
        chunks,
        output,
        model,
        resume,
        write_csv,
        pg_batch_size,
    )

    # pgvector / Postgres 로드는 비활성화 (pg_connect=None 고정)
    logger.info("[EMBED] pgvector(Postgres) 로드는 비활성화됨 (CSV 출력만 사용).")

    emb = ChunkEmbedder(
        chunk_csv=chunks,
        output_csv=output,
        embed_model=model,
        pg_connect=None,           # 항상 None → DB 사용 안 함
        pg_table="pmc_section_chunk",
        write_csv=write_csv,
        pg_batch_size=pg_batch_size,
    )

    emb.run(resume=resume)
    logger.info("[EMBED] embedding finished: %s", output)


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
        logger.info("[EMBED][CLI] pgvector/Postgres 관련 옵션은 현재 무시됩니다.")

        run(
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
