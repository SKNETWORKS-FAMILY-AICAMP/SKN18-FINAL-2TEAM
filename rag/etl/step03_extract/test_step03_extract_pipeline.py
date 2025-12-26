"""
step03_extract (00~02단계) 테스트용 파이프라인 실행 스크립트.

순서:
  1) 00_pmc_normalization_pipeline.run(cfg, source)
  2) 01_entity_extraction.run(processed_dir, entities_dir, source)
  3) 02_relation_extraction.run(entities_dir, source)

`rag.etl.pipeline_runner.PipelineConfig`를 그대로 사용하여
data/processed, data/entities 등의 기본 경로 설정을 재사용한다.
"""

from __future__ import annotations

import os
import sys
import argparse
import logging
from importlib import import_module
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트(SKN18-FINAL-2TEAM)가 import 경로에 잡히도록 설정
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드 (프로젝트 루트 기준)
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

from rag.etl.pipeline_runner import PipelineConfig, SourceType, setup_logging


def run_step03_pipeline(source: SourceType = "pubmed", limit: int | None = None) -> None:
    """
    step03_extract 단계(00~02)를 순차적으로 실행한다.
    """
    setup_logging()
    logger = logging.getLogger("etl.step03_test")

    cfg = PipelineConfig()
    logger.info("[STEP03-TEST] start: source=%s, limit=%s, cfg=%s", source, limit, cfg)

    # 00) PMC 정제 파이프라인 (pmid/section_id/cleansing)
    try:
        norm_mod = import_module("rag.etl.step03_extract.00_pmc_normalization_pipeline")
        logger.info("[STEP03-TEST] 00_pmc_normalization_pipeline.run() (limit=%s)", limit)
        norm_mod.run(cfg, source)  # 현재는 limit 미사용
    except Exception as e:
        logger.error("[STEP03-TEST] 00_pmc_normalization_pipeline 실행 실패: %s", e, exc_info=True)
        raise

    # 01) 엔터티 추출 파이프라인 (extract_for_kg)
    try:
        ent_mod = import_module("rag.etl.step03_extract.01_entity_extraction")
        logger.info("[STEP03-TEST] 01_entity_extraction.run()")
        ent_mod.run(  # type: ignore[attr-defined]
            processed_dir=cfg.processed_dir,
            entities_dir=cfg.entities_dir,
            source=source,
        )
    except Exception as e:
        logger.error("[STEP03-TEST] 01_entity_extraction 실행 실패: %s", e, exc_info=True)
        raise

    # 02) 관계/매핑 파이프라인 (mapping_fot_kg)
    try:
        rel_mod = import_module("rag.etl.step03_extract.02_relation_extraction")
        logger.info("[STEP03-TEST] 02_relation_extraction.run()")
        rel_mod.run(  # type: ignore[attr-defined]
            entities_dir=cfg.entities_dir,
            source=source,
        )
    except Exception as e:
        logger.error("[STEP03-TEST] 02_relation_extraction 실행 실패: %s", e, exc_info=True)
        raise

    logger.info("[STEP03-TEST] done")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test runner for step03_extract (00~02 pipeline)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["pubmed", "nih", "protocols", "all"],
        default="pubmed",
        help="ETL 소스 선택 (기본값: pubmed)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="테스트용 최대 처리 row 수 (현재는 로깅/확장용 파라미터)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_step03_pipeline(source=args.source, limit=args.limit)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
