import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Iterable

# 패키지 형태로 실행하지 않아도 rag.* 모듈을 찾을 수 있도록 루트 경로 추가
import os
# Lambda 환경 감지
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Lambda 환경: /var/task가 루트
    PROJECT_ROOT = Path('/var/task')
else:
    # 로컬 환경: 기존 방식
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.etl.step01_ingest.modules.protocol import (
    get_protocol,
    get_public_protocols,
    html_to_text_with_superscript,
)
from rag.etl.step01_ingest.modules import schedule_store
from bs4 import BeautifulSoup


# -------------------------
# (1) 표(table) → 텍스트 변환 함수
# -------------------------
def parse_table_to_text(html):
    if not html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    if not tables:
        return html

    for table in tables:
        rows = []

        # 모든 tr 반복
        for tr in table.find_all("tr"):
            cells = []

            # th, td 모두 읽기
            for cell in tr.find_all(["th", "td"]):
                cells.append(cell.get_text(strip=True))

            rows.append("\t".join(cells))  # 탭 구분자로 처리

        # 표 전체를 텍스트로 변환
        table_text = "\n".join(rows)
        table.replace_with("\n" + table_text + "\n")

    return str(soup)


# -------------------------
# (2) API 데이터 수집
# -------------------------
FIELDNAMES = [
    "keyword",
    "url",
    "title",
    "abstract",
    "step_content",
    "reference",
    "guidelines",
    "materials",
]

KEYWORDS = ["Protein", "Cell", "DNA", "RNA", "vivo", "mouse"]
RAW_DIR = Path("data/raw/protocols")
MAX_PARALLEL_WORKERS = 1  # 동시에 돌릴 최대 키워드 수
REQUEST_INTERVAL_SECONDS = 0.5
# 운영
PAGE_SIZE = 30  # 한 페이지당 가져올 프로토콜 수
MAX_PAGES_PER_RUN = 5  # 한 번의 실행에서 처리할 최대 페이지 수 (람다 15분 제한)
# 테스트
# PAGE_SIZE = 5
# MAX_PAGES_PER_RUN = 1


def load_existing_urls(csv_path: Path) -> set[str]:
    """
    기존 CSV 파일에서 URL 목록을 읽어서 Set으로 반환한다.
    
    Args:
        csv_path: CSV 파일 경로
    
    Returns:
        기존 URL들의 Set (파일이 없거나 비어있으면 빈 Set)
    """
    if not csv_path.exists():
        return set()
    
    existing_urls = set()
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                url = row.get("url", "").strip()
                if url:
                    existing_urls.add(url)
        print(
            f"[INGEST][Protocol.io] 기존 파일에서 {len(existing_urls)}개의 URL 로드 완료",
            flush=True,
        )
    except Exception as e:
        print(
            f"[INGEST][Protocol.io] 기존 파일 읽기 실패: {e}. 빈 Set으로 시작합니다.",
            flush=True,
        )
    
    return existing_urls


def ensure_csv(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"[INGEST][Protocol.io] initialized CSV at {path}", flush=True)
    else:
        print(f"[INGEST][Protocol.io] appending to existing file {path}", flush=True)


def ingest_keyword(search_keyword: str, raw_dir: Path | None = None) -> None:
    """
    단일 키워드에 대한 ingestion 실행.
    
    Args:
        search_keyword: 처리할 키워드
        raw_dir: raw 데이터 저장 디렉토리 (None이면 전역 RAW_DIR 사용)
    """
    schedule_store.ensure_table()
    
    # raw_dir이 제공되면 전역 변수 업데이트
    if raw_dir is not None:
        global RAW_DIR
        RAW_DIR = Path(raw_dir) / "protocols" if isinstance(raw_dir, str) else Path(raw_dir) / "protocols"
    
    # 페이지를 미리 예약 (원자적 연산으로 race condition 방지)
    start_page = schedule_store.get_and_reserve_next_page(
        search_keyword, 
        pages_to_reserve=MAX_PAGES_PER_RUN
    )
    
    if start_page is None:
        print(
            f"[INGEST][Protocol.io][{search_keyword}] 예약할 페이지가 없습니다.",
            flush=True,
        )
        return
    
    page_id = start_page
    
    # 날짜별 디렉토리 경로: data/raw/protocols/yyyymmdd/api_data_{keyword}.csv
    today = datetime.now().strftime("%Y%m%d")
    output_dir = RAW_DIR / today
    output_path = output_dir / f"api_data_{search_keyword}.csv"
    ensure_csv(output_path)
    
    # 기존 파일에서 URL 목록 로드 (중복 체크용)
    existing_urls = load_existing_urls(output_path)
    
    pages_processed = 0  # 처리한 페이지 수 카운터
    new_rows_count = 0  # 새로 추가된 행 수
    skipped_rows_count = 0  # 중복으로 건너뛴 행 수

    print(
        f"[INGEST][Protocol.io][{search_keyword}] 예약된 시작 페이지: {start_page}, "
        f"예약된 페이지 수: {MAX_PAGES_PER_RUN}",
        flush=True,
    )

    # 예약된 페이지 범위만 처리
    end_page = start_page + MAX_PAGES_PER_RUN
    
    while page_id < end_page:
        print(
            f"[INGEST][Protocol.io][{search_keyword}] Fetching list "
            f"(page_id={page_id}, 진행: {pages_processed + 1}/{MAX_PAGES_PER_RUN}) ...",
            flush=True,
        )
        public_list = get_public_protocols(
            page_size=PAGE_SIZE, page_id=page_id, search_key=search_keyword
        )
        time.sleep(REQUEST_INTERVAL_SECONDS)
        protocols = public_list.get("items", [])
        print(
            f"[INGEST][Protocol.io][{search_keyword}] page id: {page_id}, "
            f"retrieved={len(protocols)}",
            flush=True,
        )
        print("=" * 50)

        if not protocols:
            print(
                f"[INGEST][Protocol.io][{search_keyword}] no more protocols, "
                f"마지막 페이지 도달 (page {page_id}).",
                flush=True,
            )
            # 마지막 페이지 도달 표시
            schedule_store.update_next_page(search_keyword, 1, is_completed=True)
            break

        page_rows: list[dict[str, str]] = []
        new_page_rows: list[dict[str, str]] = []  # 중복이 아닌 행만 저장

        for i, proto_item in enumerate(protocols):
            print("=" * 50)
            print(
                f"[INGEST][Protocol.io][{search_keyword}] progress: "
                f"{i + 1} / {len(protocols)} (page {page_id})",
                flush=True,
            )

            protocol_id = proto_item["id"]
            protocol_url = proto_item["url"]
            print(f"url: {protocol_url}")

            # 중복 체크
            if protocol_url in existing_urls:
                print(
                    f"[INGEST][Protocol.io][{search_keyword}] 중복 URL 감지, 건너뜀: {protocol_url}",
                    flush=True,
                )
                skipped_rows_count += 1
                continue

            print(
                f"[INGEST][Protocol.io][{search_keyword}] fetching detail id={protocol_id}",
                flush=True,
            )

            detail = get_protocol(protocol_id)
            time.sleep(REQUEST_INTERVAL_SECONDS)
            proto = detail.get("payload", {})

            title_text = proto.get("title") or "<no data>"
            print(f"title: {title_text}")

            abstract_html = proto.get("description") or ""
            abstract_html = parse_table_to_text(abstract_html)
            abstract_str = html_to_text_with_superscript(abstract_html)
            if not abstract_str.strip():
                abstract_str = "<no data>"
            print(f"abstract: {abstract_str}")

            steps_list = proto.get("steps") or []
            step_str = ""
            for s in steps_list:
                step_html = s.get("step") or ""
                step_html = parse_table_to_text(step_html)
                step_str += html_to_text_with_superscript(step_html)
            if not step_str.strip():
                step_str = "<no data>"
            print(f"step_content: {step_str}")

            reference_html = proto.get("protocol_references") or ""
            reference_html = parse_table_to_text(reference_html)
            reference_str = html_to_text_with_superscript(reference_html)
            if not reference_str.strip():
                reference_str = "<no data>"
            print(f"reference: {reference_str}")

            guidelines_html = proto.get("guidelines") or ""
            guidelines_html = parse_table_to_text(guidelines_html)
            guidelines_str = html_to_text_with_superscript(guidelines_html)
            if not guidelines_str.strip():
                guidelines_str = "<no data>"
            print(f"guidelines: {guidelines_str}")

            materials_html = proto.get("materials_text") or ""
            materials_html = parse_table_to_text(materials_html)
            materials_str = html_to_text_with_superscript(materials_html)
            if not materials_str.strip():
                materials_str = "<no data>"
            print(f"materials: {materials_str}")

            row_data = {
                "keyword": search_keyword,
                "url": protocol_url,
                "title": title_text,
                "abstract": abstract_str,
                "step_content": step_str,
                "reference": reference_str,
                "guidelines": guidelines_str,
                "materials": materials_str,
            }
            
            page_rows.append(row_data)
            new_page_rows.append(row_data)
            existing_urls.add(protocol_url)  # Set에 추가하여 다음 중복 체크에 사용

        if new_page_rows:
            with output_path.open("a", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
                writer.writerows(new_page_rows)
            new_rows_count += len(new_page_rows)
            print(
                f"[INGEST][Protocol.io][{search_keyword}] appended "
                f"{len(new_page_rows)} rows (중복 제외) to {output_path}",
                flush=True,
            )
        elif page_rows:
            print(
                f"[INGEST][Protocol.io][{search_keyword}] 모든 행이 중복이므로 추가하지 않음",
                flush=True,
            )

        # 페이지 처리 완료
        pages_processed += 1
        page_id += 1

    print(
        f"[INGEST][Protocol.io][{search_keyword}] ingestion complete. "
        f"처리한 페이지 수: {pages_processed}/{MAX_PAGES_PER_RUN}, "
        f"새로 추가된 행: {new_rows_count}, 중복 건너뛴 행: {skipped_rows_count}",
        flush=True,
    )
    
    # 순수 ingest (API 호출) 완료 시점 기록
    schedule_store.update_ingestion_completed(search_keyword)


def run(raw_dir: str, keyword: str) -> None:
    """
    Lambda에서 호출되는 함수.
    
    Args:
        raw_dir: raw 데이터 디렉토리 경로
        keyword: 처리할 키워드
    """
    global RAW_DIR
    RAW_DIR = Path(raw_dir) / "protocols" if isinstance(raw_dir, str) else Path(raw_dir) / "protocols"
    ingest_keyword(keyword)


def run_parallel(keywords: Iterable[str]) -> None:
    start_time = datetime.now()
    print(f"[INGEST][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(ingest_keyword, kw): kw for kw in keywords}
        
        for future in as_completed(futures):
            keyword = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(
                    f"[INGEST][Protocol.io][{keyword}] 예외 발생: {exc}",
                    flush=True,
                )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[INGEST][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


def main() -> None:
    """메인 함수: 모든 키워드에 대해 ingestion 실행"""
    run_parallel(KEYWORDS)


if __name__ == "__main__":
    main()
