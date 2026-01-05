"""
Protocols.io 문서를 청크 단위로 분리한다.

입력: data/processed/protocols/success/.../stage=cleaned/protocol_cleaned_{keyword}.csv
출력: data/processed/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=chunked/protocol_chunked_{keyword}.csv
"""

import re
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict
import csv
import json

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

# Lambda 환경 감지 및 경로 조정
def _get_base_path() -> Path:
    """기본 경로 반환 (Lambda면 /tmp, 아니면 프로젝트 루트)"""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp")
    # 프로젝트 루트 찾기
    current_file = Path(__file__).resolve()
    # step04_chunk/ 에서 프로젝트 루트까지: 4단계 위로
    return current_file.parent.parent.parent.parent

BASE_PATH = _get_base_path()
INPUT_ROOT = BASE_PATH / "data/processed/protocols/success"
OUTPUT_ROOT = BASE_PATH / "data/processed/protocols"
CHUNKS_SPLIT_ROOT = BASE_PATH / "data/chunks/protocols"  # 분할된 청크 파일 저장 위치

# 분할 단위 (환경 변수로 제어 가능)
SPLIT_ROWS_PER_FILE = int(os.getenv("PROTOCOL_CHUNK_SPLIT_SIZE", "3000"))
# table metadata CSV 저장 위치
TABLE_OUTPUT_ROOT = BASE_PATH / "data/entities/protocols"

AGG_KEYS = {"total", "sum", "avg", "average", "mean"}

def detect_row_flags(values, header_len, row_idx, total_rows):
    flags = []

    # 세로 병합
    if values and not values[0]:
        flags.append("fill_down")

    # 가로 병합 후보 (판단은 normalize에서)
    if len(values) < header_len:
        flags.append("short_row")

    # aggregate row
    if values and any(k in values[0].lower() for k in AGG_KEYS):
        if row_idx >= total_rows - 2:
            flags.append("aggregate")

    # middle null
    if len(values) == header_len:
        empties = [i for i, v in enumerate(values) if not v]
        if empties and 0 not in empties:
            flags.append("middle_null")

    return flags

def normalize_table_rows(rows: list[dict], header: list[str]):
    header_len = len(header)

    normalized_rows = []
    table_flags = set()
    last_seen = None
    prev_values = None

    for idx, r in enumerate(rows):
        values = r["values"]
        flags = detect_row_flags(values, header_len, idx, len(rows))

        # 🔥 LEFT MERGE DETECTION
        left_merged = False
        if (
            prev_values
            and len(values) == header_len - 1
            and prev_values[0].isdigit()
            and not values[0].isdigit()
        ):
            values = [""] + values
            flags.append("left_merge")
            left_merged = True

        # 1️⃣ fill-down (left_merge 제외)
        if not left_merged and "fill_down" in flags and last_seen:
            values = [last_seen] + values

        if values and values[0]:
            last_seen = values[0]

        # 2️⃣ padding (가로 병합 / middle null)
        original_values = values.copy()

        # padding
        if len(values) < header_len:
            values = values + [""] * (header_len - len(values))

        prev_values = original_values

        # 3️⃣ 길이 초과는 잘라냄 (보수적)
        if len(values) > header_len:
            return rows, "invalid", ["length_overflow"]

        table_flags.update(flags)

        normalized_rows.append(
            {
                "row_number": r["row_number"],
                "values": values,
                "row_flags": flags,
            }
        )

    # 4️⃣ table status 결정
    if table_flags:
        parse_status = "fixed"
    else:
        parse_status = "ok"

    return normalized_rows, parse_status, sorted(table_flags)

def protect_table_blocks(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()

    extracted_tables = []
    cleaned_lines = []

    in_table = False
    current_table = []

    header_pattern = re.compile(
    r'^\s*('
    r'(\S+\s{2,}\S+)'      # 공백 2개 이상
    r'|'
    r'(.+\t.+)'            # 탭
    r'|'
    r'(\|.*\|)'            # pipe table
    r')\s*$'
    )

    row_pattern = re.compile(
    r'^\s*('
    r'(\S+\s{2,}\S+)'
    r'|'
    r'(.+\t.+)'
    r'|'
    r'(\|.*\|)'
    r'|'
    r'(\d+(\.\d+)?\s*[a-zA-Zµ°/%]+)'  # 숫자+단위
    r')\s*$'
    )


    for line in lines:
        stripped = line.strip()

        # 빈 줄은 table 종료 트리거로 사용
        if not stripped:
            if in_table:
                extracted_tables.append("\n".join(current_table))
                current_table = []
                in_table = False
            cleaned_lines.append(line)
            continue

        # table header 시작
        if not in_table and header_pattern.match(line):
            in_table = True
            current_table = [line]
            continue

        # table 내부 row
        if in_table and row_pattern.match(line):
            current_table.append(line)
            continue

        # table 종료 조건 (형식 깨짐)
        if in_table:
            extracted_tables.append("\n".join(current_table))
            current_table = []
            in_table = False
            # 현재 line은 table이 아니므로 cleaned text로 보냄
            cleaned_lines.append(line)
            continue

        # 일반 문장
        cleaned_lines.append(line)

    # 파일 끝에서 table 종료 처리
    if in_table and current_table:
        extracted_tables.append("\n".join(current_table))

    cleaned_text = "\n".join(cleaned_lines).strip()

    return cleaned_text, extracted_tables

def detect_table_splitter(header_line: str) -> str:
    """
    header line을 기준으로 table column splitter 결정
    반환값: 'pipe' | 'tab' | 'space'
    """
    if "|" in header_line:
        return "pipe"
    if "\t" in header_line:
        return "tab"
    return "space"

def table_to_json(
    table_text: str,
    table_id: str,
    chunk_id: str,
    keyword: str,
    protocol_id: str,
    url: str,
    title: str
) -> Dict:
    """
    table text → JSON
    - row_number 분리
    - header / row length 정합성 보정
    """

    # --- 1. line 정리 ---
    lines = [ln.strip() for ln in table_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {}

    # --- 2. header 파싱 ---
    splitter = detect_table_splitter(lines[0])

    if splitter == "pipe":
        header_cols = [c.strip() for c in lines[0].strip("|").split("|")]
    elif splitter == "tab":
        header_cols = [c.strip() for c in lines[0].split("\t")]
    else:  # space
        header_cols = re.split(r"\s{2,}", lines[0])

    header = [c for c in header_cols if c]
    header_len = len(header)

    # header 없는 numeric table 방어
    if header and header[0].isdigit():
        return {}

    rows = []

    # --- 3. row 파싱 ---
    for line in lines[1:]:
        if splitter == "pipe":
            raw_cols = [c.strip() for c in line.strip("|").split("|")]
        elif splitter == "tab":
            raw_cols = [c.strip() for c in line.split("\t")]
        else:  # space
            raw_cols = re.split(r"\s{2,}", line)
        if len(raw_cols) < 2:
            continue

        row_number = None
        values = raw_cols

        # ✅ row_number 분리 (첫 컬럼이 숫자일 경우)
        if raw_cols[0].isdigit():
            row_number = raw_cols[0]
            values = raw_cols[1:]

        # (A) trailing empty cell 보존
        if len(values) < header_len:
            values = values + [""] * (header_len - len(values))

        # ✅ header 길이 맞추기
        row_len = len(values)

        rows.append(
            {
                "row_number": row_number,
                "values": values,
                "value_len": row_len,
            }
        )
    header_len = len(header)

    mismatch_rows = [
        r for r in rows if r["value_len"] != header_len
    ]

    fix_flags = []

    if mismatch_rows:
        rows, parse_status, fix_flags = normalize_table_rows(rows, header)
    else:
        parse_status = "ok"

    if not rows:
        return {}

    # --- 4. table JSON ---
    table_json = {
        "header": header,
        "rows": rows,
        "parse_status": parse_status,   # ok / fixed / invalid
        "fix_flags": fix_flags
    }

    # --- 5. metadata ---
    return {
        "table_id": table_id,
        "chunk_id": chunk_id,
        "keyword": keyword,
        "protocol_id": protocol_id,
        "url": url,
        "title": title,
        "table_json": table_json
    }

def write_table_metadata_csv(
    table_metadata: list[dict],
    output_csv: str
):
    """
    table_to_json 결과(list of dict)를 CSV 파일로 저장
    """

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "table_id",
        "chunk_id",
        "keyword",
        "protocol_id",
        "url",
        "title",
        "table_json"
    ]

    file_exists = output_path.exists()

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL  # 중요
        )
        if not file_exists:
            writer.writeheader()

        for meta in table_metadata:
            writer.writerow({
                "table_id": meta["table_id"],
                "chunk_id": meta["chunk_id"],
                "keyword": meta["keyword"],
                "protocol_id": meta["protocol_id"],
                "url": meta["url"],
                "title": meta["title"],
                # JSON → string
                "table_json": json.dumps(
                    meta["table_json"],
                    ensure_ascii=False
                )
            })

def build_table_output_path(keyword: str, status: str) -> Path:
    now = datetime.now()
    parts = [
        TABLE_OUTPUT_ROOT,
        status,
        f"year={now.year:04d}",
        f"month={now.month:02d}",
        f"day={now.day:02d}",
        "stage=table_metadata",
        f"protocol_tables_{keyword}.csv",
    ]
    path = Path(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def split_into_sentences(text: str):
    """
    문장을 분리하는 함수
    표 블록을 보호한 후 문장 분리를 수행한다.
    """
    # 1) 표 블록 보호
    protected = text

    # URL 보호
    protected = re.sub(r'(https?://\S+)', r'<URL>\1</URL>', protected)

    # 약어 보호
    protected = re.sub(r'\b(e\.g\.|i\.e\.|etc\.|Fig\.|Fig\s*\d+\.|No\.|no\.)',
                       r'<ABBR>\1</ABBR>', protected)

    # "No. 1" → "No_DOT" 형태 보호
    protected = re.sub(
        r'\bNo\.(\s*\d+)',
        r'<NO>No_DOT\1</NO>',
        protected
    )

    # 숫자 목록 (1. 2. 3.) 보호
    protected = re.sub(r'\b(\d+)\.(\s+)', r'<NUM>\1.</NUM>\2', protected)

    # ✅ 로마 숫자 Heading (I. II. III. IV. 등) 보호
    protected = re.sub(
        r'\b([IVXLCDM]+)\.(\s+)',
        r'<ROMAN>\1.</ROMAN>\2',
        protected
    )

    # 괄호 안의 마침표 보호
    protected = re.sub(
        r'\(([^)]+?)\)',
        lambda m: '(' + m.group(1).replace('.', '<DOT>') + ')',
        protected
    )

    # 표는 문장 분리 제외 (TABLE_BLOCK 전체를 하나로 유지)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z<])', protected)

    # 보호 복원
    cleaned = []
    for sent in sentences:
        sent = sent.replace('No_DOT', 'No.')
        sent = sent.replace('<URL>', '').replace('</URL>', '')
        sent = sent.replace('<ABBR>', '').replace('</ABBR>', '')
        sent = sent.replace('<NUM>', '').replace('</NUM>', '')
        sent = sent.replace('<NO>', '').replace('</NO>', '')

        # 🔥 로마 숫자 복원
        sent = sent.replace('<ROMAN>', '').replace('</ROMAN>', '')

        sent = sent.replace('<DOT>', '.')

        cleaned.append(sent)

    return [s for s in cleaned if s.strip()]


def create_sentence_chunks(
    sentences, 
    chunk_size=400, 
    chunk_overlap=100, 
    min_chunk_size=300
):
    chunks = []
    current_chunk = ""
    current_sentences = []  # 현재 chunk에 포함된 문장들 추적
    
    for sentence in sentences:
        # 임시로 sentence 추가해보고 길이 측정
        test_chunk = (current_chunk + " " + sentence).strip()

        # 1) 아직 최소 chunk 길이에 못 미치면 일단 계속 붙임
        if len(test_chunk) < min_chunk_size:
            current_chunk = test_chunk
            current_sentences.append(sentence)
            continue

        # 2) 최소 길이는 지켰지만 chunk_size를 넘어가면 새 chunk 생성
        if len(test_chunk) > chunk_size:
            chunks.append(current_chunk.strip())

            # === 문장 단위 overlap 적용 ===
            if chunk_overlap > 0:
                # 오버랩할 문장 개수 계산 (대략 chunk_overlap 문장에 해당하는 문장 수)
                overlap_sentences = []
                overlap_length = 0
                
                # 마지막 문장부터 역순으로 오버랩 문장 수집
                for sent in reversed(current_sentences):
                    sent_length = len(sent) + 1  # +1 for space
                    if overlap_length + sent_length <= chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_length += sent_length
                    else:
                        break
                
                # 오버랩 문장들을 다음 chunk 시작에 추가
                if overlap_sentences:
                    overlap_text = " ".join(overlap_sentences)
                    current_chunk = (overlap_text + " " + sentence).strip()
                    current_sentences = overlap_sentences + [sentence]
                else:
                    current_chunk = sentence
                    current_sentences = [sentence]
            else:
                current_chunk = sentence
                current_sentences = [sentence]
        else:
            # chunk_size는 넘지 않으므로 그냥 문장 추가
            current_chunk = test_chunk
            current_sentences.append(sentence)

    # 마지막 chunk 처리
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def build_output_path(keyword: str, status: str) -> Path:
    now = datetime.now()
    parts = [
        OUTPUT_ROOT,
        status,
        f"year={now.year:04d}",
        f"month={now.month:02d}",
        f"day={now.day:02d}",
        "stage=chunked",
        f"protocol_chunked_{keyword}.csv",
    ]
    path = Path(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def _build_section(tag: str, text: str) -> str:
    """
    섹션 텍스트가 공백/개행만 있으면 빈 문자열 반환,
    의미 있는 내용이 있으면 <tag> + text 반환
    """
    if not isinstance(text, str):
        return ""

    # 공백 + 개행 제거 후 내용 검사
    if not text.strip():
        return ""

    return f"<{tag}>\n{text.strip()}\n"

def chunk_dataframe(
    df: pd.DataFrame,
    keyword: str,
    max_tokens: int = 500,
) -> tuple[pd.DataFrame, list[dict]]:

    output_rows = []
    table_metadata_all = []

    for _, row in df.iterrows():
        protocol_id = str(row.get("protocol_id", ""))
        url = str(row.get("url", ""))
        title = str(row.get("title", ""))

        url_hash = (
            hashlib.md5(url.encode()).hexdigest()[:12]
            if url else "no_url"
        )

        base_id = f"{keyword}_{url_hash}"

        # 1️⃣ sentence split (기존 로직 그대로 사용)
        sentences = split_into_sentences(row["cleaned_text"])

        # 2️⃣ sentence → chunk
        chunks = create_sentence_chunks(
            sentences,
            chunk_size=max_tokens,
            chunk_overlap=100,
            min_chunk_size=300,
        )

        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"{base_id}_chunk_{idx}"

            # 3️⃣ chunk 단위 table 탐지
            cleaned_chunk_text, table_blocks = protect_table_blocks(
                chunk_text
            )

            # 4️⃣ chunk row 생성
            output_rows.append(
                {
                    "chunking_id": chunk_id,
                    "protocol_id": protocol_id,
                    "url": url,
                    "title": title,
                    "content": cleaned_chunk_text,
                    "keyword": keyword,
                }
            )

            # 5️⃣ table metadata 생성 (⭐ 위치 정확)
            for t_idx, table_text in enumerate(table_blocks):
                table_id = f"table_{chunk_id}_{t_idx}"

                table_meta = table_to_json(
                    table_text=table_text,
                    table_id=table_id,
                    chunk_id=chunk_id,
                    keyword=keyword,
                    protocol_id=protocol_id,
                    url=url,
                    title=title,
                )

                if table_meta:
                    table_metadata_all.append(table_meta)

    chunks_df = pd.DataFrame(output_rows)
    return chunks_df, table_metadata_all


def load_existing_urls(csv_path: Path) -> set[str]:
    """
    기존 chunked 파일에서 URL만 읽어서 Set으로 반환 (메모리 효율적).
    
    주의사항: 대용량 파일을 위해 chunksize로 청크 단위로 읽어서 메모리 사용량 제한.
    
    Args:
        csv_path: 기존 chunked CSV 파일 경로
    
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
            f"[CHUNK] 기존 파일에서 {len(existing_urls)}개 URL 로드 완료",
            flush=True,
        )
    except Exception as e:
        print(
            f"[CHUNK] 기존 파일 URL 로드 실패: {e}. 빈 Set으로 시작합니다.",
            flush=True,
        )
    
    return existing_urls


def split_chunk_file(chunk_file: Path, keyword: str, rows_per_file: int = SPLIT_ROWS_PER_FILE) -> list[Path]:
    """
    청크 파일을 지정된 행 수 단위로 분할하여 저장한다.
    
    Args:
        chunk_file: 분할할 청크 파일 경로
        keyword: 키워드
        rows_per_file: 파일당 행 수 (기본값: 300)
    
    Returns:
        생성된 분할 파일 경로 리스트
    """
    if not chunk_file.exists():
        print(f"[CHUNK][Protocol.io][{keyword}] 분할할 파일이 없습니다: {chunk_file}", flush=True)
        return []
    
    # 출력 디렉토리: data/chunks/protocols/{날짜}_{시분}/{keyword}
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M")
    date_time_dir = f"{date_str}_{time_str}"
    output_dir = CHUNKS_SPLIT_ROOT / date_time_dir / keyword
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[CHUNK][Protocol.io][{keyword}] 청크 파일 분할 시작: {chunk_file}", flush=True)
    
    split_files = []
    try:
        # 청크 파일을 chunksize로 읽어서 메모리 효율적으로 처리
        total_rows = 0
        current_part = 1
        current_rows = []
        
        for chunk_df in pd.read_csv(chunk_file, chunksize=rows_per_file):
            total_rows += len(chunk_df)
            
            # 현재 청크를 행 리스트로 변환
            chunk_rows = chunk_df.to_dict('records')
            
            for row in chunk_rows:
                current_rows.append(row)
                
                # 지정된 행 수에 도달하면 파일로 저장
                if len(current_rows) >= rows_per_file:
                    part_file = output_dir / f"protocol_chunked_{keyword}_part{current_part:03d}.csv"
                    part_df = pd.DataFrame(current_rows)
                    part_df.to_csv(part_file, index=False)
                    split_files.append(part_file)
                    print(
                        f"[CHUNK][Protocol.io][{keyword}] 분할 파일 생성: {part_file.name} "
                        f"({len(current_rows)}개 행)",
                        flush=True,
                    )
                    current_rows = []
                    current_part += 1
        
        # 남은 행이 있으면 마지막 파일로 저장
        if current_rows:
            part_file = output_dir / f"protocol_chunked_{keyword}_part{current_part:03d}.csv"
            part_df = pd.DataFrame(current_rows)
            part_df.to_csv(part_file, index=False)
            split_files.append(part_file)
            print(
                f"[CHUNK][Protocol.io][{keyword}] 마지막 분할 파일 생성: {part_file.name} "
                f"({len(current_rows)}개 행)",
                flush=True,
            )
        
        print(
            f"[CHUNK][Protocol.io][{keyword}] 분할 완료: 총 {len(split_files)}개 파일 생성 "
            f"(전체 {total_rows}개 행, 파일당 {rows_per_file}개 행)",
            flush=True,
        )
        
    except Exception as e:
        print(f"[CHUNK][Protocol.io][{keyword}] 분할 중 오류 발생: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
    
    return split_files


def process_file(csv_path: Path) -> None:
    """
    Incremental 처리 방식으로 cleaned CSV 파일을 chunked CSV로 변환.

    역할:
    - URL 단위 중복 제거
    - cleaned_text 준비
    - chunking 실행
    - chunk CSV + table metadata CSV 저장
    """
    keyword = csv_path.stem.replace("protocol_cleaned_", "")
    status = "success"

    try:
        out_path = build_output_path(keyword, status)
        table_out_path = build_table_output_path(keyword, status)

        # 1. 기존 chunked 파일에서 URL Set만 로드
        existing_urls = load_existing_urls(out_path)

        # 2. cleaned CSV 로드
        cleaned_df = pd.read_csv(csv_path)
        total_rows = len(cleaned_df)

        # 3. URL 중복 제거
        new_cleaned_df = cleaned_df[
            ~cleaned_df["url"].astype(str).str.strip().isin(existing_urls)
        ]

        if new_cleaned_df.empty:
            print(
                f"[CHUNK][Protocol.io][{keyword}] 새 데이터 없음 "
                f"(전체 {total_rows}개 모두 중복)",
                flush=True,
            )
            # 새 데이터가 없어도 기존 청크 파일이 있으면 분할 실행
            # 오늘 날짜의 청크 파일이 없으면 모든 날짜에서 찾기
            chunk_file_to_split = None
            if out_path.exists():
                chunk_file_to_split = out_path
            else:
                # 모든 날짜의 청크 파일 검색
                chunk_files = sorted(OUTPUT_ROOT.glob(f"**/stage=chunked/protocol_chunked_{keyword}.csv"))
                if chunk_files:
                    # 가장 최근 파일 사용
                    chunk_file_to_split = chunk_files[-1]
                    print(
                        f"[CHUNK][Protocol.io][{keyword}] 오늘 날짜 청크 파일 없음. "
                        f"최근 청크 파일 사용: {chunk_file_to_split}",
                        flush=True,
                    )

            if chunk_file_to_split and chunk_file_to_split.exists():
                print(f"[CHUNK][Protocol.io][{keyword}] 기존 청크 파일 분할 시작: {chunk_file_to_split}", flush=True)
                split_files = split_chunk_file(chunk_file_to_split, keyword, rows_per_file=SPLIT_ROWS_PER_FILE)
                if split_files:
                    # 저장 위치 출력 (날짜_시분 디렉토리 포함)
                    now = datetime.now()
                    date_str = now.strftime("%Y%m%d")
                    time_str = now.strftime("%H%M")
                    date_time_dir = f"{date_str}_{time_str}"
                    print(
                        f"[CHUNK][Protocol.io][{keyword}] 분할 완료: {len(split_files)}개 파일 생성 "
                        f"(저장 위치: {CHUNKS_SPLIT_ROOT / date_time_dir / keyword})",
                        flush=True,
                    )
            else:
                print(
                    f"[CHUNK][Protocol.io][{keyword}] 분할할 청크 파일이 없습니다.",
                    flush=True,
                )
            return

        print(
            f"[CHUNK][Protocol.io][{keyword}] 새 데이터 {len(new_cleaned_df)}개 "
            f"(전체 {total_rows}개)",
            flush=True,
        )

        # 4. cleaned_text 생성 (빈 섹션 태그 제거)
        new_cleaned_df = new_cleaned_df.copy()

        new_cleaned_df["cleaned_text"] = (
            new_cleaned_df.apply(
                lambda row: (
                    _build_section("abstract", row.get("abstract", ""))
                    + _build_section("step_content", row.get("step_content", ""))
                    + _build_section("guidelines", row.get("guidelines", ""))
                ).strip(),
                axis=1,
            )
        )

        # 5. chunking + table 추출은 chunk 단계에서 수행
        new_chunks_df, table_metadata_all = chunk_dataframe(
            new_cleaned_df,
            keyword
        )

        if new_chunks_df.empty:
            raise ValueError("생성된 chunk 데이터가 없습니다.")

        # 6. 기존 chunk CSV와 병합
        if out_path.exists() and existing_urls:
            existing_chunks_df = pd.read_csv(out_path)
            combined_chunks_df = pd.concat(
                [existing_chunks_df, new_chunks_df],
                ignore_index=True,
            ).drop_duplicates(
                subset="chunking_id",
                keep="first",
            )
        else:
            combined_chunks_df = new_chunks_df

        # 7. chunk CSV 저장
        combined_chunks_df.to_csv(out_path, index=False)

        print(
            f"[CHUNK][Protocol.io][{keyword}] 저장 완료: "
            f"{len(combined_chunks_df)} chunks",
            flush=True,
        )

        # 8. table metadata CSV 저장 (⭐ 여기서만)
        if table_metadata_all:
            write_table_metadata_csv(
                table_metadata_all,
                table_out_path
            )
            print(
                f"[CHUNK][Protocol.io][{keyword}] table metadata 저장: "
                f"{len(table_metadata_all)} tables",
                flush=True,
            )

    except Exception as exc:
        status = "fail"
        out_path = build_output_path(keyword, status)
        pd.DataFrame([{"error": str(exc)}]).to_csv(out_path, index=False)
        print(
            f"[CHUNK][Protocol.io][{keyword}] 실패: {exc}",
            flush=True,
        )

def main() -> None:
    start_time = datetime.now()
    print(f"[CHUNK][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    # is_completed=True인 키워드 조회
    try:
        schedule_store.ensure_table()
        completed_keywords = schedule_store.get_completed_keywords()
        
        if not completed_keywords:
            print(f"[CHUNK][Protocol.io] ⚠️  완료된 키워드가 없습니다. chunking을 건너뜁니다.")
            return
        
        print(f"[CHUNK][Protocol.io] 완료된 키워드 목록: {completed_keywords}")
    except Exception as e:
        print(f"[CHUNK][Protocol.io] ⚠️  스케줄 테이블 조회 실패: {e}. 모든 키워드를 처리합니다.")
        completed_keywords = None  # None이면 필터링하지 않음
    
    # 오늘 날짜의 cleaned 파일만 찾기 (cleaned 실행 후 바로 chunk 실행되므로)
    now = datetime.now()
    today_path = (
        INPUT_ROOT 
        / f"year={now.year:04d}" 
        / f"month={now.month:02d}" 
        / f"day={now.day:02d}" 
        / "stage=cleaned"
    )
    all_input_files = sorted(today_path.glob("protocol_cleaned_*.csv")) if today_path.exists() else []
    
    if not all_input_files:
        print(
            f"[CHUNK][Protocol.io] 오늘 날짜({now.year:04d}-{now.month:02d}-{now.day:02d})의 cleaned 파일이 없습니다.",
            flush=True,
        )
    
    # 완료된 키워드만 필터링
    if completed_keywords:
        input_files = []
        for csv_path in all_input_files:
            # 파일명에서 키워드 추출: protocol_cleaned_{keyword}.csv
            keyword = csv_path.stem.replace("protocol_cleaned_", "")
            if keyword in completed_keywords:
                input_files.append(csv_path)
            else:
                print(f"[CHUNK][Protocol.io] ⏭️  키워드 '{keyword}'는 아직 완료되지 않아 건너뜁니다.")
    else:
        input_files = all_input_files
    
    if not input_files:
        if completed_keywords:
            print(f"[CHUNK][Protocol.io] 완료된 키워드({completed_keywords})의 cleaned 파일이 없습니다.")
        else:
            print("[CHUNK][Protocol.io] 처리할 입력 파일이 없습니다.")
        return

    print(f"[CHUNK][Protocol.io] 처리할 파일 수: {len(input_files)}/{len(all_input_files)}")

    for csv_path in input_files:
        print(f"[CHUNK][Protocol.io] processing {csv_path}")
        process_file(csv_path)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[CHUNK][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


if __name__ == "__main__":
    main()
