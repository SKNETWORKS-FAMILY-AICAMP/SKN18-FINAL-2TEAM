#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChunkEmbedder: load chunk CSV, produce embeddings, write output CSV.
"""
from pathlib import Path
import csv
import time
from typing import List, Optional
import pandas as pd
from tqdm import tqdm
from openai import OpenAI

try:
    import psycopg2
    from psycopg2.extras import execute_values
except Exception:
    psycopg2 = None

from chunking import (
    load_existing_chunk_ids,
    to_pgvector_literal,
    DEFAULT_EMBED_DIM,
    DEFAULT_EMBED_MODEL,
    OPENAI_API_KEY,
    RATE_LIMIT_DELAY,
)


class ChunkEmbedder:
    def __init__(
        self,
        chunk_csv: str,
        output_csv: str,
        embed_model: str = DEFAULT_EMBED_MODEL,
        embed_dim: int = DEFAULT_EMBED_DIM,
        pg_connect: Optional[dict] = None,
        pg_table: str = "pmc_section_chunk",
        write_csv: bool = True,
        pg_batch_size: int = 500,
    ):
        self.chunk_csv = Path(chunk_csv)
        self.output_csv = Path(output_csv)
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.pg_connect = pg_connect or {}
        self.pg_table = pg_table
        self.write_csv = write_csv
        self.pg_batch_size = pg_batch_size
        self.pg_conn = None
        self.pg_cur = None

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY 가 설정되어 있지 않습니다 (.env 확인).")
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        # initialize Postgres connection if connection info provided
        if self.pg_connect:
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required for Postgres insertion but not installed")
            self.pg_conn = psycopg2.connect(
                host=self.pg_connect.get("host", "localhost"),
                port=self.pg_connect.get("port", 5432),
                dbname=self.pg_connect.get("dbname"),
                user=self.pg_connect.get("user"),
                password=self.pg_connect.get("password"),
            )
            self.pg_conn.autocommit = True
            self.pg_cur = self.pg_conn.cursor()
            # buffer for batch inserts
            self._pg_batch_buffer = []

    def embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=self.embed_model,
            input=text,
            encoding_format="float",
        )
        return resp.data[0].embedding

    def run(self, resume: bool = True):
        if not self.chunk_csv.exists():
            raise FileNotFoundError(f"Chunk CSV not found: {self.chunk_csv}")

        # stream the chunk CSV row-by-row to avoid loading entire file into memory
        required = ["chunk_id", "section_id", "chunk_seq", "text_chunk"]

        existing_chunk_ids = set()
        # collect existing ids from CSV output if present
        if resume and self.write_csv and self.output_csv.exists():
            existing_chunk_ids = load_existing_chunk_ids(self.output_csv)
            if existing_chunk_ids:
                print(f"✓ Found {len(existing_chunk_ids)} existing embeddings in {self.output_csv} (resume mode)")

        # if pg is enabled and resume, also fetch existing ids from DB to avoid duplicates
        if resume and self.pg_cur is not None:
            try:
                self.pg_cur.execute(f"SELECT chunk_id FROM {self.pg_table}")
                for row in self.pg_cur.fetchall():
                    existing_chunk_ids.add(row[0])
                print(f"✓ Found {len(existing_chunk_ids)} existing embeddings (including DB) (resume mode)")
            except Exception:
                # silently ignore DB fetch errors (will rely on CSV)
                pass

        out_fieldnames = [
            "chunk_id",
            "section_id",
            "chunk_seq",
            "start_char",
            "end_char",
            "emb_model",
            "emb_dim",
            "text_chunk",
            "embedding",
        ]

        # prepare CSV writer if requested
        if self.write_csv:
            file_exists = self.output_csv.exists()
            out_f = self.output_csv.open("a", encoding="utf-8-sig", newline="")
            writer = csv.DictWriter(out_f, fieldnames=out_fieldnames)
            if not file_exists:
                writer.writeheader()
        else:
            out_f = None
            writer = None

        new_embeddings = 0
        pbar = tqdm(desc="Embedding chunks", unit="chunk")

        try:
            with self.chunk_csv.open("r", encoding="utf-8-sig", newline="") as inf:
                reader = csv.DictReader(inf)
                # validate header
                missing = [c for c in required if c not in (reader.fieldnames or [])]
                if missing:
                    raise ValueError(f"Chunk CSV에 필요한 컬럼이 없습니다: {missing}")

                for r in reader:
                    chunk_id = str(r.get("chunk_id"))
                    if resume and chunk_id in existing_chunk_ids:
                        pbar.update(1)
                        continue

                    text = r.get("text_chunk", "") or ""
                    try:
                        emb = self.embed(text)
                        emb_literal = to_pgvector_literal(emb)

                        # write to CSV if enabled
                        if writer is not None:
                            writer.writerow(
                                {
                                    "chunk_id": chunk_id,
                                    "section_id": r.get("section_id"),
                                    "chunk_seq": r.get("chunk_seq"),
                                    "start_char": r.get("start_char"),
                                    "end_char": r.get("end_char"),
                                    "emb_model": self.embed_model,
                                    "emb_dim": self.embed_dim,
                                    "text_chunk": text,
                                    "embedding": emb_literal,
                                }
                            )
                            out_f.flush()

                        # insert into Postgres if connection available (buffered)
                        if self.pg_cur is not None:
                            try:
                                row_tuple = (
                                    chunk_id,
                                    r.get("section_id"),
                                    r.get("chunk_seq"),
                                    r.get("start_char"),
                                    r.get("end_char"),
                                    self.embed_model,
                                    self.embed_dim,
                                    text,
                                    emb_literal,
                                )
                                self._pg_batch_buffer.append(row_tuple)
                                # flush buffer when reaching batch size
                                if len(self._pg_batch_buffer) >= self.pg_batch_size:
                                    insert_sql = (
                                        f"INSERT INTO {self.pg_table}"
                                        " (chunk_id, section_id, chunk_seq, start_char, end_char, emb_model, emb_dim, text_chunk, embedding)"
                                        " VALUES %s ON CONFLICT (chunk_id) DO NOTHING"
                                    )
                                    try:
                                        execute_values(self.pg_cur, insert_sql, self._pg_batch_buffer, page_size=self.pg_batch_size)
                                    except Exception as e:
                                        print(f"\n! Batch insert failed: {e}; falling back to single-row inserts")
                                        per_sql = (
                                            f"INSERT INTO {self.pg_table}"
                                            " (chunk_id, section_id, chunk_seq, start_char, end_char, emb_model, emb_dim, text_chunk, embedding)"
                                            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (chunk_id) DO NOTHING"
                                        )
                                        for bt in self._pg_batch_buffer:
                                            try:
                                                self.pg_cur.execute(per_sql, bt)
                                            except Exception as e2:
                                                print(f"\n! DB insert failed for chunk_id={bt[0]}: {e2}")
                                    finally:
                                        self._pg_batch_buffer = []
                            except Exception as e:
                                print(f"\n! DB buffering failed for chunk_id={chunk_id}: {e}")

                        existing_chunk_ids.add(chunk_id)
                        new_embeddings += 1
                        time.sleep(RATE_LIMIT_DELAY)

                    except Exception as e:
                        print(f"\n✗ chunk_id={chunk_id}: {e}")

                    pbar.update(1)

        except KeyboardInterrupt:
            print("\n! Interrupted by user. Progress saved so far.")
        finally:
            # flush any remaining pg batch buffer
            if getattr(self, "_pg_batch_buffer", None):
                if self.pg_cur is not None and len(self._pg_batch_buffer) > 0:
                    insert_sql = (
                        f"INSERT INTO {self.pg_table}"
                        " (chunk_id, section_id, chunk_seq, start_char, end_char, emb_model, emb_dim, text_chunk, embedding)"
                        " VALUES %s ON CONFLICT (chunk_id) DO NOTHING"
                    )
                    try:
                        execute_values(self.pg_cur, insert_sql, self._pg_batch_buffer, page_size=self.pg_batch_size)
                    except Exception as e:
                        print(f"\n! Final batch insert failed: {e}")

            pbar.close()
            if out_f is not None:
                out_f.close()
            if self.pg_cur is not None:
                try:
                    self.pg_cur.close()
                except Exception:
                    pass
            if self.pg_conn is not None:
                try:
                    self.pg_conn.close()
                except Exception:
                    pass
            print(f"\n✅ Embedding finished. new_embeddings={new_embeddings}")
