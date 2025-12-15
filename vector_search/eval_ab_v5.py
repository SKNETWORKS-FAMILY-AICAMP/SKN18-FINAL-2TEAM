# eval_ab_v2.py
import os
import json
import time
import argparse
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
from openai import OpenAI

# Optional: load environment variables from a local .env file (if python-dotenv is installed)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# patched modules (same dir)
from run_system_a_patched_v4 import run_system_a_with_metrics
from run_system_b_patched_v4 import run_system_b_with_metrics


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_mkdir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p


def _extract_ids(results: List[Dict[str, Any]]) -> List[str]:
    ids = []
    for r in results:
        cid = r.get("id") or r.get("chunk_id") or r.get("chunkId")
        if cid is not None:
            ids.append(str(cid))
    return ids


def _jaccard(a: List[str], b: List[str]) -> Tuple[int, float]:
    sa, sb = set(a), set(b)
    inter = sa & sb
    uni = sa | sb
    return len(inter), (len(inter) / len(uni) if uni else 0.0)


def _build_context(results: List[Dict[str, Any]], max_chars: int = 8000) -> str:
    parts: List[str] = []
    for i, r in enumerate(results, start=1):
        title = r.get("title") or ""
        section = r.get("section") or ""
        text = r.get("text") or ""
        block = f"[{i}] Title: {title}\nSection: {section}\nText: {text}".strip()
        parts.append(block)
    ctx = "\n\n".join(parts)
    if len(ctx) > max_chars:
        ctx = ctx[:max_chars] + "\n\n[TRUNCATED]"
    return ctx


def _responses_or_chat(client: OpenAI, model: str, system: str, user: str) -> Tuple[str, Dict[str, Any]]:
    """Return (answer_text, usage_dict). Tries Responses API first, then Chat Completions."""
    # Responses API
    try:
        t0 = time.perf_counter()
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0
        text = getattr(resp, "output_text", None)
        if text is None:
            # fallback: best-effort parse
            text = ""
            for item in getattr(resp, "output", []) or []:
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", "") == "output_text":
                        text += getattr(c, "text", "")
        usage = {}
        u = getattr(resp, "usage", None)
        if u is not None:
            usage = {
                "input_tokens": getattr(u, "input_tokens", None),
                "output_tokens": getattr(u, "output_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            }
        usage["latency_ms"] = dt_ms
        usage["api"] = "responses"
        return text, usage
    except Exception:
        pass

    # Chat Completions API
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    dt_ms = (time.perf_counter() - t0) * 1000.0
    text = resp.choices[0].message.content
    usage = {}
    u = getattr(resp, "usage", None)
    if u is not None:
        usage = {
            "prompt_tokens": getattr(u, "prompt_tokens", None),
            "completion_tokens": getattr(u, "completion_tokens", None),
            "total_tokens": getattr(u, "total_tokens", None),
        }
    usage["latency_ms"] = dt_ms
    usage["api"] = "chat.completions"
    return text, usage


def answer_with_context(question: str, results: List[Dict[str, Any]], model: str, max_context_chars: int) -> Tuple[str, Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set (needed for answer generation)")
    client = OpenAI(api_key=api_key)

    ctx = _build_context(results, max_chars=max_context_chars)
    system = (
        "You are combining two personas: (1) Concept & Mechanism Explorer and "
        "(2) Experimental Designer & Troubleshooter.\n\n"
        "Rules:\n"
        "- Answer in English.\n"
        "- Use ONLY the provided context blocks. Do not use outside knowledge.\n"
        "- If a detail is missing, explicitly write: 'Not found in context.'\n"
        "- For each substantive claim, cite the supporting context block(s) like [1], [2].\n"
        "- Avoid hand-wavy statements; when uncertain, state what evidence would be needed.\n\n"
        "Response structure (use these headings):\n"
        "1) Direct answer\n"
        "2) Mechanistic explanation (step-by-step)\n"
        "3) Experimental design & troubleshooting (Assumptions → Design → Controls → Readouts → Pitfalls)\n"
        "4) Limitations / Not found in context\n"
    )

    user = (
        f"Question:\n{question}\n\n"
        f"Context blocks:\n{ctx}\n\n"
        "Write a comprehensive answer that stays grounded in the context."
    )

    return _responses_or_chat(client, model=model, system=system, user=user)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", default="user_input_only.csv", help="CSV file with column 'user_input'")
    ap.add_argument("--outdir", default=f"ab_eval_out_{_now_tag()}", help="Output directory")
    ap.add_argument("--k", type=int, default=5, help="top-k final")
    ap.add_argument("--k-vec", type=int, default=50)
    ap.add_argument("--k-kw", type=int, default=50)
    ap.add_argument("--rrf-k", type=int, default=60)
    ap.add_argument("--ef-search", type=int, default=100)
    ap.add_argument(
        "--embedding-model",
        default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        help="Embedding model used to embed each query for retrieval",
    )
    ap.add_argument("--with-answer", action="store_true", help="Generate final answers with LLM and record token usage")
    ap.add_argument("--chat-model", default=os.getenv("CHAT_MODEL", ""), help="LLM model for answering (required if --with-answer)")
    ap.add_argument("--max-context-chars", type=int, default=8000)
    args = ap.parse_args()

    df = pd.read_csv(args.input_csv)
    if "user_input" not in df.columns:
        raise ValueError("input CSV must have a column named 'user_input'")

    outdir = _safe_mkdir(args.outdir)
    out_jsonl = os.path.join(outdir, "outputs.jsonl")
    out_csv = os.path.join(outdir, "metrics.csv")

    rows: List[Dict[str, Any]] = []

    with open(out_jsonl, "w", encoding="utf-8") as fjsonl:
        for idx, q in enumerate(df["user_input"].astype(str).tolist(), start=1):
            q = q.strip()
            if not q:
                continue

            # ---- System A
            out_a = run_system_a_with_metrics(
                q,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
                embedding_model=args.embedding_model,
            )
            res_a = out_a["results"]
            met_a = out_a["metrics"]

            # ---- System B
            out_b = run_system_b_with_metrics(
                q,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
                ef_search=args.ef_search,
                embedding_model=args.embedding_model,
            )
            res_b = out_b["results"]
            met_b = out_b["metrics"]

            ids_a = _extract_ids(res_a)
            ids_b = _extract_ids(res_b)
            overlap_n, jac = _jaccard(ids_a, ids_b)

            ans_a = ans_b = None
            ans_usage_a = ans_usage_b = None

            if args.with_answer:
                if not args.chat_model:
                    raise RuntimeError("--chat-model (or CHAT_MODEL env) is required when --with-answer is set")

                ans_a, ans_usage_a = answer_with_context(q, res_a, model=args.chat_model, max_context_chars=args.max_context_chars)
                ans_b, ans_usage_b = answer_with_context(q, res_b, model=args.chat_model, max_context_chars=args.max_context_chars)

            # write per-system outputs (jsonl)
            fjsonl.write(json.dumps({
                "qid": idx,
                "query": q,
                "system": "A",
                "metrics": met_a,
                "results": res_a,
                "answer": ans_a,
                "answer_usage": ans_usage_a,
            }, ensure_ascii=False) + "\n")
            fjsonl.write(json.dumps({
                "qid": idx,
                "query": q,
                "system": "B",
                "metrics": met_b,
                "results": res_b,
                "answer": ans_b,
                "answer_usage": ans_usage_b,
            }, ensure_ascii=False) + "\n")

            # summary row (csv)
            row = {
                "qid": idx,
                "query": q,
                "embedding_model": args.embedding_model,
                "k": args.k,
                "overlap_count": overlap_n,
                "jaccard": jac,

                "A_total_ms": met_a.get("total_ms"),
                "A_embedding_ms": met_a.get("embedding_ms"),
                "A_backend_ms": met_a.get("neo4j_ms"),
                "A_embed_total_tokens": (met_a.get("embedding_usage") or {}).get("total_tokens"),

                "B_total_ms": met_b.get("total_ms"),
                "B_embedding_ms": met_b.get("embedding_ms"),
                "B_pg_vector_ms": met_b.get("pg_vector_ms"),
                "B_neo4j_keyword_ms": met_b.get("neo4j_keyword_ms"),
                "B_neo4j_context_ms": met_b.get("neo4j_context_ms"),
                "B_embed_total_tokens": (met_b.get("embedding_usage") or {}).get("total_tokens"),
            }

            if args.with_answer:
                # normalize token keys across APIs
                def _get_total(u: Optional[Dict[str, Any]]) -> Optional[int]:
                    if not u:
                        return None
                    return u.get("total_tokens") or (u.get("input_tokens", 0) + u.get("output_tokens", 0) if u.get("input_tokens") is not None and u.get("output_tokens") is not None else None)

                row.update({
                    "A_answer_latency_ms": (ans_usage_a or {}).get("latency_ms"),
                    "A_answer_total_tokens": _get_total(ans_usage_a),
                    "B_answer_latency_ms": (ans_usage_b or {}).get("latency_ms"),
                    "B_answer_total_tokens": _get_total(ans_usage_b),
                })

            rows.append(row)

    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] wrote: {out_csv}")
    print(f"[OK] wrote: {out_jsonl}")


if __name__ == "__main__":
    main()