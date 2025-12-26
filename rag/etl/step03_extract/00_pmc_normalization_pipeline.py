"""
PMC 관련 PMC CSV들에 대해 pmid 및 section_id 기반 정제 파이프라인을 수행하는 모듈.

- 1단계: pmid 필터링
    - 입력: data/processed/pubmed/pmc_csv 안의 모든 *.csv
    - 처리: nomalization_for_kg.pmc_filter_pmid_nonzero.main() 호출
    - 출력: data/processed/pubmed/pmc_csv/filtered/<원본파일명>

- 2단계: section_id 필터링
    - 입력:
        - data/chunks/pubmed/pmc_chunks.csv
        - data/embeddings/pubmed/pmc_vector.csv
      (둘 다 section_id 컬럼을 가정)
    - 처리: nomalization_for_kg.pmc_filter_section_id_zero_prefix.main() 호출
    - 출력: 각 파일 옆에 *_filtered.csv

추후 rag.etl.pipeline_runner.run_extract 와 비슷하게
cfg, source 를 받아서 파이프라인 중간에서 호출할 수 있도록
run(cfg, source) 시그니처를 맞춰 둔다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rag.etl.pipeline_runner import PipelineConfig, SourceType

from .nomalization_for_kg.pmc_filter_pmid_nonzero import main as filter_pmid_nonzero
from .nomalization_for_kg.pmc_filter_section_id_zero_prefix import (
    main as filter_section_id_zero_prefix,
)
from .nomalization_for_kg import pmc_cleansing_ref


logger = logging.getLogger("etl.pmc_normalization")


def _pmid_filter_step(pmc_dir: Path) -> None:
    """
    pmc_csv 디렉터리 안의 모든 CSV 파일에 대해
    pmid == 0 / 빈 값 / NaN 을 제거하는 필터를 적용한다.

    결과는 pmc_csv/filtered/<원본파일명> 으로 저장한다.
    """
    if not pmc_dir.exists():
        logger.warning("[PMC] pmc_csv 디렉터리를 찾을 수 없습니다: %s", pmc_dir)
        return

    filtered_dir = pmc_dir / "filtered"
    filtered_dir.mkdir(parents=True, exist_ok=True)

    for input_path in pmc_dir.glob("*.csv"):
        if not input_path.is_file():
            continue

        output_path = filtered_dir / input_path.name
        logger.info("[PMC] pmid 필터링 시작: %s -> %s", input_path, output_path)
        filter_pmid_nonzero(str(input_path), str(output_path))
        logger.info("[PMC] pmid 필터링 완료: %s", output_path)


def _section_id_filter_step(chunks_path: Path, vector_path: Path) -> None:
    """
    section_id 컬럼 기준으로 '0_' 프리픽스를 가진 섹션들을 제거한다.

    - chunks_path: pmc_chunks.csv
    - vector_path: pmc_vector.csv
    """
    # chunks
    if chunks_path.exists():
        chunks_out = chunks_path.with_name(chunks_path.stem + "_filtered.csv")
        logger.info(
            "[PMC] section_id 필터링 (chunks) 시작: %s -> %s",
            chunks_path,
            chunks_out,
        )
        filter_section_id_zero_prefix(str(chunks_path), str(chunks_out))
        logger.info("[PMC] section_id 필터링 (chunks) 완료: %s", chunks_out)
    else:
        logger.warning("[PMC] section_id 필터 대상 chunks 파일이 없습니다: %s", chunks_path)

    # vector
    if vector_path.exists():
        vector_out = vector_path.with_name(vector_path.stem + "_filtered.csv")
        logger.info(
            "[PMC] section_id 필터링 (vector) 시작: %s -> %s",
            vector_path,
            vector_out,
        )
        filter_section_id_zero_prefix(str(vector_path), str(vector_out))
        logger.info("[PMC] section_id 필터링 (vector) 완료: %s", vector_out)
    else:
        logger.warning("[PMC] section_id 필터 대상 vector 파일이 없습니다: %s", vector_path)


def _cleansing_ref_step(filtered_dir: Path | None = None) -> None:
    """
    pmc_cleansing_ref.py 를 이용해
    references.csv / article_enriched.csv 의 제목을 정규화한다.

    기본적으로 pmc_cleansing_ref 모듈이 가진 설정 값(DATA_DIR, REF_FILE, ARTICLE_FILE)을 사용하되,
    filtered_dir 가 주어지면 DATA_DIR 을 pmid 필터링 결과 디렉터리(예: pmc_csv/filtered)로
    임시 변경해서 실행한다.
    """
    try:
        original_data_dir = getattr(pmc_cleansing_ref, "DATA_DIR", None)
        if filtered_dir is not None:
            pmc_cleansing_ref.DATA_DIR = str(filtered_dir)

        logger.info("[PMC] pmc_cleansing_ref: references 정규화 시작")
        pmc_cleansing_ref.process_csv(
            pmc_cleansing_ref.REF_FILE,
            title_col="ref_title",
            new_col="ref_title_norm",
        )
        logger.info("[PMC] pmc_cleansing_ref: references 정규화 완료")

        logger.info("[PMC] pmc_cleansing_ref: articles 정규화 시작")
        pmc_cleansing_ref.process_csv(
            pmc_cleansing_ref.ARTICLE_FILE,
            title_col="title",
            new_col="title_norm",
        )
        logger.info("[PMC] pmc_cleansing_ref: articles 정규화 완료")
    except Exception as e:
        logger.error("[PMC] pmc_cleansing_ref 실행 중 오류: %s", e, exc_info=True)
    finally:
        if filtered_dir is not None and original_data_dir is not None:
            pmc_cleansing_ref.DATA_DIR = original_data_dir


def run(cfg: PipelineConfig, source: SourceType) -> None:
    """
    PMC용 정제 파이프라인 실행.

    - source 가 'pubmed' 또는 'all' 일 때만 동작
    - cfg 에서 processed_dir / chunks_dir / embeddings_dir 를 사용해서
    실제 파일 경로를 계산한다.
    """
    if source not in ("pubmed", "all"):
        logger.info(
            "[PMC] source=%s 에 대해서는 PMC 정제를 수행하지 않습니다 (pubmed 전용).",
            source,
        )
        return

    # 1) pmid 필터링: data/processed/pubmed/pmc_csv
    pmc_dir = Path(cfg.processed_dir) / "pubmed" / "pmc_csv"
    _pmid_filter_step(pmc_dir)

    # 2) section_id 필터링:
    #    - data/chunks/pubmed/pmc_chunks.csv
    #    - data/embeddings/pubmed/pmc_vector.csv
    chunks_path = Path(cfg.chunks_dir) / "pubmed" / "pmc_chunks.csv"
    vector_path = Path(cfg.embeddings_dir) / "pubmed" / "pmc_vector.csv"
    _section_id_filter_step(chunks_path, vector_path)

    # 3) reference / article 제목 정규화 (pmc_cleansing_ref)
    filtered_dir = pmc_dir / "filtered"
    _cleansing_ref_step(filtered_dir)
