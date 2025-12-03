# pmc_json_to_csv_main.py

import argparse
import csv
import json
import os
from typing import Any, Dict, List

from pmc_processing_utils import (
    clean_content, normalize_reference_spacing, normalize_title_spacing,
    # extract_reference_markers, remove_reference_markers, <-- 제거됨
    gen_section_id,
    annotate_section_categories,
    iter_articles,
    # extract_figure_table_markers는 제거됨
)


def json_to_csv(input_json: str, out_dir: str) -> None:
    if not os.path.exists(input_json):
        print(f"[ERROR] Input file not found: {input_json}")
        return

    os.makedirs(out_dir, exist_ok=True)
    print(f"[INFO] Loading JSON from {input_json} ...")

    with open(input_json, encoding="utf-8") as f:
        obj = json.load(f)

    # 데이터 수집용 리스트
    article_rows: List[Dict[str, Any]] = []
    section_rows: List[Dict[str, Any]] = []
    equation_rows: List[Dict[str, Any]] = []
    figure_rows: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, Any]] = []
    reference_rows: List[Dict[str, Any]] = []

    count = 0
    for art in iter_articles(obj):
        count += 1
        pmcid = art.get("pmcid")
        pmid = art.get("pmid")
        topic_category = art.get("topic_category")
        doi = art.get("doi")

        # 섹션 분류 (Title/Path만 사용하므로 유지)
        if art.get("sections"):
            annotate_section_categories(art)

        sections = art.get("sections") or []
        equations = art.get("equations") or []
        figures = art.get("figure_captions") or []
        tables = art.get("table_captions") or []
        refs = art.get("references") or []

        # ------------------------------------------------
        # 1. Articles CSV
        # ------------------------------------------------
        article_rows.append({
            "pmcid": pmcid,
            "pmid": pmid,
            "topic_category": topic_category,
            "title": normalize_title_spacing(clean_content(art.get("title"))),
            "journal": clean_content(art.get("journal")),
            "year": art.get("year"),
            "doi": doi,
            "article_category": art.get("article_category"),
            "article_type_raw": art.get("article_type_raw"),
            "abstract": clean_content(art.get("abstract")), # RAW Abstract (only space cleaned)
            "n_sections": len(sections),
            "n_equations": len(equations),
            "n_figures": len(figures),
            "n_tables": len(tables),
            "n_references": len(refs),
        })

        # ------------------------------------------------
        # 2. Sections CSV (RAW 텍스트 저장 - 청크 단계로 이관)
        # ------------------------------------------------
        abstract_text = art.get("abstract")
        if abstract_text:
            abstract_clean = clean_content(abstract_text) # <- RAW 텍스트 (최소 공백 정리만)

            section_rows.append({
                "section_id": gen_section_id(),  
                "pmcid": pmcid,
                "pmid": pmid,
                "topic_category": topic_category,
                "title": "Abstract",
                "text": abstract_clean,              # RAW (마커 유지)
                "path": "abstract",
                "section_category": "abstract",
                "article_category": art.get("article_category"),
                "fig_ids": "",
                "table_ids": "",
                # "ref_ids"는 청크 단계로 이관되어 이 파일에서 저장하지 않음
            })

        for idx, sec in enumerate(sections):
            path = sec.get("path") or []
            path_str = " > ".join(path) if isinstance(path, list) else str(path or "")

            fig_ids = []
            table_ids = []
            fig_info = sec.get("figure_info") or {}
            if isinstance(fig_info, dict):
                if isinstance(fig_info.get("fig_ids"), list):
                    fig_ids = [str(x) for x in fig_info.get("fig_ids")]
                if isinstance(fig_info.get("table_ids"), list):
                    table_ids = [str(x) for x in fig_info.get("table_ids")]

            text_clean = clean_content(sec.get("text")) # <- RAW 텍스트 (최소 공백 정리만)

            raw_title = sec.get("title")
            title_clean = normalize_title_spacing(clean_content(raw_title))

            section_rows.append({
                "section_id": gen_section_id(),  
                "pmcid": pmcid,
                "pmid": pmid,
                "topic_category": topic_category,
                "title": title_clean,
                "text": text_clean,                  # RAW (마커 유지)
                "path": path_str,
                "section_category": sec.get("section_category"),
                "article_category": art.get("article_category"),
                "fig_ids": ";".join(fig_ids),
                "table_ids": ";".join(table_ids),
                # "ref_ids"는 청크 단계로 이관되어 이 파일에서 저장하지 않음
            })
        # ------------------------------------------------
        # 3. Equations CSV (Display & URL 추가)
        # ------------------------------------------------
        for idx, eq in enumerate(equations):
            latex = eq.get("latex") or eq.get("text")

            # display 정보
            is_display = eq.get("display", False)

            # image_url 처리
            image_url = eq.get("image_url") or eq.get("url") or ""

            equation_rows.append({
                "pmcid": pmcid,
                "pmid": pmid,
                "equation_index": idx,
                "display": is_display,
                "latex": clean_content(latex),
                "image_url": image_url,
            })

        # ------------------------------------------------
        # 4. Figures CSV
        # ------------------------------------------------
        for idx, fig in enumerate(figures):
            if isinstance(fig, dict):
                urls = fig.get("urls") or []
                urls_str = ";".join(urls) if isinstance(urls, list) else str(urls)

                # [수정됨] Figure Label/Caption에 normalize_title_spacing 적용
                figure_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "fig_ids": fig.get("fig_id") or fig.get("id"),
                    "fig_label": normalize_title_spacing(clean_content(fig.get("label"))),
                    "fig_caption": normalize_title_spacing(clean_content(fig.get("caption"))),
                    "fig_url": urls_str,
                })
            else:
                figure_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "fig_ids": None,
                    "fig_label": None,
                    "fig_caption": normalize_title_spacing(clean_content(str(fig))),
                    "fig_url": "",
                })

        # ------------------------------------------------
        # 5. Tables CSV
        # ------------------------------------------------
        for idx, tbl in enumerate(tables):
            if isinstance(tbl, dict):
                table_url = tbl.get("binary_url") or tbl.get("url") or tbl.get("href")

                # [수정됨] Table Label/Caption에 normalize_title_spacing 적용
                table_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "table_index": idx,
                    "table_ids": tbl.get("table_id") or tbl.get("id"),  # 숫자 table_id 우선
                    "table_label": normalize_title_spacing(clean_content(tbl.get("label"))),
                    "table_caption": normalize_title_spacing(clean_content(tbl.get("caption"))),
                    "table_url": table_url,
                })
            else:
                table_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "table_index": idx,
                    "table_ids": None,
                    "table_label": None,
                    "table_caption": normalize_title_spacing(clean_content(str(tbl))),
                    "table_url": "",
                })

        # ------------------------------------------------
        # 6. References CSV (ref_index: 1부터 시작)
        # ------------------------------------------------
        for idx, ref in enumerate(refs):
            ref_idx_1based = idx + 1
            if isinstance(ref, dict):
                # 대표 URL: JSON에 url이 있으면 그거, 없으면 urls[0] 시도
                ref_url = ref.get("url")
                if not ref_url:
                    urls = ref.get("urls") or []
                    if isinstance(urls, list) and urls:
                        ref_url = urls[0]

                # title / journal 공백 정리
                raw_title = ref.get("title")
                raw_journal = ref.get("journal")

                title_clean = normalize_reference_spacing(clean_content(raw_title))
                journal_clean = normalize_reference_spacing(clean_content(raw_journal))

                reference_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "ref_index": ref_idx_1based,
                    "title": title_clean,
                    "journal": journal_clean,
                    "year": ref.get("year"),
                    "doi": ref.get("doi"),
                    "ref_pmid": ref.get("pmid"),
                    "ref_url": ref_url,
                })
            else:
                reference_rows.append({
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "ref_index": ref_idx_1based,
                    "title": None,
                    "journal": None,
                    "year": None,
                    "doi": None,
                    "ref_pmid": None,
                    "ref_url": None,
                })



    # =========================
    #   CSV 파일 쓰기
    # =========================

    def write_csv(filename: str, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
        path = os.path.join(out_dir, filename)
        print(f"  -> Writing {filename} ({len(rows)} rows)")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    # 1) Articles
    write_csv("articles.csv", [
        "pmcid", "pmid", "topic_category", "title", "journal", "year", "doi",
        "article_category", "article_type_raw", "abstract",
        "n_sections", "n_equations", "n_figures", "n_tables", "n_references"
    ], article_rows)

    # 2) Sections
    write_csv("sections.csv", [
        "section_id", "pmcid", "pmid", "topic_category", "title", "text", "path",
        "section_category", "article_category", "fig_ids", "table_ids", 
        # ref_ids 컬럼 제거됨
    ], section_rows)

    # 3) Equations
    write_csv("equations.csv", [
        "pmcid", "pmid", "equation_index", "display", "latex", "image_url"
    ], equation_rows)

    # 4) Figures
    write_csv("figures.csv", [
        "pmcid", "pmid", "fig_ids", "fig_label", "fig_caption", "fig_url"
    ], figure_rows)

    # 5) Tables
    write_csv("tables.csv", [
        "pmcid", "pmid", "table_index", "table_ids", "table_label", "table_caption", "table_url"
    ], table_rows)

    # 6) References
    write_csv("references.csv", [
        "pmcid", "pmid", "ref_index", "title", "journal",
        "year", "doi", "ref_pmid", "ref_url"
    ], reference_rows)

    print(f"[DONE] Processing complete. Output saved to '{out_dir}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", help="pmc_api로 생성한 JSON 파일 경로")
    parser.add_argument(
        "--out_dir",
        default="csv_output",
        help="CSV를 저장할 디렉토리 (default: csv_output)",
    )
    args = parser.parse_args()

    json_to_csv(args.input_json, args.out_dir)