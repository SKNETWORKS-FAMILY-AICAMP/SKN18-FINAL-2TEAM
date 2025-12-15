# eval_ab_v5.py
import os
import json
import time
import argparse
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from openai import OpenAI

# Optional: load environment variables
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# [주의] 파일명이 업로드하신 v4 버전으로 되어 있습니다. 
# 만약 v5를 쓰신다면 import 부분을 수정해주세요.
from run_system_a_patched_v4 import run_system_a_with_metrics
from run_system_b_patched_v4 import run_system_b_with_metrics


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_mkdir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p


def _extract_ids(results: List[Dict[str, Any]]) -> List[str]:
    """검색 결과에서 Chunk ID 리스트 추출"""
    ids = []
    for r in results:
        cid = r.get("id") or r.get("chunk_id") or r.get("chunkId")
        if cid is not None:
            ids.append(str(cid))
    return ids


def _extract_contexts(results: List[Dict[str, Any]]) -> List[str]:
    """
    [추가됨] 검색 결과에서 실제 텍스트(Content) 리스트 추출
    - RAGAS 평가를 위해 ID가 아닌 본문이 필요함
    """
    texts = []
    for r in results:
        text = r.get("text")
        if text:
            texts.append(str(text))
    return texts


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


def answer_with_context(question: str, results: List[Dict[str, Any]], model: str, max_context_chars: int) -> Tuple[str, Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    client = OpenAI(api_key=api_key)

    ctx = _build_context(results, max_chars=max_context_chars)
    
    # 평가용 드라이(Dry) 프롬프트
    system = (
        "You are a research assistant utilizing a Retrieval-Augmented Generation (RAG) system.\n"
        "Your task is to answer the user's question based **ONLY** on the provided [Context] documents.\n\n"
        "**Guidelines:**\n"
        "1. **Strict Grounding:** Do not use outside knowledge. If the answer is not in the [Context], state 'The provided documents do not contain this information.'\n"
        "2. **Citations:** You must cite the source for every key statement using the format `[Document N]`.\n"
        "3. **Tone:** Maintain a neutral, objective, and scientific tone.\n"
        "4. **No Fluff:** Do not make up protocols or assumptions that are not explicitly written in the text."
    )

    user = (
        f"Question:\n{question}\n\n"
        f"Context blocks:\n{ctx}\n\n"
    )

    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0
        text = resp.choices[0].message.content
        
        u = getattr(resp, "usage", None)
        usage = {
            "total_tokens": getattr(u, "total_tokens", 0) if u else 0,
            "latency_ms": dt_ms
        }
        return text, usage
    except Exception as e:
        return f"Error: {e}", {"total_tokens": 0, "latency_ms": 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", default="user_input_only.csv", help="Column 'user_input' 필수")
    ap.add_argument("--outdir", default=f"ab_eval_out_{_now_tag()}", help="Output directory")
    ap.add_argument("--k", type=int, default=5, help="top-k final")
    ap.add_argument("--k-vec", type=int, default=50)
    ap.add_argument("--k-kw", type=int, default=50)
    ap.add_argument("--rrf-k", type=int, default=60)
    ap.add_argument("--ef-search", type=int, default=100)
    ap.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    ap.add_argument("--with-answer", action="store_true", help="Generate answers with LLM")
    ap.add_argument("--chat-model", default="gpt-4o", help="Model for answering")
    ap.add_argument("--max-context-chars", type=int, default=12000)
    args = ap.parse_args()

    df = pd.read_csv(args.input_csv)
    if "user_input" not in df.columns:
        raise ValueError("Input CSV must have a 'user_input' column.")

    outdir = _safe_mkdir(args.outdir)
    out_csv = os.path.join(outdir, "evaluation_results.csv")

    rows: List[Dict[str, Any]] = []

    print(f"🚀 Starting evaluation on {len(df)} queries...")
    print(f"📂 Output will be saved to: {out_csv}")

    for idx, q in enumerate(df["user_input"].astype(str).tolist(), start=1):
        q = q.strip()
        if not q:
            continue
        
        print(f"[{idx}/{len(df)}] Processing: {q[:50]}...")

        # ---- System A (Neo4j Hybrid)
        try:
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
        except Exception as e:
            print(f"  ❌ System A Error: {e}")
            res_a, met_a = [], {}

        # ---- System B (PG Vector + Neo4j Graph)
        try:
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
        except Exception as e:
            print(f"  ❌ System B Error: {e}")
            res_b, met_b = [], {}

        # Compare IDs (Jaccard)
        ids_a = _extract_ids(res_a)
        ids_b = _extract_ids(res_b)
        overlap_n, jac = _jaccard(ids_a, ids_b)

        # [수정됨] 실제 텍스트(Context) 추출
        # 리스트 형태이므로 json.dumps를 사용하여 CSV 셀 하나에 저장
        contexts_a = _extract_contexts(res_a)
        contexts_b = _extract_contexts(res_b)

        # Generate Answers (Optional)
        ans_a = ans_b = ""
        usage_a = usage_b = {}
        
        if args.with_answer:
            ans_a, usage_a = answer_with_context(q, res_a, args.chat_model, args.max_context_chars)
            ans_b, usage_b = answer_with_context(q, res_b, args.chat_model, args.max_context_chars)

        # Build CSV Row
        row = {
            "qid": idx,
            "query": q,
            
            # --- Comparison ---
            "overlap_count": overlap_n,
            "jaccard_similarity": jac,
            
            # --- System A ---
            "A_total_ms": met_a.get("total_ms"),
            "A_retrieved_ids": ", ".join(ids_a),
            "A_retrieved_contexts": json.dumps(contexts_a, ensure_ascii=False), # RAGAS용 텍스트
            "A_answer": ans_a,
            "A_token_usage": usage_a.get("total_tokens"),
            
            # --- System B ---
            "B_total_ms": met_b.get("total_ms"),
            "B_retrieved_ids": ", ".join(ids_b),
            "B_retrieved_contexts": json.dumps(contexts_b, ensure_ascii=False), # RAGAS용 텍스트
            "B_answer": ans_b,
            "B_token_usage": usage_b.get("total_tokens"),
        }
        rows.append(row)

    # Save to CSV
    if rows:
        result_df = pd.DataFrame(rows)
        # utf-8-sig: 엑셀에서 한글 깨짐 방지
        result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"\n✅ Evaluation Finished! Results saved to: {out_csv}")
    else:
        print("\n⚠️ No results to save.")

if __name__ == "__main__":
    main()