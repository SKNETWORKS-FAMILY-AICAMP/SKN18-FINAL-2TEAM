# caption.py
# 목적: fig_id 기준으로 (1) caption + (2) Results 섹션에서 해당 figure가 언급된 chunk 텍스트(result_text)를 붙여서 CSV로 출력
# 특징: chunk는 chunksize로 스트리밍, 중간 집계는 SQLite(WAL)로 저장해서 메모리 폭발 방지
#
# 입력:
#   - chunk_csv: chunk_id, section_id, text_chunk, ref_ids(=original_label_id 리스트) ... (컬럼명은 args로 변경 가능)
#   - section_csv: section_id(or id), section_category ... (result/results 섹션 필터)
#   - fig_csv: original_label_id, fig_id, fig_caption(또는 caption 컬럼)
#
# 출력:
#   - out_csv: fig_id, caption, result_text

import argparse
import csv
import pandas as pd
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Set, Dict


# -------------------------
# NA handling (pd.NA + "na" 문자열까지 None 처리)
# -------------------------
NA_STRINGS = {"na", "n/a", "nan", "null", "none", ""}


def sqlite_safe(v):
    """SQLite 바인딩 안전 변환: pd.NA/NaN + 'na'류 문자열 -> None"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, str):
        s = v.strip()
        if s.lower() in NA_STRINGS:
            return None
        return s

    return v


def split_ids(x) -> List[str]:
    """'a;b,c|d' 형태를 ['a','b','c','d']로. NA/na류는 제거."""
    x = sqlite_safe(x)
    if x is None:
        return []
    s = str(x).strip()
    if not s:
        return []
    parts = re.split(r"[;,|]\s*", s)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.lower() in NA_STRINGS:
            continue
        out.append(p)
    return out


def detect_col(cols, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None


def stream_write_query_to_csv(cur: sqlite3.Cursor, query: str, out_csv: str, fetch_size: int = 2000):
    cur.execute(query)
    header = [d[0] for d in cur.description]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        while True:
            rows = cur.fetchmany(fetch_size)
            if not rows:
                break
            w.writerows(rows)


def main():
    p = argparse.ArgumentParser(
        description="Build fig-level table: fig_id + caption + result_text (Results section chunks that reference the figure), batch + SQLite."
    )
    p.add_argument("--chunk_csv", required=True)
    p.add_argument("--section_csv", required=True)
    p.add_argument("--fig_csv", required=True)
    p.add_argument("--out_csv", required=True)

    # batching
    p.add_argument("--chunk_size", type=int, default=200_000)
    p.add_argument("--fig_chunk_size", type=int, default=200_000)
    p.add_argument("--section_chunk_size", type=int, default=200_000)

    # chunk columns
    p.add_argument("--chunk_section_col", default="section_id")
    p.add_argument("--chunk_text_col", default="text_chunk")
    p.add_argument("--chunk_ref_col", default="ref_ids")  # figure reference ids (= original_label_id list)

    # section columns
    p.add_argument("--section_key_candidates", default="section_id,id")
    p.add_argument("--section_category_col", default="section_category")
    p.add_argument("--results_category_values", default="result,results")

    # fig columns
    p.add_argument("--fig_orig_col", default="original_label_id")  # key that matches ref_ids items
    p.add_argument("--fig_id_col", default="fig_id")

    # caption column detection
    p.add_argument(
        "--fig_caption_candidates",
        default="fig_caption,caption,fig_text,fig_title,description",
        help="Comma-separated candidates for caption column in fig_csv (default includes fig_caption).",
    )

    # sqlite path
    p.add_argument("--sqlite_path", default="")

    args = p.parse_args()

    section_key_candidates = [x.strip() for x in args.section_key_candidates.split(",") if x.strip()]
    results_values = {x.strip().lower() for x in args.results_category_values.split(",") if x.strip()}
    caption_candidates = [x.strip() for x in args.fig_caption_candidates.split(",") if x.strip()]

    sqlite_path = args.sqlite_path.strip()
    if not sqlite_path:
        sqlite_path = str(Path(args.out_csv).with_suffix(".sqlite"))
    print(f"[INFO] sqlite_path = {sqlite_path}")

    # -------------------------
    # SQLite init
    # -------------------------
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA temp_store=MEMORY;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS figs (
            fig_id TEXT PRIMARY KEY,
            caption TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orig2fig (
            original_label_id TEXT PRIMARY KEY,
            fig_id TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            fig_id TEXT,
            chunk_text TEXT
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_fig ON edges(fig_id);")
    conn.commit()

    # -------------------------
    # 1) FIG load (stream)
    # -------------------------
    print("[1/4] Loading fig table (stream) ...")
    fig_head = pd.read_csv(args.fig_csv, nrows=5)
    if args.fig_orig_col not in fig_head.columns or args.fig_id_col not in fig_head.columns:
        raise ValueError(
            f"fig_csv must include '{args.fig_orig_col}' and '{args.fig_id_col}'. actual={list(fig_head.columns)}"
        )

    caption_col = detect_col(fig_head.columns, caption_candidates)
    if caption_col is None:
        print(f"[WARN] caption column not found. candidates={caption_candidates}. caption will be NULL.")
    else:
        print(f"[INFO] detected caption_col = {caption_col}")

    usecols = [args.fig_orig_col, args.fig_id_col] + ([caption_col] if caption_col else [])

    insert_o2f = []
    insert_figs = []
    total = 0

    for fchunk in pd.read_csv(
        args.fig_csv,
        usecols=usecols,
        dtype="string",
        chunksize=args.fig_chunk_size,
    ):
        # normalize
        fchunk[args.fig_orig_col] = fchunk[args.fig_orig_col].astype("string")
        fchunk[args.fig_id_col] = fchunk[args.fig_id_col].astype("string")

        for row in fchunk.itertuples(index=False):
            orig = sqlite_safe(getattr(row, args.fig_orig_col))
            fid = sqlite_safe(getattr(row, args.fig_id_col))
            cap = sqlite_safe(getattr(row, caption_col)) if caption_col else None

            if not orig or not fid:
                continue

            insert_o2f.append((orig, fid))
            insert_figs.append((fid, cap))
            total += 1

        if len(insert_o2f) >= 200_000:
            cur.executemany(
                "INSERT OR REPLACE INTO orig2fig(original_label_id, fig_id) VALUES (?, ?);",
                insert_o2f,
            )
            cur.executemany(
                "INSERT OR REPLACE INTO figs(fig_id, caption) VALUES (?, ?);",
                insert_figs,
            )
            conn.commit()
            insert_o2f.clear()
            insert_figs.clear()

    if insert_o2f:
        cur.executemany(
            "INSERT OR REPLACE INTO orig2fig(original_label_id, fig_id) VALUES (?, ?);",
            insert_o2f,
        )
        cur.executemany(
            "INSERT OR REPLACE INTO figs(fig_id, caption) VALUES (?, ?);",
            insert_figs,
        )
        conn.commit()

    print(f"[OK] fig rows processed = {total:,}")

    # -------------------------
    # 2) Collect Results section IDs (stream)
    # -------------------------
    print("[2/4] Loading section table to collect result section IDs (stream) ...")
    sec_head = pd.read_csv(args.section_csv, nrows=5)
    sec_key = detect_col(sec_head.columns, section_key_candidates)
    if sec_key is None:
        raise ValueError(
            f"section key not found. candidates={section_key_candidates}, actual={list(sec_head.columns)}"
        )

    if args.section_category_col not in sec_head.columns:
        raise ValueError(
            f"section_csv must include '{args.section_category_col}'. actual={list(sec_head.columns)}"
        )

    result_section_ids: Set[str] = set()
    for schunk in pd.read_csv(
        args.section_csv,
        usecols=[sec_key, args.section_category_col],
        dtype="string",
        chunksize=args.section_chunk_size,
    ):
        schunk[sec_key] = schunk[sec_key].astype("string")
        schunk[args.section_category_col] = schunk[args.section_category_col].astype("string").str.lower()

        mask = schunk[args.section_category_col].isin(results_values)
        for sid in schunk.loc[mask, sec_key].tolist():
            sid = sqlite_safe(sid)
            if sid:
                result_section_ids.add(sid)

    print(f"[OK] result_section_ids = {len(result_section_ids):,} (values={sorted(results_values)})")

    # -------------------------
    # 3) Process chunks (stream) -> edges(fig_id, chunk_text)
    # -------------------------
    print("[3/4] Processing chunk table (stream) -> edges(fig_id, chunk_text) ...")
    chunk_head = pd.read_csv(args.chunk_csv, nrows=5)
    for col in [args.chunk_section_col, args.chunk_text_col, args.chunk_ref_col]:
        if col not in chunk_head.columns:
            raise ValueError(f"chunk_csv missing column '{col}'. actual={list(chunk_head.columns)}")

    # SQLite lookup cache to reduce query spam
    orig_cache: Dict[str, Optional[str]] = {}
    CACHE_MAX = 500_000

    def get_fig_id_by_orig(orig_id: str) -> Optional[str]:
        if orig_id in orig_cache:
            return orig_cache[orig_id]
        cur.execute("SELECT fig_id FROM orig2fig WHERE original_label_id=? LIMIT 1;", (orig_id,))
        row = cur.fetchone()
        fid = row[0] if row else None
        orig_cache[orig_id] = fid
        if len(orig_cache) > CACHE_MAX:
            orig_cache.clear()
        return fid

    edge_buf = []
    processed_chunks = 0
    matched_edges = 0

    for cchunk in pd.read_csv(
        args.chunk_csv,
        dtype="string",
        chunksize=args.chunk_size,
    ):
        # results 섹션만 필터
        cchunk[args.chunk_section_col] = cchunk[args.chunk_section_col].astype("string")
        cchunk = cchunk[cchunk[args.chunk_section_col].isin(result_section_ids)]
        if cchunk.empty:
            continue

        processed_chunks += len(cchunk)

        for sid, txt, ref in zip(
            cchunk[args.chunk_section_col],
            cchunk[args.chunk_text_col],
            cchunk[args.chunk_ref_col],
        ):
            txt = sqlite_safe(txt)
            if txt is None:
                continue

            ref_ids = split_ids(ref)
            if not ref_ids:
                continue

            for orig_id in ref_ids:
                fid = get_fig_id_by_orig(orig_id)
                if not fid:
                    continue
                edge_buf.append((fid, txt))
                matched_edges += 1

        if len(edge_buf) >= 200_000:
            cur.executemany("INSERT INTO edges(fig_id, chunk_text) VALUES (?, ?);", edge_buf)
            conn.commit()
            edge_buf.clear()

    if edge_buf:
        cur.executemany("INSERT INTO edges(fig_id, chunk_text) VALUES (?, ?);", edge_buf)
        conn.commit()

    print(f"[OK] processed result-chunks = {processed_chunks:,}, matched edges = {matched_edges:,}")

    # -------------------------
    # 4) Aggregate by fig_id -> out_csv (stream)
    # -------------------------
    print("[4/4] Aggregating by fig_id and writing out_csv (stream) ...")
    query = """
    SELECT
        f.fig_id,
        f.caption,
        group_concat(e.chunk_text, '\n') AS result_text
    FROM figs f
    LEFT JOIN edges e ON e.fig_id = f.fig_id
    GROUP BY f.fig_id, f.caption
    ORDER BY f.fig_id;
    """
    stream_write_query_to_csv(cur, query, args.out_csv, fetch_size=2000)

    print(f"[DONE] saved -> {args.out_csv}")
    conn.close()


if __name__ == "__main__":
    main()
