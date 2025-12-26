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
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal, Sequence

# 패키지 형태로 실행하지 않아도 rag.* 모듈을 찾을 수 있도록 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
    step01_ingest/ 아래 각 소스 모듈의 run()을 호출.

    기대하는 모듈 & 함수 시그니처:
      - rag.etl.step01_ingest.01_ingest_pubmed.run(raw_dir: str, limit: int | None)
      - rag.etl.step01_ingest.02_ingest_nih.run(raw_dir: str, limit: int | None)
      - rag.etl.step01_ingest.03_ingest_protocols.run(raw_dir: str, limit: int | None)
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
            mod = import_module("rag.etl.step01_ingest.ingest_pubmed")
            mod.run(raw_dir=cfg.raw_dir, limit=limit)
        elif s == "nih":
            mod = import_module("rag.etl.step01_ingest.ingest_nih")
            mod.run(raw_dir=cfg.raw_dir, limit=limit)
        elif s == "protocols":
            mod = import_module("rag.etl.step01_ingest.ingest_protocols")
            # protocols는 main() 함수만 있음
            if hasattr(mod, 'run'):
                mod.run(raw_dir=cfg.raw_dir, limit=limit)
            else:
                mod.main()
        else:
            raise ValueError(f"Unknown source: {s}")

        logger.info("✔ [INGEST] done source=%s", s)


# ─────────────────────────────────────────────
# 2) Normalize 단계
# ─────────────────────────────────────────────


def run_normalize(source: SourceType, cfg: PipelineConfig) -> None:
    """
    02_normalize/ 아래 각 소스 모듈의 run()을 호출.

    기대하는 모듈 & 시그니처:
      - rag.etl.step02_normalize.normalize_pubmed.run(raw_dir, processed_dir)
      - rag.etl.step02_normalize.normalize_nih.run(raw_dir, processed_dir)
      - rag.etl.step02_normalize.normalize_protocols.run(raw_dir, processed_dir)
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
            mod = import_module("rag.etl.step02_normalize.normalize_pubmed")
        elif s == "nih":
            mod = import_module("rag.etl.step02_normalize.normalize_nih")
        elif s == "protocols":
            mod = import_module("rag.etl.step02_normalize.normalize_protocols")
        else:
            raise ValueError(f"Unknown source: {s}")

        mod.run(raw_dir=cfg.raw_dir, processed_dir=cfg.processed_dir)
        logger.info("✔ [NORMALIZE] done source=%s", s)


# ─────────────────────────────────────────────
# 3) Extract (엔터티/관계) 단계
# ─────────────────────────────────────────────


def run_extract(cfg: PipelineConfig, source: SourceType) -> None:
    """
    03_extract/pmc_normalization_pipeline.py,
    entity_extraction.py,
    relation_extraction.py 의 run()을 순차 실행.
    """
    logger = logging.getLogger("etl.extract")
    ensure_dirs(cfg.entities_dir)

    src_filter = None if source == "all" else source

    # 0) PMC 정제 파이프라인 (pmid/section_id/cleansing)
    try:
        logger.info("▶ [EXTRACT] pmc_normalization_pipeline start (source=%s)", source)
        norm_mod = import_module("rag.etl.step03_extract.pmc_normalization_pipeline")
        norm_mod.run(cfg, source)  # cfg: PipelineConfig, source: SourceType
        logger.info("✔ [EXTRACT] pmc_normalization_pipeline done")
    except ModuleNotFoundError:
        logger.info("⏭  [EXTRACT] pmc_normalization_pipeline 모듈 없음 → 스킵")
    except Exception as e:
        logger.error("[EXTRACT] pmc_normalization_pipeline 실행 실패: %s", e, exc_info=True)
        raise

    # 1) 엔터티 추출
    logger.info("▶ [EXTRACT] entity_extraction start (source=%s)", source)
    ent_mod = import_module("rag.etl.step03_extract.entity_extraction")
    ent_mod.run(
        processed_dir=cfg.processed_dir,
        entities_dir=cfg.entities_dir,
        source=src_filter,
    )
    logger.info("✔ [EXTRACT] entity_extraction done")

    # 2) 관계 추출 (파일 없으면 스킵 가능하도록 try/except)
    try:
        logger.info("▶ [EXTRACT] relation_extraction start (source=%s)", source)
        rel_mod = import_module("rag.etl.step03_extract.relation_extraction")
        rel_mod.run(
            entities_dir=cfg.entities_dir,
            source=src_filter,
        )
        logger.info("✔ [EXTRACT] relation_extraction done")
    except ModuleNotFoundError:
        logger.info("⏭  [EXTRACT] relation_extraction 모듈 없음 → 스킵")


# ─────────────────────────────────────────────
# 4) Chunk 단계
# ─────────────────────────────────────────────


def run_chunk(source: SourceType, cfg: PipelineConfig) -> None:
    """
    04_chunk/ 아래 각 소스 모듈의 run() 또는 main() 호출.

    기대 시그니처:
      rag.etl.step04_chunk.chunker_pubmed.run(...)
      rag.etl.step04_chunk.chunker_nih.main()  # main() 함수 사용
      rag.etl.step04_chunk.chunker_protocols.main()  # main() 함수 사용
    """
    logger = logging.getLogger("etl.chunk")
    ensure_dirs(cfg.chunks_dir)

    if source == "all":
        targets: Sequence[SourceType] = ["pubmed", "nih", "protocols"]
    else:
        targets = [source]

    for s in targets:
        logger.info("▶ [CHUNK] start source=%s", s)

        try:
            if s == "pubmed":
                mod = import_module("rag.etl.step04_chunk.chunker_pubmed")
                if hasattr(mod, 'run'):
                    mod.run(processed_dir=cfg.processed_dir, chunks_dir=cfg.chunks_dir)
                elif hasattr(mod, 'main'):
                    mod.main()
                else:
                    logger.warning("⚠ [CHUNK] pubmed: run() 또는 main() 함수가 없습니다. 스킵합니다.")
            elif s == "nih":
                mod = import_module("rag.etl.step04_chunk.chunker_nih")
                if hasattr(mod, 'main'):
                    mod.main()
                elif hasattr(mod, 'run'):
                    mod.run(processed_dir=cfg.processed_dir, chunks_dir=cfg.chunks_dir)
                else:
                    logger.warning("⚠ [CHUNK] nih: run() 또는 main() 함수가 없습니다. 스킵합니다.")
            elif s == "protocols":
                mod = import_module("rag.etl.step04_chunk.chunker_protocols")
                if hasattr(mod, 'main'):
                    mod.main()
                elif hasattr(mod, 'run'):
                    mod.run(processed_dir=cfg.processed_dir, chunks_dir=cfg.chunks_dir)
                else:
                    logger.warning("⚠ [CHUNK] protocols: run() 또는 main() 함수가 없습니다. 스킵합니다.")
            else:
                raise ValueError(f"Unknown source: {s}")

            logger.info("✔ [CHUNK] done source=%s", s)
        except Exception as e:
            logger.error(f"❌ [CHUNK] source={s} 실패: {e}", exc_info=True)


# ─────────────────────────────────────────────
# 5) Embedding 단계
# ─────────────────────────────────────────────


def run_embed(source: SourceType, cfg: PipelineConfig, limit: int | None = None) -> None:
    """
    05_embed/ 아래 각 소스 모듈의 run() 또는 main() 호출.

    기대 시그니처:
      rag.etl.step05_embed.embed_pubmed.run(chunks_dir, embeddings_dir)
      rag.etl.step05_embed.embed_nih.run(...)
      rag.etl.step05_embed.embed_protocols.main()  # main() 함수 사용
    """
    logger = logging.getLogger("etl.embed")
    ensure_dirs(cfg.embeddings_dir)

    if source == "all":
        targets: Sequence[SourceType] = ["pubmed", "nih", "protocols"]
    else:
        targets = [source]

    for s in targets:
        logger.info("▶ [EMBED] start source=%s (limit=%s)", s, limit)

        try:
            if s == "pubmed":
                mod = import_module("rag.etl.step05_embed.embed_pubmed")
                if hasattr(mod, 'run'):
                    mod.run(
                        chunks_dir=cfg.chunks_dir,
                        embeddings_dir=cfg.embeddings_dir,
                    )
                elif hasattr(mod, 'main'):
                    mod.main()
                else:
                    logger.warning("⚠ [EMBED] pubmed: run() 또는 main() 함수가 없습니다. 스킵합니다.")
            elif s == "nih":
                mod = import_module("rag.etl.step05_embed.embed_nih")
                nih_processed_root = Path(cfg.processed_dir) / "nih"
                if hasattr(mod, 'run'):
                    mod.run(
                        chunks_dir=str(nih_processed_root),
                        embeddings_dir=cfg.embeddings_dir,
                    )
                elif hasattr(mod, 'main'):
                    mod.main()
                else:
                    logger.warning("⚠ [EMBED] nih: 모듈이 비어있거나 run()/main() 함수가 없습니다. 스킵합니다.")
            elif s == "protocols":
                mod = import_module("rag.etl.step05_embed.embed_protocols")
                if hasattr(mod, 'main'):
                    mod.main()
                elif hasattr(mod, 'run'):
                    mod.run(chunks_dir=cfg.chunks_dir, embeddings_dir=cfg.embeddings_dir)
                else:
                    logger.warning("⚠ [EMBED] protocols: run() 또는 main() 함수가 없습니다. 스킵합니다.")
            else:
                raise ValueError(f"Unknown source: {s}")

            logger.info("✔ [EMBED] done source=%s", s)
        except ModuleNotFoundError as e:
            logger.warning(f"⏭  [EMBED] source={s} 모듈을 찾을 수 없습니다. 스킵합니다: {e}")
        except Exception as e:
            logger.error(f"❌ [EMBED] source={s} 실패: {e}", exc_info=True)


# ─────────────────────────────────────────────
# 6) Upsert 단계 (pgvector)
# ─────────────────────────────────────────────


def run_upsert(cfg: PipelineConfig) -> None:
    """
    06_upsert/upsert_pgvector.py 의 run() 호출.

    기대 시그니처:
      rag.etl.step06_upsert.upsert_pgvector.run(
          embeddings_dir: str,
      )
    """
    logger = logging.getLogger("etl.upsert")

    logger.info("▶ [UPSERT] start")

    mod = import_module("rag.etl.step06_upsert.upsert_pgvector")
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

    run_chunk(source=args.source, cfg=cfg)
    run_embed(source=args.source, cfg=cfg)
    run_upsert(cfg=cfg)

    logger.info("=== RAG ETL PIPELINE DONE ===")


if __name__ == "__main__":
    main()
