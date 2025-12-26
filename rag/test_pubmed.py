#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from pathlib import Path
import sys

# === 프로젝트 루트를 sys.path에 추가 ===
# 이 파일 위치: <project_root>/rag/test_pubmed.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.etl.pipeline_runner import (
    PipelineConfig,
    run_ingest,
    run_normalize,
    run_chunk,
    run_embed,
    setup_logging,
)


def _ensure_dirs(cfg: PipelineConfig) -> None:
    for d in [cfg.raw_dir, cfg.processed_dir, cfg.chunks_dir, cfg.embeddings_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)


def test_pubmed_pipeline(limit: int = 3) -> None:
    setup_logging()
    logger = logging.getLogger("etl.test_pubmed")

    cfg = PipelineConfig()
    _ensure_dirs(cfg)

    logger.info("=== PubMed ETL smoke test start ===")
    logger.info(
        "raw_dir=%s, processed_dir=%s, chunks_dir=%s, embeddings_dir=%s",
        cfg.raw_dir,
        cfg.processed_dir,
        cfg.chunks_dir,
        cfg.embeddings_dir,
    )

    try:
        logger.info("[1/4] run_ingest(pubmed)")
        run_ingest(source="pubmed", cfg=cfg, limit=limit)
        logger.info("[1/4] OK")
    except Exception as e:
        logger.exception("[1/4] FAILED: %s", e)
        return

    try:
        logger.info("[2/4] run_normalize(pubmed)")
        run_normalize(source="pubmed", cfg=cfg)
        logger.info("[2/4] OK")
    except Exception as e:
        logger.exception("[2/4] FAILED: %s", e)
        return

    try:
        logger.info("[3/4] run_chunk(pubmed)")
        run_chunk(source="pubmed", cfg=cfg)
        logger.info("[3/4] OK")
    except Exception as e:
        logger.exception("[3/4] FAILED: %s", e)
        return

    try:
        logger.info("[4/4] run_embed(pubmed)")
        run_embed(source="pubmed", cfg=cfg, limit=10)
        logger.info("[4/4] OK")
    except Exception as e:
        logger.exception("[4/4] FAILED: %s", e)
        return

    logger.info("=== PubMed ETL smoke test DONE (all steps OK) ===")


if __name__ == "__main__":
    test_pubmed_pipeline(limit=1)
