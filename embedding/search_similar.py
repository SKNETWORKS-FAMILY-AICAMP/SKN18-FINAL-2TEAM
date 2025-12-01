#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vector Similarity Search for Interview Q&A Database (no DB functions needed)
- Q-Index: qa.vec_q_index ⟷ qa.meta_df
- A-Index: qa.vec_a_index ⟷ qa.meta_df
- Hybrid:  Q-Index k_q개 + A-Index (top_k - k_q)개 병합
Cosine similarity = 1 - (embedding <=> query_vec)  # pgvector cosine_ops
"""

import os
import sys
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Optional

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-large"
EMB_DIM = 3072

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5431"),
    "database": os.getenv("DB_NAME", "interview_chunking_db"),
    "user": os.getenv("DB_USER", "interview_user"),
    "password": os.getenv("DB_PASSWORD", "interview_pass")
}


class VectorSearch:
    """Vector similarity search for interview embeddings without stored functions."""
    def __init__(self):
        if not OPENAI_API_KEY:
            print("✗ OPENAI_API_KEY not found in .env")
            sys.exit(1)
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None

    # --- DB ---
    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✓ Connected to database")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)

    def close_db(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    # --- Embedding ---
    def get_query_embedding(self, query: str) -> List[float]:
        try:
            resp = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=query,
                encoding_format="float"
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"✗ Failed to generate query embedding: {e}")
            return []

    # --- SQL builders ---
    @staticmethod
    def _build_where(filters: Dict) -> (str, list):
        """Build WHERE and params for optional filters."""
        where = []
        params: list = []
        if not filters:
            return "", []

        if filters.get("occupation"):
            where.append("m.occupation = %s")
            params.append(filters["occupation"])

        if filters.get("question_intent"):
            # only for Q-index
            where.append("m.question_intent = %s")
            params.append(filters["question_intent"])

        if filters.get("answer_intent"):
            # only for A-index
            where.append("m.answer_intent_category = %s")
            params.append(filters["answer_intent"])

        if where:
            return "WHERE " + " AND ".join(where), params
        return "", []

    # --- Searches ---
    def search_questions(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """
        Q-Index search (question embeddings, joins meta_df on chunk_id)
        """
        qvec = self.get_query_embedding(query)
        if not qvec:
            return []

        where_sql, where_params = self._build_where(filters or {})
        # remove answer_intent from Q-index filters if passed
        # (it would add an unused predicate)
        if "m.answer_intent_category = %s" in where_sql:
            # rebuild without answer_intent
            f = dict(filters or {})
            f.pop("answer_intent", None)
            where_sql, where_params = self._build_where(f)

        # Use a CTE to bind the vector with explicit dimension
        sql = f"""
        WITH q AS (SELECT %s::vector({EMB_DIM}) AS v)
        SELECT
            m.chunk_id,
            m.doc_id,
            m.question_text,
            m.answer_text,
            (1 - (v.embedding <=> q.v)) AS similarity,
            m.occupation,
            m.question_intent,
            m.answer_intent_category
        FROM qa.vec_q_index AS v
        JOIN q ON TRUE
        JOIN qa.meta_df AS m
          ON m.chunk_id = v.chunk_id
        {where_sql}
        ORDER BY v.embedding <=> q.v ASC
        LIMIT %s::int
        """
        params = [qvec, *where_params, top_k]

        try:
            self.cursor.execute(sql, params)
            rows = self.cursor.fetchall()
            return [
                {
                    "chunk_id": r[0],
                    "doc_id": r[1],
                    "question_text": r[2],
                    "answer_text": r[3],
                    "similarity": float(r[4]),
                    "occupation": r[5],
                    "question_intent": r[6],
                    "answer_intent": r[7],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"✗ Q-Index search failed: {e}")
            return []

    def search_answers(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """
        A-Index search (answer embeddings, joins meta_df on chunk_id)
        """
        qvec = self.get_query_embedding(query)
        if not qvec:
            return []

        where_sql, where_params = self._build_where(filters or {})

        # For A-index, question_intent filter is irrelevant unless user wants it too.
        # Keep both if provided; otherwise it's fine.
        sql = f"""
        WITH q AS (SELECT %s::vector({EMB_DIM}) AS v)
        SELECT
            m.chunk_id,
            m.doc_id,
            m.question_text,
            m.answer_text,
            m.content_combined,
            (1 - (v.embedding <=> q.v)) AS similarity,
            m.occupation,
            m.answer_intent_category
        FROM qa.vec_a_index AS v
        JOIN q ON TRUE
        JOIN qa.meta_df AS m
          ON m.chunk_id = v.chunk_id
        {where_sql}
        ORDER BY v.embedding <=> q.v ASC
        LIMIT %s::int
        """
        params = [qvec, *where_params, top_k]

        try:
            self.cursor.execute(sql, params)
            rows = self.cursor.fetchall()
            return [
                {
                    "chunk_id": r[0],
                    "doc_id": r[1],
                    "question_text": r[2],
                    "answer_text": r[3],
                    "content_combined": r[4],
                    "similarity": float(r[5]),
                    "occupation": r[6],
                    "answer_intent": r[7],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"✗ A-Index search failed: {e}")
            return []

    def search_hybrid(self, query: str, top_k: int = 10, k_q: int = 3, filters: Dict = None) -> List[Dict]:
        """
        Hybrid search: fetch top k_q from Q-index + top (top_k - k_q) from A-index, then merge.
        (No DB functions, two separate queries.)
        """
        k_q = max(0, min(k_q, top_k))
        k_a = max(0, top_k - k_q)

        q_results = self.search_questions(query, top_k=k_q, filters=filters or {})
        a_results = self.search_answers(query, top_k=k_a, filters=filters or {})

        # merge (keep order: Q first then A)
        merged = []
        for r in q_results:
            merged.append({
                "chunk_id": r["chunk_id"],
                "doc_id": r["doc_id"],
                "question_text": r["question_text"],
                "answer_text": r["answer_text"],
                "source_index": "Q",
                "similarity": r["similarity"],
                "occupation": r.get("occupation"),
            })
        for r in a_results:
            merged.append({
                "chunk_id": r["chunk_id"],
                "doc_id": r["doc_id"],
                "question_text": r["question_text"],
                "answer_text": r["answer_text"],
                "source_index": "A",
                "similarity": r["similarity"],
                "occupation": r.get("occupation"),
            })
        return merged[:top_k]

    # --- Display ---
    def display_results(self, results: List[Dict], search_type: str = ""):
        if not results:
            print("No results found.")
            return
        print(f"\n{'='*80}")
        print(f"Found {len(results)} results{f' ({search_type})' if search_type else ''}:")
        print(f"{'='*80}\n")

        for i, r in enumerate(results, 1):
            print(f"[Result {i}] Similarity: {r['similarity']:.4f}")
            print(f"Chunk ID: {r['chunk_id']} | Doc ID: {r['doc_id']}")
            if 'source_index' in r:
                print(f"Source: {r['source_index']}-Index")
            if 'occupation' in r and r['occupation']:
                print(f"Occupation: {r['occupation']}")
            print(f"\n질문: {r['question_text']}")
            ans_prev = r['answer_text'][:300] + ("..." if len(r['answer_text']) > 300 else "")
            print(f"\n답변: {ans_prev}")
            print(f"\n{'-'*80}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Search similar interview Q&A (no DB functions)")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--mode", choices=["q", "a", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--k-q", type=int, default=2, help="Q-Index results in hybrid")
    parser.add_argument("--occupation", help="Filter by occupation")
    parser.add_argument("--q-intent", help="Filter by question intent (Q-Index)")
    parser.add_argument("--a-intent", help="Filter by answer intent (A-Index)")
    args = parser.parse_args()

    filters = {}
    if args.occupation:
        filters["occupation"] = args.occupation
    if args.q_intent:
        filters["question_intent"] = args.q_intent
    if args.a_intent:
        filters["answer_intent"] = args.a_intent

    searcher = VectorSearch()
    try:
        searcher.connect_db()
        print(f"\n🔍 Query: {args.query}")
        print(f"📋 Mode: {args.mode.upper()}")
        if filters:
            print(f"🔎 Filters: {filters}")

        if args.mode == "q":
            res = searcher.search_questions(args.query, top_k=args.top_k, filters=filters)
            label = "Q-Index"
        elif args.mode == "a":
            res = searcher.search_answers(args.query, top_k=args.top_k, filters=filters)
            label = "A-Index"
        else:
            res = searcher.search_hybrid(args.query, top_k=args.top_k, k_q=args.k_q, filters=filters)
            label = "Hybrid"

        searcher.display_results(res, label)
    except KeyboardInterrupt:
        print("\n⚠ Interrupted")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback; traceback.print_exc()
    finally:
        searcher.close_db()


if __name__ == "__main__":
    main()
