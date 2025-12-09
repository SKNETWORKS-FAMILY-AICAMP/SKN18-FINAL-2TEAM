"""
Protocols.io raw CSV → cleaned CSV.

입력: data/raw/protocols/yyyymmdd/api_data_{keyword}.csv
출력: data/processed/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=cleaned/protocol_cleaned_{keyword}.csv
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw/protocols")
OUTPUT_ROOT = Path("data/processed/protocols")


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # url 중복제거 후 테이블
    if "url" not in df.columns:
        raise ValueError("url 컬럼이 없습니다.")
    df = df.drop_duplicates(subset="url", keep="first").reset_index()
    df = df.rename(columns={"index": "protocol_id"})

    # title 중복제거 후 테이블
    if "title" not in df.columns:
        raise ValueError("title 컬럼이 없습니다.")
    df = df.drop_duplicates(subset="title", keep="first").reset_index()
    df = df.drop(columns=["index"])

    # 정규화 및 텍스트 치환
    df = df.replace(r'"+', '"', regex=True)
    df = df.replace(r"\n+", "\n", regex=True)
    df = df.replace("<no data>", "")
    # 따옴표만 있거나 공백만 있는 경우 빈 문자열로 변환
    df = df.replace(r"\\u[0-9a-fA-F]{4}", "", regex=True)
    df = df.replace(r'^\s*["“”\'’]*\s*$', "", regex=True)
    # NaN을 빈 문자열로 변경
    df = df.replace("NA", "")
    df = df.fillna("")
    # 공백만 있는 문자열을 빈 문자열로 변경
    df = df.applymap(lambda x: "" if isinstance(x, str) and x.strip() == "" else x)
    return df


def build_output_path(keyword: str, status: str) -> Path:
    now = datetime.now()
    parts = [
        OUTPUT_ROOT,
        status,
        f"year={now.year:04d}",
        f"month={now.month:02d}",
        f"day={now.day:02d}",
        "stage=cleaned",
        f"protocol_cleaned_{keyword}.csv",
    ]
    path = Path(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def process_file(csv_path: Path) -> None:
    # 파일명에서 키워드 추출: api_data_{keyword}.csv
    # 경로에서 날짜 디렉토리명도 제거해야 함
    keyword = csv_path.stem.replace("api_data_", "")
    status = "success"
    try:
        df = pd.read_csv(csv_path)
        df = normalize_dataframe(df)
    except Exception as exc:
        status = "fail"
        df = pd.DataFrame([{"error": str(exc)}])
        print(f"[NORMALIZE][Protocol.io][{keyword}] 실패: {exc}")
    else:
        print(
            f"[NORMALIZE][Protocol.io][{keyword}] cleaned rows={len(df)}",
            flush=True,
        )

    out_path = build_output_path(keyword, status)
    df.to_csv(out_path, index=False)
    print(f"[NORMALIZE][Protocol.io][{keyword}] 저장 완료: {out_path}")


def run(raw_dir: str, processed_dir: str) -> None:
    """
    Pipeline runner에서 호출되는 함수.
    
    Args:
        raw_dir: raw 데이터 디렉토리
        processed_dir: processed 데이터 저장 디렉토리
    """
    global RAW_DIR, OUTPUT_ROOT
    RAW_DIR = Path(raw_dir)
    OUTPUT_ROOT = Path(processed_dir)
    main()


def main() -> None:
    start_time = datetime.now()
    print(f"[NORMALIZE][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    # 날짜별 디렉토리 내의 모든 api_data_*.csv 파일 찾기
    csv_files = []
    for date_dir in sorted(RAW_DIR.glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]")):
        # 각 날짜 디렉토리 내의 api_data_*.csv 파일 찾기
        csv_files.extend(sorted(date_dir.glob("api_data_*.csv")))
    
    if not csv_files:
        print("[NORMALIZE][Protocol.io] 처리할 파일이 없습니다.")
        return

    for csv_path in csv_files:
        print(f"[NORMALIZE][Protocol.io] processing {csv_path}")
        process_file(csv_path)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[NORMALIZE][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


if __name__ == "__main__":
    main()
