# Retriever Pipeline (Rewrite -> Route -> Embed -> Retrieve)

Files:
- `query_rewrite_node_soft.py` : (1) 쿼리 리라이트 (soft-enforce)
- `query_router.py`           : (2) 쿼리 라우팅 (retrieval_plan 생성)
- `embedding_router.py`       : (3) 임베딩 라우팅 (1536/1024 분기)
- `retriever_runner.py`       : (4) 전체 실행 파일

Run:
```bash
export OPENAI_API_KEY=...
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=...

python retriever_runner.py --question "PH20 변이체 Tm 근거 문장 찾아줘" --pretty
```

Optional:
```bash
export OPENAI_CHAT_MODEL=gpt-4o-mini
export OPENAI_EMBED_MODEL=text-embedding-3-small
export PROTOCOL_EMBED_MODEL=BAAI/bge-m3
export PROTOCOL_EMBED_DEVICE=cuda
```
