#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전처리 스크립트: sections.csv를 메타데이터와 청킹용 데이터로 분리

기능:
- 입력: sections.csv (메타정보 + 청킹할 텍스트 포함)
- 출력1: 메타데이터 CSV (메타정보만)
- 출력2: 청킹용 전처리 CSV (청킹에 필요한 컬럼만)
"""

import csv
import sys
from pathlib import Path
from tqdm import tqdm


def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = " ".join(s.split())
    return s


def combine_title_text(title: str, text: str) -> str:
    t = normalize_text(title)
    body = normalize_text(text)
    if not t:
        return body
    if not body:
        return t
    return f"{t}\n\n{body}"


def split_sections(input_csv, meta_out, chunk_prep_out):
    """
    sections.csv를 메타데이터와 청킹용 데이터로 분리
    
    Args:
        input_csv: 입력 sections.csv 경로
        meta_out: 메타데이터를 저장할 CSV 경로
        chunk_prep_out: 청킹용 전처리 데이터를 저장할 CSV 경로
    """
    input_path = Path(input_csv)
    meta_path = Path(meta_out)
    chunk_prep_path = Path(chunk_prep_out)
    
    if not input_path.exists():
        print(f"오류: 입력 파일이 없습니다: {input_path}")
        return False
    
    # 메타데이터 컬럼 정의
    meta_columns = [
        "section_id",
        "pmcid",
        "pmid",
        "topic_category",
        "path",
        "section_category",
        "article_category",
        "fig_ids",
        "table_ids",
        "ref_ids",
    ]
    
    # 청킹용 컬럼 정의 (청킹에 필요한 것들)
    chunk_prep_columns = [
        "section_id",
        "title",
        "text",
    ]
    
    try:
        # 입력 파일 행 개수 먼저 세기 (진행률 표시용)
        total_rows = 0
        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            total_rows = sum(1 for _ in reader)
        
        print(f"[INFO] 입력 파일에서 {total_rows}개 행 발견")
        
        # 파일 분리
        with input_path.open("r", encoding="utf-8-sig", newline="") as f_in:
            reader = csv.DictReader(f_in)
            
            # 메타데이터 파일 열기
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            f_meta = meta_path.open("w", encoding="utf-8-sig", newline="")
            writer_meta = csv.DictWriter(f_meta, fieldnames=meta_columns)
            writer_meta.writeheader()
            
            # 청킹용 파일 열기
            chunk_prep_path.parent.mkdir(parents=True, exist_ok=True)
            f_chunk = chunk_prep_path.open("w", encoding="utf-8-sig", newline="")
            writer_chunk = csv.DictWriter(f_chunk, fieldnames=chunk_prep_columns)
            writer_chunk.writeheader()
            
            # 진행률 표시 바
            pbar = tqdm(total=total_rows, desc="데이터 분리 중", unit="rows")
            
            try:
                for row in reader:
                    # 메타데이터 추출 (모든 행에 대해 메타는 저장)
                    meta_row = {col: row.get(col, "") for col in meta_columns}
                    writer_meta.writerow(meta_row)

                    # 청킹용 데이터: chunking.py의 combine/normalize 로직 사용
                    title = row.get("title", "")
                    body = row.get("text", "")
                    combined = combine_title_text(title, body)
                    combined_norm = normalize_text(combined)

                    # 길이가 100자 이하이면 청킹용 CSV에는 쓰지 않고 건너뜀
                    if combined_norm and len(combined_norm) > 70:
                        chunk_row = {
                            "section_id": row.get("section_id", ""),
                            "title": "",
                            "text": combined_norm,
                        }
                        writer_chunk.writerow(chunk_row)

                    pbar.update(1)
            finally:
                pbar.close()
                f_meta.close()
                f_chunk.close()
        
        print(f"[OK] 메타데이터 저장: {meta_path}")
        print(f"[OK] 청킹용 전처리 데이터 저장: {chunk_prep_path}")
        return True
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return False


def main():
    """
    커맨드라인 인터페이스
    
    사용법:
        python preprocess_split.py --input sections.csv --meta-out sections_meta.csv --chunk-out sections_for_chunk.csv
    """
    import argparse
    
    ap = argparse.ArgumentParser(
        description="sections.csv를 메타데이터와 청킹용 데이터로 분리",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python preprocess_split.py \\
    --input ./data/pmc_data/pmc_csv18/sections.csv \\
    --meta-out ./data/pmc_data/pmc_csv18/sections_meta.csv \\
    --chunk-out ./data/pmc_data/pmc_csv18/sections_for_chunk.csv
        """,
    )
    
    ap.add_argument("--input", required=True, help="입력 sections.csv 경로")
    ap.add_argument("--meta-out", required=True, help="메타데이터 CSV 출력 경로")
    ap.add_argument("--chunk-out", required=True, help="청킹용 데이터 CSV 출력 경로")
    
    args = ap.parse_args()
    
    print("[START] 전처리 시작...")
    success = split_sections(args.input, args.meta_out, args.chunk_out)
    
    if success:
        print("[DONE] 전처리 완료!")
        return 0
    else:
        print("[ERROR] 전처리 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
