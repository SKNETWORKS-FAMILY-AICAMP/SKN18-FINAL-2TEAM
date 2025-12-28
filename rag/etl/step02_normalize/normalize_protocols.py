"""
Protocols.io raw CSV → cleaned CSV.

입력: data/raw/protocols/yyyymmdd/api_data_{keyword}.csv
출력: data/processed/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=cleaned/protocol_cleaned_{keyword}.csv
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# 패키지 형태로 실행하지 않아도 rag.* 모듈을 찾을 수 있도록 루트 경로 추가
# Lambda 환경 감지
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Lambda 환경: /var/task가 루트
    PROJECT_ROOT = Path('/var/task')
else:
    # 로컬 환경: 기존 방식
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

# schedule_store는 is_completed 키워드 조회용으로 사용
from rag.etl.step01_ingest.modules import schedule_store

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
    
    중복 문제 방지를 위해:
    1. 기존 파일이 있으면 전체를 읽어서 정규화된 DataFrame으로 로드
    2. 새 raw 데이터를 정규화
    3. 두 DataFrame을 병합하고 URL 기반 중복 제거
    4. 기존 파일을 삭제하고 새로 저장 (중복 누적 방지)
    """
    # 파일명에서 키워드 추출: api_data_{keyword}.csv
    keyword = csv_path.stem.replace("api_data_", "")
    status = "success"
    
    try:
        out_path = build_output_path(keyword, status)
        
        # 1. 새 raw 데이터 읽기 및 정규화
        new_df = pd.read_csv(csv_path)
        total_rows = len(new_df)
        normalized_new = normalize_dataframe(new_df)
        
        # 2. 기존 cleaned 파일이 있으면 읽어서 처리
        existing_df = None
        if out_path.exists():
            try:
                existing_df = pd.read_csv(out_path)
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] 기존 파일에서 {len(existing_df)}개 데이터 로드",
                    flush=True,
                )
            except Exception as e:
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] 기존 파일 읽기 실패: {e}. "
                    f"새 데이터만 처리합니다.",
                    flush=True,
                )
                existing_df = None
        
        # 3. 기존 데이터와 새 데이터 병합
        if existing_df is not None:
            # 기존 데이터와 새 데이터 병합
            combined_df = pd.concat([existing_df, normalized_new], ignore_index=True)
            before_dedup = len(combined_df)
            
            # URL 기반 중복 제거 (keep='first'이므로 기존 데이터 우선)
            combined_df = combined_df.drop_duplicates(subset="url", keep="first")
            after_dedup = len(combined_df)
            
            removed_duplicates = before_dedup - after_dedup
            if removed_duplicates > 0:
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] 중복 제거: "
                    f"{before_dedup}개 → {after_dedup}개 (제거: {removed_duplicates}개)",
                    flush=True,
                )
        else:
            # 기존 파일이 없으면 새 데이터만 사용
            combined_df = normalized_new
            after_dedup = len(combined_df)
        
        # 4. protocol_id 재생성 (0부터 시작하는 고유 ID로 재설정)
        combined_df = combined_df.reset_index(drop=True)
        combined_df['protocol_id'] = combined_df.index
        
        # 4. 기존 파일 삭제 (중복 누적 방지)
        if out_path.exists():
            try:
                out_path.unlink()
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] 기존 파일 삭제 완료 (중복 누적 방지)",
                    flush=True,
                )
            except Exception as e:
                print(
                    f"[NORMALIZE][Protocol.io][{keyword}] ⚠️  기존 파일 삭제 실패: {e}",
                    flush=True,
                )
        
        # 5. 새 파일로 저장
        combined_df.to_csv(out_path, index=False)
        print(
            f"[NORMALIZE][Protocol.io][{keyword}] 저장 완료: 총 {after_dedup}개 "
            f"(입력: {total_rows}개, 기존: {len(existing_df) if existing_df is not None else 0}개)",
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
    
    # is_completed=True인 키워드와 updated_at 조회
    try:
        schedule_store.ensure_table()
        completed_keywords_with_updated_at = schedule_store.get_completed_keywords_with_updated_at()
        
        if not completed_keywords_with_updated_at:
            print(f"[NORMALIZE][Protocol.io] ⚠️  완료된 키워드가 없습니다. normalize를 건너뜁니다.")
            return
        
        print(f"[NORMALIZE][Protocol.io] 완료된 키워드 목록: {list(completed_keywords_with_updated_at.keys())}")
        for keyword, updated_at in completed_keywords_with_updated_at.items():
            print(f"[NORMALIZE][Protocol.io]   - {keyword}: updated_at={updated_at}")
    except Exception as e:
        print(f"[NORMALIZE][Protocol.io] ⚠️  스케줄 테이블 조회 실패: {e}. 모든 키워드를 처리합니다.")
        completed_keywords_with_updated_at = None  # None이면 필터링하지 않음
    
    # 날짜별 디렉토리 내의 모든 api_data_*.csv 파일 찾기
    all_csv_files = []
    for date_dir in sorted(RAW_DIR.glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]")):
        # 각 날짜 디렉토리 내의 api_data_*.csv 파일 찾기
        all_csv_files.extend(sorted(date_dir.glob("api_data_*.csv")))
    
    # 완료된 키워드만 필터링하고, updated_at 기준으로 날짜 폴더 필터링
    if completed_keywords_with_updated_at:
        csv_files = []
        completed_keywords = set(completed_keywords_with_updated_at.keys())
        
        for csv_path in all_csv_files:
            # 파일명에서 키워드 추출: api_data_{keyword}.csv
            keyword = csv_path.stem.replace("api_data_", "")
            
            # 완료된 키워드인지 확인
            if keyword not in completed_keywords:
                print(f"[NORMALIZE][Protocol.io] ⏭️  키워드 '{keyword}'는 아직 완료되지 않아 건너뜁니다.")
                continue
            
            # updated_at 기준으로 날짜 폴더 필터링
            updated_at = completed_keywords_with_updated_at[keyword]
            # updated_at의 날짜 부분 추출 (timezone-aware든 아니든 date()는 동일하게 동작)
            updated_date = updated_at.date()
            
            # 폴더 이름에서 날짜 추출 (yyyymmdd 형식)
            date_dir_name = csv_path.parent.name
            try:
                folder_date = datetime.strptime(date_dir_name, "%Y%m%d").date()
            except ValueError:
                print(f"[NORMALIZE][Protocol.io] ⚠️  날짜 형식 오류: {date_dir_name}, 건너뜁니다.")
                continue
            
            # updated_at 날짜보다 이전 또는 같은 날짜의 폴더만 포함
            if folder_date <= updated_date:
                csv_files.append(csv_path)
                print(
                    f"[NORMALIZE][Protocol.io] ✅ 키워드 '{keyword}', 폴더 '{date_dir_name}' "
                    f"(updated_at: {updated_date}, 폴더 날짜: {folder_date}) 포함"
                )
            else:
                print(
                    f"[NORMALIZE][Protocol.io] ⏭️  키워드 '{keyword}', 폴더 '{date_dir_name}' "
                    f"(updated_at: {updated_date}, 폴더 날짜: {folder_date}) 제외"
                )
    else:
        csv_files = all_csv_files
    
    if not csv_files:
        if completed_keywords:
            print(f"[NORMALIZE][Protocol.io] 완료된 키워드({completed_keywords})의 raw 파일이 없습니다.")
        else:
            print("[NORMALIZE][Protocol.io] 처리할 파일이 없습니다.")
        return

    print(f"[NORMALIZE][Protocol.io] 처리할 파일 수: {len(csv_files)}/{len(all_csv_files)}")

    for csv_path in csv_files:
        print(f"[NORMALIZE][Protocol.io] processing {csv_path}")
        process_file(csv_path)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[NORMALIZE][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


if __name__ == "__main__":
    main()
