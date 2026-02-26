"""
rag/etl/pipeline_runner_01245.py

PubMed 전용 RAG ETL 파이프라인 (ingest → normalize → chunk → embed).

단계:
  1) ingest    : PubMed API에서 raw 데이터 수집
  2) normalize : raw JSON → CSV (sections_for_chunk.csv 등)
  3) chunk     : sections_for_chunk.csv → pmc_chunks.csv
  4) embed     : pmc_chunks.csv → pmc_vector.csv

출력 파일은 모두 실행 시점 타임스탬프(MMDD_HHMM)로 구분됩니다.
  예) pubmed_new_0209_2026.json
      pmc_csv_0209_2026/sections_for_chunk.csv
      pmc_chunks_0209_2026.csv
      pmc_vector_0209_2026.csv

사용 예:
  python rag/etl/pipeline_runner_01245.py
"""

# ════════════════════════════════════════════════════════
#  PubMed Pipeline Config  ← 여기만 수정하세요
# ════════════════════════════════════════════════════════

PUBMED_FROM_YEAR: int = 2024   # 수집 시작 연도
PUBMED_TO_YEAR:   int = 2024   # 수집 종료 연도

PUBMED_TARGET_COUNT: int = 1  # 카테고리당 수집 목표 논문 수
PUBMED_BATCH_SIZE:   int = 50  # API 한 번에 검색할 배치 크기

SKIP_INGEST:    bool = False   # True면 ingest 단계 건너뜀 (이미 raw JSON이 있을 때)
SKIP_NORMALIZE: bool = False   # True면 normalize 단계 건너뜀 (이미 CSV가 있을 때)
SKIP_CHUNK:     bool = False   # True면 chunk 단계 건너뜀 (이미 pmc_chunks가 있을 때)
SKIP_EMBED:     bool = False   # True면 embed 단계 건너뜀

# ════════════════════════════════════════════════════════

import logging
import os
import sys
from datetime import datetime
from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAW_DIR        = str(PROJECT_ROOT / "data" / "raw")
PROCESSED_DIR  = str(PROJECT_ROOT / "data" / "processed")
CHUNKS_DIR     = str(PROJECT_ROOT / "data" / "chunks")
EMBEDDINGS_DIR = str(PROJECT_ROOT / "data" / "embeddings")


def setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def patch_pmc_config() -> None:
    """
    pmc_config.py의 날짜 범위를 파이프라인 상단 컨피그 값으로 덮어씁니다.
    ingest_pubmed.py가 import-time에 pmc_config 변수를 읽으므로
    ingest 모듈을 import하기 전에 반드시 먼저 호출해야 합니다.
    """
    import rag.etl.common.pmc_config as pmc_cfg

    pmc_cfg.DEFAULT_FROM_DATE  = f"{PUBMED_FROM_YEAR}/01/01"
    pmc_cfg.DEFAULT_UNTIL_DATE = f"{PUBMED_TO_YEAR}/12/31"

    logger = logging.getLogger("etl.pipeline")
    logger.info(
        "[CONFIG] PubMed 수집 기간: %s ~ %s",
        pmc_cfg.DEFAULT_FROM_DATE,
        pmc_cfg.DEFAULT_UNTIL_DATE,
    )


# ─────────────────────────────────────────────
# STEP 1: Ingest
# ─────────────────────────────────────────────

def run_ingest(stamp: str) -> str:
    """
    실행 파일 : rag/etl/step01_ingest/ingest_pubmed.py → run_incremental()
    입  력   : PubMed E-utilities API + OAI-PMH API
    출  력   : data/raw/pubmed/pubmed_new_{MMDD_HHMM}.json
    반환값   : 생성된 JSON 파일 경로
    """
    logger = logging.getLogger("etl.ingest")
    logger.info("▶ [STEP 1] INGEST start")

    raw_pubmed_dir = Path(RAW_DIR) / "pubmed"
    raw_pubmed_dir.mkdir(parents=True, exist_ok=True)

    prev_file = raw_pubmed_dir / "pubmed_existing.json"
    new_file  = raw_pubmed_dir / f"pubmed_new_{stamp}.json"

    from rag.etl.step01_ingest.ingest_pubmed import run_incremental
    run_incremental(
        prev_file=str(prev_file),
        new_file=str(new_file),
        target_count=PUBMED_TARGET_COUNT,
        batch=PUBMED_BATCH_SIZE,
    )

    logger.info("✔ [STEP 1] INGEST done  →  %s", new_file)
    return str(new_file)


# ─────────────────────────────────────────────
# STEP 2: Normalize
# ─────────────────────────────────────────────

def run_normalize(stamp: str) -> str:
    """
    실행 파일 : rag/etl/step02_normalize/normalize_pubmed.py → run()
    입  력   : data/raw/pubmed/*.json (가장 최신 파일 자동 선택)
    출  력   : data/processed/pubmed/pmc_csv_{MMDD_HHMM}/
                 ├── articles.csv
                 ├── sections.csv
                 ├── sections_meta.csv
                 ├── sections_for_chunk.csv  ← STEP 3 입력
                 ├── equations.csv
                 ├── figures.csv
                 ├── tables.csv
                 └── references.csv
    반환값   : sections_for_chunk.csv 절대 경로
    """
    logger = logging.getLogger("etl.normalize")
    logger.info("▶ [STEP 2] NORMALIZE start")

    csv_out_subdir = f"pubmed/pmc_csv_{stamp}"

    mod = import_module("rag.etl.step02_normalize.normalize_pubmed")
    mod.run(raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR, csv_out_dir=csv_out_subdir)

    chunk_input = Path(PROCESSED_DIR) / csv_out_subdir / "sections_for_chunk.csv"
    logger.info("✔ [STEP 2] NORMALIZE done  →  %s", chunk_input.parent)
    return str(chunk_input)


# ─────────────────────────────────────────────
# STEP 3: Chunk
# ─────────────────────────────────────────────

def run_chunk(stamp: str, input_csv: str) -> str:
    """
    실행 파일 : rag/etl/step04_chunk/chunker_pubmed.py → run()
    입  력   : sections_for_chunk.csv (STEP 2 출력)
    출  력   : data/chunks/pubmed/pmc_chunks_{MMDD_HHMM}.csv
    반환값   : 생성된 청크 CSV 경로
    """
    logger = logging.getLogger("etl.chunk")
    logger.info("▶ [STEP 3] CHUNK start")

    chunks_pubmed_dir = Path(CHUNKS_DIR) / "pubmed"
    chunks_pubmed_dir.mkdir(parents=True, exist_ok=True)

    output_csv = str(chunks_pubmed_dir / f"pmc_chunks_{stamp}.csv")

    mod = import_module("rag.etl.step04_chunk.chunker_pubmed")
    mod.run(
        processed_dir=PROCESSED_DIR,
        chunks_dir=CHUNKS_DIR,
        input_csv=input_csv,
        output_csv=output_csv,
    )

    logger.info("✔ [STEP 3] CHUNK done  →  %s", output_csv)
    return output_csv


# ─────────────────────────────────────────────
# STEP 4: Embed
# ─────────────────────────────────────────────

def run_embed(stamp: str, chunk_csv: str) -> None:
    """
    실행 파일 : rag/etl/step05_embed/embed_pubmed.py → run_for_files()
    입  력   : data/chunks/pubmed/pmc_chunks_{MMDD_HHMM}.csv (STEP 3 출력)
    출  력   : data/embeddings/pubmed/pmc_vector_{MMDD_HHMM}.csv
    """
    logger = logging.getLogger("etl.embed")
    logger.info("▶ [STEP 4] EMBED start")

    embed_pubmed_dir = Path(EMBEDDINGS_DIR) / "pubmed"
    embed_pubmed_dir.mkdir(parents=True, exist_ok=True)

    output_csv = str(embed_pubmed_dir / f"pmc_vector_{stamp}.csv")

    from rag.etl.step05_embed.embed_pubmed import run_for_files
    run_for_files(
        chunks=chunk_csv,
        output=output_csv,
        resume=True,
        write_csv=True,
        pg_batch_size=500,
    )

    logger.info("✔ [STEP 4] EMBED done  →  %s", output_csv)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    setup_logging()
    logger = logging.getLogger("etl.pipeline")

    stamp = datetime.now().strftime("%m%d_%H%M")

    logger.info("=== PubMed ETL PIPELINE START (stamp=%s) ===", stamp)
    logger.info(
        "Config: from=%d, to=%d, target=%d/category, batch=%d",
        PUBMED_FROM_YEAR, PUBMED_TO_YEAR, PUBMED_TARGET_COUNT, PUBMED_BATCH_SIZE,
    )
    logger.info(
        "Paths: raw=%s, processed=%s, chunks=%s, embeddings=%s",
        RAW_DIR, PROCESSED_DIR, CHUNKS_DIR, EMBEDDINGS_DIR,
    )

    patch_pmc_config()

    if not SKIP_INGEST:
        run_ingest(stamp)
    else:
        logger.info("⏭  [STEP 1] INGEST skipped")

    if not SKIP_NORMALIZE:
        chunk_input = run_normalize(stamp)
    else:
        chunk_input = str(
            Path(PROCESSED_DIR) / f"pubmed/pmc_csv_{stamp}" / "sections_for_chunk.csv"
        )
        logger.info("⏭  [STEP 2] NORMALIZE skipped  (input: %s)", chunk_input)

    if not SKIP_CHUNK:
        chunk_csv = run_chunk(stamp, chunk_input)
    else:
        chunk_csv = str(Path(CHUNKS_DIR) / "pubmed" / f"pmc_chunks_{stamp}.csv")
        logger.info("⏭  [STEP 3] CHUNK skipped  (input: %s)", chunk_csv)

    if not SKIP_EMBED:
        run_embed(stamp, chunk_csv)
    else:
        logger.info("⏭  [STEP 4] EMBED skipped")

    logger.info("=== PubMed ETL PIPELINE DONE ===")
    logger.info(
        "최종 임베딩 파일: %s",
        str(Path(EMBEDDINGS_DIR) / "pubmed" / f"pmc_vector_{stamp}.csv"),
    )


if __name__ == "__main__":
    main()
