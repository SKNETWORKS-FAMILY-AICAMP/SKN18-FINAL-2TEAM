import pandas as pd
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
import os

# --------------------------
# 1. Load .env
# --------------------------
load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
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
            chunking_id TEXT,
            url TEXT,
            title TEXT,
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
# 5. DB 삽입
# --------------------------
def insert_row(chunking_id: str, url: str, title: str, text: str, embedding: list):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO documents (chunking_id, url, title, text, embedding)
        VALUES (%s, %s, %s, %s, %s);
    """, (chunking_id, url, title, text, embedding))

    conn.commit()
    cur.close()
    conn.close()

# --------------------------
# 6. <abstract>, <step_content>, <guidelines> 분리 => 요청 토큰 초과 방지
# --------------------------

def split_sections(text):
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
            sections[tag] = text[start_idx:end_idx].strip()
        else:
            # Last section till end of text
            sections[tag] = text[start_idx:].strip()
    return sections

# --------------------------
# 7. CSV 처리 메인 로직
# --------------------------
def process_csv(csv_path: str):
    print(f"📂 CSV 불러오는 중: {csv_path}")
    df = pd.read_csv(csv_path)

    if "text" not in df.columns:
        raise ValueError("❌ CSV 파일에 'text' 컬럼이 없습니다.")

    print(f"🔍 총 {len(df)}개의 행 처리 시작")

    for idx, row in df.iterrows():
        text = str(row["text"]).strip()
        chunking_id = str(row["chunking_id"])
        url = str(row["url"])
        title = str(row["title"])

        sections = split_sections(text)
        if not sections:
            continue

        for key, val in sections.items():
            # 임베딩 생성
            for n, e in enumerate(val.split("\n")):
                if e.strip() == "":
                    continue
                
                if n == 0:
                    embedding = embed_text(key + "\n" + e)
                    save_text = key + "\n" + e
                else:
                    embedding = embed_text(e)
                    save_text = e

                # ⚡ DB 저장 (5개 인자 전달)
                insert_row(chunking_id, url, title, save_text, embedding)

        print(f"✓ {idx + 1}/{len(df)} 저장 완료")

    print("🎉 모든 CSV 데이터 임베딩 및 삽입 완료!")


# --------------------------
# 7. 실행
# --------------------------
if __name__ == "__main__":
    create_table()
    process_csv("./data/chunked_text_cleaned_data_Cell.csv")