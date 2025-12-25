# add_result_desc_markers_then_section_fallback_csv_only.py
# ---------------------------------------------------------
# 목적:
#   - PRIMARY: chunk.fig_ref_markers -> fig_label 추출 -> (pmid, fig_label)로 fig_id 매칭
#   - FALLBACK: PRIMARY 매칭이 0개면 section_id -> section_fig_ids(=fig_id 리스트)로 매핑
#   - fig_id별로 result_desc(설명 텍스트) + result_section_ids(검증용 섹션ID 목록) 생성
#   - figure.csv에 두 컬럼을 추가해 out_csv로 저장
#
# 특징:
#   - SQLite 사용 X
#   - 메모리 터짐 방지: edges를 bucket CSV로 분산 저장 후 bucket별로 집계
#   - result_desc / result_section_ids는 콤마(,)로 연결된 "한 줄" 형태
#
# 입력 요구:
#   - chunk_csv: section_id, text_chunk(또는 네 컬럼명), fig_ref_markers
#   - figure_csv: pmid, fig_label, fig_id
#   - sections_map_csv(선택): section_id, section_fig_ids  (fallback용)
#
# 사용 예:
#   python .../add_result_desc_markers_then_section_fallback_csv_only.py ^
#     --chunk_csv ./data/pmc_1000/chunks.csv ^
#     --figure_csv ./data/pmc_1000/t_figures.csv ^
#     --out_csv ./data/pmc_1000/t_figures_with_result_desc.csv ^
#     --sections_map_csv ./data/pmc_1000/chunk_with_section_fig_ids.csv ^
#     --chunk_section_col section_id ^
#     --chunk_text_col text_chunk ^
#     --chunk_marker_col fig_ref_markers ^
#     --sections_map_section_id_col section_id ^
#     --sections_map_section_fig_ids_col section_fig_ids ^
#     --pmid_col pmid ^
#     --fig_label_col fig_label ^
#     --fig_id_col fig_id ^
#     --chunk_size 100000 ^
#     --bucket_count 64

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

NA_STRINGS = {"na", "n/a", "nan", "null", "none", ""}


def safe_str(v) -> Optional[str]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip()
    if s.lower() in NA_STRINGS:
        return None
    return s


def normalize_spaces(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    # 줄바꿈/탭 포함 공백을 단일 공백으로
    return re.sub(r"\s+", " ", s).strip()


def stable_bucket(key: str, bucket_count: int) -> int:
    # 안정 해시 (python hash()는 세션마다 변할 수 있음)
    h = 5381
    for ch in key:
        h = ((h << 5) + h) + ord(ch)
    return h % bucket_count


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def extract_pmid_from_section_id(section_id: Optional[str]) -> Optional[str]:
    """
    예: '38598310_sec1' -> '38598310'
    예: '36779817_sec4_C11' -> '36779817'
    """
    s = safe_str(section_id)
    if not s:
        return None
    m = re.match(r"^(\d+)_", s)
    return m.group(1) if m else None


def split_ids(raw: Optional[str]) -> List[str]:
    s = safe_str(raw)
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


def split_marker_items(raw: Optional[str]) -> List[str]:
    s = safe_str(raw)
    if not s:
        return []
    s2 = s.strip()
    # 리스트 문자열 형태 대응: "['Fig. 1', 'Fig. 2']"
    if s2.startswith("[") and s2.endswith("]"):
        s2 = s2[1:-1]
    s2 = s2.replace('"', "").replace("'", "")
    parts = re.split(r"[;,|]\s*|\s{2,}", s2)
    return [p.strip() for p in parts if p.strip()]


def marker_to_figlabels(marker_text: str) -> List[str]:
    """
    marker_text에서 fig_label 후보를 뽑아 'fig1', 'fig2', 'figs1' 형태로 normalize
    - Fig. 2a / Figure 3 / fig S1 / F 4 등 대응
    - subpanel(a,b,...)은 무시하고 숫자만 사용
    """
    items = split_marker_items(marker_text)
    labels: List[str] = []

    for it in items:
        t = it.strip().lower()

        # fig/figure/f + (optional S) + number
        m = re.search(r"(fig(?:ure)?|f)\s*\.?\s*(s)?\s*(\d+)", t)
        if m:
            is_supp = m.group(2) is not None
            num = m.group(3)
            lab = f"figs{num}" if is_supp else f"fig{num}"
            if lab not in labels:
                labels.append(lab)
            continue

        # 's1' 축약
        m2 = re.fullmatch(r"s\s*(\d+)", t.replace(".", "").replace(" ", ""))
        if m2:
            lab = f"figs{m2.group(1)}"
            if lab not in labels:
                labels.append(lab)
            continue

        # 이미 fig1/figs1
        t2 = t.replace(".", "")
        m3 = re.search(r"\bfigs?\d+\b", t2)
        if m3:
            lab = m3.group(0).lower()
            if lab not in labels:
                labels.append(lab)

    return labels


def build_pmid_figlabel_to_figid(
    figure_csv: str,
    pmid_col: str,
    fig_label_col: str,
    fig_id_col: str,
    chunksize: int = 200_000,
) -> Dict[Tuple[str, str], str]:
    head = pd.read_csv(figure_csv, nrows=5)
    for c in [pmid_col, fig_label_col, fig_id_col]:
        if c not in head.columns:
            raise ValueError(f"figure_csv missing '{c}'. actual={list(head.columns)}")

    mapping: Dict[Tuple[str, str], str] = {}
    for fchunk in pd.read_csv(
        figure_csv, usecols=[pmid_col, fig_label_col, fig_id_col], dtype="string", chunksize=chunksize
    ):
        for pmid, flab, fid in zip(fchunk[pmid_col], fchunk[fig_label_col], fchunk[fig_id_col]):
            pmid_s = safe_str(pmid)
            fid_s = safe_str(fid)
            flab_s = safe_str(flab)
            if not pmid_s or not fid_s or not flab_s:
                continue
            mapping[(pmid_s, flab_s.lower())] = fid_s
    return mapping


def build_section_to_figids_from_sections_map_csv(
    sections_map_csv: str,
    section_id_col: str,
    section_fig_ids_col: str,
    chunksize: int = 200_000,
) -> Dict[str, List[str]]:
    """
    sections_map_csv(예: chunk_with_section_fig_ids.csv)에서
    section_id -> [fig_id...] 만들기
    """
    head = pd.read_csv(sections_map_csv, nrows=5)
    for c in [section_id_col, section_fig_ids_col]:
        if c not in head.columns:
            raise ValueError(f"sections_map_csv missing '{c}'. actual={list(head.columns)}")

    m: Dict[str, List[str]] = {}
    for schunk in pd.read_csv(
        sections_map_csv, usecols=[section_id_col, section_fig_ids_col], dtype="string", chunksize=chunksize
    ):
        for sid, figlist in zip(schunk[section_id_col], schunk[section_fig_ids_col]):
            sid_s = safe_str(sid)
            if not sid_s:
                continue
            figs = split_ids(figlist)
            if figs:
                m[sid_s] = figs
    return m


def main():
    ap = argparse.ArgumentParser(
        description="PRIMARY: fig_ref_markers->fig_label->(pmid,fig_label)->fig_id; FALLBACK: section_id->section_fig_ids. CSV-only, bucketed aggregation."
    )
    ap.add_argument("--chunk_csv", required=True, help="chunks.csv (must contain section_id, text_chunk, fig_ref_markers)")
    ap.add_argument("--figure_csv", required=True, help="t_figures.csv (must contain pmid, fig_label, fig_id)")
    ap.add_argument("--out_csv", required=True, help="output figure csv with result_desc/result_section_ids columns")

    # fallback mapping source
    ap.add_argument("--sections_map_csv", default="", help="(Optional) chunk_with_section_fig_ids.csv for fallback section_id->section_fig_ids")
    ap.add_argument("--sections_map_section_id_col", default="section_id")
    ap.add_argument("--sections_map_section_fig_ids_col", default="section_fig_ids")

    # chunk cols
    ap.add_argument("--chunk_section_col", default="section_id")
    ap.add_argument("--chunk_text_col", default="text_chunk")
    ap.add_argument("--chunk_marker_col", default="fig_ref_markers")

    # figure cols
    ap.add_argument("--pmid_col", default="pmid")
    ap.add_argument("--fig_label_col", default="fig_label")
    ap.add_argument("--fig_id_col", default="fig_id")

    # batching/buckets
    ap.add_argument("--chunk_size", type=int, default=200_000)
    ap.add_argument("--fig_chunk_size", type=int, default=200_000)
    ap.add_argument("--bucket_count", type=int, default=64)
    ap.add_argument("--tmp_dir", default="")
    ap.add_argument("--keep_tmp", action="store_true")
    ap.add_argument("--max_texts_per_fig", type=int, default=50)

    args = ap.parse_args()

    out_path = Path(args.out_csv)
    tmp_dir = Path(args.tmp_dir) if args.tmp_dir.strip() else out_path.parent / (out_path.stem + "_tmp_buckets")
    ensure_dir(tmp_dir)
    print(f"[INFO] tmp_dir={tmp_dir} bucket_count={args.bucket_count}")

    # 1) PRIMARY 매핑: (pmid, fig_label)->fig_id
    print("[1/5] Building (pmid, fig_label)->fig_id map ...")
    pmid_figlab_to_fid = build_pmid_figlabel_to_figid(
        args.figure_csv, args.pmid_col, args.fig_label_col, args.fig_id_col, chunksize=args.fig_chunk_size
    )
    print(f"[OK] primary map size = {len(pmid_figlab_to_fid):,}")

    # 2) FALLBACK 매핑: section_id -> [fig_id...]
    section_to_figids: Dict[str, List[str]] = {}
    if args.sections_map_csv.strip():
        print("[2/5] Building fallback section_id->fig_ids map from sections_map_csv ...")
        section_to_figids = build_section_to_figids_from_sections_map_csv(
            args.sections_map_csv,
            args.sections_map_section_id_col,
            args.sections_map_section_fig_ids_col,
            chunksize=200_000,
        )
        print(f"[OK] fallback map size = {len(section_to_figids):,}")
    else:
        print("[2/5] No sections_map_csv provided. Fallback disabled.")

    # 3) bucket edges writer 준비 (fig_id, section_id, chunk_text)
    print("[3/5] Preparing bucket edge files ...")
    bucket_paths = [tmp_dir / f"edges_bucket_{i:03d}.csv" for i in range(args.bucket_count)]
    bucket_files = [open(p, "w", newline="", encoding="utf-8") for p in bucket_paths]
    bucket_writers = [csv.writer(f) for f in bucket_files]
    for w in bucket_writers:
        w.writerow([args.fig_id_col, args.chunk_section_col, "chunk_text"])

    # 4) chunk 스트리밍: PRIMARY 시도 -> 실패하면 FALLBACK
    print("[4/5] Streaming chunks -> edges (primary then fallback) ...")
    head = pd.read_csv(args.chunk_csv, nrows=5)
    for c in [args.chunk_section_col, args.chunk_text_col, args.chunk_marker_col]:
        if c not in head.columns:
            raise ValueError(f"chunk_csv missing '{c}'. actual={list(head.columns)}")

    written_edges = 0
    processed_rows = 0
    usecols = [args.chunk_section_col, args.chunk_text_col, args.chunk_marker_col]

    for cchunk in pd.read_csv(args.chunk_csv, usecols=usecols, dtype="string", chunksize=args.chunk_size):
        processed_rows += len(cchunk)

        for sec_id, txt, markers in zip(
            cchunk[args.chunk_section_col],
            cchunk[args.chunk_text_col],
            cchunk[args.chunk_marker_col],
        ):
            sec_id_s = safe_str(sec_id)
            if not sec_id_s:
                continue

            txt_s = normalize_spaces(safe_str(txt))
            if txt_s is None:
                continue

            pmid = extract_pmid_from_section_id(sec_id_s)

            # ---- PRIMARY
            matched_fig_ids: List[str] = []
            markers_s = safe_str(markers)
            if pmid and markers_s:
                figlabels = marker_to_figlabels(markers_s)
                if figlabels:
                    for flab in figlabels:
                        fid = pmid_figlab_to_fid.get((pmid, flab))
                        if fid and fid not in matched_fig_ids:
                            matched_fig_ids.append(fid)

            if matched_fig_ids:
                for fid in matched_fig_ids:
                    b = stable_bucket(fid, args.bucket_count)
                    bucket_writers[b].writerow([fid, sec_id_s, txt_s])
                    written_edges += 1
                continue  # primary 성공이면 fallback 안 함

            # ---- FALLBACK: section_id 기준으로 섹션에 속한 fig_id들에 붙이기
            if section_to_figids:
                figs = section_to_figids.get(sec_id_s, [])
                if figs:
                    for fid in figs:
                        b = stable_bucket(fid, args.bucket_count)
                        bucket_writers[b].writerow([fid, sec_id_s, txt_s])
                        written_edges += 1

    for f in bucket_files:
        f.close()

    print(f"[OK] processed chunk rows = {processed_rows:,}, written edges = {written_edges:,}")

    # 5) bucket 집계 -> desc_map.csv(fig_id, result_desc, result_section_ids) -> figure_csv에 merge
    print("[5/5] Aggregating buckets -> writing out_csv ...")
    desc_map_path = tmp_dir / "desc_map.csv"
    with open(desc_map_path, "w", newline="", encoding="utf-8") as out_f:
        w = csv.writer(out_f)
        w.writerow([args.fig_id_col, "result_desc", "result_section_ids"])

        for i, bp in enumerate(bucket_paths):
            if not bp.exists() or bp.stat().st_size == 0:
                continue

            agg_text: Dict[str, List[str]] = {}
            agg_secs: Dict[str, List[str]] = {}

            with open(bp, "r", newline="", encoding="utf-8") as f:
                r = csv.reader(f)
                _ = next(r, None)  # header
                for row in r:
                    if len(row) < 3:
                        continue
                    fid = safe_str(row[0])
                    sid = safe_str(row[1])
                    t = safe_str(row[2])
                    if not fid or t is None:
                        continue

                    # 텍스트 누적(연속 중복 방지 + 최대 개수 제한)
                    lst = agg_text.setdefault(fid, [])
                    if lst and lst[-1] == t:
                        pass
                    else:
                        if len(lst) < args.max_texts_per_fig:
                            lst.append(t)

                    # 섹션ID 누적(중복 제거)
                    if sid:
                        slst = agg_secs.setdefault(fid, [])
                        if sid not in slst:
                            slst.append(sid)

            # bucket 결과 출력: 콤마로 연결(한 줄)
            for fid in sorted(agg_text.keys()):
                desc = ",".join(agg_text.get(fid, []))
                secs = ",".join(agg_secs.get(fid, []))
                w.writerow([fid, desc, secs])

            if (i + 1) % 10 == 0:
                print(f"  - aggregated buckets: {i+1}/{args.bucket_count}")

    # desc_map 로드(figure 수 수준)
    desc_df = pd.read_csv(desc_map_path, dtype="string")
    desc_dict = dict(zip(desc_df[args.fig_id_col].astype("string"), desc_df["result_desc"].astype("string")))
    sec_dict = dict(zip(desc_df[args.fig_id_col].astype("string"), desc_df["result_section_ids"].astype("string")))

    first = True
    for fchunk in pd.read_csv(args.figure_csv, dtype="string", chunksize=args.fig_chunk_size):
        fchunk[args.fig_id_col] = fchunk[args.fig_id_col].astype("string")
        fchunk["result_desc"] = fchunk[args.fig_id_col].map(desc_dict)
        fchunk["result_section_ids"] = fchunk[args.fig_id_col].map(sec_dict)
        fchunk.to_csv(args.out_csv, mode="w" if first else "a", index=False, header=first)
        first = False

    print(f"[DONE] saved -> {args.out_csv}")

    if not args.keep_tmp:
        for bp in bucket_paths:
            try:
                bp.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            desc_map_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            tmp_dir.rmdir()
        except Exception:
            pass


if __name__ == "__main__":
    main()
