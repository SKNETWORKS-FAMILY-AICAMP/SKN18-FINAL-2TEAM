#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embed Interview Q&A as paired chunks (char_len=300, overlap=100)
Schema:
  - interview.meta_df(doc_id PK, ... , content_combined, tokens_answer, tokens_combined)
  - interview.vector(chunk_id PK, doc_id FK, chunk_seq, start_char, end_char, emb_model, emb_dim, embedding VECTOR(3072))
"""

import os, sys, re, time, argparse
from typing import List, Tuple, Set
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from openai import OpenAI
from dotenv import load_dotenv
import tiktoken
from tqdm import tqdm

# -------------------
# Config
# -------------------
# Load .env from project root
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent  # backend/embedding -> backend -> project_root
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback: try current directory
    load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "localhost")),
    "port": os.getenv("POSTGRES_PORT", os.getenv("DB_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", os.getenv("DB_NAME", "skn4th_db")),
    "user": os.getenv("POSTGRES_USER", os.getenv("DB_USER", "skn4th")),
    "password": os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD", "sk4th1234")),
}
SCHEMA = os.getenv("DB_SCHEMA", "interview")

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")
EMBED_DIM = 3072
BATCH_SIZE = 50
RATE_LIMIT_DELAY = float(os.getenv("EMBED_RATE_DELAY", "0.2"))

CHUNK_SIZE = 300
CHUNK_OVERLAP = 100
CHECKPOINT_INTERVAL = 3000  # Save checkpoint every N documents

# -------------------
# Helpers
# -------------------
def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def to_chunk_id(doc_id: int, seq: int) -> str:
    return f"DOC{int(doc_id):06d}_C{int(seq):02d}"

def char_chunks(text: str, max_len: int, overlap: int) -> List[Tuple[int,int,str]]:
    """
    Simple char-based chunking with overlap. Returns list of (start, end, chunk_text).
    Uses step = max_len - overlap.
    """
    txt = text
    n = len(txt)
    if n <= max_len:
        return [(0, n, txt)]
    step = max(1, max_len - overlap)
    chunks = []
    start = 0
    while start < n:
        end = min(start + max_len, n)
        # try to end at a boundary if possible (Korean/English sentence-ish)
        boundary = max(txt.rfind(" ", start, end), txt.rfind(".", start, end), txt.rfind("!", start, end), txt.rfind("?", start, end), txt.rfind("。", start, end), txt.rfind("…", start, end))
        if boundary != -1 and boundary > start + int(max_len*0.6):
            end = boundary + 1
        chunk = txt[start:end]
        chunks.append((start, end, chunk))
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def make_combined(q: str, a: str) -> str:
    q = normalize_text(q)
    a = normalize_text(a)
    return f"Q: {q}\nA: {a}"

def to_pgvector_literal(vec: List[float]) -> str:
    # pgvector accepts string literal like '[0.1, 0.2, ...]'
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"

# -------------------
# Main class
# -------------------
class PairEmbedder:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.conn = None
        self.cur = None
        self.encoding = tiktoken.get_encoding("cl100k_base")

    # --- DB ---
    def connect_db(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        print("✓ Connected to database")

    def close_db(self):
        if self.cur: self.cur.close()
        if self.conn: 
            self.conn.close()
            print("✓ Database connection closed")

    def get_processed_doc_ids(self) -> Set[int]:
        """Get set of doc_ids that already have embeddings in the database"""
        try:
            sql = f"""
            SELECT DISTINCT doc_id 
            FROM {SCHEMA}.vector
            WHERE emb_model = %s
            """
            self.cur.execute(sql, (EMBED_MODEL,))
            result = self.cur.fetchall()
            return {row[0] for row in result}
        except Exception as e:
            print(f"Warning: Could not check existing doc_ids: {e}")
            return set()

    # --- IO ---
    def load_df(self) -> pd.DataFrame:
        df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        req = ["question", "answer"]
        miss = [c for c in req if c not in df.columns]
        if miss:
            raise ValueError(f"Missing required columns: {miss}")
        return df

    # --- OpenAI ---
    def embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=EMBED_MODEL,
            input=text,
            encoding_format="float"
        )
        return resp.data[0].embedding

    def count_tokens(self, text: str) -> int:
        try:
            return len(self.encoding.encode(text))
        except Exception:
            return 0

    # --- Inserts ---
    def upsert_meta_df(self, rows: List[tuple]):
        sql = f"""
        INSERT INTO {SCHEMA}.meta_df (
            doc_id, occupation, gender, age_range, experience,
            answer_intent_category, answer_emotion_expression, answer_emotion_category,
            question_intent, question_text, answer_text, content_combined,
            tokens_answer, tokens_combined
        ) VALUES (
            %s,%s,%s,%s,%s,
            %s,%s,%s,
            %s,%s,%s,%s,
            %s,%s
        )
        ON CONFLICT (doc_id) DO UPDATE SET
            occupation = EXCLUDED.occupation,
            gender = EXCLUDED.gender,
            age_range = EXCLUDED.age_range,
            experience = EXCLUDED.experience,
            answer_intent_category = EXCLUDED.answer_intent_category,
            answer_emotion_expression = EXCLUDED.answer_emotion_expression,
            answer_emotion_category = EXCLUDED.answer_emotion_category,
            question_intent = EXCLUDED.question_intent,
            question_text = EXCLUDED.question_text,
            answer_text = EXCLUDED.answer_text,
            content_combined = EXCLUDED.content_combined,
            tokens_answer = EXCLUDED.tokens_answer,
            tokens_combined = EXCLUDED.tokens_combined
        """
        execute_batch(self.cur, sql, rows, page_size=100)
        self.conn.commit()

    def insert_vector_rows(self, rows: List[tuple]):
        """
        rows: (chunk_id, doc_id, chunk_seq, start_char, end_char, emb_model, emb_dim, embedding_literal)
        """
        sql = f"""
        INSERT INTO {SCHEMA}.vector
        (chunk_id, doc_id, chunk_seq, start_char, end_char, emb_model, emb_dim, embedding)
        VALUES (%s,%s,%s,%s,%s,%s,%s, %s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            doc_id = EXCLUDED.doc_id,
            chunk_seq = EXCLUDED.chunk_seq,
            start_char = EXCLUDED.start_char,
            end_char = EXCLUDED.end_char,
            emb_model = EXCLUDED.emb_model,
            emb_dim = EXCLUDED.emb_dim,
            embedding = EXCLUDED.embedding
        """
        # IMPORTANT: tell psycopg2 that last param is typed as vector using explicit cast
        # We can embed the cast in the VALUES by passing as sql literal with ::vector
        # Since execute_batch paramizes, we pass the vector literal as text and rely on cast in SQL.
        # So we slightly modify SQL to add ::vector
        sql = sql.replace("EXCLUDED.embedding", "EXCLUDED.embedding").replace(
            "VALUES (%s,%s,%s,%s,%s,%s,%s, %s)",
            "VALUES (%s,%s,%s,%s,%s,%s,%s, %s::vector)"
        )
        execute_batch(self.cur, sql, rows, page_size=50)
        self.conn.commit()

    # --- Process ---
    def run(self, resume: bool = True):
        df = self.load_df()
        total = len(df)
        print(f"✓ Loaded {total} rows")

        # Get already processed doc_ids if resuming
        processed_doc_ids = set()
        if resume:
            print("Checking for already processed documents...")
            processed_doc_ids = self.get_processed_doc_ids()
            if processed_doc_ids:
                print(f"✓ Found {len(processed_doc_ids)} already processed documents (will skip)")
            else:
                print("✓ No existing embeddings found, starting fresh")

        meta_buf, vec_buf = [], []
        done, errors, skipped = 0, 0, 0
        last_checkpoint = 0

        # Create progress bar
        pbar = tqdm(total=total, desc="Embedding", unit="doc", 
                   bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

        for i, row in df.iterrows():
            try:
                # doc_id = sample_id (fallback i+1)
                sample_id = row.get("sample_id")
                doc_id = int(sample_id) if pd.notna(sample_id) else (i + 1)

                # Skip if already processed
                if doc_id in processed_doc_ids:
                    skipped += 1
                    pbar.update(1)
                    pbar.set_postfix({"done": done, "skipped": skipped, "errors": errors})
                    continue

                q = str(row.get("question", ""))
                a = str(row.get("answer", ""))
                occupation = str(row.get("occupation", "") or "")
                gender = str(row.get("gender", "") or "")
                age_range = str(row.get("ageRange", "") or row.get("age_range", "") or "")
                experience = str(row.get("experience", "") or "")
                ans_intent = str(row.get("answer-intent_category", "") or row.get("answer_intent_category", "") or "")
                ans_em_exp = str(row.get("answer-emotion_expression", "") or "")
                ans_em_cat = str(row.get("answer-emotion_category", "") or "")
                q_intent   = str(row.get("question_intent", "") or "")

                combined = make_combined(q, a)
                tok_ans = self.count_tokens(a)
                tok_comb = self.count_tokens(combined)

                meta_buf.append((
                    doc_id, occupation, gender, age_range, experience,
                    ans_intent, ans_em_exp, ans_em_cat,
                    q_intent, q, a, combined,
                    tok_ans, tok_comb
                ))

                # chunk + embed
                chunks = char_chunks(combined, CHUNK_SIZE, CHUNK_OVERLAP)
                for seq, (s, e, ch_text) in enumerate(chunks, start=1):
                    emb = self.embed(ch_text)
                    chunk_id = to_chunk_id(doc_id, seq)
                    vec_buf.append((
                        chunk_id, doc_id, seq, s, e, EMBED_MODEL, EMBED_DIM,
                        to_pgvector_literal(emb)  # casted to vector in SQL
                    ))
                    time.sleep(RATE_LIMIT_DELAY)

                done += 1
                processed_doc_ids.add(doc_id)  # Mark as processed

                # Flush meta first if either buffer is full (to respect FK constraint)
                if len(meta_buf) >= BATCH_SIZE or len(vec_buf) >= BATCH_SIZE:
                    if meta_buf:
                        self.upsert_meta_df(meta_buf)
                        meta_buf = []
                    if vec_buf:
                        self.insert_vector_rows(vec_buf)
                        vec_buf = []

                # Checkpoint every CHECKPOINT_INTERVAL documents
                if done > 0 and done % CHECKPOINT_INTERVAL == 0:
                    # Flush any remaining buffers
                    if meta_buf:
                        self.upsert_meta_df(meta_buf)
                        meta_buf = []
                    if vec_buf:
                        self.insert_vector_rows(vec_buf)
                        vec_buf = []
                    last_checkpoint = done
                    pbar.set_postfix({
                        "done": done, 
                        "skipped": skipped, 
                        "errors": errors,
                        "checkpoint": f"@{done}"
                    })
                    print(f"\n✓ Checkpoint: {done} documents processed")

            except KeyboardInterrupt:
                print("\n! Interrupted by user")
                # Flush buffers before exit
                if meta_buf:
                    self.upsert_meta_df(meta_buf)
                    meta_buf = []
                if vec_buf:
                    self.insert_vector_rows(vec_buf)
                    vec_buf = []
                print(f"✓ Saved progress: {done} documents processed")
                print(f"  To resume, run the same command again (will skip {len(processed_doc_ids)} already processed)")
                break
            except Exception as e:
                errors += 1
                print(f"\n✗ Row {i} (doc_id={row.get('sample_id')}): {e}")
                pbar.set_postfix({"done": done, "skipped": skipped, "errors": errors})

            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({"done": done, "skipped": skipped, "errors": errors})

        # Final flush
        if meta_buf: 
            self.upsert_meta_df(meta_buf)
            meta_buf = []
        if vec_buf:  
            self.insert_vector_rows(vec_buf)
            vec_buf = []

        pbar.close()
        print(f"\n✅ Done. processed={done}, skipped={skipped}, errors={errors}")

# -------------------
# CLI
# -------------------
def main():
    global SCHEMA, CHUNK_SIZE, CHUNK_OVERLAP, CHECKPOINT_INTERVAL
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to CSV")
    ap.add_argument("--schema", default=SCHEMA, help="DB schema (default: interview)")
    ap.add_argument("--chunk", type=int, default=CHUNK_SIZE, help="chunk char length (default 300)")
    ap.add_argument("--overlap", type=int, default=CHUNK_OVERLAP, help="overlap char length (default 100)")
    ap.add_argument("--no-resume", action="store_true", help="Don't resume from existing embeddings (start fresh)")
    ap.add_argument("--checkpoint-interval", type=int, default=CHECKPOINT_INTERVAL, 
                    help=f"Checkpoint interval in documents (default {CHECKPOINT_INTERVAL})")
    args = ap.parse_args()

    SCHEMA = args.schema
    CHUNK_SIZE = args.chunk
    CHUNK_OVERLAP = args.overlap
    CHECKPOINT_INTERVAL = args.checkpoint_interval

    if not OPENAI_API_KEY:
        print("✗ OPENAI_API_KEY missing")
        sys.exit(1)

    # Debug: print DB config (without password)
    print(f"DB Config: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, database={DB_CONFIG['database']}, user={DB_CONFIG['user']}")
    
    runner = PairEmbedder(args.input)
    try:
        runner.connect_db()
        runner.run(resume=not args.no_resume)
    finally:
        runner.close_db()

if __name__ == "__main__":
    main()
