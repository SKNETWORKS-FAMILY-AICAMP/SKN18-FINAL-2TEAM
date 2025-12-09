"""
Protocols.io 문서를 청크 단위로 분리한다.

입력: data/processed/protocols/success/.../stage=cleaned/protocol_cleaned_{keyword}.csv
출력: data/processed/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=chunked/protocol_chunked_{keyword}.csv
"""

import re
import os
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


def split_into_sentences(text):
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

    # 문장 분리
    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z<])',
        protected
    )

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
                # 오버랩할 문장 개수 계산 (대략 chunk_overlap 문자에 해당하는 문장 수)
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
        for idx, chunk in enumerate(chunks):
            output_rows.append({
                "protocol_id": f"{protocol_id}",
                "url": row["url"],
                "title": row["title"],
                "chunking_id": f"{filename}_chunk_{protocol_id}_{idx}",
                "text": chunk.replace(" ,", "")
            })

    return pd.DataFrame(output_rows)


def process_file(csv_path: Path) -> None:
    keyword = csv_path.stem.replace("protocol_cleaned_", "")
    status = "success"
    try:
        df = pd.read_csv(csv_path)
        output_df = chunk_dataframe(df, keyword)
        if output_df.empty:
            raise ValueError("생성된 chunk 데이터가 없습니다.")
    except Exception as exc:
        status = "fail"
        output_df = pd.DataFrame([{"error": str(exc)}])
        print(f"[CHUNK][Protocol.io][{keyword}] 실패: {exc}")
    else:
        print(
            f"[CHUNK][Protocol.io][{keyword}] chunk rows={len(output_df)}",
            flush=True,
        )

    out_path = build_output_path(keyword, status)
    output_df.to_csv(out_path, index=False)
    print(f"[CHUNK][Protocol.io][{keyword}] 저장 완료: {out_path}")


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
