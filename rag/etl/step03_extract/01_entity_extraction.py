"""
KG 엔터티 추출 파이프라인 진입점.

`extract_for_kg` 디렉터리의 스크립트들을 파이프라인 형태로 순차 실행한다.

- PubMed (`source == "pubmed"` 또는 `"all"`)
    1) `pmc_section_generate_keywords.py`
    2) `pmc_entity_gilda_mappiing.py`
    3) `pmc_section_keywords_primekg.py`
    4) `pmc_experiment_table_llm.py`

- NIH (`source == "nih"` 또는 `"all"`)
    - `nih_entity_batch_extractor.py`

- Protocols.io (`source == "protocols"` 또는 `"all"`)
    - `protocol_category_etl.py`

주의: 각 스크립트는 내부에 자체 경로(입력/출력 CSV, Neo4j import 디렉터리 등)를
하드코딩해 둔 상태라, 실제 데이터 위치에 맞게 해당 스크립트들을 먼저 정리해 두어야 한다.
여기서는 단순히 스크립트들을 정해진 순서로 실행만 해 준다.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path


def _run_module(module: str, *args: str) -> None:
    """
    주어진 모듈을 별도 파이썬 프로세스로 실행한다.

    예: _run_module("rag.etl.step03_extract.extract_for_kg.pmc_section_generate_keywords")
    """
    cmd = [sys.executable, "-m", module]
    cmd.extend(args)
    logging.getLogger("etl.extract.entities").info("▶ run module: %s %s", module, " ".join(args))
    subprocess.run(cmd, check=True)


def _run_pubmed_pipeline() -> None:
    log = logging.getLogger("etl.extract.entities")
    base_mod = "rag.etl.step03_extract.extract_for_kg"

    # 0) article 메타데이터 LLM 기반 enrich (article_enriched.csv 등 생성)
    try:
        _run_module(f"{base_mod}.pmc_enrich_metadata")
    except Exception as e:
        log.error("pmc_enrich_metadata 실행 실패: %s", e, exc_info=True)
        raise

    # 1) 섹션 단위 키워드/엔터티 추출
    try:
        _run_module(f"{base_mod}.pmc_section_generate_keywords")
    except Exception as e:
        log.error("pmc_section_generate_keywords 실행 실패: %s", e, exc_info=True)
        raise

    # 2) 엔터티를 Gilda/PrimeKG에 매핑
    try:
        _run_module(f"{base_mod}.pmc_entity_gilda_mappiing")
    except Exception as e:
        log.error("pmc_entity_gilda_mappiing 실행 실패: %s", e, exc_info=True)
        raise

    # 3) 섹션 키워드에 PrimeKG 노드 ID 부여
    try:
        _run_module(f"{base_mod}.pmc_section_keywords_primekg")
    except Exception as e:
        log.error("pmc_section_keywords_primekg 실행 실패: %s", e, exc_info=True)
        raise

    # 4) 실험 테이블 추출 (LLM 기반)
    try:
        _run_module(f"{base_mod}.pmc_experiment_table_llm")
    except Exception as e:
        log.error("pmc_experiment_table_llm 실행 실패: %s", e, exc_info=True)
        raise


def _run_nih_pipeline() -> None:
    log = logging.getLogger("etl.extract.entities")
    try:
        _run_module("rag.etl.step03_extract.extract_for_kg.nih_entity_batch_extractor")
    except Exception as e:
        log.error("nih_entity_batch_extractor 실행 실패: %s", e, exc_info=True)
        raise


def _run_protocols_pipeline() -> None:
    log = logging.getLogger("etl.extract.entities")
    try:
        _run_module("rag.etl.step03_extract.extract_for_kg.protocol_category_etl")
    except Exception as e:
        log.error("protocol_category_etl 실행 실패: %s", e, exc_info=True)
        raise


def run(processed_dir: str, entities_dir: str, source: str | None = None) -> None:
    """
    KG 엔터티 추출 전체 파이프라인 실행.

    processed_dir, entities_dir 인자는 현재는 경로 계산에는 사용하지 않고
    로그 용도로만 사용한다. (각 하위 스크립트가 자체 경로 설정을 가지고 있기 때문)
    """
    logger = logging.getLogger("etl.extract.entities")
    logger.info(
        "[EXTRACT:Entities] start: processed_dir=%s, entities_dir=%s, source=%s",
        processed_dir,
        entities_dir,
        source,
    )

    src = source or "pubmed"

    if src in ("pubmed", "all"):
        logger.info("[EXTRACT:Entities] PubMed KG 파이프라인 실행")
        _run_pubmed_pipeline()

    if src in ("nih", "all"):
        logger.info("[EXTRACT:Entities] NIH KG 파이프라인 실행")
        _run_nih_pipeline()

    if src in ("protocols", "all"):
        logger.info("[EXTRACT:Entities] Protocols.io KG 파이프라인 실행")
        _run_protocols_pipeline()

    logger.info("[EXTRACT:Entities] done")
