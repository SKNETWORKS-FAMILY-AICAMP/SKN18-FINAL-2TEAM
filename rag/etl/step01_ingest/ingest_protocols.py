import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Iterable
import re

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

PLACEHOLDER_PATTERN = re.compile(r'%s+', re.I)

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
def extract_cell_text(cell: BeautifulSoup) -> str:
    """
    td/th 안에 직접 텍스트가 없을 경우
    내부 block 구조를 줄 단위로 풀어냄
    """
    text = cell.get_text(separator=" ", strip=True)

    if text:
        return text

    # fallback: li, p, div 단위 추출
    lines = []

    for tag in cell.find_all(["li", "p", "div"], recursive=True):
        t = tag.get_text(strip=True)
        if t:
            lines.append(t)

    return "; ".join(lines)

def parse_table_to_text(html: str) -> str:
    if not html:
        return html

    soup = BeautifulSoup(html, "html.parser")

    # sup → ^ 변환 (이전 논의 반영)
    for sup in soup.find_all("sup"):
        sup.replace_with(f"^{sup.get_text(strip=True)}")

    tables = soup.find_all("table")

    for table in tables:
        rows = []

        for tr in table.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"]):
                cells.append(extract_cell_text(cell))
            rows.append(cells)

        # 🔥 모든 cell이 빈 경우 → table 전체 fallback
        if all(all(not c for c in row) for row in rows):
            continue

        lines = ["[TABLE]"]
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("[/TABLE]")

        table.replace_with("\n" + "\n".join(lines) + "\n")

    return str(soup)

def find_header_candidates(lines: list[str]) -> set[int]:
    candidates = set()

    for i in range(len(lines) - 1):
        if looks_like_table_header(lines[i], lines[i+1]):
            candidates.add(i)
    return candidates

def is_pseudo_table(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    
    # ❌ STEP / 리스트형 row 방지
    step_like = 0
    for ln in lines:
        if re.match(r"^\(?STEP\s*\d+", ln, re.I):
            step_like += 1
    if step_like >= len(lines) * 0.6:
        return False

    def split_line(line: str) -> list[str]:
        if "\t" in line:
            return [c.strip() for c in line.split("\t")]
        if "|" in line:
            return [c.strip() for c in line.strip("|").split("|")]
        return [c.strip() for c in re.split(r"\s{2,}", line)]

    split_rows = [split_line(ln) for ln in lines]

    col_lens = [len(r) for r in split_rows]

    # 모든 줄에서 column 수 동일해야 함
    if len(set(col_lens)) != 1:
        return False

    # column 수 2 미만은 표 아님
    if col_lens[0] < 2:
        return False

    # header + data 최소 구조
    if len(split_rows) < 2:
        return False

    # data row 최소 개수 (header 제외)
    data_like = 0
    for row in split_rows[1:]:
        joined = " ".join(row)
        if re.search(r"\d", joined) or re.search(r"(µ|°|mg|ml|min|sec)", joined, re.I):
            data_like += 1

    if data_like < 1:
        return False
    
    VERB_PATTERN = re.compile(
        r"\b(add|mix|incubate|prepare|wash|place|remove|spin|pipette)\b",
        re.I
    )

    sentence_like = 0
    for ln in lines:
        if VERB_PATTERN.search(ln):
            sentence_like += 1

    # 문장형 라인이 절반 이상이면 pseudo-table 아님
    if sentence_like >= len(lines) / 2:
        return False

    return True

def looks_like_table_header(header: str, first_body_row: str) -> bool:
    """
    pseudo-table body 바로 위의 header 후보가
    column 구조상 header인지 판단
    """
    def split_cols(line: str) -> list[str]:
        if "\t" in line:
            return [c.strip() for c in line.split("\t")]
        if "|" in line:
            return [c.strip() for c in line.strip("|").split("|")]
        return [c.strip() for c in re.split(r"\s{2,}", line)]

    h_cols = split_cols(header)
    b_cols = split_cols(first_body_row)

    # column 수 동일 + header는 숫자 위주가 아니어야 함
    if len(h_cols) != len(b_cols):
        return False

    numeric_ratio = sum(bool(re.search(r"\d", c)) for c in h_cols) / len(h_cols)
    if numeric_ratio > 0.3:
        return False

    return True

def detect_pseudo_table_from_text(text: str) -> str:
    raw_lines = text.splitlines()   # ❗ strip / filter 하지 않음
    n = len(raw_lines)

    i = 0
    while i < n:
        # 공백 라인은 스킵
        if not raw_lines[i].strip():
            i += 1
            continue

        # header 후보인지 확인
        if i + 1 < n and looks_like_table_header(
            raw_lines[i].strip(),
            raw_lines[i + 1].strip()
        ):
            # 연속 block 수집
            block = []
            j = i
            while j < n and raw_lines[j].strip():
                block.append(raw_lines[j].strip())
                j += 1

            if is_pseudo_table(block):
                wrapped = (
                    ["<PSEUDO_TABLE>"]
                    + block
                    + ["</PSEUDO_TABLE>"]
                )
                raw_lines[i:j] = wrapped
                n = len(raw_lines)
                i += len(wrapped)
                continue

        i += 1

    return "\n".join(raw_lines)

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

def build_ordered_steps(steps: list[dict]) -> list[dict]:
    if not steps:
        return []

    # 1️⃣ id → step 맵
    step_by_id = {}
    for s in steps:
        sid = s.get("id")
        if sid is not None:
            step_by_id[sid] = s

    # 2️⃣ previous_id → next step 맵
    next_by_prev = {}
    for s in steps:
        prev = s.get("previous_id")
        if prev:
            # 중복 prev 방어 (뒤에 온 것을 우선)
            next_by_prev[prev] = s

    # 3️⃣ HEAD 찾기 (previous_id == 0 or None)
    head = None
    for s in steps:
        if not s.get("previous_id"):
            head = s
            break

    # 방어: HEAD 못 찾았을 경우
    if head is None:
        # fallback: number 기준 정렬
        return sorted(
            steps,
            key=lambda x: str(x.get("number", 0) or 0)
        )

    # 4️⃣ 체인 따라가며 순서 복원
    ordered = []
    visited = set()
    current = head

    while current:
        cid = current.get("id")
        if cid in visited:
            # 루프 감지 → 중단
            break

        ordered.append(current)
        visited.add(cid)

        current = next_by_prev.get(cid)

    # 5️⃣ 체인에 포함되지 못한 step들 (section, dangling step 등)
    if len(ordered) < len(steps):
        remaining = [
            s for s in steps
            if s.get("id") not in visited
        ]

        # number 기준으로 보조 정렬 후 뒤에 붙임
        remaining_sorted = sorted(
            remaining,
            key=lambda x: str(x.get("number", 0) or 0)
        )

        ordered.extend(remaining_sorted)

    return ordered

def ingest_keyword(search_keyword: str, raw_dir: Path | None = None) -> None:
    """
    단일 키워드에 대한 ingestion 실행.
    
    Args:
        search_keyword: 처리할 키워드
        raw_dir: raw 데이터 저장 디렉토리 (None이면 전역 RAW_DIR 사용)
    """
    # 테이블 생성 및 마이그레이션 (테이블이 없으면 생성, 있으면 컬럼 체크)
    print(
        f"[INGEST][Protocol.io][{search_keyword}] 테이블 생성/확인 중...",
        flush=True,
    )
    schedule_store.ensure_table()
    print(
        f"[INGEST][Protocol.io][{search_keyword}] 테이블 생성/확인 완료",
        flush=True,
    )
    
    # raw_dir이 제공되면 전역 변수 업데이트
    if raw_dir is not None:
        global RAW_DIR
        RAW_DIR = Path(raw_dir) / "protocols" if isinstance(raw_dir, str) else Path(raw_dir) / "protocols"
    
    # 페이지를 미리 예약 (원자적 연산으로 race condition 방지)
    start_page = schedule_store.get_and_reserve_next_page(
        search_keyword, 
        pages_to_reserve=MAX_PAGES_PER_RUN
    )
    # start_page = 1 # 디버그용 하드코딩
    
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
            # 마지막 페이지 도달 표시 (is_completed=True 설정)
            # next_page는 마지막 페이지 번호를 유지 (실제로는 is_completed=True이므로 다음 실행 시 중단됨)
            schedule_store.update_next_page(search_keyword, page_id, is_completed=True)
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
            abstract_str = detect_pseudo_table_from_text(abstract_str)
            if not abstract_str.strip():
                abstract_str = "<no data>"
            print(f"abstract: {abstract_str}")

            steps_list = proto.get("steps") or []
            ordered_steps = build_ordered_steps(steps_list)
            step_str = ""

            current_section = None
            for s in ordered_steps:
                section_html = s.get("section") or ""
                section_text = html_to_text_with_superscript(section_html).strip()
                if section_text and section_text != current_section:
                    step_str += f"\n[SECTION] {section_text}\n"
                    current_section = section_text

                step_html = s.get("step") or ""
                step_number = s.get("number") or ""
                
                # 버튼 태그 텍스트를 포함시키는 로직 추가
                soup = BeautifulSoup(step_number, "html.parser")
                
                # 버튼 텍스트를 추출 (모두 공백으로 join)
                button_texts = [btn.get_text(strip=True) for btn in soup]
                
                if button_texts:
                    buttons_combined = f"(STEP {button_texts[0]}) "
                else:
                    buttons_combined = ""
                
                # 기존 테이블 변환 및 superscript 변환 적용
                step_html = parse_table_to_text(step_html)
                step_text = html_to_text_with_superscript(step_html)

                if PLACEHOLDER_PATTERN.fullmatch(step_text.strip()):
                    step_text = ""
                
                # 버튼 텍스트가 있으면 앞이나 뒤에 붙임 (예: 앞에 번호 넣기)
                if buttons_combined:
                    step_text = buttons_combined + " " + step_text
                
                step_str += step_text
            if not step_str.strip():
                step_str = "<no data>"

            step_str = detect_pseudo_table_from_text(step_str)
            print(f"step_content: {step_str}")


            reference_html = proto.get("protocol_references") or ""
            reference_html = parse_table_to_text(reference_html)
            reference_str = html_to_text_with_superscript(reference_html)
            reference_str = detect_pseudo_table_from_text(reference_str)
            if not reference_str.strip():
                reference_str = "<no data>"
            print(f"reference: {reference_str}")

            guidelines_html = proto.get("guidelines") or ""
            guidelines_html = parse_table_to_text(guidelines_html)
            guidelines_str = html_to_text_with_superscript(guidelines_html)
            guidelines_str = detect_pseudo_table_from_text(guidelines_str)
            if not guidelines_str.strip():
                guidelines_str = "<no data>"
            print(f"guidelines: {guidelines_str}")

            materials_html = proto.get("materials_text") or ""
            materials_html = parse_table_to_text(materials_html)
            materials_str = html_to_text_with_superscript(materials_html)
            materials_str = detect_pseudo_table_from_text(materials_str)
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


def main(raw_dir: str | None = None) -> None:
    """
    메인 함수: 모든 키워드에 대해 ingestion 실행
    
    Args:
        raw_dir: raw 데이터 디렉토리 경로 (None이면 기본값 "data/raw" 사용)
    """
    global RAW_DIR
    if raw_dir is not None:
        RAW_DIR = Path(raw_dir) / "protocols" if isinstance(raw_dir, str) else Path(raw_dir) / "protocols"
    run_parallel(KEYWORDS)


if __name__ == "__main__":
    main()
