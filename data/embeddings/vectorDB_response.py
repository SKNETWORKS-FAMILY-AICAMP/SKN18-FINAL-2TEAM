import psycopg2
import numpy as np
import os
from dotenv import load_dotenv
from openai import OpenAI

# env 로드
load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI()

# -----------------------------------------
# 임베딩 생성 함수 (예: OpenAI, HuggingFace 등)
# -----------------------------------------
def embed(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding  # 리스트 형태 (1536차원)


# -----------------------------------------
# PGVector 기반 Top-5 chunking_id 검색 + 전체 text 반환
# -----------------------------------------
def search_related_chunks(query):
    query_vec = embed(query)
    query_vec_str = "[" + ",".join(map(str, query_vec)) + "]"  # 벡터를 '[0.1,0.2,...]' 문자열로 변환
    
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    sql_top5 = """
    SELECT id, chunking_id, text, 1 - (embedding <=> %s::vector) AS similarity
    FROM documents
    ORDER BY embedding <=> %s::vector
    LIMIT 5;
    """
    
    cur.execute(sql_top5, (query_vec_str, query_vec_str))
    top_rows = cur.fetchall()


    # 결과 예:
    # (id, chunking_id, text, similarity)

    if not top_rows:
        return {"result": [], "message": "검색 결과 없음"}

    # ---------------------------------------------------
    # STEP 2: chunking_id 그룹핑 및 대표 similarity 설정
    # ---------------------------------------------------
    chunk_map = {}   # { chunking_id : {"similarity": float, "texts": []} }

    for row in top_rows:
        _, chunking_id, text, similarity = row
        if chunking_id not in chunk_map:
            # 대표 similarity는 해당 chunking_id의 가장 높은 chunk 유사도
            chunk_map[chunking_id] = {
                "similarity": float(similarity),
                "texts": []
            }

    # ---------------------------------------------------
    # STEP 3: 동일 chunking_id 전체 text 재조회
    # ---------------------------------------------------
    chunk_ids = tuple(chunk_map.keys())

    sql_alltexts = """
        SELECT chunking_id, text
        FROM documents
        WHERE chunking_id IN %s
        ORDER BY chunking_id, id;
    """
    cur.execute(sql_alltexts, (chunk_ids,))
    all_text_rows = cur.fetchall()

    # all_text_rows 예:
    # (chunking_id, text)

    for row in all_text_rows:
        chunking_id, text = row
        chunk_map[chunking_id]["texts"].append(text)

    conn.close()

    # ---------------------------------------------------
    # STEP 4: JSON 구조로 정리하여 최종 반환
    # ---------------------------------------------------
    result_list = []
    for cid, data in chunk_map.items():
        result_list.append({
            "chunking_id": cid,
            "similarity": data["similarity"],
            "texts": data["texts"]
        })

    # similarity 높은 순으로 정렬
    result_list.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "query": query,
        "result_count": len(result_list),
        "results": result_list
    }



# -----------------------------------------
# 실행 예시
# -----------------------------------------
if __name__ == "__main__":
    query = input("Enter the question: ")
    result = search_related_chunks(query)
    
    if result["result_count"] == 0:
        print("검색 결과가 없습니다.")
    else:
        print(f'쿼리: {result["query"]}')
        print(f'총 결과 개수: {result["result_count"]}\n')

        for rank, item in enumerate(result["results"], start=1):
            chunk_id = item["chunking_id"]
            similarity = item["similarity"]
            # texts 리스트에서 첫 번째 텍스트 일부만 출력 (100자 제한)
            text_preview = item["texts"][0][:100].replace('\n', ' ') + ("..." if len(item["texts"][0]) > 100 else "")
            
            print(f"Rank: {rank}")
            print(f"Chunk ID: {chunk_id}")
            print(f"Similarity: {similarity:.4f}")
            print(f"Text Preview: {text_preview}")
            print("-" * 50)