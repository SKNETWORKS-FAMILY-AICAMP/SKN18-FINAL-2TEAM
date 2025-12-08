import pandas as pd
import psycopg2
import json
import glob
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import os

# --------------------------
# 1. Load .env
# --------------------------
load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "pmc_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "pmc")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pmc1234")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI 초기화
client = OpenAI(api_key=OPENAI_API_KEY)


# --------------------------
# 2. DB 연결
# --------------------------
def get_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


# --------------------------
# 3. 테이블 생성
# --------------------------
def create_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY, 
            chunk_id TEXT UNIQUE, 
            nctid TEXT,
            text TEXT,
            embedding vector(1536)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


# --------------------------
# 4. 임베딩 생성
# --------------------------
def embed_text(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# --------------------------
# 5. JSON chunk 파싱
# --------------------------
def parse_chunk_json(chunk_str: str) -> str:
    """Parse JSON chunk and extract text content."""
    try:
        chunk_data = json.loads(chunk_str)
        # Extract all text values from the JSON object
        texts = []
        for key, value in chunk_data.items():
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
        return " ".join(texts) if texts else chunk_str
    except (json.JSONDecodeError, TypeError):
        # If parsing fails, return the original string
        return chunk_str


# --------------------------
# 6. DB 삽입
# --------------------------
def insert_row(chunk_id: str, nctid: str, text: str, embedding: list):
    conn = get_connection()
    cur = conn.cursor()

    # Convert embedding list to pgvector format string
    embedding_str = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"

    cur.execute("""
        INSERT INTO documents (chunk_id, nctid, text, embedding)
        VALUES (%s, %s, %s, %s::vector)
        ON CONFLICT (chunk_id) DO UPDATE SET
            nctid = EXCLUDED.nctid,
            text = EXCLUDED.text,
            embedding = EXCLUDED.embedding;
    """, (chunk_id, nctid, text, embedding_str))

    conn.commit()
    cur.close()
    conn.close()


# --------------------------
# 7. CSV 처리 메인 로직
# --------------------------
def process_csv(csv_path: str):
    print(f"[INFO] CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)

    # 필수 컬럼 확인
    required_cols = ["nctid", "chunk_id", "chunk"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"[ERROR] CSV 파일에 필요한 컬럼이 없습니다: {missing}")

    print(f"[INFO] 총 {len(df)}개의 행 처리 시작")

    for idx, row in df.iterrows():
        try:
            nctid = str(row["nctid"]).strip()
            chunk_id = str(row["chunk_id"]).strip()
            chunk_json = str(row["chunk"]).strip()

            if not chunk_json:
                continue

            # JSON chunk 파싱하여 텍스트 추출
            text = parse_chunk_json(chunk_json)

            if not text:
                continue

            # 임베딩 생성
            embedding = embed_text(text)

            # DB 저장
            insert_row(chunk_id, nctid, text, embedding)
            
            if (idx + 1) % 100 == 0:
                print(f"[OK] {idx + 1}/{len(df)} 저장 완료")
        except Exception as e:
            print(f"[ERROR] Row {idx + 1} 처리 실패: {e}")
            continue

    print(f"[SUCCESS] {csv_path} 처리 완료!")


# --------------------------
# 8. 여러 CSV 파일 처리
# --------------------------
def process_clinical_folder(folder_path: str):
    """Process all test_chunk7*.csv files in the clinical folder."""
    folder = Path(folder_path)
    csv_files = sorted(glob.glob(str(folder / "test_chunk7*.csv")))
    
    if not csv_files:
        raise FileNotFoundError(f"[ERROR] No test_chunk7 CSV files found in {folder_path}")
    
    print(f"[INFO] Found {len(csv_files)} CSV files to process")
    
    for csv_file in csv_files:
        print(f"\n{'='*60}")
        print(f"[INFO] Processing: {Path(csv_file).name}")
        print(f"{'='*60}")
        process_csv(csv_file)
    
    print(f"\n[SUCCESS] 모든 CSV 파일 처리 완료!")


# --------------------------
# 9. 실행
# --------------------------
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process clinical trial data and create embeddings")
    parser.add_argument(
        "--input",
        type=str,
        default="../data/clinical",
        help="Clinical data folder path or single CSV file path (default: ../data/clinical)"
    )
    args = parser.parse_args()
    
    # 테이블 생성
    print("[INFO] Creating database table...")
    create_table()
    print("[OK] Table created/verified")
    
    # CSV 파일 처리
    input_path = Path(args.input)
    if input_path.is_dir():
        process_clinical_folder(str(input_path))
    else:
        process_csv(str(input_path))



