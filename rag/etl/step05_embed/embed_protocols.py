"""
Protocols.io 청크 데이터를 임베딩하여 CSV 파일로 저장한다.

입력: data/processed/protocols/success/.../stage=chunked/protocol_chunked_{keyword}.csv
출력: data/embeddings/protocols/protocol_embedded_{keyword}.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
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
from dotenv import load_dotenv
from datetime import datetime

# DB insert는 upsert_protocols.py로 이동했으므로 주석처리
# from rag.etl.common.db_connection import get_connection

# schedule_store는 is_completed 키워드 조회용으로 사용
from rag.etl.step01_ingest.modules import schedule_store

from sentence_transformers import SentenceTransformer

load_dotenv()

EMBEDDING_MODEL = os.getenv("PROTOCOL_EMBED_MODEL")

_embedder: SentenceTransformer | None = None

def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder

# Lambda 환경 감지 및 경로 조정
def _get_base_path() -> Path:
    """기본 경로 반환 (Lambda면 /tmp, 아니면 프로젝트 루트)"""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp")
    # 프로젝트 루트 찾기
    current_file = Path(__file__).resolve()
    # step05_embed/ 에서 프로젝트 루트까지: 4단계 위로
    return current_file.parent.parent.parent.parent

BASE_PATH = _get_base_path()
INPUT_ROOT = BASE_PATH / "data/processed/protocols/success"  # 기존 청크 파일 위치 (fallback)
CHUNKS_SPLIT_ROOT = BASE_PATH / "data/chunks/protocols"  # 분할된 청크 파일 위치 (우선 사용)
OUTPUT_ROOT = BASE_PATH / "data/embeddings/protocols"
EMBEDDING_DIM = 1536
TABLE_NAME = "ts_protocol_embedding"

# 단순 모드 설정 (환경 변수로 제어 가능)
USE_SIMPLE_MODE = os.getenv("PROTOCOL_EMBED_SIMPLE_MODE", "false").lower() == "true"

# 배치 처리 설정 (메모리 효율성을 위해)
BATCH_SIZE = int(os.getenv("PROTOCOL_EMBED_BATCH_SIZE", "100"))

# 분할된 청크 파일 사용 여부 (환경 변수로 제어 가능)
USE_SPLIT_CHUNKS = os.getenv("PROTOCOL_EMBED_USE_SPLIT_CHUNKS", "true").lower() == "true"


# DB 테이블 생성은 upsert_protocols.py로 이동
# def ensure_table() -> None:
#     """pgvector 확장 및 테이블 생성"""
#     with get_connection(autocommit=False) as conn:
#         with conn.cursor() as cur:
#             # pgvector 확장 설치
#             cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
#             
#             # 테이블 생성
#             cur.execute(f"""
#                 CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
#                     id SERIAL PRIMARY KEY,
#                     chunking_id TEXT UNIQUE,
#                     url TEXT,
#                     title TEXT,
#                     text TEXT,
#                     embedding vector({EMBEDDING_DIM})
#                 );
#             """)
#             
#             # 인덱스 생성 (선택적, 검색 성능 향상)
#             cur.execute(f"""
#                 CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx 
#                 ON {TABLE_NAME} 
#                 USING ivfflat (embedding vector_cosine_ops)
#                 WITH (lists = 100);
#             """)
#             
#         conn.commit()


def embed_text(text: str) -> list[float]:
    model = get_embedder()
    vec = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False
    )
    return vec.tolist()

def load_table_metadata(table_csv_path: Path) -> dict[str, list[dict]]:
    """
    chunk_id → table_metadata 리스트
    """
    if not table_csv_path.exists():
        return {}

    df = pd.read_csv(table_csv_path)
    table_map: dict[str, list[dict]] = {}

    for _, row in df.iterrows():
        chunk_id = str(row["chunk_id"])
        table_map.setdefault(chunk_id, []).append({
            "table_id": row["table_id"],
            "table_json": json.loads(row["table_json"]),
        })

    return table_map

def summarize_table_for_embedding(table_json: dict) -> str:
    """
    table_json → embedding용 자연어 요약
    """
    headers = table_json.get("header", [])
    rows = table_json.get("rows", [])

    if not headers or not rows:
        return ""

    lines = []
    lines.append(f"This table contains the following columns: {', '.join(headers)}.")

    # 상위 몇 개 row만 요약 (전체 숫자 나열 방지)
    for row in rows[:5]:
        row_desc = []
        for h, v in zip(headers, row):
            row_desc.append(f"{h}: {v}")
        lines.append("; ".join(row_desc))

    if len(rows) > 5:
        lines.append(f"The table contains {len(rows)} total rows.")

    return " ".join(lines)


def split_sections(text: str) -> dict[str, str]:
    """
    <abstract>, <step_content>, <guidelines> 섹션을 분리한다.
    요청 토큰 초과 방지를 위해 섹션별로 분리하여 임베딩한다.
    """
    sections = {}
    tags = ['abstract', 'step_content', 'guidelines']
    
    for i, tag in enumerate(tags):
        start_tag = f'<{tag}>'
        start_idx = text.find(start_tag)
        
        if start_idx == -1:
            sections[tag] = ''
            continue
            
        start_idx += len(start_tag)
        
        if i + 1 < len(tags):
            next_tag = f'<{tags[i+1]}>'
            end_idx = text.find(next_tag)
            sections[tag] = text[start_idx:end_idx].strip() if end_idx != -1 else text[start_idx:].strip()
        else:
            # 마지막 섹션은 끝까지
            sections[tag] = text[start_idx:].strip()
    
    return sections


# DB insert는 upsert_protocols.py로 이동
# def insert_row(chunking_id: str, url: str, title: str, text: str, embedding: list[float]) -> None:
#     """PostgreSQL에 임베딩 데이터 삽입 (UPSERT)"""
#     with get_connection(autocommit=False) as conn:
#         with conn.cursor() as cur:
#             cur.execute(f"""
#                 INSERT INTO {TABLE_NAME} (chunking_id, url, title, text, embedding)
#                 VALUES (%s, %s, %s, %s, %s)
#                 ON CONFLICT (chunking_id)
#                 DO UPDATE SET
#                     url = EXCLUDED.url,
#                     title = EXCLUDED.title,
#                     text = EXCLUDED.text,
#                     embedding = EXCLUDED.embedding;
#             """, (chunking_id, url, title, text, embedding))
#         conn.commit()


def process_csv_simple(csv_path: Path, keyword: str, output_path: Path, table_metadata_map: dict[str, list[dict]]) -> None:
    """
    단순 모드: 텍스트 전체를 그대로 임베딩 (소스 파일 방식)
    섹션 분리 없이 각 행의 전체 텍스트를 직접 임베딩한다.
    배치 처리로 메모리 효율적으로 CSV 파일에 저장.
    """
    print(f"[EMBED][Protocol.io][{keyword}] >>> CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path)

    # text 컬럼 검증 (소스 파일 방식)
    if "text" not in df.columns:
        raise ValueError("❌ CSV 파일에 'text' 컬럼이 없습니다.")

    print(f"[EMBED][Protocol.io][{keyword}] 🔍 총 {len(df)}개의 행 처리 시작")
    
    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # CSV 파일 필드명
    fieldnames = ["chunking_id", "url", "title", "text", "embedding_model", "embedding_dim", "embedding"]
    
    csv_rows = []
    is_first_batch = True
    total_processed = 0

    for idx, row in df.iterrows():
        text = str(row["text"]).strip()
        chunking_id = str(row["chunking_id"])

        tables = table_metadata_map.get(chunking_id, [])

        table_summaries = []
        for t in tables:
            summary = summarize_table_for_embedding(t["table_json"])
            if summary:
                table_summaries.append(summary)

        embedding_input = text
        if table_summaries:
            embedding_input = (
                text
                + "\n\n[Associated Tables]\n"
                + "\n".join(table_summaries)
            )
        
        # chunking_id, url, title은 선택적 (없으면 빈 문자열)
        chunking_id = str(row.get("chunking_id", ""))
        url = str(row.get("url", ""))
        title = str(row.get("title", ""))

        if not text:
            continue

        # 텍스트 전체를 그대로 embedding
        embedding = embed_text(embedding_input)
        
        # CSV 행 데이터 준비
        csv_rows.append({
            "chunking_id": chunking_id,
            "url": url,
            "title": title,
            "text": text,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "embedding": json.dumps(embedding, ensure_ascii=False)  # JSON 문자열로 저장
        })
        
        total_processed += 1

        # 배치 크기에 도달하면 파일에 저장
        if len(csv_rows) >= BATCH_SIZE:
            print(f"[EMBED][Protocol.io][{keyword}] 💾 배치 저장 중: {len(csv_rows)}개 행을 파일에 저장...", flush=True)
            batch_df = pd.DataFrame(csv_rows)
            # 첫 배치면 헤더 포함, 이후는 헤더 없이 append
            batch_df.to_csv(
                output_path,
                mode="w" if is_first_batch else "a",
                index=False,
                header=is_first_batch,
                encoding="utf-8-sig" if is_first_batch else "utf-8",  # BOM은 첫 배치만
                quoting=csv.QUOTE_ALL,
            )
            csv_rows.clear()  # 배치 비우기
            is_first_batch = False
            print(f"[EMBED][Protocol.io][{keyword}] ✓ 배치 저장 완료: 총 {total_processed}/{len(df)} 행 처리됨", flush=True)

        if (idx + 1) % 10 == 0 or idx == 0:
            print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} embedding 완료", flush=True)

    # 남은 데이터 저장
    if csv_rows:
        print(f"[EMBED][Protocol.io][{keyword}] 💾 마지막 배치 저장 중: {len(csv_rows)}개 행...", flush=True)
        batch_df = pd.DataFrame(csv_rows)
        batch_df.to_csv(
            output_path,
            mode="w" if is_first_batch else "a",
            index=False,
            header=is_first_batch,
            encoding="utf-8-sig" if is_first_batch else "utf-8",
            quoting=csv.QUOTE_ALL,
        )
        print(f"[EMBED][Protocol.io][{keyword}] ✓ 마지막 배치 저장 완료", flush=True)

    print(f"[EMBED][Protocol.io][{keyword}] 🎉 모든 CSV 데이터 임베딩 및 저장 완료! 출력: {output_path}")

def build_embedding_output_path(keyword: str, status: str = "success", part_suffix: str | None = None) -> Path:
    """
    data/embeddings/protocols/{success|fail}/year=YYYY/month=MM/day=DD/stage=embedded/
      protocol_embedded_{keyword}[ _partXXX].csv
    """
    now = datetime.now()

    filename = f"protocol_embedded_{keyword}"
    if part_suffix:
        filename += f"_part{part_suffix}"
    filename += ".csv"

    parts = [
        OUTPUT_ROOT,
        status,
        f"year={now.year:04d}",
        f"month={now.month:02d}",
        f"day={now.day:02d}",
        "stage=embedded",
        filename,
    ]

    path = Path(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def is_table_like_text(text: str, min_rows: int = 3, min_cols: int = 3) -> bool:
    """
    텍스트가 표(tabular) 형태인지 간단히 판별
    - 여러 줄 존재
    - 각 줄에 탭 또는 2칸 이상 공백으로 구분된 컬럼이 반복
    """
    lines = [line for line in text.splitlines() if line.strip()]
    
    if len(lines) < min_rows:
        return False

    col_counts = []
    for line in lines:
        # 탭 또는 2칸 이상 공백 기준 분리
        if "\t" in line:
            cols = line.split("\t")
        else:
            cols = [c for c in line.split("  ") if c.strip()]
        col_counts.append(len(cols))

    # 대부분의 줄이 일정 컬럼 수 이상이면 표로 간주
    avg_cols = sum(col_counts) / len(col_counts)
    return avg_cols >= min_cols


def process_csv(csv_path: Path, keyword: str, output_path: Path, table_metadata_map: dict[str, list[dict]]) -> None:
    """CSV 파일을 읽어서 임베딩 생성 및 CSV 파일 저장 (배치 처리)"""
    # 단순 모드 사용 여부 확인
    if USE_SIMPLE_MODE:
        return process_csv_simple(csv_path, keyword, output_path, table_metadata_map)
    print(f"[EMBED][Protocol.io][{keyword}] >>> CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path)

    # ================================
    # 필수 컬럼 / 텍스트 컬럼 결정 (스키마 호환)
    # ================================

    # chunking_id는 반드시 필요
    if "chunking_id" not in df.columns:
        raise ValueError(
            "*** !!! CSV 파일에 필수 컬럼 chunking_id가 없습니다 !!! ***"
        )

    # 텍스트 컬럼 자동 선택
    if "text" in df.columns:
        text_col = "text"
    elif "content" in df.columns:
        text_col = "content"
    elif "chunk_text" in df.columns:
        text_col = "chunk_text"
    else:
        raise ValueError(
            "*** !!! CSV 파일에 텍스트 컬럼이 없습니다. "
            "가능 컬럼: text, content, chunk_text / "
            f"실제 컬럼: {list(df.columns)} !!! ***"
        )

    print(f"[EMBED][Protocol.io][{keyword}] 🔍 총 {len(df)}개의 행 처리 시작")
    
    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    csv_rows = []
    is_first_batch = True
    total_processed = 0

    for idx, row in df.iterrows():
        text = str(row[text_col]).strip()
        chunking_id = str(row["chunking_id"])
        url = str(row["url"])
        title = str(row["title"])

        if not text:
            continue

        # 섹션별로 분리하여 임베딩
        sections = split_sections(text)

        no_section_tags = (
            sections["abstract"].strip() == "" and
            sections["step_content"].strip() == "" and
            sections["guidelines"].strip() == ""
        )

        table_like = is_table_like_text(text)

        if no_section_tags or table_like:
            # 섹션 태그가 없거나, 표 형태 데이터면 전체 텍스트 임베딩
            embedding = embed_text(text)
            csv_rows.append({
                "chunking_id": chunking_id,
                "url": url,
                "title": title,
                "text": text,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dim": EMBEDDING_DIM,
                "embedding": json.dumps(embedding, ensure_ascii=False)
            })
            total_processed += 1
            
            # 배치 저장 체크
            if len(csv_rows) >= BATCH_SIZE:
                _save_batch(csv_rows, output_path, is_first_batch, keyword, total_processed, len(df))
                csv_rows.clear()
                is_first_batch = False
            
            if (idx + 1) % 10 == 0 or idx == 0:
                print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} 저장 완료 (전체 텍스트)", flush=True)
            continue

        # 각 섹션별로 임베딩 생성 및 저장
        for section_key, section_value in sections.items():
            if not section_value.strip():
                continue

            # 섹션별로 줄 단위로 분리하여 처리
            lines = section_value.split("\n")
            for line_idx, line in enumerate(lines):
                if not line.strip():
                    continue

                # 첫 번째 줄은 섹션 태그와 함께, 나머지는 줄만
                if line_idx == 0:
                    embedding_text = f"{section_key}\n{line}"
                    save_text = f"{section_key}\n{line}"
                else:
                    embedding_text = line
                    save_text = line

                # 임베딩 생성
                embedding = embed_text(embedding_text)
                
                # chunking_id에 섹션 정보 추가하여 고유성 보장
                section_chunking_id = f"{chunking_id}_{section_key}_{line_idx}"
                
                # CSV 행 데이터 준비
                csv_rows.append({
                    "chunking_id": section_chunking_id,
                    "url": url,
                    "title": title,
                    "text": save_text,
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding_dim": EMBEDDING_DIM,
                    "embedding": json.dumps(embedding, ensure_ascii=False)
                })
                total_processed += 1
                
                # 배치 저장 체크
                if len(csv_rows) >= BATCH_SIZE:
                    _save_batch(csv_rows, output_path, is_first_batch, keyword, total_processed, len(df))
                    csv_rows.clear()
                    is_first_batch = False

        if (idx + 1) % 10 == 0 or idx == 0:
            print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} 저장 완료", flush=True)

    # 남은 데이터 저장
    if csv_rows:
        _save_batch(csv_rows, output_path, is_first_batch, keyword, total_processed, len(df))

    print(f"[EMBED][Protocol.io][{keyword}] 🎉 CSV 처리 완료: {csv_path} → {output_path}")


def _save_batch(csv_rows: list[dict], output_path: Path, is_first_batch: bool, keyword: str, processed: int, total: int) -> None:
    """배치 데이터를 CSV 파일에 저장"""
    print(f"[EMBED][Protocol.io][{keyword}] 💾 배치 저장 중: {len(csv_rows)}개 행을 파일에 저장...", flush=True)
    batch_df = pd.DataFrame(csv_rows)
    batch_df.to_csv(
        output_path,
        mode="w" if is_first_batch else "a",
        index=False,
        header=is_first_batch,
        encoding="utf-8-sig" if is_first_batch else "utf-8",
        quoting=csv.QUOTE_ALL,
    )
    # processed는 실제 생성된 임베딩 행 수, total은 입력 청크 파일의 행 수
    print(f"[EMBED][Protocol.io][{keyword}] ✓ 배치 저장 완료: {processed}개 임베딩 생성됨 (입력 청크: {total}개)", flush=True)


def process_file(csv_path: Path, embeddings_base_dir: Path | None = None, table_metadata_map: dict[str, list[dict]] | None = None) -> None:
    """단일 CSV 파일 처리 (에러 핸들링 포함)"""
    # 파일명에서 키워드 추출
    # 분할 파일: protocol_chunked_{keyword}_part{번호}.csv
    # 기존 파일: protocol_chunked_{keyword}.csv
    filename = csv_path.stem
    if "_part" in filename:
        # 분할 파일: protocol_chunked_{keyword}_part{번호} -> keyword 추출
        keyword = filename.replace("protocol_chunked_", "").split("_part")[0]
    else:
        # 기존 파일: protocol_chunked_{keyword}
        keyword = filename.replace("protocol_chunked_", "")
    
    status = "success"

    if "_part" in filename:
        part_num = filename.split("_part")[1]
        output_path = build_embedding_output_path(
            keyword=keyword,
            status=status,
            part_suffix=part_num,
        )
    else:
        output_path = build_embedding_output_path(
            keyword=keyword,
            status=status,
        )

    
    try:
        process_csv(csv_path, keyword, output_path, table_metadata_map or {})
        print(f"[EMBED][Protocol.io][{keyword}] 처리 완료: {output_path}")
    except Exception as exc:
        print(f"[EMBED][Protocol.io][{keyword}] 실패: {exc}")
        raise


def main(embeddings_dir: str | None = None) -> None:
    """메인 함수: is_completed=True인 키워드의 chunked CSV 파일만 처리"""
    start_time = datetime.now()
    print(f"[EMBED][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    # 처리 모드 출력
    mode = "단순 모드" if USE_SIMPLE_MODE else "섹션 분리 모드"
    print(f"[EMBED][Protocol.io] 처리 모드: {mode}")
    print(f"[EMBED][Protocol.io] 배치 크기: {BATCH_SIZE}")
    
    # DB 테이블 생성은 upsert 단계로 이동
    # ensure_table()
    
    # is_completed=True이고 is_embeded=False인 키워드만 조회 (임베딩이 아직 완료되지 않은 완료된 키워드)
    completed_keywords = None
    completed_keywords_set = None
    try:
        schedule_store.ensure_table()
        completed_keywords = schedule_store.get_completed_not_embedded_keywords()
        
        if not completed_keywords:
            print(f"[EMBED][Protocol.io] ⚠️  임베딩이 필요한 키워드가 없습니다 (is_completed=True & is_embeded=False). embedding을 건너뜁니다.")
            return
        
        # 대소문자 구분 없이 비교하기 위해 소문자로 변환
        completed_keywords_set = set(k.lower() for k in completed_keywords)
        print(f"[EMBED][Protocol.io] 임베딩 대상 키워드 목록 (is_completed=True & is_embeded=False): {completed_keywords}")
        print(f"[EMBED][Protocol.io] 대소문자 무시 비교용 키워드 집합: {completed_keywords_set}")
    except Exception as e:
        print(f"[EMBED][Protocol.io] ⚠️  스케줄 테이블 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        print(f"[EMBED][Protocol.io] 임베딩을 중단합니다. (예외 발생 시 모든 키워드를 처리하지 않음)")
        return  # 예외 발생 시 중단 (모든 키워드 처리 방지)
    
    # 분할된 청크 파일 우선 사용, 없으면 기존 청크 파일 사용
    # chunk는 cleaned 실행 후 바로 실행되므로 오늘 날짜의 파일만 가져옴
    all_input_files = []
    today = datetime.now()
    today_date_str = today.strftime("%Y%m%d")
    
    if USE_SPLIT_CHUNKS:
        # 분할된 청크 파일 찾기: data/chunks/protocols/{날짜}_{시분}/{keyword}/protocol_chunked_{keyword}_part*.csv
        # 오늘 날짜의 디렉토리만 검색 (cleaned/chunk 실행 날짜)
        print(f"[EMBED][Protocol.io] 분할된 청크 파일 검색 중: {CHUNKS_SPLIT_ROOT} (오늘 날짜: {today_date_str})")
        if CHUNKS_SPLIT_ROOT.exists():
            # 오늘 날짜로 시작하는 날짜_시분 디렉토리만 찾기 (예: 20251226_0611)
            for date_time_dir in sorted(CHUNKS_SPLIT_ROOT.iterdir()):
                if date_time_dir.is_dir() and "_" in date_time_dir.name:
                    # 날짜 부분만 추출하여 오늘 날짜와 비교
                    dir_date_str = date_time_dir.name.split("_")[0]
                    if dir_date_str == today_date_str:
                        # 키워드 디렉토리 찾기
                        for keyword_dir in sorted(date_time_dir.iterdir()):
                            if keyword_dir.is_dir():
                                keyword = keyword_dir.name
                                part_files = sorted(keyword_dir.glob("protocol_chunked_*_part*.csv"))
                                all_input_files.extend(part_files)
                                if part_files:
                                    print(f"[EMBED][Protocol.io] 키워드 '{keyword}' ({date_time_dir.name}): {len(part_files)}개 분할 파일 발견")
        
        # 분할된 파일이 없으면 기존 청크 파일 사용 (fallback)
        if not all_input_files:
            print(f"[EMBED][Protocol.io] 분할된 파일이 없어 기존 청크 파일 검색 중...")
            date_pattern = f"year={today.year:04d}/month={today.month:02d}/day={today.day:02d}/stage=chunked"
            all_input_files = sorted(INPUT_ROOT.glob(f"**/{date_pattern}/protocol_chunked_*.csv"))
    else:
        # 기존 방식: 오늘 날짜의 청크 파일 사용
        date_pattern = f"year={today.year:04d}/month={today.month:02d}/day={today.day:02d}/stage=chunked"
        all_input_files = sorted(INPUT_ROOT.glob(f"**/{date_pattern}/protocol_chunked_*.csv"))
    
    # 완료된 키워드만 필터링 (대소문자 구분 없이 비교)
    if completed_keywords:
        input_files = []
        for csv_path in all_input_files:
            # 파일명에서 키워드 추출
            # 분할 파일: protocol_chunked_{keyword}_part{번호}.csv
            # 기존 파일: protocol_chunked_{keyword}.csv
            filename = csv_path.stem
            if "_part" in filename:
                # 분할 파일: protocol_chunked_{keyword}_part{번호} -> keyword 추출
                keyword = filename.replace("protocol_chunked_", "").split("_part")[0]
            else:
                # 기존 파일: protocol_chunked_{keyword}
                keyword = filename.replace("protocol_chunked_", "")
            
            # 대소문자 구분 없이 비교
            if keyword.lower() in completed_keywords_set:
                input_files.append(csv_path)
                print(f"[EMBED][Protocol.io] ✅ 키워드 '{keyword}' 포함 (임베딩 대상)")
            else:
                print(f"[EMBED][Protocol.io] ⏭️  키워드 '{keyword}'는 아직 완료되지 않아 건너뜁니다. (is_completed=False 또는 is_embeded=True)")
    else:
        # completed_keywords가 None이면 처리하지 않음 (이미 위에서 return했음)
        print(f"[EMBED][Protocol.io] ⚠️  completed_keywords가 None입니다. 처리할 파일이 없습니다.")
        input_files = []
    
    if not input_files:
        if completed_keywords:
            print(f"[EMBED][Protocol.io] 완료된 키워드({completed_keywords})의 chunk 파일이 없습니다.")
        else:
            print(f"[EMBED][Protocol.io] 오늘 날짜({today.strftime('%Y-%m-%d')})의 처리할 입력 파일이 없습니다.")
        return

    print(f"[EMBED][Protocol.io] 처리할 파일 수: {len(input_files)}/{len(all_input_files)}")
    
    # 키워드별로 그룹화하여 처리 (각 키워드의 모든 파일이 완료되면 is_embeded=True로 설정)
    # completed_keywords가 None이면 이미 위에서 return했으므로 여기 도달하지 않음
    if completed_keywords:
        # 키워드별로 파일 그룹화 (원본 키워드 대소문자 유지)
        keyword_files = {}
        for csv_path in input_files:
            filename = csv_path.stem
            if "_part" in filename:
                keyword = filename.replace("protocol_chunked_", "").split("_part")[0]
            else:
                keyword = filename.replace("protocol_chunked_", "")
            
            if keyword not in keyword_files:
                keyword_files[keyword] = []
            keyword_files[keyword].append(csv_path)
        
        # completed_keywords의 원본 키워드와 keyword_files의 키워드를 매칭하여 처리
        # 대소문자 차이를 고려하여 매칭
        processed_keywords = set()
        for keyword_from_db in completed_keywords:
            # keyword_files에서 대소문자 구분 없이 매칭
            matched_keyword = None
            for file_keyword in keyword_files.keys():
                if file_keyword.lower() == keyword_from_db.lower():
                    matched_keyword = file_keyword
                    break
            
            if matched_keyword is None:
                print(f"[EMBED][Protocol.io] ⚠️  키워드 '{keyword_from_db}'의 파일이 없습니다. 건너뜁니다.")
                continue
            
            # 이미 처리된 키워드는 건너뛰기 (중복 방지)
            if matched_keyword in processed_keywords:
                continue
            processed_keywords.add(matched_keyword)
            
            files_for_keyword = keyword_files[matched_keyword]
            print(f"[EMBED][Protocol.io] 키워드 '{matched_keyword}' (DB: '{keyword_from_db}') 처리 시작: {len(files_for_keyword)}개 파일")

            print(f"[EMBED][Protocol.io] 키워드 '{matched_keyword}' 처리 시작")

            # ✅ (1) table metadata 경로 생성
            table_csv_path = (
                BASE_PATH
                / "data/entities/protocols/success"
                / f"protocol_table_{matched_keyword}.csv"
            )

            # ✅ (2) table metadata 로드 (키워드당 1회)
            table_metadata_map = load_table_metadata(table_csv_path)

            # ✅ (3) 해당 키워드의 모든 chunk 파일 처리
            for csv_path in files_for_keyword:
                process_file(
                    csv_path,
                    table_metadata_map=table_metadata_map,  # ← 반드시 전달
                )
            
            # 키워드의 모든 파일 처리가 완료되면 is_embeded=True로 설정 (DB의 원본 키워드 사용)
            print(f"[EMBED][Protocol.io] 키워드 '{matched_keyword}' (DB: '{keyword_from_db}')의 모든 파일 처리 완료. is_embeded=True로 설정합니다.")
            schedule_store.update_is_embeded(keyword_from_db)

    print("[EMBED][Protocol.io] 🎉 모든 파일 처리 완료!")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[EMBED][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


def run(chunks_dir: str | None = None, embeddings_dir: str | None = None) -> None:
    """
    pipeline_runner.run_embed에서 사용하는 엔트리 포인트.
    
    Args:
        chunks_dir: 청크 파일 디렉토리 (현재는 사용하지 않음, 오늘 날짜 기준으로 자동 탐색)
        embeddings_dir: 임베딩 CSV 출력 디렉토리
    """
    main(embeddings_dir=embeddings_dir)


if __name__ == "__main__":
    main()
