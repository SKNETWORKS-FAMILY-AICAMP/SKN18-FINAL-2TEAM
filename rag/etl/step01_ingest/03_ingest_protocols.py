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
MAX_PAGES_PER_RUN = 5  # 한 번의 실행에서 처리할 최대 페이지 수 (람다 15분 제한)


def ensure_csv(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"[INGEST][Protocol.io] initialized CSV at {path}", flush=True)
    else:
        print(f"[INGEST][Protocol.io] appending to existing file {path}", flush=True)


def ingest_keyword(search_keyword: str) -> None:
    schedule_store.ensure_table()
    
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

    pages_processed = 0  # 처리한 페이지 수 카운터

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
            page_size=30, page_id=page_id, search_key=search_keyword
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

            page_rows.append(
                {
                    "keyword": search_keyword,
                    "url": protocol_url,
                    "title": title_text,
                    "abstract": abstract_str,
                    "step_content": step_str,
                    "reference": reference_str,
                    "guidelines": guidelines_str,
                    "materials": materials_str,
                }
            )

        if page_rows:
            with output_path.open("a", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=FIELDNAMES)
                writer.writerows(page_rows)
            print(
                f"[INGEST][Protocol.io][{search_keyword}] appended "
                f"{len(page_rows)} rows to {output_path}",
                flush=True,
            )

        # 페이지 처리 완료
        pages_processed += 1
        page_id += 1

    print(
        f"[INGEST][Protocol.io][{search_keyword}] ingestion complete. "
        f"처리한 페이지 수: {pages_processed}/{MAX_PAGES_PER_RUN}",
        flush=True,
    )


def run_parallel(keywords: Iterable[str]) -> None:
    start_time = datetime.now()
    print(f"[INGEST][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    keyword_list = list(keywords)
    if not keyword_list:
        print("[INGEST][Protocol.io] No keywords provided.", flush=True)
        return

    max_workers = min(len(keyword_list), MAX_PARALLEL_WORKERS)
    with ThreadPoolExecutor(max_workers=max_workers or 1) as executor:
        future_map = {executor.submit(ingest_keyword, kw): kw for kw in keyword_list}
        for future in as_completed(future_map):
            keyword = future_map[future]
            try:
                future.result()
                print(
                    f"[INGEST][Protocol.io][{keyword}] finished without error.",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[INGEST][Protocol.io][{keyword}] failed: {exc}",
                    flush=True,
                )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[INGEST][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


def run(raw_dir: str, keyword: str | None = None, limit: int | None = None) -> None:
    """
    Pipeline runner에서 호출되는 함수.
    Lambda 핸들러에서도 호출 가능하도록 keyword 파라미터 추가.
    
    Args:
        raw_dir: raw 데이터 저장 디렉토리 (예: "data/raw")
        keyword: 처리할 키워드 (None이면 모든 키워드 처리, Lambda에서는 특정 키워드 전달)
        limit: 최대 처리할 문서 수 (현재는 사용하지 않음)
    """
    start_time = datetime.now()
    print(f"[INGEST][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    global RAW_DIR
    # raw_dir에 protocols 서브디렉토리 추가
    RAW_DIR = Path(raw_dir) / "protocols"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    # 키워드가 지정된 경우 해당 키워드만 처리
    if keyword:
        print(f"[INGEST][Protocol.io] Processing single keyword: {keyword}", flush=True)
        ingest_keyword(keyword)
    else:
        # 키워드가 없으면 모든 키워드 처리 (로컬 개발용)
        print(f"[INGEST][Protocol.io] Processing all keywords: {KEYWORDS}", flush=True)
        main()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[INGEST][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 함수.
    
    이벤트 형식:
    {
        "keyword": "Protein",  # 필수: 처리할 키워드
        "raw_dir": "data/raw"  # 선택: 기본값 "data/raw"
    }
    """
    keyword = event.get("keyword")
    raw_dir = event.get("raw_dir", "data/raw")
    
    if not keyword:
        raise ValueError("'keyword' is required in event")
    
    if keyword not in KEYWORDS:
        raise ValueError(f"Invalid keyword: {keyword}. Must be one of {KEYWORDS}")
    
    print(f"[INGEST][Protocol.io][Lambda] Processing keyword: {keyword}", flush=True)
    
    try:
        run(raw_dir=raw_dir, keyword=keyword)
        return {
            "statusCode": 200,
            "body": {
                "message": f"Successfully processed keyword: {keyword}",
                "keyword": keyword
            }
        }
    except Exception as e:
        print(f"[INGEST][Protocol.io][Lambda] Error processing {keyword}: {e}", flush=True)
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "keyword": keyword
            }
        }


def main() -> None:
    run_parallel(KEYWORDS)


if __name__ == "__main__":
    main()
