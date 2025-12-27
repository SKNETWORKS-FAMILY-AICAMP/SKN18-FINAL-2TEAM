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


def protect_table_blocks(text: str) -> str:
    """
    표 블록을 감지하여 보호하는 함수
    3-column 이상 table header와 2-column 이상 table row를 감지하여
    <TABLE_BLOCK> 태그로 감싸서 문장 분리 시 보호한다.
    """
    lines = text.split("\n")
    table_blocks = []
    in_table = False
    current_block = []

    # 3-column 이상 table header 감지
    header_pattern = re.compile(r'^[^\s].*(\s{2,}[^\s]+){2,}')

    # table row 감지 (2-column 이상)
    row_pattern = re.compile(r'^\s*\S+(\s{2,}\S+){1,}')

    for line in lines:
        if header_pattern.match(line) or (in_table and row_pattern.match(line)):
            # 표 시작 또는 표 내부
            if not in_table:
                in_table = True
                current_block = []
            current_block.append(line)
        else:
            # 표 종료
            if in_table:
                table_blocks.append("<TABLE_BLOCK>\n" + "\n".join(current_block) + "\n</TABLE_BLOCK>")
                in_table = False
            table_blocks.append(line)

    # 마지막 줄이 표였을 경우 처리
    if in_table:
        table_blocks.append("<TABLE_BLOCK>\n" + "\n".join(current_block) + "\n</TABLE_BLOCK>")

    return "\n".join(table_blocks)


def split_into_sentences(text: str):
    """
    문장을 분리하는 함수
    표 블록을 보호한 후 문장 분리를 수행한다.
    """
    # 1) 표 블록 보호
    text = protect_table_blocks(text)
    
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

        # 표 블록 복원
        sent = sent.replace('<TABLE_BLOCK>', '').replace('</TABLE_BLOCK>', '')

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


def chunk_dataframe(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    df["abstract"] = df["abstract"].fillna("").astype(str)
    df["step_content"] = df["step_content"].fillna("").astype(str)
    df["guidelines"] = df.get("guidelines", "").fillna("").astype(str)
    # 🔹 url과 title 컬럼 추가 처리
    df["url"] = df.get("url", "").fillna("").astype(str)
    df["title"] = df.get("title", "").fillna("").astype(str)

    output_rows = []
    filename = f"protocol_chunked_{keyword}"

    for _, row in df.iterrows():
        protocol_id = str(row["protocol_id"]).strip()
        url = str(row["url"]).strip()
        
        # URL 기반 고유 ID 생성 (같은 URL은 항상 같은 해시값)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12] if url else "no_url"

        combined_text = (
            "<abstract>\n" + row["abstract"] + "\n"
            "<step_content>\n" + row["step_content"] + "\n"
            "<guidelines>\n" + row["guidelines"]
        )

        # 1) 문장 단위 split
        sentences = split_into_sentences(combined_text)

        # 2) 문장 기반 chunk + 최소 길이 적용
        chunks = create_sentence_chunks(
            sentences,
            chunk_size=400,
            chunk_overlap=100,
            min_chunk_size=300
        )

        # 3) CSV 저장용 구조
        # chunking_id에 URL 해시 사용하여 날짜와 무관하게 고유성 보장
        for idx, chunk in enumerate(chunks):
            output_rows.append({
                "protocol_id": f"{protocol_id}",
                "url": row["url"],
                "title": row["title"],
                "chunking_id": f"{filename}_{url_hash}_chunk_{idx}",
                "text": chunk.replace(" ,", "")
            })

    return pd.DataFrame(output_rows)


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
    
    주의사항:
    1. 기존 파일이 있으면 URL Set만 로드하여 메모리 효율성 확보
    2. 새 데이터만 필터링하여 처리 시간 단축
    3. 병합 후 chunking_id 기반 중복 제거로 안전장치 제공
    """
    keyword = csv_path.stem.replace("protocol_cleaned_", "")
    status = "success"
    
    try:
        out_path = build_output_path(keyword, status)
        
        # 1. 기존 chunked 파일에서 URL Set만 로드 (메모리 효율적)
        existing_urls = load_existing_urls(out_path)
        
        # 2. 새 cleaned 데이터 읽기
        cleaned_df = pd.read_csv(csv_path)
        total_rows = len(cleaned_df)
        
        # 3. 중복 제거: 기존에 없는 URL만 필터링
        new_cleaned_df = cleaned_df[
            ~cleaned_df["url"].astype(str).str.strip().isin(existing_urls)
        ]
        
        if len(new_cleaned_df) == 0:
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
        
        duplicate_count = total_rows - len(new_cleaned_df)
        print(
            f"[CHUNK][Protocol.io][{keyword}] 새 데이터 {len(new_cleaned_df)}개 "
            f"(전체 {total_rows}개, 중복 {duplicate_count}개)",
            flush=True,
        )
        
        # 4. 새 데이터만 chunking
        new_chunks_df = chunk_dataframe(new_cleaned_df, keyword)
        
        if new_chunks_df.empty:
            raise ValueError("생성된 chunk 데이터가 없습니다.")
        
        # 5. 기존 chunks와 병합 (메모리 효율적으로 처리)
        if out_path.exists() and len(existing_urls) > 0:
            # 기존 파일이 있으면 읽어서 병합
            try:
                existing_chunks_df = pd.read_csv(out_path)
                # 병합
                combined_chunks_df = pd.concat(
                    [existing_chunks_df, new_chunks_df], ignore_index=True
                )
                # 안전장치: chunking_id 기반 중복 제거 (병합 과정에서 중복 발생 가능)
                before_dedup = len(combined_chunks_df)
                combined_chunks_df = combined_chunks_df.drop_duplicates(
                    subset="chunking_id", keep="first"
                )
                after_dedup = len(combined_chunks_df)
                
                if before_dedup != after_dedup:
                    print(
                        f"[CHUNK][Protocol.io][{keyword}] 병합 후 중복 제거: "
                        f"{before_dedup}개 → {after_dedup}개 chunks",
                        flush=True,
                    )
            except Exception as e:
                print(
                    f"[CHUNK][Protocol.io][{keyword}] 기존 파일 읽기 실패: {e}. "
                    f"새 데이터만 저장합니다.",
                    flush=True,
                )
                combined_chunks_df = new_chunks_df
        else:
            # 기존 파일이 없으면 새 데이터만 저장
            combined_chunks_df = new_chunks_df
        
        # 6. 저장
        combined_chunks_df.to_csv(out_path, index=False)
        print(
            f"[CHUNK][Protocol.io][{keyword}] 저장 완료: 총 {len(combined_chunks_df)}개 chunks "
            f"(기존 {len(existing_urls)}개 URL의 chunks + 새 {len(new_chunks_df)}개 chunks)",
            flush=True,
        )
        
        # 7. 청크 파일을 300개 단위로 분할하여 data/chunks/protocols/{날짜}_{시분}/{keyword}에 저장
        print(f"[CHUNK][Protocol.io][{keyword}] 청크 파일 분할 시작...", flush=True)
        split_files = split_chunk_file(out_path, keyword, rows_per_file=SPLIT_ROWS_PER_FILE)
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
        
    except Exception as exc:
        status = "fail"
        out_path = build_output_path(keyword, status)
        output_df = pd.DataFrame([{"error": str(exc)}])
        output_df.to_csv(out_path, index=False)
        print(f"[CHUNK][Protocol.io][{keyword}] 실패: {exc}", flush=True)


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
