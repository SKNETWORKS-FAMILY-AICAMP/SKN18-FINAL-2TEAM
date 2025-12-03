#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMC Vector Similarity Search Tool
- Search Target: pmc_section_chunk (embedding) + pmc_section_meta (metadata)
- Metric: Cosine similarity = 1 - (embedding <=> query_vec)
"""

import os
import sys
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Optional

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMB_DIM = 1536  # PMC 프로젝트 설정에 맞춤 (기존 3072 -> 1536)

# DB Connection Settings (기존 .env 설정 사용)
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "pmc_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password")
}

class VectorSearch:
    """Vector similarity search for PMC chunks."""
    
    def __init__(self):
        if not OPENAI_API_KEY:
            print("❌ Error: OPENAI_API_KEY not found in .env")
            sys.exit(1)
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None

    # --- DB Connection ---
    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to database: {DB_CONFIG['database']}")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            print(f"  (Check your .env variables: POSTGRES_HOST, POSTGRES_DB, etc.)")
            sys.exit(1)

    def close_db(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    # --- Embedding ---
    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding vector for the query string."""
        try:
            resp = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=query,
                encoding_format="float"
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"❌ OpenAI API Error: {e}")
            return []

    # --- Search Logic ---
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for most similar chunks in 'pmc_section_chunk'.
        Joins with 'pmc_section_meta' to get context (PMID, Section Category).
        """
        query_vec = self.get_query_embedding(query)
        if not query_vec:
            return []

        # SQL: Cosine Similarity Search with Metadata Join
        # Note: '1 - (embedding <=> vector)' calculates cosine similarity (1 is identical, 0 is orthogonal)
        sql = f"""
        SELECT 
            c.chunk_id,
            c.text_chunk,
            c.ref_ids,
            c.fig_ref_markers,
            (1 - (c.embedding <=> %s::vector)) as similarity,
            m.pmid,
            m.section_category,
            m.article_category,
            m.topic_category
        FROM pmc_section_chunk c
        LEFT JOIN pmc_section_meta m ON c.section_id = m.section_id
        ORDER BY c.embedding <=> %s::vector ASC
        LIMIT %s
        """
        
        try:
            # Pass query vector twice (once for similarity calc, once for ordering)
            self.cursor.execute(sql, (query_vec, query_vec, top_k))
            rows = self.cursor.fetchall()
            
            results = []
            for r in rows:
                results.append({
                    "chunk_id": r[0],
                    "text": r[1],
                    "ref_ids": r[2],
                    "fig_markers": r[3],
                    "similarity": float(r[4]),
                    "pmid": r[5],
                    "section": r[6],
                    "article_type": r[7],
                    "topic": r[8]
                })
            return results

        except Exception as e:
            print(f"❌ Search Query Failed: {e}")
            return []

    # --- Display ---
    def display_results(self, results: List[Dict]):
        if not results:
            print("\nNo results found.")
            return

        print(f"\n{'='*60}")
        print(f"🔍 Top {len(results)} Similar Chunks")
        print(f"{'='*60}")

        for i, r in enumerate(results, 1):
            sim_score = r['similarity']
            pmid = r['pmid'] or "N/A"
            section = r['section'] or "Unknown"
            
            print(f"\n[{i}] Similarity: {sim_score:.4f}")
            print(f"    source: PMID {pmid} | Section: {section}")
            print(f"    chunk_id: {r['chunk_id']}")
            
            # 텍스트 출력 (너무 길면 자름)
            text_preview = r['text'].strip()
            print(f"    --------------------------------------------------")
            print(f"    {text_preview}")
            print(f"    --------------------------------------------------")
            
            # 참조 정보가 있으면 출력
            if r['ref_ids'] or r['fig_markers']:
                refs = []
                if r['ref_ids']: refs.append(f"Refs: [{r['ref_ids']}]")
                if r['fig_markers']: refs.append(f"Figs: {r['fig_markers']}")
                print(f"    📎 {' | '.join(refs)}")
            
            print(f"{'-'*60}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Search PMC Database by Vector Similarity")
    parser.add_argument("query", help="Text query to search (e.g. 'protein folding mechanism')")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return (default: 5)")
    
    args = parser.parse_args()

    searcher = VectorSearch()
    try:
        searcher.connect_db()
        print(f"\n🔎 Searching for: '{args.query}'")
        
        results = searcher.search(args.query, top_k=args.top_k)
        searcher.display_results(results)
        
    except KeyboardInterrupt:
        print("\n⚠ Interrupted")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        searcher.close_db()

if __name__ == "__main__":
    main()