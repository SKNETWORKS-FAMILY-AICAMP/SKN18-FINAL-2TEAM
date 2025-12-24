#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChunkGenerator: read sections CSV and produce chunk CSV (batch processing).
"""
from pathlib import Path
import csv
import re
from tqdm import tqdm

from chunking import (
    sentence_chunks,
    make_chunk_id,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    process_section_text_for_chunking,
)

# [수정됨] load_existing_chunk_ids를 pmc_data_loader에서 직접 임포트합니다.
from rag.etl.step04_chunk.pmc_chunk_common.pmc_chunk_csv_utils import load_existing_chunk_ids 


class ChunkGenerator:
    def __init__(
        self,
        input_csv: str,
        chunk_csv: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        batch_size: int = 100,
        meta_csv: str = None,
        split_meta: bool = False,
    ):
        self.input_csv = Path(input_csv)
        self.chunk_csv = Path(chunk_csv)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.batch_size = batch_size
        self.meta_csv = Path(meta_csv) if meta_csv else None
        self.split_meta = bool(split_meta)

    def run(self, resume: bool = True):
        if not self.input_csv.exists():
            raise FileNotFoundError(f"Input CSV not found: {self.input_csv}")

        existing_chunk_ids = set()
        file_exists = self.chunk_csv.exists()
        if resume and file_exists:
            existing_chunk_ids = load_existing_chunk_ids(self.chunk_csv)
            if existing_chunk_ids:
                print(f"[OK] Found {len(existing_chunk_ids)} existing chunks in {self.chunk_csv} (resume mode)")

        fieldnames = [
            "chunk_id",
            "section_id",
            "chunk_seq",
            "path",
            "start_char",
            "end_char",
            "text_chunk",
            "fig_ref_markers",
            "ref_ids",
        ]

        out_f = self.chunk_csv.open("a", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        new_chunks = 0
        total_sections = 0
        pbar = None

        try:
            with self.input_csv.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                total_sections = sum(1 for _ in reader)

            if self.split_meta and self.meta_csv is not None:
                meta_cols = [
                    "section_id",
                    "pmid",
                    "topic_category",
                    "path",
                    "section_category",
                    "article_category",
                    "fig_ids",
                    "table_ids",
                    "section_title",
                ]
                with self.input_csv.open("r", encoding="utf-8-sig", newline="") as fr:
                    rdr = csv.DictReader(fr)
                    self.meta_csv.parent.mkdir(parents=True, exist_ok=True)
                    with self.meta_csv.open("w", encoding="utf-8-sig", newline="") as fw:
                        writer_meta = csv.DictWriter(fw, fieldnames=meta_cols)
                        writer_meta.writeheader()
                        for r in rdr:
                            out = {k: (r.get(k) if k in r else None) for k in meta_cols}
                            writer_meta.writerow(out)

            est_total_chunks = max(total_sections * 2, 100)
            pbar = tqdm(total=est_total_chunks, desc="데이터 분리 중", unit="chunk")

            with self.input_csv.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    written = self._process_row(row, writer, out_f, existing_chunk_ids, resume, pbar)
                    new_chunks += written

        except KeyboardInterrupt:
            print("\n[!] Interrupted by user. Progress saved so far.")
        finally:
            if pbar:
                pbar.close()
            out_f.close()
            print(f"\n[DONE] Chunking finished. new_chunks={new_chunks}")

    def _process_row(self, row, writer, out_f, existing_chunk_ids, resume, pbar):
        new_count = 0
        section_id = str(row.get("section_id", "")).strip()
        raw_text = str(row.get("section_text", "")).strip() # <- [RAW 텍스트 로드]
        
        # [FIX] path_str 정의 추가 (CSV의 'path' 컬럼 값 읽기)
        path_str = str(row.get("path", "")).strip()

        if not section_id or not raw_text:
            return 0

        # 청크 생성 직전에 chunking.py의 통합 함수 호출
        processed = process_section_text_for_chunking(raw_text)
        
        combined = processed["clean_text"] # <- Clean Text로 청킹 시작

        for seq, (start, end, ch_text) in enumerate(sentence_chunks(combined, self.chunk_size, self.overlap), start=1):
            chunk_id = make_chunk_id(section_id, seq)

            if resume and chunk_id in existing_chunk_ids:
                continue

            csv_text = re.sub(r"[\r\n]+", " ", ch_text)
            csv_text = re.sub(r"\s+", " ", csv_text).strip()
            csv_text = csv_text.lstrip(" \t.,-−")

            if not csv_text:
                continue

            writer.writerow(
                {
                    "chunk_id": chunk_id,
                    "section_id": section_id,
                    "chunk_seq": seq,
                    "path": path_str,  # 이제 정의된 변수를 사용하므로 에러 없음
                    "start_char": start,
                    "end_char": end,
                    "text_chunk": csv_text,
                    "fig_ref_markers": processed["fig_ref_markers"], 
                    "ref_ids": processed["ref_ids"],                 
                }
            )
            existing_chunk_ids.add(chunk_id)
            new_count += 1
            
            if pbar:
                pbar.update(1)
        
        out_f.flush()
        return new_count