#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ts_meta_new.csv + ts_embedding_v2.csv + global_mention_master.csv 를
합쳐서 평가용 청크 테이블(eval_chunks_with_mentions.csv)을 만드는 스크립트.

- ts_meta_new.csv
    section_id, pmid, topic_category, path, ...

- ts_embedding_v2.csv (또는 동일 스키마의 벡터 CSV)
    chunk_id, section_id, chunk_seq, path,
    start_char, end_char, emb_model, emb_dim,
    text_chunk, embedding

- global_mention_master.csv
    mention_id, source, doc_id, location_id,
    raw_text, normalized_text, entity_id, entity_type, umls_cui, ...

출력: eval_chunks_with_mentions.csv
    chunk_id, section_id, pmid, topic_category, path,
    chunk_seq, start_char, end_char, emb_model, emb_dim,
    text_chunk, embedding,
    mention_ids, entity_ids, raw_mentions, norm_mentions
"""

import argparse
from pathlib import Path

import pandas as pd


# --------------------------------------------------------
# 1. 섹션 메타 + 청크(벡터) 병합
# --------------------------------------------------------
def load_chunk_base(ts_meta_path: Path, chunk_path: Path) -> pd.DataFrame:
    """ts_meta_new.csv + chunk_vector(csv)를 불러와 section_id 기준으로 merge."""
    print(f"📂 Loading section meta: {ts_meta_path}")
    ts_meta = pd.read_csv(ts_meta_path)

    print(f"📂 Loading chunk vectors: {chunk_path}")

    # 기본 C 엔진으로 먼저 시도
    try:
        chunks = pd.read_csv(chunk_path)
    except Exception as e:
        print("⚠️ 기본 C 엔진으로 읽기 실패, python 엔진 + on_bad_lines='warn' 로 재시도합니다.")
        print(f"   원래 에러: {type(e).__name__}: {e}")

        # CSV 내부에 깨진 라인(따옴표 안 닫힘 등)이 있어도 넘어가도록 설정
        chunks = pd.read_csv(
            chunk_path,
            engine="python",
            on_bad_lines="warn",  # 문제 있는 줄은 스킵 + 경고만 출력
        )

    # 필수 컬럼 체크
    for col in ["section_id"]:
        if col not in ts_meta.columns:
            raise ValueError(f"[ts_meta_new] '{col}' column missing.")
        if col not in chunks.columns:
            raise ValueError(f"[chunk_vector] '{col}' column missing.")

    # text 컬럼 이름 정리: text_chunk 가 기본, 없으면 *text* 포함 컬럼을 찾아서 text_chunk 로 rename
    if "text_chunk" not in chunks.columns:
        candidates = [c for c in chunks.columns if "text" in c.lower()]
        if not candidates:
            raise ValueError(
                "[chunk_vector] 'text_chunk' column not found and no *text* candidate column."
            )
        print(f"ℹ️ 'text_chunk' column not found, use '{candidates[0]}' instead.")
        chunks = chunks.rename(columns={candidates[0]: "text_chunk"})

    # section_id 기준 inner join (섹션 메타 + 해당 섹션의 모든 chunk)
    base = ts_meta.merge(chunks, on="section_id", how="inner")
    print(f"✅ Chunk base merged: {len(base)} rows")

    return base


# --------------------------------------------------------
# 2. mention 정보 aggregation (논문만 사용)
# --------------------------------------------------------
def aggregate_mentions(mention_path: Path, source_filter: str = "paper") -> pd.DataFrame:
    """global_mention_master.csv 를 읽어 section_id 단위로 엔티티/멘션을 집계."""
    print(f"📂 Loading global mention master: {mention_path}")
    mentions = pd.read_csv(mention_path)

    # 기본 컬럼 체크
    required_cols = [
        "mention_id",
        "source",
        "location_id",
        "raw_text",
        "normalized_text",
        "entity_id",
    ]
    for col in required_cols:
        if col not in mentions.columns:
            raise ValueError(f"[global_mention_master] '{col}' column missing.")

    # paper / clinical 등 필터링
    if source_filter is not None:
        before = len(mentions)
        mentions = mentions[mentions["source"] == source_filter].copy()
        print(f"🔎 Filter source == '{source_filter}': {before} -> {len(mentions)} rows")

    if mentions.empty:
        print("⚠️ Mention rows are empty after filtering. Only chunk base will be used.")
        # 빈 DF 반환 (merge 시 모든 mention_* 컬럼이 NaN)
        return pd.DataFrame(
            columns=[
                "section_id",
                "mention_ids",
                "entity_ids",
                "raw_mentions",
                "norm_mentions",
            ]
        )

    # location_id == section_id 로 매핑
    mentions["section_id"] = mentions["location_id"].astype(str)

    def agg_fn(df: pd.DataFrame) -> pd.Series:
        # 유니크 값만 모아서 join
        mention_ids = "|".join(sorted(df["mention_id"].astype(str).unique()))
        # entity_id가 NaN일 수 있음
        entity_ids = "|".join(
            sorted(df["entity_id"].dropna().astype(str).unique())
        )

        raw_mentions = " || ".join(
            sorted(set(df["raw_text"].dropna().astype(str)))
        )
        norm_mentions = " || ".join(
            sorted(set(df["normalized_text"].dropna().astype(str)))
        )

        return pd.Series(
            {
                "mention_ids": mention_ids,
                "entity_ids": entity_ids,
                "raw_mentions": raw_mentions,
                "norm_mentions": norm_mentions,
            }
        )

    agg = (
        mentions.groupby("section_id")
        .apply(agg_fn)
        .reset_index()
    )

    print(f"✅ Aggregated mention info per section: {len(agg)} rows")
    return agg


# --------------------------------------------------------
# 3. 최종 eval_chunks DataFrame 생성
# --------------------------------------------------------
def build_eval_chunks(
    ts_meta_path: Path,
    chunk_path: Path,
    mention_path: Path,
    source_filter: str = "paper",
) -> pd.DataFrame:
    """섹션 메타 + 청크 + 멘션 정보를 합쳐 최종 평가용 chunk 테이블을 만든다."""
    # 섹션 메타 + 청크 정보
    base = load_chunk_base(ts_meta_path, chunk_path)
    # 섹션 단위 mention aggregation
    mention_agg = aggregate_mentions(mention_path, source_filter=source_filter)

    # section_id 기준 left join (멘션이 없는 섹션도 유지)
    eval_df = base.merge(mention_agg, on="section_id", how="left")

    # NaN → 빈 문자열로 치환
    for col in ["mention_ids", "entity_ids", "raw_mentions", "norm_mentions"]:
        if col in eval_df.columns:
            eval_df[col] = eval_df[col].fillna("")

    # 컬럼 정리 (존재하는 것만 사용)
    wanted_cols = [
        "chunk_id",
        "section_id",
        "pmid",
        "topic_category",
        "path",        # ts_meta의 path + chunk의 path가 둘 다 있으면 하나가 덮어씀
        "chunk_seq",
        "start_char",
        "end_char",
        "emb_model",
        "emb_dim",
        "text_chunk",
        "embedding",
        "mention_ids",
        "entity_ids",
        "raw_mentions",
        "norm_mentions",
    ]
    existing_cols = [c for c in wanted_cols if c in eval_df.columns]
    eval_df = eval_df[existing_cols].copy()

    print(f"✅ Final eval_chunks shape: {eval_df.shape}")
    return eval_df


# --------------------------------------------------------
# 4. CLI entrypoint
# --------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build evaluation chunk table from ts_meta_new, ts_embedding_v2 "
            "and global_mention_master."
        )
    )
    parser.add_argument(
        "--ts-meta",
        type=Path,
        default=Path("ts_meta_new.csv"),
        help="Path to ts_meta_new.csv",
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("ts_embedding_v2.csv"),
        help="Path to chunk vector CSV (chunk_id, section_id, text_chunk, embedding, ...)",
    )
    parser.add_argument(
        "--mentions",
        type=Path,
        default=Path("global_mention_master.csv"),
        help="Path to global_mention_master.csv",
    )
    parser.add_argument(
        "--source-filter",
        type=str,
        default="paper",
        help="Filter mentions by source column "
             "(e.g., 'paper', 'clinical', or '' for no filter).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval_chunks_with_mentions.csv"),
        help="Output CSV path.",
    )

    args = parser.parse_args()

    # 빈 문자열이면 필터링 안 함
    source_filter = args.source_filter if args.source_filter else None

    eval_df = build_eval_chunks(
        ts_meta_path=args.ts_meta,
        chunk_path=args.chunks,
        mention_path=args.mentions,
        source_filter=source_filter,
    )

    # 저장
    args.output.parent.mkdir(parents=True, exist_ok=True)
    eval_df.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"💾 Saved: {args.output}")
    print("\n🔍 Sample rows:")
    print(eval_df.head())


if __name__ == "__main__":
    main()
