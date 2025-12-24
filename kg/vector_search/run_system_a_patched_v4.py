# run_system_a_patched_v5_graph_rag.py
# System A (Enhanced): Neo4j Internal Hybrid (Vector + Graph RAG) + Cypher RRF
# - Vector Search: Chunk node 'embedding' property
# - Keyword Search: Logic 1 (Entity->Chunk) + Logic 2 (Direct Chunk)
# - Integration: RRF inside Cypher

import os
import argparse
import csv
import time
import json
from typing import List, Dict, Any, Tuple, Optional

from neo4j import GraphDatabase
from openai import OpenAI

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# ─────────────────────────────────────
# Common: Neo4j / Embedding client
# ─────────────────────────────────────

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
    # 1. 통합 인덱스 우선
    preferred = "integrated_search_index"
    override = os.getenv("FULLTEXT_CHUNK_INDEX")

    idxs = _list_fulltext_indexes(driver)
    by_name = {i.get("name"): i for i in idxs if i.get("name")}

    if override and override in by_name:
        return override, by_name[override]

    if preferred in by_name:
        return preferred, by_name[preferred]

    # fallback logic (기존 로직 유지)
    chunk_candidates = []
    for i in idxs:
        labels = i.get("labelsOrTypes") or []
        if isinstance(labels, str): labels = [labels]
        # Chunk 또는 Keyword를 포함하면 후보
        if "Chunk" in labels or "Keyword" in labels:
            chunk_candidates.append(i)

    if chunk_candidates:
        return chunk_candidates[0].get("name"), chunk_candidates[0]

    return None, {}


# ─────────────────────────────────────
# System A: Neo4j Hybrid + RRF (One-Shot Cypher)
# ─────────────────────────────────────

def run_system_a_with_metrics(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    embedding_model: Optional[str] = None,
) -> Dict[str, Any]:
    
    t_total0 = time.perf_counter()

    # 1. 임베딩 생성
    embedding, emb_usage, emb_ms = get_query_embedding_with_usage(query_text, embedding_model=embedding_model)

    vector_index = os.getenv("VECTOR_CHUNK_INDEX", "chunk_vector_index")
    driver = get_neo4j_driver()
    ft_index, ft_meta = pick_fulltext_chunk_index(driver)

    # ─────────────────────────────────────────────────────────────────────────────
    # [Cypher Query 구조]
    # Part 1: Vector Search (Chunk 노드, embedding 속성)
    # Part 2: Keyword Search (Keyword/Chunk 노드 -> Logic 1 & 2 -> Chunk 확장)
    # Part 3: RRF Fusion (Vector Rank + Keyword Rank 합산)
    # ─────────────────────────────────────────────────────────────────────────────
    
    cypher_hybrid = f"""
    // -------------------------------------------------------
    // [Part 1] Vector Search
    // : Chunk 노드의 'embedding' 속성을 이용하여 유사도 검색
    // -------------------------------------------------------
    CALL {{
      CALL db.index.vector.queryNodes('{vector_index}', $k_vec, $embedding)
      YIELD node, score
      // 벡터 검색 결과 랭킹 매기기
      WITH node, score
      ORDER BY score DESC
      WITH collect(node) AS nodes, collect(score) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS node, (i + 1) AS rank, scores[i] AS rawScore, 'vector' AS src
    }}
    WITH collect({{node: node, rank: rank, rawScore: rawScore, src: src}}) AS vecRows

    // -------------------------------------------------------
    // [Part 2] Keyword Graph Search (Logic 1 + Logic 2)
    // : 키워드 노드면 확장, 청크 노드면 직접 사용
    // -------------------------------------------------------
    CALL {{
      CALL db.index.fulltext.queryNodes('{ft_index}', $text, {{limit: $k_kw}})
      YIELD node, score
      
      // [Logic 1] Keyword -> Chunk 확장
      OPTIONAL MATCH (node)<-[:HAS_KEYWORD]-(linked_chunk:Chunk)
      
      // [Logic 2] Chunk 직접 매칭
      WITH coalesce(linked_chunk, CASE WHEN node:Chunk THEN node END) AS final_chunk, score
      WHERE final_chunk IS NOT NULL
      
      // 중복 제거 및 점수 집계 (한 Chunk가 여러 키워드에 걸릴 수 있음)
      WITH final_chunk, max(score) AS kscore
      ORDER BY kscore DESC
      LIMIT $k_kw
      
      // 키워드 검색 결과 랭킹 매기기
      WITH collect(final_chunk) AS nodes, collect(kscore) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS node, (i + 1) AS rank, scores[i] AS rawScore, 'keyword' AS src
    }}
    
    // -------------------------------------------------------
    // [Part 3] RRF Fusion
    // : vecRows와 kwRows를 합쳐서 최종 점수 계산
    // -------------------------------------------------------
    WITH vecRows, collect({{node: node, rank: rank, rawScore: rawScore, src: src}}) AS kwRows
    WITH vecRows + kwRows AS rows
    UNWIND rows AS r
    WITH r.node AS chunk, r.src AS src, r.rank AS rank
    
    // 하나의 Chunk에 대해 Vector/Keyword 각각의 최고 등수를 가져옴
    WITH chunk, src, min(rank) AS bestRank
    
    // RRF Score 계산: score = sum(1 / (k + rank))
    WITH chunk,
         sum(1.0 / ($rrf_k + bestRank)) AS rrfScore,
         collect(DISTINCT src) AS sources

    ORDER BY rrfScore DESC
    LIMIT $k_final

    // 메타데이터 조인 (Article, Section 정보)
    MATCH (chunk)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN
      chunk.chunk_id AS id,
      chunk.text     AS text,
      a.title        AS title,
      s.title        AS section,
      rrfScore       AS similarity,
      sources        AS sources,
      'SystemA_Neo4j_Hybrid_GraphRAG' AS system
    """

    # 벡터 전용 (Fallback) - 키워드 인덱스가 없을 때 사용
    cypher_vec_only = f"""
    CALL {{
      CALL db.index.vector.queryNodes('{vector_index}', $k_vec, $embedding)
      YIELD node, score
      WITH node, score
      ORDER BY score DESC
      WITH collect(node) AS nodes, collect(score) AS scores
      UNWIND range(0, size(nodes)-1) AS i
      RETURN nodes[i] AS chunk, (i + 1) AS rank
    }}
    WITH chunk, rank
    WITH chunk, (1.0 / ($rrf_k + rank)) AS rrfScore, ['vector'] AS sources
    ORDER BY rrfScore DESC
    LIMIT $k_final

    MATCH (chunk)<-[:HAS_CHUNK]-(s:Section)<-[:HAS_SECTION]-(a:Article)
    RETURN
      chunk.chunk_id AS id,
      chunk.text     AS text,
      a.title        AS title,
      s.title        AS section,
      rrfScore       AS similarity,
      sources        AS sources,
      'SystemA_Neo4j_VectorOnly' AS system
    """

    neo_ms = 0.0
    results = []
    
    driver = get_neo4j_driver()
    try:
        t0 = time.perf_counter()
        with driver.session() as session:
            # 키워드 인덱스가 있고 k_kw > 0 이면 하이브리드, 아니면 벡터 전용
            if ft_index and k_kw > 0:
                rs = session.run(
                    cypher_hybrid,
                    text=query_text,
                    embedding=embedding,
                    k_vec=k_vec,
                    k_kw=k_kw,
                    k_final=k_final,
                    rrf_k=rrf_k,
                )
            else:
                rs = session.run(
                    cypher_vec_only,
                    embedding=embedding,
                    k_vec=k_vec,
                    k_final=k_final,
                    rrf_k=rrf_k,
                )
            results = [record.data() for record in rs]
        neo_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        driver.close()

    total_ms = (time.perf_counter() - t_total0) * 1000.0
    metrics = {
        "system": "A",
        "embedding_ms": emb_ms,
        "neo4j_ms": neo_ms,
        "total_ms": total_ms,
        "embedding_usage": emb_usage,
        "k_final": k_final,
        "k_vec": k_vec,
        "k_kw": k_kw,
        "rrf_k": rrf_k,
        "vector_index": vector_index,
        "fulltext_index": ft_index,
        "fulltext_index_meta": ft_meta,
        "fulltext_enabled": bool(ft_index and k_kw > 0),
    }
    return {"results": results, "metrics": metrics}


def run_system_a(
    query_text: str,
    k_final: int = 5,
    k_vec: int = 50,
    k_kw: int = 50,
    rrf_k: int = 60,
    embedding_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return run_system_a_with_metrics(
        query_text=query_text,
        k_final=k_final,
        k_vec=k_vec,
        k_kw=k_kw,
        rrf_k=rrf_k,
        embedding_model=embedding_model,
    )["results"]


# ─────────────────────────────────────
# 5) LLM Answer Generation (Evaluation Mode)
# ─────────────────────────────────────

def generate_answer(query_text: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    RAG 성능 평가를 위한 Baseline 답변 생성
    """
    context_text = ""
    for i, chunk in enumerate(retrieved_chunks):
        context_text += f"\n[Document {i+1}]\n"
        source_info = f"{chunk.get('title', 'Unknown')} > {chunk.get('section', '')}"
        context_text += f"Source: {source_info}\n"
        context_text += f"Content: {chunk.get('text', '')}\n"

    system_prompt = """
    You are a research assistant utilizing a Retrieval-Augmented Generation (RAG) system.
    Answer the user's question based **ONLY** on the provided [Context].
    1. **Strict Grounding:** Do not use outside knowledge. If not found, say so.
    2. **Citations:** Cite source like `[Document N]`.
    3. **Tone:** Scientific and objective.
    """

    user_prompt = f"[Context]\n{context_text}\n\n[Question]\n{query_text}"

    client, _ = _embedding_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


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
# Main Execution
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
                    out = run_system_a_with_metrics(
                        query_text=query_text,
                        k_final=args.k,
                        k_vec=args.k_vec,
                        k_kw=args.k_kw,
                        rrf_k=args.rrf_k,
                        embedding_model=args.embedding_model,
                    )
                    results = out["results"]
                    metrics = out["metrics"]
                else:
                    results = run_system_a(
                        query_text=query_text,
                        k_final=args.k,
                        k_vec=args.k_vec,
                        k_kw=args.k_kw,
                        rrf_k=args.rrf_k,
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
            # 자동 번호 증가: batch_results_a_1.json, batch_results_a_2.json, ...
            from pathlib import Path
            import re
            
            # 현재 디렉토리에서 batch_results_a_*.json 파일 찾기
            existing_files = list(Path('.').glob('batch_results_a_*.json'))
            
            # 기존 파일에서 번호 추출
            max_num = 0
            for f in existing_files:
                match = re.search(r'batch_results_a_(\d+)\.json', f.name)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
            
            # 다음 번호로 파일명 생성
            output_file = f"batch_results_a_{max_num + 1}.json"
        
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
        # 1. 검색 수행
        if args.with_metrics:
            out = run_system_a_with_metrics(
                query_text=args.query,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
                embedding_model=args.embedding_model,
            )
            results = out["results"]
            # CSV 저장이 아닐 때만 콘솔에 JSON 출력
            if not args.output and not args.generate:
                print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            results = run_system_a(
                query_text=args.query,
                k_final=args.k,
                k_vec=args.k_vec,
                k_kw=args.k_kw,
                rrf_k=args.rrf_k,
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
            
            # 답변도 텍스트 파일로 저장하고 싶다면 아래 주석 해제
            # with open(f"answer_{args.output or 'output.txt'}.txt", "w", encoding="utf-8") as f:
            #     f.write(final_answer)