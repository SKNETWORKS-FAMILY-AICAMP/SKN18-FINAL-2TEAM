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
    combine_title_text,
    sentence_chunks,
    make_chunk_id,
    load_existing_chunk_ids,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
)


class ChunkGenerator:
    def __init__(
        self,
        input_csv: str,
        chunk_csv: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        batch_size: int = 100,
    ):
        self.input_csv = Path(input_csv)
        self.chunk_csv = Path(chunk_csv)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.batch_size = batch_size

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
            "start_char",
            "end_char",
            "text_chunk",
        ]

        out_f = self.chunk_csv.open("a", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        new_chunks = 0
        batch = []
        total_sections = 0
        pbar = None

        try:
            # First pass: count total rows (for progress bar)
            with self.input_csv.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                total_sections = sum(1 for _ in reader)
            
            # Estimate total chunks (rough: ~2-3 chunks per section on average)
            est_total_chunks = max(total_sections * 2, 1000)
            pbar = tqdm(total=est_total_chunks, desc="Chunking & writing", unit="chunk")

            # Second pass: process in batches
            with self.input_csv.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    batch.append(row)
                    
                    # Process batch when it reaches batch_size
                    if len(batch) >= self.batch_size:
                        chunks_written = self._process_batch(batch, writer, out_f, existing_chunk_ids, resume, pbar)
                        new_chunks += chunks_written
                        batch = []
                
                # Process remaining rows
                if batch:
                    chunks_written = self._process_batch(batch, writer, out_f, existing_chunk_ids, resume, pbar)
                    new_chunks += chunks_written

        except KeyboardInterrupt:
            print("\n[!] Interrupted by user. Progress saved so far.")
        finally:
            if pbar:
                pbar.close()
            out_f.close()
            print(f"\n[DONE] Chunking finished. new_chunks={new_chunks}")

    def _process_batch(self, batch, writer, out_f, existing_chunk_ids, resume, pbar):
        """Process a batch of rows and write chunks to CSV."""
        new_count = 0
        
        for row in batch:
            section_id = str(row.get("section_id", "")).strip()
            title = str(row.get("title", "")).strip()
            text = str(row.get("text", "")).strip()
            
            if not section_id or (not title and not text):
                continue
            
            combined = combine_title_text(title, text)
            if not combined or not combined.strip():
                continue
            
            chunks = sentence_chunks(combined, self.chunk_size, self.overlap)
            
            for seq, (start, end, ch_text) in enumerate(chunks, start=1):
                chunk_id = make_chunk_id(section_id, seq)
                
                if resume and chunk_id in existing_chunk_ids:
                    continue
                
                csv_text = re.sub(r"[\r\n]+", " ", ch_text)
                csv_text = re.sub(r"\s+", " ", csv_text).strip()
                
                writer.writerow(
                    {
                        "chunk_id": chunk_id,
                        "section_id": section_id,
                        "chunk_seq": seq,
                        "start_char": start,
                        "end_char": end,
                        "text_chunk": csv_text,
                    }
                )
                out_f.flush()
                existing_chunk_ids.add(chunk_id)
                new_count += 1
                # Update progress bar for each chunk written
                pbar.update(1)
        
        return new_count
