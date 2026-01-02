"""
Protocols.io 임베딩 CSV 파일을 PostgreSQL pgvector 테이블에 업서트한다.

입력: data/embeddings/protocols/protocol_embedded_{keyword}.csv
출력: PostgreSQL ts_protocol_embedding 테이블에 저장
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Generator

# 패키지 형태로 실행하지 않아도 rag.* 모듈을 찾을 수 있도록 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.etl.common.db_connection import get_connection
from rag.etl.step01_ingest.modules import schedule_store

TABLE_NAME = "ts_protocol_embedding"
EMBEDDING_DIM = 1024
BATCH_SIZE = int(os.getenv("PROTOCOL_UPSERT_BATCH_SIZE", "1000"))


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
                    chunking_id TEXT UNIQUE NOT NULL,
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
        print(f"[UPSERT][Protocol.io] 테이블 확인 완료: {TABLE_NAME}")


def infer_vector_dim_from_str(vec_str: str) -> int:
    """
    "[0.1, 0.2, ...]" / "0.1,0.2,..." 같은 문자열에서 실제 원소 개수를 셉니다.
    """
    if vec_str is None:
        return 0
    s = vec_str.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    if not s.strip():
        return 0
    parts = s.split(",")
    parts = [p.strip() for p in parts if p.strip() != ""]
    return len(parts)


def iter_csv_rows(csv_path: Path) -> Generator[dict[str, str], None, None]:
    """
    임베딩 CSV 파일을 row-by-row로 읽는 제너레이터입니다.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"임베딩 CSV 파일을 찾을 수 없습니다: {csv_path}")

    required_cols = ["chunking_id", "url", "title", "text", "embedding"]
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as inf:
        reader = csv.DictReader(inf)
        # 헤더 검증
        if reader.fieldnames is None:
            raise ValueError(f"CSV 파일에 헤더가 없습니다: {csv_path}")
        
        missing = [c for c in required_cols if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV 파일에 필요한 컬럼이 없습니다: {missing} (파일: {csv_path})")

        for r in reader:
            yield r


def upsert_csv(csv_path: Path, expected_dim: int = EMBEDDING_DIM, batch_size: int = BATCH_SIZE) -> None:
    """
    CSV 파일을 읽어서 PostgreSQL 테이블에 업서트한다.
    
    Args:
        csv_path: 임베딩 CSV 파일 경로
        expected_dim: 예상되는 임베딩 차원 (기본값: 1536)
        batch_size: 배치 크기 (기본값: 1000)
    """
    print(f"[UPSERT][Protocol.io] CSV 파일 로드 시작: {csv_path}")
    
    with get_connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            try:
                rows_buffer = []
                row_idx = 0
                total_inserted = 0

                for row in iter_csv_rows(csv_path):
                    row_idx += 1

                    # embedding 문자열 검증
                    embedding_str = row["embedding"]
                    vec_len = infer_vector_dim_from_str(embedding_str)
                    if vec_len != expected_dim:
                        raise ValueError(
                            f"[UPSERT][Protocol.io] embedding vector length({vec_len}) != expected_dim({expected_dim}) "
                            f"at row {row_idx} (chunking_id={row.get('chunking_id')})"
                        )

                    # 데이터 준비
                    rows_buffer.append((
                        row["chunking_id"],
                        row["url"],
                        row["title"],
                        row["text"],
                        embedding_str,
                    ))

                    # 배치 크기에 도달하면 DB에 저장
                    if len(rows_buffer) >= batch_size:
                        cur.executemany(
                            f"""
                            INSERT INTO {TABLE_NAME} (
                                chunking_id,
                                url,
                                title,
                                text,
                                embedding
                            )
                            VALUES (
                                %s, %s, %s, %s, %s::vector
                            )
                            ON CONFLICT (chunking_id)
                            DO UPDATE SET
                                url = EXCLUDED.url,
                                title = EXCLUDED.title,
                                text = EXCLUDED.text,
                                embedding = EXCLUDED.embedding;
                            """,
                            rows_buffer,
                        )
                        total_inserted += len(rows_buffer)
                        rows_buffer.clear()
                        print(f"[UPSERT][Protocol.io] 배치 저장 완료: {total_inserted}개 행 처리됨", flush=True)

                # 남은 데이터 저장
                if rows_buffer:
                    cur.executemany(
                        f"""
                        INSERT INTO {TABLE_NAME} (
                            chunking_id,
                            url,
                            title,
                            text,
                            embedding
                        )
                        VALUES (
                            %s, %s, %s, %s, %s::vector
                        )
                        ON CONFLICT (chunking_id)
                        DO UPDATE SET
                            url = EXCLUDED.url,
                            title = EXCLUDED.title,
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding;
                        """,
                        rows_buffer,
                    )
                    total_inserted += len(rows_buffer)
                    print(f"[UPSERT][Protocol.io] 마지막 배치 저장 완료: 총 {total_inserted}개 행 처리됨", flush=True)

                conn.commit()
                print(f"[UPSERT][Protocol.io] ✅ 업서트 완료: {csv_path} → {total_inserted}개 행 저장됨")

            except Exception as e:
                conn.rollback()
                print(f"[UPSERT][Protocol.io] ❌ 오류 발생: {e}")
                raise


def run(embeddings_dir: str) -> None:
    """
    ETL 파이프라인용 엔트리 포인트.
    
    Args:
        embeddings_dir: 임베딩 CSV 파일이 있는 디렉토리 (예: data/embeddings/protocols)
                       키워드별 하위 디렉토리 구조: {embeddings_dir}/{keyword}/protocol_embedded_{keyword}.csv
    """
    embeddings_path = Path(embeddings_dir)
    
    # embeddings_dir이 이미 "protocols"까지 포함하고 있는지 확인
    if embeddings_path.name == "protocols":
        protocols_root = embeddings_path
    else:
        protocols_root = embeddings_path / "protocols"

    success_dir = protocols_root / "success"

    if not success_dir.exists():
        print(f"[UPSERT][Protocol.io] ⚠️ success 디렉토리가 존재하지 않습니다: {success_dir}")
        return
    
    # 테이블 생성 확인
    ensure_table()

    # 스케줄 테이블에서 is_embeded=True인 키워드만 조회
    try:
        schedule_store.ensure_table()
        embedded_keywords = schedule_store.get_embedded_keywords()
    except Exception as e:
        print(f"[UPSERT][Protocol.io] ⚠️  스케줄 테이블 조회 실패: {e}")
        return

    if not embedded_keywords:
        print("[UPSERT][Protocol.io] ⚠️  is_embeded=True인 키워드가 없어 업서트를 건너뜁니다.")
        return

    embedded_keywords_set = {k.lower(): k for k in embedded_keywords}
    keyword_to_files: dict[str, list[Path]] = {}

    for lower_keyword, original_keyword in embedded_keywords_set.items():
        csv_name = f"protocol_embedded_{original_keyword}.csv"

        # 대소문자 무시 검색
        matched_files = list(
            success_dir.glob(f"**/{csv_name}")
        )


        if not matched_files:
            print(
                f"[UPSERT][Protocol.io] ⚠️  키워드 '{original_keyword}'의 임베딩 CSV를 찾을 수 없습니다. ({csv_name})",
                flush=True,
            )
            continue

        keyword_to_files[original_keyword] = matched_files

    if not keyword_to_files:
        print("[UPSERT][Protocol.io] ⚠️  처리할 CSV 파일이 없습니다 (is_embeded=True 조건에 해당하는 디렉토리 없음).")
        return
    
    # 키워드별 디렉토리에서 protocol_embedded_*.csv 파일 찾기
    # 구조: {protocols_dir}/{keyword}/protocol_embedded_{keyword}.csv
    total_files = sum(len(files) for files in keyword_to_files.values())
    print(f"[UPSERT][Protocol.io] 임베딩 완료 키워드 수: {len(keyword_to_files)} (총 파일 {total_files}개)")

    for keyword, files in keyword_to_files.items():
        print(f"[UPSERT][Protocol.io] ▶ 키워드 '{keyword}' 처리 시작 ({len(files)}개 파일)")
        for csv_path in files:
            print(f"[UPSERT][Protocol.io]   - {csv_path.name}")
            try:
                upsert_csv(csv_path, expected_dim=EMBEDDING_DIM, batch_size=BATCH_SIZE)
            except Exception as e:
                print(f"[UPSERT][Protocol.io] ❌ 파일 처리 실패: {csv_path.name} - {e}")
                raise
    
    print(f"[UPSERT][Protocol.io] 🎉 모든 파일 처리 완료!")


def main() -> None:
    """직접 실행용 엔트리 포인트"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Protocols.io 임베딩 CSV를 PostgreSQL에 업서트")
    parser.add_argument(
        "--embeddings-dir",
        type=str,
        default=os.getenv("ETL_EMBEDDINGS_DIR", "data/embeddings/protocols"),
        help="임베딩 CSV 파일 디렉토리 (기본값: data/embeddings/protocols)",
    )
    
    args = parser.parse_args()
    run(args.embeddings_dir)


if __name__ == "__main__":
    main()
