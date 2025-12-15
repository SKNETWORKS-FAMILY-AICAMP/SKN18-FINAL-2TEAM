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
    # 작은따옴표 문자열 내에서 작은따옴표를 올바르게 이스케이프
    df = df.replace(r'^\s*[""\'\u201C\u201D\u2018\u2019]*\s*$', "", regex=True)
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


def load_existing_urls(csv_path: Path) -> set[str]:
    """
    기존 cleaned 파일에서 URL만 읽어서 Set으로 반환 (메모리 효율적).
    
    주의사항: 대용량 파일을 위해 chunksize로 청크 단위로 읽어서 메모리 사용량 제한.
    
    Args:
        csv_path: 기존 cleaned CSV 파일 경로
    
    Returns:
        기존 URL들의 Set (파일이 없거나 비어있으면 빈 Set)
    """
    if not csv_path.exists():
        return set()
    
    existing_urls = set()
    try:
        # chunksize로 청크 단위로 읽어서 메모리 사용량 제한
        # usecols로 URL 컬럼만 읽어서 메모리 절약
        for chunk in pd.read_csv(csv_path, chunksize=1000, usecols=["url"]):
            # URL 컬럼이 있는 경우만 처리
            if "url" in chunk.columns:
                existing_urls.update(
                    chunk["url"].dropna().astype(str).str.strip()
                )
        print(
            f"[NORMALIZE] 기존 파일에서 {len(existing_urls)}개 URL 로드 완료",
            flush=True,
        )
    except Exception as e:
        print(
            f"[NORMALIZE] 기존 파일 URL 로드 실패: {e}. 빈 Set으로 시작합니다.",
            flush=True,
        )
    
    return existing_urls


def process_file(csv_path: Path) -> None:
    """
    Incremental 처리 방식으로 raw CSV 파일을 cleaned CSV로 변환.
    
    주의사항:
    1. 기존 파일이 있으면 URL Set만 로드하여 메모리 효율성 확보
    2. 새 데이터만 필터링하여 처리 시간 단축
    3. 병합 후 중복 제거로 안전장치 제공
    """
    # 파일명에서 키워드 추출: api_data_{keyword}.csv
    keyword = csv_path.stem.replace("api_data_", "")
    status = "success"
    
    try:
        out_path = build_output_path(keyword, status)
        
        # 1. 기존 cleaned 파일에서 URL Set만 로드 (메모리 효율적)
        existing_urls = load_existing_urls(out_path)
        
        # 2. 새 raw 데이터 읽기
        new_df = pd.read_csv(csv_path)
        total_rows = len(new_df)
        
        # 3. 중복 제거: 기존에 없는 URL만 필터링
        new_df_filtered = new_df[
            ~new_df["url"].astype(str).str.strip().isin(existing_urls)
        ]
        
        if len(new_df_filtered) == 0:
            print(
                f"[NORMALIZE][Protocol.io][{keyword}] 새 데이터 없음 "
                f"(전체 {total_rows}개 모두 중복)",
                flush=True,
            )
            return
        
        duplicate_count = total_rows - len(new_df_filtered)
        print(
            f"[NORMALIZE][Protocol.io][{keyword}] 새 데이터 {len(new_df_filtered)}개 "
            f"(전체 {total_rows}개, 중복 {duplicate_count}개)",
            flush=True,
        )
        
        # 4. 새 데이터 정규화
        normalized_new = normalize_dataframe(new_df_filtered)
        
        # 5. 기존 데이터와 병합 (메모리 효율적으로 처리)
        if out_path.exists() and len(existing_urls) > 0:
            # 기존 파일이 있으면 읽어서 병합
            try:
                existing_df = pd.read_csv(out_path)
                # 병합
                combined_df = pd.concat([existing_df, normalized_new], ignore_index=True)
                # 안전장치: URL 기반 중복 제거 (병합 과정에서 중복 발생 가능)
                before_dedup = len(combined_df)
                combined_df = combined_df.drop_duplicates(subset="url", keep="first")
                after_dedup = len(combined_df)
                
                if before_dedup != after_dedup:
                    print(
                        f"[NORMALIZE][Protocol.io][{keyword}] 병합 후 중복 제거: "
                        f"{before_dedup}개 → {after_dedup}개",
                        flush=True,
                    )
            except Exception as e:
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] 기존 파일 읽기 실패: {e}. "
                    f"새 데이터만 저장합니다.",
                    flush=True,
                )
                combined_df = normalized_new
        else:
            # 기존 파일이 없으면 새 데이터만 저장
            combined_df = normalized_new
        
        # 6. 저장
        combined_df.to_csv(out_path, index=False)
        print(
            f"[NORMALIZE][Protocol.io][{keyword}] 저장 완료: 총 {len(combined_df)}개 "
            f"(기존 {len(existing_urls)}개 + 새 {len(normalized_new)}개)",
            flush=True,
        )
        
    except Exception as exc:
        status = "fail"
        out_path = build_output_path(keyword, status)
        df = pd.DataFrame([{"error": str(exc)}])
        df.to_csv(out_path, index=False)
        print(f"[NORMALIZE][Protocol.io][{keyword}] 실패: {exc}", flush=True)


def run(raw_dir: str, processed_dir: str) -> None:
    """
    Pipeline runner에서 호출되는 함수.
    
    Args:
        raw_dir: raw 데이터 디렉토리
        processed_dir: processed 데이터 저장 디렉토리
    """
    global RAW_DIR, OUTPUT_ROOT
    RAW_DIR = Path(raw_dir) / "protocols"  # protocols 서브디렉토리 추가
    OUTPUT_ROOT = Path(processed_dir) / "protocols"  # protocols 서브디렉토리 추가
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
