"""
rag/etl/pipeline_runner.py

Bio/Med RAG ETL 전체 파이프라인 오케스트레이터.

단계:
  1) ingest      : PubMed / NIH / Protocols.io API에서 raw 데이터 수집
  2) normalize   : raw → 공통 internal_doc_format
  3) extract     : (선택) 엔터티/관계 추출 (KG용)
  4) chunk       : 문서 청킹
  5) embed       : 청크 임베딩 생성
  6) upsert      : pgvector(RDB)에 업서트

사용 예:
  python -m rag.etl.pipeline_runner --source pubmed
  python -m rag.etl.pipeline_runner --source all --skip-extract
"""

import argparse
import logging
import os
from dataclasses import dataclass
from importlib import import_module
from typing import Literal, Sequence


SourceType = Literal["pubmed", "nih", "protocols", "all"]


@dataclass
class PipelineConfig:
    """ETL 디렉터리, 기본 옵션 설정 (환경변수와 연동)."""

    raw_dir: str = os.getenv("ETL_RAW_DIR", "data/raw")
    processed_dir: str = os.getenv("ETL_PROCESSED_DIR", "data/processed")
    entities_dir: str = os.getenv("ETL_ENTITIES_DIR", "data/entities")
    chunks_dir: str = os.getenv("ETL_CHUNKS_DIR", "data/chunks")
    embeddings_dir: str = os.getenv("ETL_EMBEDDINGS_DIR", "data/embeddings")

    batch_size: int = int(os.getenv("ETL_BATCH_SIZE", "50"))


def setup_logging() -> None:
    """공통 logging 설정. common.logging_utils 가 있으면 그걸 우선 사용."""
    try:
        from .common import logging_utils

        logging_utils.setup_logging()
    except Exception:
        # fallback
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        )


def ensure_dirs(*dirs: str) -> None:
    for d in dirs:
        os.makedirs(d, exist_ok=True)


# ─────────────────────────────────────────────
# 1) Ingest 단계
# ─────────────────────────────────────────────


def run_ingest(source: SourceType, cfg: PipelineConfig, limit: int | None = None) -> None:
    """
    01_ingest/ 아래 각 소스 모듈의 run()을 호출.

    기대하는 모듈 & 함수 시그니처:
      - rag.etl.01_ingest.01_ingest_pubmed.run(raw_dir: str, limit: int | None)
      - rag.etl.01_ingest.02_ingest_nih.run(raw_dir: str, limit: int | None)
      - rag.etl.01_ingest.03_ingest_protocols_io.run(raw_dir: str, limit: int | None)
    """
    logger = logging.getLogger("etl.ingest")

    if source == "all":
        targets: Sequence[SourceType] = ["pubmed", "nih", "protocols"]
    else:
        targets = [source]

    ensure_dirs(cfg.raw_dir)

    for s in targets:
        logger.info("▶ [INGEST] start source=%s", s)

        if s == "pubmed":
            mod = import_module("rag.etl.01_ingest.01_ingest_pubmed")
        elif s == "nih":
            mod = import_module("rag.etl.01_ingest.02_ingest_nih")
        elif s == "protocols":
            mod = import_module("rag.etl.01_ingest.03_ingest_protocols_io")
        else:
            raise ValueError(f"Unknown source: {s}")

        # 각 모듈에 run 함수가 있다고 가정
        mod.run(raw_dir=cfg.raw_dir, limit=limit)
        logger.info("✔ [INGEST] done source=%s", s)


# ─────────────────────────────────────────────
# 2) Normalize 단계
# ─────────────────────────────────────────────


def run_normalize(source: SourceType, cfg: PipelineConfig) -> None:
    """
    02_normalize/ 아래 각 소스 모듈의 run()을 호출.

    기대하는 모듈 & 시그니처:
      - rag.etl.02_normalize.01_normalize_pubmed.run(raw_dir, processed_dir)
      - rag.etl.02_normalize.02_normalize_nih.run(raw_dir, processed_dir)
      - rag.etl.02_normalize.03_normalize_protocols_io.run(raw_dir, processed_dir)
    """
    logger = logging.getLogger("etl.normalize")

    if source == "all":
        targets: Sequence[SourceType] = ["pubmed", "nih", "protocols"]
    else:
        targets = [source]

    ensure_dirs(cfg.processed_dir)

    for s in targets:
        logger.info("▶ [NORMALIZE] start source=%s", s)

        if s == "pubmed":
            mod = import_module("rag.etl.02_normalize.01_normalize_pubmed")
        elif s == "nih":
            mod = import_module("rag.etl.02_normalize.02_normalize_nih")
        elif s == "protocols":
            mod = import_module("rag.etl.02_normalize.03_normalize_protocols_io")
        else:
            raise ValueError(f"Unknown source: {s}")

        mod.run(raw_dir=cfg.raw_dir, processed_dir=cfg.processed_dir)
        logger.info("✔ [NORMALIZE] done source=%s", s)


# ─────────────────────────────────────────────
# 3) Extract (엔터티/관계) 단계
# ─────────────────────────────────────────────


def run_extract(cfg: PipelineConfig, source: SourceType) -> None:
    """
    03_extract/01_entity_extraction.py 및 02_relation_extraction.py 의 run() 호출.

    기대 시그니처:
      rag.etl.03_extract.01_entity_extraction.run(
          processed_dir: str,
          entities_dir: str,
          source: str | None,
      )

      rag.etl.03_extract.02_relation_extraction.run(
          entities_dir: str,
          source: str | None,
      )
    """
    logger = logging.getLogger("etl.extract")
    ensure_dirs(cfg.entities_dir)

    src_filter = None if source == "all" else source

    # 엔터티 추출
    logger.info("▶ [EXTRACT] entity extraction start (source=%s)", source)
    ent_mod = import_module("rag.etl.03_extract.01_entity_extraction")
    ent_mod.run(
        processed_dir=cfg.processed_dir,
        entities_dir=cfg.entities_dir,
        source=src_filter,
    )
    logger.info("✔ [EXTRACT] entity extraction done")

    # 관계 추출 (파일 없으면 스킵 가능하도록 try/except)
    try:
        logger.info("▶ [EXTRACT] relation extraction start (source=%s)", source)
        rel_mod = import_module("rag.etl.03_extract.02_relation_extraction")
        rel_mod.run(
            entities_dir=cfg.entities_dir,
            source=src_filter,
        )
        logger.info("✔ [EXTRACT] relation extraction done")
    except ModuleNotFoundError:
        logger.info("⏭  [EXTRACT] relation_extraction 모듈 없음 → 스킵")


# ─────────────────────────────────────────────
# 4) Chunk 단계
# ─────────────────────────────────────────────


def run_chunk(cfg: PipelineConfig) -> None:
    """
    04_chunk/01_chunker.py 의 run() 호출.

    기대 시그니처:
      rag.etl.04_chunk.01_chunker.run(
          processed_dir: str,
          chunks_dir: str,
      )
    """
    logger = logging.getLogger("etl.chunk")
    ensure_dirs(cfg.chunks_dir)

    logger.info("▶ [CHUNK] start")

    mod = import_module("rag.etl.04_chunk.01_chunker")
    mod.run(
        processed_dir=cfg.processed_dir,
        chunks_dir=cfg.chunks_dir,
    )

    logger.info("✔ [CHUNK] done")


# ─────────────────────────────────────────────
# 5) Embedding 단계
# ─────────────────────────────────────────────


def run_embed(cfg: PipelineConfig) -> None:
    """
    05_embed/01_embed_texts.py 의 run() 호출.

    기대 시그니처:
      rag.etl.05_embed.01_embed_texts.run(
          chunks_dir: str,
          embeddings_dir: str,
      )
    """
    logger = logging.getLogger("etl.embed")
    ensure_dirs(cfg.embeddings_dir)

    logger.info("▶ [EMBED] start")

    mod = import_module("rag.etl.05_embed.01_embed_texts")
    mod.run(
        chunks_dir=cfg.chunks_dir,
        embeddings_dir=cfg.embeddings_dir,
    )

    logger.info("✔ [EMBED] done")


# ─────────────────────────────────────────────
# 6) Upsert 단계 (pgvector)
# ─────────────────────────────────────────────


def run_upsert(cfg: PipelineConfig) -> None:
    """
    06_upsert/01_upsert_pgvector.py 의 run() 호출.

    기대 시그니처:
      rag.etl.06_upsert.01_upsert_pgvector.run(
          embeddings_dir: str,
      )
    """
    logger = logging.getLogger("etl.upsert")

    logger.info("▶ [UPSERT] start")

    mod = import_module("rag.etl.06_upsert.01_upsert_pgvector")
    mod.run(
        embeddings_dir=cfg.embeddings_dir,
    )

    logger.info("✔ [UPSERT] done")


# ─────────────────────────────────────────────
# CLI 파라미터 & main
# ─────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG ETL Pipeline Runner (PubMed / NIH / Protocols.io)"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["pubmed", "nih", "protocols", "all"],
        default="pubmed",
        help="데이터 소스 선택 (기본: pubmed)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="ingest 단계에서 가져올 최대 문서 수 (None이면 제한 없음)",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="KG용 엔터티/관계 추출 단계 건너뛰기",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="이미 raw 데이터가 있을 때 ingest 단계 건너뛰기",
    )
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="이미 정규화된 문서가 있을 때 normalize 단계 건너뛰기",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    logger = logging.getLogger("etl.pipeline")

    args = parse_args()
    cfg = PipelineConfig()

    logger.info("=== RAG ETL PIPELINE START ===")
    logger.info("Config: %s", cfg)
    logger.info("Source: %s, limit=%s", args.source, args.limit)

    if not args.skip_ingest:
        run_ingest(source=args.source, cfg=cfg, limit=args.limit)
    else:
        logger.info("⏭  Skip ingest")

    if not args.skip_normalize:
        run_normalize(source=args.source, cfg=cfg)
    else:
        logger.info("⏭  Skip normalize")

    if not args.skip_extract:
        run_extract(cfg=cfg, source=args.source)
    else:
        logger.info("⏭  Skip extract (KG entity/relation)")

    run_chunk(cfg=cfg)
    run_embed(cfg=cfg)
    run_upsert(cfg=cfg)

    logger.info("=== RAG ETL PIPELINE DONE ===")


if __name__ == "__main__":
    main()
