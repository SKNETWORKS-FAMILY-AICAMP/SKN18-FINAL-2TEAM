#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PubMed 테이블 캡션 임베딩 모듈.

- 입력:  {processed_dir}/pubmed/pmc_csv/tables.csv
- 출력:  {embeddings_dir}/pubmed/article_table_emb.csv

tables.csv의 table_caption 필드를 임베딩하여
article_table_emb.csv를 생성한다.
"""

import csv
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Set

from openai import OpenAI
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ─────────────────────────────────────
# 공용 설정 임포트
# ─────────────────────────────────────
from rag.etl.step04_chunk.pmc_chunk_common.chunking import (
    DEFAULT_EMBED_DIM,
    DEFAULT_EMBED_MODEL,
    OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    RATE_LIMIT_DELAY,
    to_pgvector_literal,
)

# ─────────────────────────────────────
# 출력 CSV 컬럼 정의
# ─────────────────────────────────────
OUTPUT_FIELDNAMES = [
    "pmcid",
    "pmid",
    "table_id",
    "table_content",
    "table_caption",
    "table_url",
    "table_caption_emb",
]

INPUT_REQUIRED_COLS = [
    "table_id",
    "pmcid",
    "pmid",
    "table_caption",
]


def _load_existing_table_ids(csv_path: Path) -> Set[str]:
    """이미 임베딩된 table_id 집합을 반환 (resume용)."""
    if not csv_path.exists():
        return set()
    existing: Set[str] = set()
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "table_id" not in reader.fieldnames:
                return set()
            for row in reader:
                tid = row.get("table_id")
                if tid:
                    existing.add(tid)
    except Exception:
        return set()
    return existing


def embed_text(client: OpenAI, text: str, model: str = DEFAULT_EMBED_MODEL) -> List[float]:
    """OpenAI 임베딩 API 호출."""
    resp = client.embeddings.create(
        input=[text],
        model=model,
    )
    return resp.data[0].embedding


def run(processed_dir: str, embeddings_dir: str, resume: bool = True) -> None:
    """
    pipeline_runner.run_embed에서 호출되는 엔트리포인트.

    - 입력:  {processed_dir}/pubmed/pmc_csv/tables.csv
    - 출력:  {embeddings_dir}/pubmed/article_table_emb.csv
    """
    proc_base = Path(processed_dir)
    embeds_base = Path(embeddings_dir)

    input_csv = proc_base / "pubmed" / "pmc_csv" / "tables.csv"
    output_csv = embeds_base / "pubmed" / "article_table_emb.csv"

    logger.info(
        "[EMBED:Tables] run() called with processed_dir=%s, embeddings_dir=%s",
        processed_dir,
        embeddings_dir,
    )
    logger.info(
        "[EMBED:Tables] resolved paths: input_csv=%s, output_csv=%s",
        input_csv,
        output_csv,
    )

    if not input_csv.exists():
        logger.warning("[EMBED:Tables] tables.csv not found: %s → 스킵", input_csv)
        return

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다 (.env 확인).")

    # Azure OpenAI 또는 표준 OpenAI 클라이언트 초기화
    if AZURE_OPENAI_ENDPOINT:
        # Azure OpenAI 사용
        client = OpenAI(
            base_url=AZURE_OPENAI_ENDPOINT,
            api_key=OPENAI_API_KEY
        )
        logger.info(f"[EMBED:Tables] Azure OpenAI 사용: {AZURE_OPENAI_ENDPOINT}")
    else:
        # 표준 OpenAI 사용
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("[EMBED:Tables] 표준 OpenAI 사용")

    # resume: 기존 임베딩된 table_id 건너뛰기
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    existing_ids: Set[str] = set()
    file_exists = output_csv.exists()
    if resume and file_exists:
        existing_ids = _load_existing_table_ids(output_csv)
        if existing_ids:
            logger.info("[EMBED:Tables] resume mode: %d개 기존 table_id 발견", len(existing_ids))

    # 입력 CSV 행 수 계산 (진행률 표시용)
    total_rows = 0
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # 필수 컬럼 검증
        missing = [c for c in INPUT_REQUIRED_COLS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"[EMBED:Tables] tables.csv에 필수 컬럼이 없습니다: {missing}")
        total_rows = sum(1 for _ in reader)

    logger.info("[EMBED:Tables] 총 %d개 테이블 행 처리 시작", total_rows)

    # 출력 파일 열기 (append 모드)
    out_f = output_csv.open("a", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(out_f, fieldnames=OUTPUT_FIELDNAMES)
    if not file_exists:
        writer.writeheader()

    new_count = 0
    skip_count = 0

    try:
        with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            pbar = tqdm(reader, total=total_rows, desc="[EMBED:Tables]", unit="row")

            for row in pbar:
                table_id = (row.get("table_id") or "").strip()
                if not table_id:
                    continue

                # resume: 이미 처리된 행 건너뛰기
                if resume and table_id in existing_ids:
                    skip_count += 1
                    continue

                caption = (row.get("table_caption") or "").strip()
                if not caption:
                    # 캡션이 없으면 임베딩 불가 → 건너뛰기
                    skip_count += 1
                    continue

                # 임베딩 생성
                try:
                    emb = embed_text(client, caption, model=DEFAULT_EMBED_MODEL)
                except Exception as e:
                    logger.error("[EMBED:Tables] table_id=%s 임베딩 실패: %s", table_id, e)
                    continue

                emb_literal = to_pgvector_literal(emb)

                writer.writerow({
                    "pmcid": row.get("pmcid", ""),
                    "pmid": row.get("pmid", ""),
                    "table_id": table_id,
                    "table_content": row.get("table_content", ""),
                    "table_caption": caption,
                    "table_url": row.get("table_url", ""),
                    "table_caption_emb": emb_literal,
                })
                out_f.flush()
                new_count += 1

                # Rate limit 대응
                if RATE_LIMIT_DELAY and RATE_LIMIT_DELAY > 0:
                    time.sleep(RATE_LIMIT_DELAY)

    except KeyboardInterrupt:
        logger.warning("[EMBED:Tables] 사용자 인터럽트. 현재까지 저장됨.")
    finally:
        out_f.close()

    logger.info(
        "[EMBED:Tables] 완료: new=%d, skipped=%d, output=%s",
        new_count,
        skip_count,
        output_csv,
    )


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level="INFO", format="[%(asctime)s] %(name)s - %(message)s")

    ap = argparse.ArgumentParser(description="PubMed 테이블 캡션 임베딩")
    ap.add_argument("--processed-dir", default="data/processed", help="processed 디렉터리")
    ap.add_argument("--embeddings-dir", default="data/embeddings", help="embeddings 출력 디렉터리")
    ap.add_argument("--no-resume", action="store_true", help="처음부터 다시 임베딩")
    args = ap.parse_args()

    run(
        processed_dir=args.processed_dir,
        embeddings_dir=args.embeddings_dir,
        resume=not args.no_resume,
    )
