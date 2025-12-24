# run_system_b_patched_v5_graph_rag.py
# System B (Enhanced): Postgres 벡터검색 + Neo4j Graph RAG (Entity+Text) + Python RRF
# - Logic: Keyword Node Hit -> Expand to Chunks (Graph Traversal)
# - Logic: Chunk Node Hit -> Direct Use (Fulltext)

import os
import argparse
import csv
import time
import json
from typing import List, Dict, Tuple, Any, Optional

import psycopg2
from neo4j import GraphDatabase
from openai import OpenAI

# Optional: load environment variables from a local .env file
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────
# Common: PG / Neo4j / Embedding
# ─────────────────────────────────────

def get_pg_conn():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")
        user = os.getenv("POSTGRES_USER", "postgres")
        pw = os.getenv("POSTGRES_PASSWORD", "postgres")
        dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg2.connect(dsn)


def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def _embedding_client(model_override: Optional[str] = None) -> Tuple[OpenAI, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    model = model_override or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    return OpenAI(api_key=api_key), model


def get_query_embedding_with_usage(
    query_text: str,
    embedding_model: Optional[str] = None,
) -> Tuple[List[float], Dict[str, Any], float]:
    """Return (embedding, usage_dict, latency_ms)."""
    client, model = _embedding_client(model_override=embedding_model)
    t0 = time.perf_counter()
    resp = client.embeddings.create(model=model, input=query_text)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    usage: Dict[str, Any] = {"model": model}
    if getattr(resp, "usage", None) is not None:
        u = resp.usage
        usage.update({
            "prompt_tokens": getattr(u, "prompt_tokens", None),
            "total_tokens": getattr(u, "total_tokens", None),
        })
    return resp.data[0].embedding, usage, dt_ms


# ─────────────────────────────────────
# Fulltext index detection
# ─────────────────────────────────────

def _list_fulltext_indexes(driver) -> List[Dict[str, Any]]:
    queries = [
        "SHOW FULLTEXT INDEXES YIELD name, entityType, labelsOrTypes, properties RETURN name, entityType, labelsOrTypes, properties",
        "CALL db.indexes() YIELD name, type, entityType, labelsOrTypes, properties WHERE type = 'FULLTEXT' RETURN name, entityType, labelsOrTypes, properties",
    ]
    for q in queries:
        try:
            with driver.session() as session:
                rs = session.run(q)
                out = []
                for r in rs:
                    out.append({
                        "name": r.get("name"),
                        "entityType": r.get("entityType"),
                        "labelsOrTypes": r.get("labelsOrTypes"),
                        "properties": r.get("properties"),
                    })
                return out
        except Exception:
            continue
    return []


def pick_fulltext_chunk_index(driver) -> Tuple[Optional[str], Dict[str, Any]]:
    # 1. 환경변수 우선
    override = os.getenv("FULLTEXT_CHUNK_INDEX")
    
    # 2. 우리가 합의한 통합 인덱스 이름 (Chunk + Keyword)
    preferred = "integrated_search_index"

    idxs = _list_fulltext_indexes(driver)
    by_name = {i.get("name"): i for i in idxs if i.get("name")}

    def _exists(name: str) -> bool:
        return name in by_name

    if override and _exists(override):
        return override, by_name[override]

    if _exists(preferred):
        return preferred, by_name[preferred]

    # 3. 없으면 기존 로직대로 'Chunk'에 걸린 인덱스 중 아무거나 찾음
    # (주의: 이 경우 Keyword 검색 로직은 작동 안 할 수 있음)
    chunk_candidates = []
    for i in idxs:
        labels = i.get("labelsOrTypes") or []
        if isinstance(labels, str):
            labels = [labels]
        # Chunk 혹은 Keyword가 포함된 인덱스를 찾음
        if "Chunk" in labels or "Keyword" in labels:
            chunk_candidates.append(i)

    def _score(i: Dict[str, Any]) -> int:
        props = i.get("properties") or []
        if isinstance(props, str):
            props = [props]
        # text와 name이 다 있으면 금상첨화
        score = 0
        if "text" in props: score += 2
        if "name" in props: score += 1
        return score

    if chunk_candidates:
        chunk_candidates.sort(key=_score, reverse=True)
        chosen = chunk_candidates[0]
        return chosen.get("name"), chosen

    return None, {}


# ─────────────────────────────────────
# 1) Postgres vector search
# ─────────────────────────────────────

def pg_vector_search_article(
    conn,
    query_embedding: List[float],
    k_vec: int,
    ef_search: int = 100,
) -> List[Dict[str, Any]]:
    vec_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

    sql_set = "SET LOCAL hnsw.ef_search = %s;"
    sql = """
        SELECT chunk_id,
               1 - (embedding <=> %s::vector) AS vscore
        FROM article_section_embedding
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    with conn.cursor() as cur:
        cur.execute("BEGIN;")
        try:
            cur.execute(sql_set, (ef_search,))
        except Exception:
            pass
        cur.execute(sql, (vec_literal, vec_literal, k_vec))
        rows = cur.fetchall()
        cur.execute("COMMIT;")

    results: List[Dict[str, Any]] = []
    for chunk_id, vscore in rows:
        results.append({"chunk_id": chunk_id, "vscore": float(vscore)})
    return results


# ─────────────────────────────────────
# 2) Neo4j keyword search (Fulltext + Graph Traversal)
# ─────────────────────────────────────

def neo4j_keyword_search_chunks(
    driver,
    query_text: str,
    k_kw: int,
    fulltext_index: Optional[str],
) -> List[Dict[str, Any]]:
    """
    [Logic 1 + Logic 2 구현]
    - 인덱스에서 노드를 찾음 (Keyword 또는 Chunk)
    - Keyword라면 -> 관계(HAS_KEYWORD)를 타고 Chunk를 찾음 (Graph RAG)
    - Chunk라면 -> 바로 사용
    """
    if not fulltext_index or k_kw <= 0:
        return []

    cypher = f"""
    // 1. 통합 인덱스 검색 (Keyword 노드일 수도, Chunk 노드일 수도 있음)
    CALL db.index.fulltext.queryNodes('{fulltext_index}', $text, {{limit: $k_kw}})
    YIELD node, score

    // 2. [Logic 1] 만약 검색된 게 Keyword라면 -> 연결된 Chunk들을 펼친다(Expand)
    // (관계명이 HAS_KEYWORD가 아니라면 실제 스키마에 맞게 수정 필요)
    OPTIONAL MATCH (node)<-[:HAS_KEYWORD]-(linked_chunk:Chunk)

    // 3. [Logic 1 & 2 병합]
    // - linked_chunk가 있다? => Logic 1 (키워드 타고 옴)
    // - 없다? => node가 직접 Chunk인지 확인 => Logic 2 (본문 검색됨)
    WITH coalesce(linked_chunk, CASE WHEN node:Chunk THEN node END) AS final_chunk, score
    
    // 4. 유효한 Chunk만 남김
    WHERE final_chunk IS NOT NULL

    // 5. 결과 집계 (하나의 Chunk가 여러 경로로 검색될 수 있으므로 점수는 가장 높은 것으로)
    RETURN final_chunk.chunk_id AS chunk_id, max(score) AS kscore
    ORDER BY kscore DESC
    LIMIT $k_kw
    """
    
    with driver.session() as session:
        rs = session.run(cypher, text=query_text, k_kw=k_kw)
        return [r.data() for r in rs]


# ─────────────────────────────────────
# 3) Python RRF Fusion
# ─────────────────────────────────────

def rrf_fusion(
    vec_results: List[Dict[str, Any]],
    kw_results: List[Dict[str, Any]],
    k_final: int,
    rrf_k: int = 60,
) -> List[Tuple[str, float, List[str]]]:
    rank_map_vec: Dict[str, int] = {}
    for i, row in enumerate(vec_results):
        rank_map_vec[str(row["chunk_id"])] = i + 1

    rank_map_kw: Dict[str, int] = {}
    for i, row in enumerate(kw_results):
        rank_map_kw[str(row["chunk_id"])] = i + 1

    chunk_ids = set(rank_map_vec.keys()) | set(rank_map_kw.keys())

    fused: List[Tuple[str, float, List[str]]] = []
    for cid in chunk_ids:
        score = 0.0
        sources: List[str] = []
        if cid in rank_map_vec:
            score += 1.0 / (rrf_k + rank_map_vec[cid])
            sources.append("vector")
        if cid in rank_map_kw:
            score += 1.0 / (rrf_k + rank_map_kw[cid])
            sources.append("keyword")
        fused.append((cid, score, sources))

    fused.sort(key=lambda x: x[1], reverse=True)
    return fused[:k_final]


# ─────────────────────────────────────
# 4) Fetch chunk contexts from Neo4j
# ─────────────────────────────────────

def fetch_chunk_contexts(driver, chunk_ids: List[str]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []

    cypher = """
    UNWIND $ids AS cid
    MATCH (c:Chunk {chunk_id: cid})
    MATCH (c)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN c.chunk_id AS id,
           c.text AS text,
           a.title AS title,
           s.title AS section
    """
    with driver.session() as session:
        rs = session.run(cypher, ids=chunk_ids)
        rows = [r.data() for r in rs]

    # preserve input order
    by_id = {str(r["id"]): r for r in rows}
    out: List[Dict[str, Any]] = []
    for cid in chunk_ids:
        r = by_id.get(str(cid))
        if r:
            out.append(r)
    return out


def run_system_b_with_metrics(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    ef_search: int = 100,
    embedding_model: Optional[str] = None,
) -> Dict[str, Any]:
    t_total0 = time.perf_counter()

    embedding, emb_usage, emb_ms = get_query_embedding_with_usage(query_text, embedding_model=embedding_model)

    # Vector search (PG)
    t0 = time.perf_counter()
    conn = get_pg_conn()
    try:
        vec_results = pg_vector_search_article(conn, embedding, k_vec=k_vec, ef_search=ef_search)
    finally:
        conn.close()
    pg_ms = (time.perf_counter() - t0) * 1000.0

    # Keyword search (Neo4j Graph RAG)
    t1 = time.perf_counter()
    driver = get_neo4j_driver()
    try:
        ft_index, ft_meta = pick_fulltext_chunk_index(driver)
        kw_results = neo4j_keyword_search_chunks(driver, query_text, k_kw=k_kw, fulltext_index=ft_index)
        
        # Fuse
        fused = rrf_fusion(vec_results, kw_results, k_final=k_final, rrf_k=rrf_k)
        fused_ids = [cid for cid, _, _ in fused]
        contexts = fetch_chunk_contexts(driver, fused_ids)

        # attach fused score + sources
        fuse_map = {cid: (score, sources) for cid, score, sources in fused}
        for r in contexts:
            cid = str(r.get("id"))
            score, sources = fuse_map.get(cid, (None, []))
            r["similarity"] = score
            r["sources"] = sources
            r["system"] = "SystemB_PGVector_Neo4jGraphRRF"

    finally:
        driver.close()
    neo_ms = (time.perf_counter() - t1) * 1000.0

    total_ms = (time.perf_counter() - t_total0) * 1000.0

    metrics = {
        "system": "B (Graph RAG)",
        "embedding_ms": emb_ms,
        "pg_ms": pg_ms,
        "neo4j_ms": neo_ms,
        "total_ms": total_ms,
        "embedding_usage": emb_usage,
        "k_final": k_final,
        "k_vec": k_vec,
        "k_kw": k_kw,
        "rrf_k": rrf_k,
        "ef_search": ef_search,
        "fulltext_index": ft_index,
        "fulltext_index_meta": ft_meta,
        "fulltext_enabled": bool(ft_index and k_kw > 0),
    }

    return {"results": contexts, "metrics": metrics}


def run_system_b(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    ef_search: int = 100,
    embedding_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return run_system_b_with_metrics(
        query_text=query_text,
        k_final=k_final,
        k_vec=k_vec,
        k_kw=k_kw,
        rrf_k=rrf_k,
        ef_search=ef_search,
        embedding_model=embedding_model,
    )["results"]

def generate_answer(query_text: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    RAG 성능 평가를 위한 Baseline 답변 생성
    - 복잡한 페르소나나 구조 강요를 제거하여, 검색된 데이터(Context)의 품질을 날것 그대로 평가함.
    """
    
    # 1. Context 구성
    context_text = ""
    for i, chunk in enumerate(retrieved_chunks):
        context_text += f"\n[Document {i+1}]\n"
        # 메타데이터가 있다면 활용, 없으면 본문만
        source_info = f"{chunk.get('title', '')} > {chunk.get('section', '')}"
        context_text += f"Source: {source_info}\n"
        context_text += f"Content: {chunk.get('text', '')}\n"

    # 2. 평가용(Baseline) 시스템 프롬프트
    # 기교를 부리지 말고, 주어진 정보만으로 건조하게 답변하도록 지시
    system_prompt = """
    You are a research assistant utilizing a Retrieval-Augmented Generation (RAG) system.
    
    Your task is to answer the user's question based **ONLY** on the provided [Context] documents.
    
    **Guidelines:**
    1. **Strict Grounding:** Do not use outside knowledge. If the answer is not in the [Context], state "The provided documents do not contain this information."
    2. **Citations:** You must cite the source for every key statement using the format `[Document N]`.
    3. **Tone:** Maintain a neutral, objective, and scientific tone.
    4. **No Fluff:** Do not make up protocols or assumptions that are not explicitly written in the text.
    """

    user_prompt = f"""
    [Context]
    {context_text}

    [Question]
    {query_text}
    """

    # 3. LLM 호출
    client, _ = _embedding_client()
    chat_model = "gpt-4o"  # 평가에는 똑똑한 모델을 써야 '모델 멍청함'과 '데이터 부족'을 구분 가능

    try:
        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0, # 창의성 0% -> 검색된 데이터에만 의존하게 만듦
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating answer: {e}"

# ─────────────────────────────────────
# 6) Utility: Save to CSV
# ─────────────────────────────────────
def save_to_csv(results: List[Dict[str, Any]], filename: str):
    """
    검색 결과를 CSV 파일로 저장 (Excel 호환 utf-8-sig 인코딩 사용)
    """
    if not results:
        print("⚠️ 저장할 결과가 없습니다.")
        return

    # CSV 컬럼 순서 지정 (보기 좋게 정렬)
    fieldnames = ["similarity", "id", "title", "section", "sources", "text", "system"]
    
    # 결과에 있는 키가 fieldnames에 없으면 뒤에 추가
    existing_keys = results[0].keys()
    for k in existing_keys:
        if k not in fieldnames:
            fieldnames.append(k)

    try:
        # utf-8-sig: 엑셀에서 한글 안 깨지게 함
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                # sources 같은 리스트 타입은 문자열로 변환하여 저장
                row_copy = row.copy()
                if "sources" in row_copy and isinstance(row_copy["sources"], list):
                    row_copy["sources"] = ", ".join(row_copy["sources"])
                writer.writerow(row_copy)
        print(f"✅ 결과가 CSV 파일로 저장되었습니다: {filename}")
    except Exception as e:
        print(f"❌ CSV 저장 중 오류 발생: {e}")


# ─────────────────────────────────────
# Main Execution (System B 전용으로 수정됨)
# ─────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    # --query 또는 --query-file 중 하나는 필수
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", "-q", help="단일 질문 내용")
    query_group.add_argument("--query-file", "-f", help="질문이 담긴 파일 경로 (CSV 또는 TXT)")
    
    parser.add_argument("--k", type=int, default=5, help="최종 반환 개수")
    parser.add_argument("--k-vec", type=int, default=50)
    parser.add_argument("--k-kw", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--ef-search", type=int, default=100, help="Postgres HNSW 검색 파라미터")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--with-metrics", action="store_true")
    
    # [옵션] 결과 저장 파일명
    parser.add_argument("--output", "-o", default=None, help="결과를 저장할 파일 경로")
    # [옵션] 답변 생성 여부
    parser.add_argument("--generate", "-g", action="store_true", help="LLM 답변 생성")
    
    args = parser.parse_args()

    # ========================================
    # 배치 처리: 파일에서 여러 질문 읽기
    # ========================================
    if args.query_file:
        import pandas as pd
        from pathlib import Path
        
        file_path = Path(args.query_file)
        
        # 파일 확장자에 따라 다르게 처리
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
            # user_input 컬럼이 있으면 사용, 없으면 첫 번째 컬럼 사용
            if 'user_input' in df.columns:
                queries = df['user_input'].dropna().tolist()
            else:
                queries = df.iloc[:, 0].dropna().tolist()
        else:
            # 텍스트 파일: 한 줄에 하나씩 질문
            with open(file_path, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()]
        
        print(f"📁 파일에서 {len(queries)}개 질문 로드 완료\n")
        
        # 전체 결과 저장
        batch_results = []
        
        for idx, query_text in enumerate(queries, 1):
            print(f"\n{'='*70}")
            print(f"📝 질문 {idx}/{len(queries)}")
            print(f"{'='*70}")
            print(f"Q: {query_text[:100]}..." if len(query_text) > 100 else f"Q: {query_text}")
            
            try:
                # 검색 수행
                if args.with_metrics:
                    out = run_system_b_with_metrics(
                        query_text=query_text,
                        k_final=args.k,
                        k_vec=args.k_vec,
                        k_kw=args.k_kw,
                        rrf_k=args.rrf_k,
                        ef_search=args.ef_search,
                        embedding_model=args.embedding_model,
                    )
                    results = out["results"]
                    metrics = out["metrics"]
                else:
                    results = run_system_b(
                        query_text=query_text,
                        k_final=args.k,
                        k_vec=args.k_vec,
                        k_kw=args.k_kw,
                        rrf_k=args.rrf_k,
                        ef_search=args.ef_search,
                        embedding_model=args.embedding_model,
                    )
                    metrics = {}
                
                print(f"✅ 검색 완료: {len(results)}개 결과")
                if metrics:
                    print(f"⏱️  소요 시간: {metrics.get('total_ms', 0):.1f}ms")
                
                # 결과 저장
                batch_results.append({
                    "question_id": idx,
                    "question": query_text,
                    "results_count": len(results),
                    "results": results,
                    "metrics": metrics if args.with_metrics else None
                })
                
            except Exception as e:
                print(f"❌ 에러: {e}")
                batch_results.append({
                    "question_id": idx,
                    "question": query_text,
                    "error": str(e)
                })
            
            # 부하 방지
            time.sleep(0.5)
        
        # 전체 결과 저장
        if args.output:
            output_file = args.output
        else:
            # 자동 번호 증가: batch_results_b_1.json, batch_results_b_2.json, ...
            from pathlib import Path
            import re
            
            # 현재 디렉토리에서 batch_results_b_*.json 파일 찾기
            existing_files = list(Path('.').glob('batch_results_b_*.json'))
            
            # 기존 파일에서 번호 추출
            max_num = 0
            for f in existing_files:
                match = re.search(r'batch_results_b_(\d+)\.json', f.name)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
            
            # 다음 번호로 파일명 생성
            output_file = f"batch_results_b_{max_num + 1}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(batch_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*70}")
        print(f"🎉 배치 처리 완료!")
        print(f"{'='*70}")
        print(f"✅ 총 처리: {len(batch_results)}개")
        print(f"📊 결과 있음: {sum(1 for r in batch_results if r.get('results_count', 0) > 0)}개")
        print(f"⚠️  결과 없음: {sum(1 for r in batch_results if r.get('results_count', 0) == 0)}개")
        print(f"📁 결과 저장: {output_file}")
        print(f"{'='*70}")
        
    # ========================================
    # 단일 질문 처리 (기존 로직)
    # ========================================
    else:
        # 1. 검색 수행 (System B 함수 호출로 수정)
        if args.with_metrics:
            out = run_system_b_with_metrics(
                query_text=args.query,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
                ef_search=args.ef_search, 
                embedding_model=args.embedding_model,
            )
            results = out["results"]
            # CSV 저장이 아닐 때만 콘솔에 JSON 출력
            if not args.output and not args.generate:
                print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            results = run_system_b(
                query_text=args.query,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
                ef_search=args.ef_search,
                embedding_model=args.embedding_model,
            )
            if not args.output and not args.generate:
                print(json.dumps(results, ensure_ascii=False, indent=2))

        # 2. CSV 저장 (옵션이 있을 경우)
        if args.output:
            save_to_csv(results, args.output)

        # 3. 답변 생성 (옵션이 있을 경우)
        if args.generate:
            print(f"\n🚀 검색된 청크 개수: {len(results)}개")
            print("-" * 50)
            final_answer = generate_answer(args.query, results)
            print(f"📄 질문: {args.query}")
            print("=" * 50)
            print(f"🤖 AI 답변:\n{final_answer}")
            print("=" * 50)
            
            # 답변 파일 저장 필요시 주석 해제
            # with open(f"answer_{args.output or 'output.txt'}.txt", "w", encoding="utf-8") as f:
            #     f.write(final_answer)