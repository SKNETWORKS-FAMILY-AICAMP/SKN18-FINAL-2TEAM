"""
Protocols.io 문서를 청크 단위로 분리한다.

입력: data/processed/protocols/success/.../stage=cleaned/protocol_cleaned_{keyword}.csv
출력: data/processed/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=chunked/protocol_chunked_{keyword}.csv
"""

import re
import os
import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd

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
        
    except Exception as exc:
        status = "fail"
        out_path = build_output_path(keyword, status)
        output_df = pd.DataFrame([{"error": str(exc)}])
        output_df.to_csv(out_path, index=False)
        print(f"[CHUNK][Protocol.io][{keyword}] 실패: {exc}", flush=True)


def main() -> None:
    start_time = datetime.now()
    print(f"[CHUNK][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    input_files = sorted(INPUT_ROOT.glob("**/stage=cleaned/protocol_cleaned_*.csv"))
    if not input_files:
        print("[CHUNK][Protocol.io] 처리할 입력 파일이 없습니다.")
        return

    for csv_path in input_files:
        print(f"[CHUNK][Protocol.io] processing {csv_path}")
        process_file(csv_path)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[CHUNK][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


if __name__ == "__main__":
    main()
