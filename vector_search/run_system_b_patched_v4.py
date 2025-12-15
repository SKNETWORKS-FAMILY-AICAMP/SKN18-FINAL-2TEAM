# run_system_b_patched_v3.py
# System B: Postgres 벡터검색 + Neo4j Fulltext + Python RRF
# - Fulltext index name auto-detected (or overridden via FULLTEXT_CHUNK_INDEX)
# - If no suitable fulltext index exists, keyword retrieval becomes empty.

import os
import argparse
import json
import time
from typing import List, Dict, Tuple, Any, Optional

import psycopg2
from neo4j import GraphDatabase
from openai import OpenAI

# Optional: load environment variables from a local .env file (if python-dotenv is installed)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────
# Common: PG / Neo4j / Embedding
# ─────────────────────────────────────

def get_pg_conn():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")
        user = os.getenv("POSTGRES_USER", "postgres")
        pw = os.getenv("POSTGRES_PASSWORD", "postgres")
        dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg2.connect(dsn)


def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def _embedding_client(model_override: Optional[str] = None) -> Tuple[OpenAI, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    model = model_override or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    return OpenAI(api_key=api_key), model


def get_query_embedding_with_usage(
    query_text: str,
    embedding_model: Optional[str] = None,
) -> Tuple[List[float], Dict[str, Any], float]:
    """Return (embedding, usage_dict, latency_ms)."""
    client, model = _embedding_client(model_override=embedding_model)
    t0 = time.perf_counter()
    resp = client.embeddings.create(model=model, input=query_text)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    usage: Dict[str, Any] = {"model": model}
    if getattr(resp, "usage", None) is not None:
        u = resp.usage
        usage.update({
            "prompt_tokens": getattr(u, "prompt_tokens", None),
            "total_tokens": getattr(u, "total_tokens", None),
        })
    return resp.data[0].embedding, usage, dt_ms


# ─────────────────────────────────────
# Fulltext index detection
# ─────────────────────────────────────

def _list_fulltext_indexes(driver) -> List[Dict[str, Any]]:
    queries = [
        "SHOW FULLTEXT INDEXES YIELD name, entityType, labelsOrTypes, properties RETURN name, entityType, labelsOrTypes, properties",
        "CALL db.indexes() YIELD name, type, entityType, labelsOrTypes, properties WHERE type = 'FULLTEXT' RETURN name, entityType, labelsOrTypes, properties",
    ]
    for q in queries:
        try:
            with driver.session() as session:
                rs = session.run(q)
                out = []
                for r in rs:
                    out.append({
                        "name": r.get("name"),
                        "entityType": r.get("entityType"),
                        "labelsOrTypes": r.get("labelsOrTypes"),
                        "properties": r.get("properties"),
                    })
                return out
        except Exception:
            continue
    return []


def pick_fulltext_chunk_index(driver) -> Tuple[Optional[str], Dict[str, Any]]:
    override = os.getenv("FULLTEXT_CHUNK_INDEX")
    preferred = "keyword_chunk_index"

    idxs = _list_fulltext_indexes(driver)
    by_name = {i.get("name"): i for i in idxs if i.get("name")}

    def _exists(name: str) -> bool:
        return name in by_name

    if override and _exists(override):
        return override, by_name[override]

    if _exists(preferred):
        return preferred, by_name[preferred]

    chunk_candidates = []
    for i in idxs:
        if i.get("entityType") != "NODE":
            continue
        labels = i.get("labelsOrTypes") or []
        if isinstance(labels, str):
            labels = [labels]
        if "Chunk" in labels:
            chunk_candidates.append(i)

    def _score(i: Dict[str, Any]) -> int:
        props = i.get("properties") or []
        if isinstance(props, str):
            props = [props]
        return 2 if "text" in props else 1

    if chunk_candidates:
        chunk_candidates.sort(key=_score, reverse=True)
        chosen = chunk_candidates[0]
        return chosen.get("name"), chosen

    node_candidates = [i for i in idxs if i.get("entityType") == "NODE"]
    if node_candidates:
        chosen = node_candidates[0]
        return chosen.get("name"), chosen

    return None, {}


# ─────────────────────────────────────
# 1) Postgres vector search
# ─────────────────────────────────────

def pg_vector_search_article(
    conn,
    query_embedding: List[float],
    k_vec: int,
    ef_search: int = 100,
) -> List[Dict[str, Any]]:
    # IMPORTANT: pgvector operators (e.g., <=>) expect both sides to be `vector`.
    # If we pass a Python list directly, psycopg2 adapts it to `numeric[]`, causing:
    #   operator does not exist: vector <=> numeric[]
    # So we pass a pgvector literal and cast it to ::vector.
    vec_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

    sql_set = "SET LOCAL hnsw.ef_search = %s;"
    sql = """
        SELECT chunk_id,
               1 - (embedding <=> %s::vector) AS vscore
        FROM article_section_embedding
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    with conn.cursor() as cur:
        cur.execute("BEGIN;")
        # Some environments may not have HNSW / the GUC enabled; don't hard-fail.
        try:
            cur.execute(sql_set, (ef_search,))
        except Exception:
            pass
        cur.execute(sql, (vec_literal, vec_literal, k_vec))
        rows = cur.fetchall()
        cur.execute("COMMIT;")

    results: List[Dict[str, Any]] = []
    for chunk_id, vscore in rows:
        results.append({"chunk_id": chunk_id, "vscore": float(vscore)})
    return results


# ─────────────────────────────────────
# 2) Neo4j keyword search (Fulltext)
# ─────────────────────────────────────

def neo4j_keyword_search_chunks(
    driver,
    query_text: str,
    k_kw: int,
    fulltext_index: Optional[str],
) -> List[Dict[str, Any]]:
    if not fulltext_index or k_kw <= 0:
        return []

    cypher = f"""
    CALL db.index.fulltext.queryNodes('{fulltext_index}', $text, {{limit: $k_kw}})
    YIELD node, score
    WHERE node:Chunk
    RETURN node.chunk_id AS chunk_id, score AS kscore
    ORDER BY kscore DESC
    """
    with driver.session() as session:
        rs = session.run(cypher, text=query_text, k_kw=k_kw)
        return [r.data() for r in rs]


# ─────────────────────────────────────
# 3) Python RRF Fusion
# ─────────────────────────────────────

def rrf_fusion(
    vec_results: List[Dict[str, Any]],
    kw_results: List[Dict[str, Any]],
    k_final: int,
    rrf_k: int = 60,
) -> List[Tuple[str, float, List[str]]]:
    rank_map_vec: Dict[str, int] = {}
    for i, row in enumerate(vec_results):
        rank_map_vec[str(row["chunk_id"])] = i + 1

    rank_map_kw: Dict[str, int] = {}
    for i, row in enumerate(kw_results):
        rank_map_kw[str(row["chunk_id"])] = i + 1

    chunk_ids = set(rank_map_vec.keys()) | set(rank_map_kw.keys())

    fused: List[Tuple[str, float, List[str]]] = []
    for cid in chunk_ids:
        score = 0.0
        sources: List[str] = []
        if cid in rank_map_vec:
            score += 1.0 / (rrf_k + rank_map_vec[cid])
            sources.append("vector")
        if cid in rank_map_kw:
            score += 1.0 / (rrf_k + rank_map_kw[cid])
            sources.append("keyword")
        fused.append((cid, score, sources))

    fused.sort(key=lambda x: x[1], reverse=True)
    return fused[:k_final]


# ─────────────────────────────────────
# 4) Fetch chunk contexts from Neo4j
# ─────────────────────────────────────

def fetch_chunk_contexts(driver, chunk_ids: List[str]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []

    cypher = """
    UNWIND $ids AS cid
    MATCH (c:Chunk {chunk_id: cid})
    MATCH (c)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN c.chunk_id AS id,
           c.text AS text,
           a.title AS title,
           s.title AS section
    """
    with driver.session() as session:
        rs = session.run(cypher, ids=chunk_ids)
        rows = [r.data() for r in rs]

    # preserve input order
    by_id = {str(r["id"]): r for r in rows}
    out: List[Dict[str, Any]] = []
    for cid in chunk_ids:
        r = by_id.get(str(cid))
        if r:
            out.append(r)
    return out


def run_system_b_with_metrics(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    ef_search: int = 100,
    embedding_model: Optional[str] = None,
) -> Dict[str, Any]:
    t_total0 = time.perf_counter()

    embedding, emb_usage, emb_ms = get_query_embedding_with_usage(query_text, embedding_model=embedding_model)

    # Vector search (PG)
    t0 = time.perf_counter()
    conn = get_pg_conn()
    try:
        vec_results = pg_vector_search_article(conn, embedding, k_vec=k_vec, ef_search=ef_search)
    finally:
        conn.close()
    pg_ms = (time.perf_counter() - t0) * 1000.0

    # Keyword search (Neo4j)
    t1 = time.perf_counter()
    driver = get_neo4j_driver()
    try:
        ft_index, ft_meta = pick_fulltext_chunk_index(driver)
        kw_results = neo4j_keyword_search_chunks(driver, query_text, k_kw=k_kw, fulltext_index=ft_index)
        # Fuse
        fused = rrf_fusion(vec_results, kw_results, k_final=k_final, rrf_k=rrf_k)
        fused_ids = [cid for cid, _, _ in fused]
        contexts = fetch_chunk_contexts(driver, fused_ids)

        # attach fused score + sources
        fuse_map = {cid: (score, sources) for cid, score, sources in fused}
        for r in contexts:
            cid = str(r.get("id"))
            score, sources = fuse_map.get(cid, (None, []))
            r["similarity"] = score
            r["sources"] = sources
            r["system"] = "SystemB_PGVector_Neo4jFT_RRF"

    finally:
        driver.close()
    neo_ms = (time.perf_counter() - t1) * 1000.0

    total_ms = (time.perf_counter() - t_total0) * 1000.0

    metrics = {
        "system": "B",
        "embedding_ms": emb_ms,
        "pg_ms": pg_ms,
        "neo4j_ms": neo_ms,
        "total_ms": total_ms,
        "embedding_usage": emb_usage,
        "k_final": k_final,
        "k_vec": k_vec,
        "k_kw": k_kw,
        "rrf_k": rrf_k,
        "ef_search": ef_search,
        "fulltext_index": ft_index,
        "fulltext_index_meta": ft_meta,
        "fulltext_enabled": bool(ft_index and k_kw > 0),
    }

    return {"results": contexts, "metrics": metrics}


def run_system_b(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    ef_search: int = 100,
    embedding_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return run_system_b_with_metrics(
        query_text=query_text,
        k_final=k_final,
        k_vec=k_vec,
        k_kw=k_kw,
        rrf_k=rrf_k,
        ef_search=ef_search,
        embedding_model=embedding_model,
    )["results"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", "-q", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--k-vec", type=int, default=50)
    parser.add_argument("--k-kw", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--ef-search", type=int, default=100)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--with-metrics", action="store_true")
    args = parser.parse_args()

    if args.with_metrics:
        out = run_system_b_with_metrics(
            query_text=args.query,
            k_final=args.k,
            k_vec=args.k_vec,
            k_kw=args.k_kw,
            rrf_k=args.rrf_k,
            ef_search=args.ef_search,
            embedding_model=args.embedding_model,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        results = run_system_b(
            query_text=args.query,
            k_final=args.k,
            k_vec=args.k_vec,
            k_kw=args.k_kw,
            rrf_k=args.rrf_k,
            ef_search=args.ef_search,
            embedding_model=args.embedding_model,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
