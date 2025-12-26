import argparse
import pandas as pd
import re
import sys


# -------------------------
# Helpers
# -------------------------
def parse_ids(x):
    if pd.isna(x):
        return []
    s = str(x).strip()
    if not s:
        return []
    parts = re.split(r"[;,|]\s*", s)
    return [p.strip() for p in parts if p.strip()]


def build_orig2fig(fig_csv: str, fig_chunk_size: int) -> dict:
    """fig.csv에서 original_label_id -> fig_id 매핑 생성 (streaming)"""
    orig2fig = {}
    for fchunk in pd.read_csv(
        fig_csv,
        usecols=["original_label_id", "fig_id"],
        dtype={"original_label_id": "string", "fig_id": "string"},
        chunksize=fig_chunk_size,
    ):
        fchunk["original_label_id"] = fchunk["original_label_id"].astype("string").str.strip()
        orig2fig.update(dict(zip(fchunk["original_label_id"], fchunk["fig_id"])))
    return orig2fig


def detect_section_key(section_csv: str, candidates: list[str]) -> str:
    head = pd.read_csv(section_csv, nrows=5)
    sec_key = next((c for c in candidates if c in head.columns), None)
    if sec_key is None:
        raise ValueError(
            f"SECTION_CSV에 section 키 컬럼이 없음. 후보={candidates}, 실제={list(head.columns)}"
        )
    return sec_key


def build_section_map(
    section_csv: str,
    sec_key: str,
    orig2fig: dict,
    section_chunk_size: int,
    section_category_col: str,
    allowed_categories: set[str],
) -> dict:
    """
    section.csv에서 (section_category in allowed_categories) 인 행만 사용하여
    section_id(or id) -> 'fig_id;fig_id;...' 매핑 생성 (streaming)
    """
    # 컬럼 존재 체크
    head = pd.read_csv(section_csv, nrows=5)
    if section_category_col not in head.columns:
        raise ValueError(
            f"section_csv missing column '{section_category_col}'. actual={list(head.columns)}"
        )

    section_map = {}
    for schunk in pd.read_csv(
        section_csv,
        usecols=[sec_key, "fig_ids", section_category_col],
        dtype={sec_key: "string", "fig_ids": "string", section_category_col: "string"},
        chunksize=section_chunk_size,
    ):
        schunk[sec_key] = schunk[sec_key].astype("string").str.strip()

        # section_category 필터 (대소문자/공백 안전)
        cat = schunk[section_category_col].astype("string").str.strip().str.lower()
        keep = cat.isin(allowed_categories)
        schunk = schunk[keep]
        if schunk.empty:
            continue

        for sid, fig_ids in zip(schunk[sec_key], schunk["fig_ids"]):
            if pd.isna(sid):
                continue
            orig_ids = parse_ids(fig_ids)
            fig_list = []
            for oid in orig_ids:
                fid = orig2fig.get(str(oid).strip())
                if fid and fid not in fig_list:  # 순서 유지 + 중복 제거
                    fig_list.append(fid)
            section_map[sid] = ";".join(fig_list)

    return section_map


def process_chunks(chunk_csv: str, out_csv: str, section_map: dict, chunk_size: int, section_id_col: str):
    """chunk.csv를 chunksize로 읽어서 section_fig_ids 붙이고 바로 out_csv로 append 저장"""
    first = True
    for cchunk in pd.read_csv(
        chunk_csv,
        dtype={section_id_col: "string"},
        chunksize=chunk_size,
    ):
        cchunk[section_id_col] = cchunk[section_id_col].astype("string").str.strip()
        cchunk["section_fig_ids"] = cchunk[section_id_col].map(section_map)  # 없으면 NaN

        cchunk.to_csv(out_csv, mode="w" if first else "a", index=False, header=first)
        first = False


def main():
    parser = argparse.ArgumentParser(
        description="Attach fig_id list (section_fig_ids) to each chunk row by section_id, using batch/stream processing. Uses ONLY result/results sections."
    )
    parser.add_argument("--chunk_csv", required=True, help="Path to chunks.csv")
    parser.add_argument("--section_csv", required=True, help="Path to section_meta.csv (section metadata)")
    parser.add_argument("--fig_csv", required=True, help="Path to figure table CSV (figure table)")
    parser.add_argument("--out_csv", required=True, help="Output CSV path")

    parser.add_argument("--chunk_size", type=int, default=200_000, help="Chunksize for reading chunk CSV")
    parser.add_argument("--fig_chunk_size", type=int, default=200_000, help="Chunksize for reading fig CSV")
    parser.add_argument("--section_chunk_size", type=int, default=200_000, help="Chunksize for reading section CSV")

    parser.add_argument(
        "--section_key_candidates",
        default="section_id,id",
        help="Comma-separated candidate column names for section key in section_csv (default: section_id,id)",
    )
    parser.add_argument(
        "--chunk_section_col",
        default="section_id",
        help="Column name in chunk_csv that stores section id (default: section_id)",
    )

    # ✅ 추가: result 섹션 필터 설정
    parser.add_argument(
        "--section_category_col",
        default="section_category",
        help="Column name in section_csv for section category (default: section_category)",
    )
    parser.add_argument(
        "--allowed_section_categories",
        default="result,results",
        help="Comma-separated allowed categories (case-insensitive). default: result,results",
    )

    args = parser.parse_args()

    candidates = [c.strip() for c in args.section_key_candidates.split(",") if c.strip()]
    if not candidates:
        print("[ERR] section_key_candidates is empty", file=sys.stderr)
        sys.exit(1)

    allowed_categories = {c.strip().lower() for c in args.allowed_section_categories.split(",") if c.strip()}
    if not allowed_categories:
        print("[ERR] allowed_section_categories is empty", file=sys.stderr)
        sys.exit(1)

    print("[1/3] Building orig2fig (original_label_id -> fig_id) ...")
    orig2fig = build_orig2fig(args.fig_csv, args.fig_chunk_size)
    print(f"[OK] orig2fig size = {len(orig2fig):,}")

    print("[2/3] Building section_map (ONLY result/results sections) ...")
    sec_key = detect_section_key(args.section_csv, candidates)
    print(f"[INFO] Detected section key column: {sec_key}")
    print(f"[INFO] Filtering section_category in {sorted(allowed_categories)} (col={args.section_category_col})")

    section_map = build_section_map(
        section_csv=args.section_csv,
        sec_key=sec_key,
        orig2fig=orig2fig,
        section_chunk_size=args.section_chunk_size,
        section_category_col=args.section_category_col,
        allowed_categories=allowed_categories,
    )
    print(f"[OK] section_map size = {len(section_map):,}")

    print("[3/3] Processing chunks in batches and writing output ...")
    process_chunks(args.chunk_csv, args.out_csv, section_map, args.chunk_size, args.chunk_section_col)

    print(f"[DONE] saved -> {args.out_csv}")


if __name__ == "__main__":
    main()
