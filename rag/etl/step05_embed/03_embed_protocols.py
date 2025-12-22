"""
Protocols.io 청크 데이터를 임베딩하여 PostgreSQL에 저장한다.

입력: data/processed/protocols/success/.../stage=chunked/protocol_chunked_{keyword}.csv
출력: PostgreSQL pgvector 테이블에 직접 저장
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

from rag.etl.common.db_connection import get_connection

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다.")

# OpenAI 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

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
INPUT_ROOT = BASE_PATH / "data/processed/protocols/success"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
TABLE_NAME = "ts_protocol_embedding"

# 단순 모드 설정 (환경 변수로 제어 가능)
USE_SIMPLE_MODE = os.getenv("PROTOCOL_EMBED_SIMPLE_MODE", "false").lower() == "true"


def ensure_table() -> None:
    """pgvector 확장 및 테이블 생성"""
    with get_connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            # pgvector 확장 설치
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # 테이블 생성
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    chunking_id TEXT UNIQUE,
                    url TEXT,
                    title TEXT,
                    text TEXT,
                    embedding vector({EMBEDDING_DIM})
                );
            """)
            
            # 인덱스 생성 (선택적, 검색 성능 향상)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx 
                ON {TABLE_NAME} 
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
        conn.commit()


def embed_text(text: str) -> list[float]:
    """텍스트를 임베딩 벡터로 변환"""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


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


def insert_row(chunking_id: str, url: str, title: str, text: str, embedding: list[float]) -> None:
    """PostgreSQL에 임베딩 데이터 삽입 (UPSERT)"""
    with get_connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {TABLE_NAME} (chunking_id, url, title, text, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chunking_id)
                DO UPDATE SET
                    url = EXCLUDED.url,
                    title = EXCLUDED.title,
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding;
            """, (chunking_id, url, title, text, embedding))
        conn.commit()


def process_csv_simple(csv_path: Path, keyword: str) -> None:
    """
    단순 모드: 텍스트 전체를 그대로 임베딩 (소스 파일 방식)
    섹션 분리 없이 각 행의 전체 텍스트를 직접 임베딩한다.
    """
    print(f"[EMBED][Protocol.io][{keyword}] >>> CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path)

    # text 컬럼 검증 (소스 파일 방식)
    if "text" not in df.columns:
        raise ValueError("❌ CSV 파일에 'text' 컬럼이 없습니다.")

    print(f"[EMBED][Protocol.io][{keyword}] 🔍 총 {len(df)}개의 행 처리 시작")

    for idx, row in df.iterrows():
        text = str(row["text"]).strip()
        
        # chunking_id, url, title은 선택적 (없으면 빈 문자열)
        chunking_id = str(row.get("chunking_id", ""))
        url = str(row.get("url", ""))
        title = str(row.get("title", ""))

        if not text:
            continue

        # 텍스트 전체를 그대로 embedding
        embedding = embed_text(text)

        # 한 줄로 DB에 저장
        insert_row(chunking_id, url, title, text, embedding)

        print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} embedding 완료")

    print(f"[EMBED][Protocol.io][{keyword}] 🎉 모든 CSV 데이터 임베딩 및 삽입 완료!")

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


def process_csv(csv_path: Path, keyword: str) -> None:
    """CSV 파일을 읽어서 임베딩 생성 및 DB 저장"""
    # 단순 모드 사용 여부 확인
    if USE_SIMPLE_MODE:
        return process_csv_simple(csv_path, keyword)
    
    print(f"[EMBED][Protocol.io][{keyword}] >>> CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path)

    required_columns = ["chunking_id", "url", "title", "text"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"*** !!! CSV 파일에 필수 컬럼이 없습니다: {missing_columns} !!! ***")

    print(f"[EMBED][Protocol.io][{keyword}] 🔍 총 {len(df)}개의 행 처리 시작")

    for idx, row in df.iterrows():
        text = str(row["text"]).strip()
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
            insert_row(chunking_id, url, title, text, embedding)
            print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} 저장 완료 (전체 텍스트)")
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
                
                # DB 저장
                insert_row(section_chunking_id, url, title, save_text, embedding)

        print(f"[EMBED][Protocol.io][{keyword}] ✓ {idx + 1}/{len(df)} 저장 완료")

    print(f"[EMBED][Protocol.io][{keyword}] 🎉 CSV 처리 완료: {csv_path}")


def process_file(csv_path: Path) -> None:
    """단일 CSV 파일 처리 (에러 핸들링 포함)"""
    keyword = csv_path.stem.replace("protocol_chunked_", "")
    try:
        process_csv(csv_path, keyword)
        print(f"[EMBED][Protocol.io][{keyword}] 처리 완료")
    except Exception as exc:
        print(f"[EMBED][Protocol.io][{keyword}] 실패: {exc}")
        raise


def main() -> None:
    """메인 함수: 오늘 날짜의 chunked CSV 파일만 처리"""
    start_time = datetime.now()
    print(f"[EMBED][Protocol.io] TIMESTAMP_START={start_time.isoformat()}", flush=True)
    
    # 처리 모드 출력
    mode = "단순 모드" if USE_SIMPLE_MODE else "섹션 분리 모드"
    print(f"[EMBED][Protocol.io] 처리 모드: {mode}")
    
    ensure_table()
    
    # 오늘 날짜의 청크 파일만 필터링
    today = datetime.now()
    date_pattern = f"year={today.year:04d}/month={today.month:02d}/day={today.day:02d}/stage=chunked"
    input_files = sorted(INPUT_ROOT.glob(f"**/{date_pattern}/protocol_chunked_*.csv"))
    
    if not input_files:
        print(f"[EMBED][Protocol.io] 오늘 날짜({today.strftime('%Y-%m-%d')})의 처리할 입력 파일이 없습니다.")
        return

    print(f"[EMBED][Protocol.io] 오늘 날짜({today.strftime('%Y-%m-%d')})의 발견된 파일 수: {len(input_files)}")
    
    for csv_path in input_files:
        print(f"[EMBED][Protocol.io] processing {csv_path}")
        process_file(csv_path)

    print("[EMBED][Protocol.io] 🎉 모든 파일 처리 완료!")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[EMBED][Protocol.io] TIMESTAMP_END={end_time.isoformat()} | DURATION={duration:.2f}초", flush=True)


if __name__ == "__main__":
    main()
