# pmc_json_to_csv_main.py

import argparse
import csv
import json
import os
from typing import Any, Dict, List

from sympy import re

from pmc_processing_utils import (
    clean_content, normalize_reference_spacing, normalize_title_spacing,
    annotate_section_categories,
    iter_articles,
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
        pmid = str(art.get("pmid") or "0") 
        topic_category = art.get("topic_category")
        doi = art.get("doi")

        # 섹션 분류
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
            "abstract": clean_content(art.get("abstract")),
            "n_sections": len(sections),
            "n_equations": len(equations),
            "n_figures": len(figures),
            "n_tables": len(tables),
            "n_references": len(refs),
        })

        # ------------------------------------------------
        # 2. Sections CSV
        # 조건: 텍스트 길이가 70자 이하이면 제외
        # ------------------------------------------------
        
        # (1) Abstract 처리
        abstract_text = art.get("abstract")
        if abstract_text:
            abstract_clean = clean_content(abstract_text)
            
            # [수정됨] 텍스트가 있고, 길이가 70자를 초과하는 경우에만 추가
            if abstract_clean and len(abstract_clean) > 70:
                abs_sec_id = f"{pmid}_sec0"
                section_rows.append({
                    "section_id": abs_sec_id,  
                    "pmid": pmid,
                    "topic_category": topic_category,
                    "section_title": "Abstract",
                    "section_text": abstract_clean,
                    "path": "abstract",
                    "section_category": "abstract",
                    "article_category": art.get("article_category"),
                    "fig_ids": "",
                    "table_ids": "",
                })

        # (2) 본문 섹션 처리
        for idx, sec in enumerate(sections):
            text_clean = clean_content(sec.get("text"))

            # [수정됨] 텍스트가 비어있거나, 길이가 70자 이하이면 건너뜀 (행 삭제)
            if not text_clean or len(text_clean) <= 70:
                continue

            # ID 생성 (원본 인덱스 유지하여 추적 용이하게 함)
            curr_sec_id = f"{pmid}_sec{idx + 1}"

            # [수정됨] Path 처리: 기존 유틸리티(clean/normalize) + 번호 제거 정규식 결합
            raw_path = sec.get("path") or []
            if isinstance(raw_path, list):
                cleaned_path_list = []
                for p in raw_path:
                    # 1단계: 기존 텍스트/타이틀 정제 로직 사용 (HTML 제거, 공백 정리)
                    temp_p = normalize_title_spacing(clean_content(p))
                    
                    # 2단계: 맨 앞의 섹션 번호 제거 (예: "4. Materials" -> "Materials")
                    # ^[\d\.]+\s* : 시작 부분의 숫자와 점, 그리고 뒤따르는 공백 제거
                    cleaned_item = re.sub(r'^[\d\.]+\s*', '', temp_p).strip()
                    
                    if cleaned_item:
                        cleaned_path_list.append(cleaned_item)
                
                path_str = " > ".join(cleaned_path_list)
            else:
                # 리스트가 아닌 경우에도 동일한 정제 로직 적용
                temp_p = normalize_title_spacing(clean_content(str(raw_path or "")))
                path_str = re.sub(r'^[\d\.]+\s*', '', temp_p).strip()

            fig_ids = []
            table_ids = []
            fig_info = sec.get("figure_info") or {}
            if isinstance(fig_info, dict):
                if isinstance(fig_info.get("fig_ids"), list):
                    fig_ids = [str(x) for x in fig_info.get("fig_ids")]
                if isinstance(fig_info.get("table_ids"), list):
                    table_ids = [str(x) for x in fig_info.get("table_ids")]

            raw_title = sec.get("title")
            title_clean = normalize_title_spacing(clean_content(raw_title))

            section_rows.append({
                "section_id": curr_sec_id,  
                "pmid": pmid,
                "topic_category": topic_category,
                "section_title": title_clean,
                "section_text": text_clean,
                "path": path_str,
                "section_category": sec.get("section_category"),
                "article_category": art.get("article_category"),
                "fig_ids": ";".join(fig_ids),
                "table_ids": ";".join(table_ids),
            })

        # ------------------------------------------------
        # 3. Equations CSV
        # ------------------------------------------------
        for idx, eq in enumerate(equations):
            eq_id = f"{pmid}_eq{idx + 1}"
            latex = eq.get("latex") or eq.get("text")
            is_display = eq.get("display", False)
            image_url = eq.get("image_url") or eq.get("url") or ""

            equation_rows.append({
                "equation_id": eq_id,
                "pmid": pmid,
                "equation_index": idx,
                "display": is_display,
                "equation_rep": clean_content(latex),
                "equation_img": image_url,
            })

        # ------------------------------------------------
        # 4. Figures CSV
        # ------------------------------------------------
        for idx, fig in enumerate(figures):
            fig_unique_id = f"{pmid}_fig{idx + 1}"
            if isinstance(fig, dict):
                urls = fig.get("urls") or []
                urls_str = ";".join(urls) if isinstance(urls, list) else str(urls)
                figure_rows.append({
                    "fig_id": fig_unique_id,
                    "pmid": pmid,
                    "original_label_id": fig.get("fig_id") or fig.get("id"),
                    "fig_label": normalize_title_spacing(clean_content(fig.get("label"))),
                    "fig_caption": normalize_title_spacing(clean_content(fig.get("caption"))),
                    "fig_url": urls_str,
                })
            else:
                figure_rows.append({
                    "fig_id": fig_unique_id,
                    "pmid": pmid,
                    "original_label_id": None,
                    "fig_label": None,
                    "fig_caption": normalize_title_spacing(clean_content(str(fig))),
                    "fig_url": "",
                })

        # ------------------------------------------------
        # 5. Tables CSV
        # ------------------------------------------------
        for idx, tbl in enumerate(tables):
            tbl_unique_id = f"{pmid}_tbl{idx + 1}"
            if isinstance(tbl, dict):
                table_url = tbl.get("binary_url") or tbl.get("url") or tbl.get("href")
                table_rows.append({
                    "table_id": tbl_unique_id,
                    "pmid": pmid,
                    "table_index": idx,
                    "original_label_id": tbl.get("table_id") or tbl.get("id"),
                    "table_label": normalize_title_spacing(clean_content(tbl.get("label"))),
                    "table_caption": normalize_title_spacing(clean_content(tbl.get("caption"))),
                    "table_url": table_url,
                })
            else:
                table_rows.append({
                    "table_id": tbl_unique_id,
                    "pmid": pmid,
                    "table_index": idx,
                    "original_label_id": None,
                    "table_label": None,
                    "table_caption": normalize_title_spacing(clean_content(str(tbl))),
                    "table_url": "",
                })

        # ------------------------------------------------
        # 6. References CSV
        # ------------------------------------------------
        for idx, ref in enumerate(refs):
            ref_idx_1based = idx + 1
            ref_unique_id = f"{pmid}_ref{ref_idx_1based}"
            if isinstance(ref, dict):
                ref_url = ref.get("url")
                if not ref_url:
                    urls = ref.get("urls") or []
                    if isinstance(urls, list) and urls:
                        ref_url = urls[0]
                raw_title = ref.get("title")
                raw_journal = ref.get("journal")
                title_clean = normalize_reference_spacing(clean_content(raw_title))
                journal_clean = normalize_reference_spacing(clean_content(raw_journal))

                reference_rows.append({
                    "ref_id": ref_unique_id,
                    "pmid": pmid,
                    "ref_index": ref_idx_1based,
                    "ref_title": title_clean,
                    "ref_journal": journal_clean,
                    "ref_year": ref.get("year"),
                    "ref_doi": ref.get("doi"),
                    "ref_pmid": ref.get("pmid"),
                    "ref_url": ref_url,
                })
            else:
                reference_rows.append({
                    "ref_id": ref_unique_id,
                    "pmid": pmid,
                    "ref_index": ref_idx_1based,
                    "ref_title": None,
                    "ref_journal": None,
                    "ref_year": None,
                    "ref_doi": None,
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
        "article_category", "abstract",
        "n_sections", "n_equations", "n_figures", "n_tables", "n_references"
    ], article_rows)

    # 2) Sections
    write_csv("sections.csv", [
        "section_id", "pmid", "topic_category", "section_title", "section_text", "path",
        "section_category", "article_category", "fig_ids", "table_ids", 
    ], section_rows)

    # 3) Equations
    write_csv("equations.csv", [
        "equation_id", "pmid", "equation_index", "display", "equation_rep", "equation_img"
    ], equation_rows)

    # 4) Figures
    write_csv("figures.csv", [
        "fig_id", "pmid", "original_label_id", "fig_label", "fig_caption", "fig_url"
    ], figure_rows)

    # 5) Tables
    write_csv("tables.csv", [
        "table_id", "pmid", "table_index", "original_label_id", "table_label", "table_caption", "table_url"
    ], table_rows)

    # 6) References
    write_csv("references.csv", [
        "ref_id", "pmid", "ref_index", "ref_title", "ref_journal",
        "ref_year", "ref_doi", "ref_pmid", "ref_url"
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