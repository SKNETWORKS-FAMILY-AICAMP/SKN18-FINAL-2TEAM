# run_system_a_patched_v4.py
# System A: Neo4j Hybrid(Vector + Fulltext) + RRF
# - Fulltext index name auto-detected (or overridden via FULLTEXT_CHUNK_INDEX)
# - If no suitable fulltext index exists, falls back to vector-only retrieval.

import os
import argparse
import json
import time
from typing import List, Dict, Any, Tuple, Optional

from neo4j import GraphDatabase
from openai import OpenAI

# Optional: load environment variables from a local .env file
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────
# Common: Neo4j / Embedding client
# ─────────────────────────────────────

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
    """Return a list of {name, entityType, labelsOrTypes, properties}."""
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
    """Choose a fulltext index that can query Chunk nodes.

    Priority:
    1) FULLTEXT_CHUNK_INDEX env override (if exists)
    2) preferred name 'keyword_chunk_index' (if exists)
    3) any NODE fulltext index whose labelsOrTypes includes 'Chunk'
    4) any NODE fulltext index
    5) None
    """
    override = os.getenv("FULLTEXT_CHUNK_INDEX")
    preferred = "keyword_chunk_index"

    idxs = _list_fulltext_indexes(driver)
    by_name = {i.get("name"): i for i in idxs if i.get("name")}

    def _exists(name: str) -> bool:
        return name in by_name

    # 1) override
    if override and _exists(override):
        return override, by_name[override]

    # 2) preferred
    if _exists(preferred):
        return preferred, by_name[preferred]

    # 3) Chunk NODE index
    chunk_candidates = []
    for i in idxs:
        if i.get("entityType") != "NODE":
            continue
        labels = i.get("labelsOrTypes") or []
        # labelsOrTypes can be list or string depending on version
        if isinstance(labels, str):
            labels = [labels]
        if "Chunk" in labels:
            chunk_candidates.append(i)

    # prefer those indexing text
    def _score(i: Dict[str, Any]) -> int:
        props = i.get("properties") or []
        if isinstance(props, str):
            props = [props]
        return 2 if "text" in props else 1

    if chunk_candidates:
        chunk_candidates.sort(key=_score, reverse=True)
        chosen = chunk_candidates[0]
        return chosen.get("name"), chosen

    # 4) any NODE fulltext index
    node_candidates = [i for i in idxs if i.get("entityType") == "NODE"]
    if node_candidates:
        chosen = node_candidates[0]
        return chosen.get("name"), chosen

    return None, {}


# ─────────────────────────────────────
# System A: Neo4j Hybrid + RRF
# ─────────────────────────────────────

def run_system_a_with_metrics(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    embedding_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Return {'results': [...], 'metrics': {...}}."""
    t_total0 = time.perf_counter()

    embedding, emb_usage, emb_ms = get_query_embedding_with_usage(query_text, embedding_model=embedding_model)

    vector_index = os.getenv("VECTOR_CHUNK_INDEX", "chunk_vector_index")

    driver = get_neo4j_driver()
    ft_index, ft_meta = pick_fulltext_chunk_index(driver)

    cypher_vec_only = f"""
    // 1) Vector TopN (Neo4j vector index)
    CALL {{
      CALL db.index.vector.queryNodes('{vector_index}', $k_vec, $embedding)
      YIELD node, score
      WITH node, score
      ORDER BY score DESC
      WITH collect(node) AS nodes, collect(score) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS chunk, (i + 1) AS rank
    }}
    WITH chunk, rank
    WITH chunk, (1.0 / ($rrf_k + rank)) AS rrfScore, ['vector'] AS sources
    ORDER BY rrfScore DESC
    LIMIT $k_final

    MATCH (chunk)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN
      chunk.chunk_id AS id,
      chunk.text     AS text,
      a.title        AS title,
      s.title        AS section,
      rrfScore       AS similarity,
      sources        AS sources,
      'SystemA_Neo4j_VectorOnly' AS system
    """

    cypher_hybrid = f"""
    // 1) Vector TopN (Neo4j vector index)
    CALL {{
      CALL db.index.vector.queryNodes('{vector_index}', $k_vec, $embedding)
      YIELD node, score
      WITH node, score
      ORDER BY score DESC
      WITH collect(node) AS nodes, collect(score) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS node, (i + 1) AS rank, scores[i] AS rawScore, 'vector' AS src
    }}

    WITH collect({{node: node, rank: rank, rawScore: rawScore, src: src}}) AS vecRows

    // 2) Keyword TopN (Neo4j fulltext index)
    CALL {{
      CALL db.index.fulltext.queryNodes('{ft_index}', $text, {{limit: $k_kw}})
      YIELD node, score
      WHERE node:Chunk
      WITH node, score
      ORDER BY score DESC
      WITH collect(node) AS nodes, collect(score) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS node, (i + 1) AS rank, scores[i] AS rawScore, 'keyword' AS src
    }}

    // 3) RRF fusion (fix: separate aggregation)
    WITH vecRows, collect({{node: node, rank: rank, rawScore: rawScore, src: src}}) AS kwRows
    WITH vecRows + kwRows AS rows
    UNWIND rows AS r
    WITH r.node AS chunk, r.src AS src, r.rank AS rank
    WITH chunk, src, min(rank) AS bestRank
    WITH chunk,
         sum(1.0 / ($rrf_k + bestRank)) AS rrfScore,
         collect(DISTINCT src) AS sources

    ORDER BY rrfScore DESC
    LIMIT $k_final

    MATCH (chunk)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN
      chunk.chunk_id AS id,
      chunk.text     AS text,
      a.title        AS title,
      s.title        AS section,
      rrfScore       AS similarity,
      sources        AS sources,
      'SystemA_Neo4j_Hybrid_RRF' AS system
    """

    neo_ms = None
    try:
        t0 = time.perf_counter()
        with driver.session() as session:
            if ft_index and k_kw > 0:
                rs = session.run(
                    cypher_hybrid,
                    text=query_text,
                    embedding=embedding,
                    k_vec=k_vec,
                    k_kw=k_kw,
                    k_final=k_final,
                    rrf_k=rrf_k,
                )
            else:
                rs = session.run(
                    cypher_vec_only,
                    embedding=embedding,
                    k_vec=k_vec,
                    k_final=k_final,
                    rrf_k=rrf_k,
                )
            results = [record.data() for record in rs]
        neo_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        driver.close()

    total_ms = (time.perf_counter() - t_total0) * 1000.0
    metrics = {
        "system": "A",
        "embedding_ms": emb_ms,
        "neo4j_ms": neo_ms,
        "total_ms": total_ms,
        "embedding_usage": emb_usage,
        "k_final": k_final,
        "k_vec": k_vec,
        "k_kw": k_kw,
        "rrf_k": rrf_k,
        "vector_index": vector_index,
        "fulltext_index": ft_index,
        "fulltext_index_meta": ft_meta,
        "fulltext_enabled": bool(ft_index and k_kw > 0),
    }
    return {"results": results, "metrics": metrics}


def run_system_a(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    embedding_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return run_system_a_with_metrics(
        query_text=query_text,
        k_final=k_final,
        k_vec=k_vec,
        k_kw=k_kw,
        rrf_k=rrf_k,
        embedding_model=embedding_model,
    )["results"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", "-q", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--k-vec", type=int, default=50)
    parser.add_argument("--k-kw", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--embedding-model", default=None, help="Override embedding model for the query")
    parser.add_argument("--with-metrics", action="store_true")
    args = parser.parse_args()

    if args.with_metrics:
        out = run_system_a_with_metrics(
            query_text=args.query,
            k_final=args.k,
            k_vec=args.k_vec,
            k_kw=args.k_kw,
            rrf_k=args.rrf_k,
            embedding_model=args.embedding_model,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        results = run_system_a(
            query_text=args.query,
            k_final=args.k,
            k_vec=args.k_vec,
            k_kw=args.k_kw,
            rrf_k=args.rrf_k,
            embedding_model=args.embedding_model,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
