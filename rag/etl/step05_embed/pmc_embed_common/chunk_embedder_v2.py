#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChunkEmbedder: load chunk CSV, produce embeddings, write output CSV.
- Refactored to use data loader utility.
"""
from pathlib import Path
import csv
import time
from typing import List, Optional, Tuple, Any, Dict
from tqdm import tqdm
from openai import OpenAI

try:
    import psycopg2
    from psycopg2.extras import execute_values
except Exception:
    psycopg2 = None

# [수정됨] 공용 유틸리티 임포트
from rag.etl.step04_chunk.pmc_chunk_common.chunking import (
    to_pgvector_literal,
    DEFAULT_EMBED_DIM,
    DEFAULT_EMBED_MODEL,
    OPENAI_API_KEY,
    RATE_LIMIT_DELAY,
)

from rag.etl.step04_chunk.pmc_chunk_common.pmc_chunk_csv_utils import load_existing_chunk_ids, iter_chunk_csv_rows


def _build_embedding_row(
    chunk_row: Dict[str, Any],
    embedding: List[float],
    model: str,
    dim: int,
    emb_literal: str,
) -> Dict[str, Any]:
    """
    [공용 데이터 노드 함수]
    임베딩 결과를 포함하는 최종 Row 딕셔너리를 구성합니다.
    """
    return {
        "chunk_id": chunk_row.get("chunk_id"),
        "section_id": chunk_row.get("section_id"),
        "chunk_seq": chunk_row.get("chunk_seq"),
        "path": chunk_row.get("path"),
        "start_char": chunk_row.get("start_char"),
        "end_char": chunk_row.get("end_char"),
        "emb_model": model,
        "emb_dim": dim,
        "text_chunk": chunk_row.get("text_chunk"),
        "embedding": emb_literal,
    }


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
        self._pg_batch_buffer = []

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

    def embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=self.embed_model,
            input=text,
            encoding_format="float",
        )
        return resp.data[0].embedding

    def _build_pg_tuple(self, row: Dict[str, Any], emb_literal: str, text: str) -> Tuple[Any, ...]:
        """Postgres batch insert를 위한 튜플 생성"""
        return (
            row.get("chunk_id"),
            row.get("section_id"),
            row.get("chunk_seq"),
            row.get("start_char"),
            row.get("end_char"),
            self.embed_model,
            self.embed_dim,
            text,
            emb_literal,
        )

    def _flush_pg_buffer(self, final: bool = False):
        """
        [DB 적재 전용 함수]
        Postgres 배치 버퍼를 비우고 DB에 삽입합니다.
        """
        if not self.pg_cur or not self._pg_batch_buffer:
            return

        batch = self._pg_batch_buffer
        if not final and len(batch) < self.pg_batch_size:
            return

        insert_sql = (
            f"INSERT INTO {self.pg_table}"
            " (chunk_id, section_id, chunk_seq, start_char, end_char, emb_model, emb_dim, text_chunk, embedding)"
            " VALUES %s ON CONFLICT (chunk_id) DO NOTHING"
        )
        
        try:
            execute_values(self.pg_cur, insert_sql, batch, page_size=self.pg_batch_size)
        except Exception as e:
            print(f"\n! Batch insert failed: {e}; falling back to single-row inserts")
            per_sql = (
                f"INSERT INTO {self.pg_table}"
                " (chunk_id, section_id, chunk_seq, start_char, end_char, emb_model, emb_dim, text_chunk, embedding)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (chunk_id) DO NOTHING"
            )
            for bt in batch:
                try:
                    self.pg_cur.execute(per_sql, bt)
                except Exception as e2:
                    print(f"\n! DB insert failed for chunk_id={bt[0]}: {e2}")
        finally:
            self._pg_batch_buffer = []

    # [chunk_embedder.py] 클래스 내부 run 메서드 교체

    def run(self, resume: bool = True):
        if not self.chunk_csv.exists():
            raise FileNotFoundError(f"Chunk CSV not found: {self.chunk_csv}")

        # [수정 1] CSV 읽을 때 'path' 컬럼도 읽도록 명시 (필수는 아니지만 명시적)
        required = ["chunk_id", "section_id", "chunk_seq", "text_chunk"]
        
        existing_chunk_ids = set()
        
        if resume and self.write_csv and self.output_csv.exists():
            existing_chunk_ids = load_existing_chunk_ids(self.output_csv)
            
        if resume and self.pg_cur is not None:
            try:
                self.pg_cur.execute(f"SELECT chunk_id FROM {self.pg_table}")
                for row in self.pg_cur.fetchall():
                    existing_chunk_ids.add(row[0])
            except Exception:
                pass
        
        if existing_chunk_ids:
            print(f"✓ Found {len(existing_chunk_ids)} existing embeddings (resume mode)")

        # [수정 2] 결과 CSV 헤더에 'path' 추가
        out_fieldnames = [
            "chunk_id", "section_id", "chunk_seq", 
            "path",  # <--- [NEW] 결과 파일 헤더에 추가
            "start_char", "end_char",
            "emb_model", "emb_dim", "text_chunk", "embedding",
        ]

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
            # [수정 3] iter_chunk_csv_rows에 required 리스트 전달
            for r in iter_chunk_csv_rows(self.chunk_csv, required):
                chunk_id = str(r.get("chunk_id"))
                if resume and chunk_id in existing_chunk_ids:
                    pbar.update(1)
                    continue

                text_clean = r.get("text_chunk", "") or ""
                path_str = r.get("path", "")  # <--- [NEW] CSV에서 경로 정보 읽기

                try:
                    # ★★★ [핵심 로직] Context Injection ★★★
                    # 경로가 있으면 "경로: 본문" 형태로 합쳐서 임베딩 (검색 정확도 향상)
                    if path_str:
                        text_to_embed = f"{path_str}: {text_clean}"
                    else:
                        text_to_embed = text_clean
                    
                    # API 호출은 합쳐진 텍스트로!
                    emb = self.embed(text_to_embed)
                    emb_literal = to_pgvector_literal(emb)
                    
                    # 저장은 분리해서 깔끔하게! (_build_embedding_row 호출)
                    final_row = _build_embedding_row(r, emb, self.embed_model, self.embed_dim, emb_literal)

                    # CSV 쓰기
                    if writer is not None:
                        writer.writerow(final_row)
                        out_f.flush()

                    # DB 적재 (버퍼링)
                    if self.pg_cur is not None:
                        row_tuple = self._build_pg_tuple(r, emb_literal, text_clean)
                        self._pg_batch_buffer.append(row_tuple)
                        self._flush_pg_buffer(final=False)

                    existing_chunk_ids.add(chunk_id)
                    new_embeddings += 1
                    time.sleep(RATE_LIMIT_DELAY)

                except Exception as e:
                    print(f"\n✗ chunk_id={chunk_id}: {e}")

                pbar.update(1)

        except KeyboardInterrupt:
            print("\n! Interrupted by user. Progress saved so far.")
        finally:
            self._flush_pg_buffer(final=True)
            pbar.close()
            if out_f is not None:
                out_f.close()
            if self.pg_conn is not None:
                try:
                    self.pg_cur.close()
                    self.pg_conn.close()
                except Exception:
                    pass
            print(f"\n✅ Embedding finished. new_embeddings={new_embeddings}")