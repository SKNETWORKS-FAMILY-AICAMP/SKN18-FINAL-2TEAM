#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PubMed 섹션 CSV를 받아 청크 CSV를 만드는 실행 스크립트.

- pipeline_runner 에서: run(processed_dir, chunks_dir)
- 단독 실행: python rag/etl/step04_chunk/01_chunker_pubmed.py [옵션]
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from rag.etl.step04_chunk.pmc_chunk_common.chunk_generator_v2 import ChunkGenerator
from rag.etl.step04_chunk.pmc_chunk_common.chunking import DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP

logger = logging.getLogger(__name__)


def _run_internal(
    input_csv: str,
    chunks_dir: str,
    chunk_size: int,
    overlap: int,
    batch_size: int,
    resume: bool,
) -> None:
    """실제 청킹 실행 헬퍼 (입력 CSV 경로를 직접 받음)."""
    input_path = Path(input_csv)
    chunks_base = Path(chunks_dir)

    chunk_csv = chunks_base / "pubmed" / "pmc_chunks.csv"

    logger.info(
        "[CHUNK:PubMed] input_csv=%s, chunk_csv=%s, chunk_size=%d, overlap=%d, "
        "batch_size=%d, resume=%s",
        input_path,
        chunk_csv,
        chunk_size,
        overlap,
        batch_size,
        resume,
    )

    if not input_path.exists():
        logger.error("[CHUNK:PubMed] 입력 섹션 CSV가 없습니다: %s", input_path)
        return

    # 출력 디렉터리 생성
    chunk_csv.parent.mkdir(parents=True, exist_ok=True)

    gen = ChunkGenerator(
        input_csv=str(input_path),
        chunk_csv=str(chunk_csv),
        chunk_size=chunk_size,
        overlap=overlap,
        batch_size=batch_size,
        meta_csv=None,      # 메타는 이미 분리되어 있다고 가정
        split_meta=False,
    )

    gen.run(resume=resume)
    logger.info("[CHUNK:PubMed] chunking 완료: %s", chunk_csv)


def run(
    processed_dir: str,
    chunks_dir: str,
    input_csv: Optional[str] = None,
) -> None:
    """pipeline_runner 에서 사용하는 엔트리포인트.

    Args:
        processed_dir: 정규화된 데이터 루트 (`data/processed`)
        chunks_dir: 청크 결과 루트 (`data/chunks`)
        input_csv: (선택) 섹션 CSV 경로.
        - None 이면 processed_dir/pubmed/pmc_csv/sections_for_chunk.csv 사용
    """
    logger.info(
        "[CHUNK:PubMed] run() called with processed_dir=%s, chunks_dir=%s, input_csv=%s",
        processed_dir,
        chunks_dir,
        input_csv,
    )

    if input_csv is None:
        # 기본 경로: processed_dir/pubmed/pmc_csv/sections_for_chunk.csv
        input_path = Path(processed_dir) / "pubmed" / "pmc_csv" / "sections_for_chunk.csv"
    else:
        input_path = Path(input_csv)

    _run_internal(
        input_csv=str(input_path),
        chunks_dir=chunks_dir,
        chunk_size=DEFAULT_CHUNK_SIZE,
        overlap=DEFAULT_OVERLAP,
        batch_size=100,
        resume=True,
    )


def main(argv=None) -> None:
    """직접 실행용 CLI 엔트리포인트."""
    ap = argparse.ArgumentParser(
        description="PubMed sections CSV 를 pmc_chunks.csv 로 청킹하는 스크립트"
    )
    ap.add_argument(
        "--processed-dir",
        default=os.getenv("ETL_PROCESSED_DIR", "data/processed"),
        help="정규화된 데이터 루트 디렉터리 (기본: data/processed)",
    )
    ap.add_argument(
        "--chunks-dir",
        default=os.getenv("ETL_CHUNKS_DIR", "data/chunks"),
        help="청크 결과 루트 디렉터리 (기본: data/chunks)",
    )
    ap.add_argument(
        "--input",
        help=(
            "입력 섹션 CSV 경로. "
            "지정하지 않으면 processed-dir/pubmed/pmc_csv/sections_for_chunk.csv 사용"
        ),
    )
    ap.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"청크 길이 (기본: {DEFAULT_CHUNK_SIZE})",
    )
    ap.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_OVERLAP,
        help=f"청크 오버랩 길이 (기본: {DEFAULT_OVERLAP})",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="진행률 출력용 배치 사이즈 (기본: 100)",
    )
    ap.add_argument(
        "--no-resume",
        action="store_true",
        help="기존 pmc_chunks.csv를 무시하고 처음부터 다시 생성",
    )

    args = ap.parse_args(argv)

    # 입력 경로 결정
    if args.input:
        input_path = Path(args.input)
    else:
        input_path = Path(args.processed_dir) / "pubmed" / "pmc_csv" / "sections_for_chunk.csv"

    logger.info(
        "[CHUNK:PubMed] CLI 실행: processed_dir=%s, chunks_dir=%s, input=%s, "
        "chunk_size=%d, overlap=%d, batch_size=%d, no_resume=%s",
        args.processed_dir,
        args.chunks_dir,
        input_path,
        args.chunk_size,
        args.overlap,
        args.batch_size,
        args.no_resume,
    )

    _run_internal(
        input_csv=str(input_path),
        chunks_dir=args.chunks_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        batch_size=args.batch_size,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
