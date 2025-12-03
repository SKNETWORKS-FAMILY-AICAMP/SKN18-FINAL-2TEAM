#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI runner for the chunking step only.
"""
import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Add embedding directory to path for imports
# =========================================================
# [FINAL FIX] pmc_processing_utils 모듈 경로 강제 등록
# =========================================================
# 현재 파일 위치: .../SKN18-FINAL-2TEAM/embedding/run_chunk.py
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

# 1. 프로젝트 루트 추가 (.../SKN18-FINAL-2TEAM)
sys.path.insert(0, str(project_root))

# 2. 유틸리티 파일이 있는 폴더 직접 추가 (로그상 오타 'data_preprocessiog' 사용)
# 목표 경로: .../SKN18-FINAL-2TEAM/data_preprocessiog/pmc_etl
etl_dir = project_root / "data_preprocessiog" / "pmc_etl"

if etl_dir.exists():
    sys.path.insert(0, str(etl_dir))

# Now import local modules
from chunk_generator import ChunkGenerator
from chunking import DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP


def main(argv=None):
    ap = argparse.ArgumentParser(description="[STEP 1/2] Create chunk CSV from sections CSV")
    sub = ap.add_subparsers(dest="cmd", required=False)

    # --- CHUNK ---
    p_chunk = sub.add_parser("chunk", help="Create chunk CSV from sections CSV")
    p_chunk.add_argument("--input", required=True, help="sections CSV path")
    p_chunk.add_argument("--chunk-out", default="pmc_chunks.csv", help="output chunk CSV path")
    p_chunk.add_argument("--meta-out", help="Optional path to write extracted metadata CSV")
    p_chunk.add_argument("--split-meta", action="store_true", help="Extract metadata CSV before chunking")
    p_chunk.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="chunk char length")
    p_chunk.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP, help="overlap char length")
    p_chunk.add_argument("--batch-size", type=int, default=100, help="batch size")
    p_chunk.add_argument("--no-resume", action="store_true", help="regenerate chunks from scratch")

    args = ap.parse_args(argv)
    cmd = args.cmd or "chunk" # 기본 명령을 chunk로 설정

    # 실행 로직
    if cmd == "chunk":
        print("[START] Chunking process started.")
        gen = ChunkGenerator(
            input_csv=args.input,
            chunk_csv=args.chunk_out,
            chunk_size=args.chunk,
            overlap=args.overlap,
            batch_size=getattr(args, "batch_size", 100),
            meta_csv=getattr(args, "meta_out", None),
            split_meta=getattr(args, "split_meta", False),
        )
        gen.run(resume=(not args.no_resume))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()