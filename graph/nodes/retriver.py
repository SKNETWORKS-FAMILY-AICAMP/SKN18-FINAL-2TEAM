"""
retrieval.py
-------------------------------------
질문 유형별로 RAG 검색을 수행하는 LangGraph 노드.

이 버전에서는 기존 임시 pgvector/neo4j 더미 검색 대신
rag/retriver/retriever_runner.py 에 정의된 RAG 파이프라인을 호출해서
실제 Retrieval Plan + Embeddings + Contexts 를 가져오도록 연동한다.
"""

from typing import Dict, Any, List

from graph.nodes.rag_retriever_bridge import run_rag_retrieval_pipeline


# ============================================
# Helper: Context 로깅 함수
# ============================================

def _log_contexts_pretty(contexts: List[Dict[str, Any]]) -> None:
    """
    검색된 contexts의 전체 내용을 보기 좋게 로그 출력
    - 근거 파일(Graph Node) 메타데이터 포함
    - CSV 파일 추적 가능하도록 DOI, chunk_id 등 명시

    Args:
        contexts: RAG 파이프라인에서 검색된 청크 리스트
    """

    if not contexts:
        print("\n  ℹ️  검색된 contexts 없음\n")
        return

    print(f"\n{'='*60}")
    print(f"📚 RAG 검색 결과: 총 {len(contexts)}개 청크 검색됨")
    print(f"{'='*60}\n")

    for i, ctx in enumerate(contexts, 1):
        # dict가 아닌 경우 처리
        if not isinstance(ctx, dict):
            print(f"╔{'═'*59}")
            print(f"║ 📄 청크 #{i} [UNKNOWN TYPE]")
            print(f"╠{'═'*59}")
            print(f"║ ⚠️  예상치 못한 타입: {type(ctx)}")
            print(f"╠{'─'*59}")
            print(f"║ {str(ctx)}")
            print(f"╚{'═'*59}\n")
            continue

        # Context 타입 판별 (PAPER, PROTOCOL, CLINICAL 등)
        ctx_type = "UNKNOWN"
        metadata_lines = []
        score = None
        all_chunks = []  # 실제 텍스트 청크들

        # PAPER 타입 감지
        if "article" in ctx:
            ctx_type = "PAPER"
            article = ctx.get("article", {})
            doi = article.get("doi", "N/A")
            title = article.get("title", "N/A")
            year = article.get("year", "N/A")
            journal = ctx.get("journal_title", "N/A")

            metadata_lines.append(f"║    └─ Article DOI: {doi}")
            metadata_lines.append(f"║    └─ Title: {title}")
            metadata_lines.append(f"║    └─ Year: {year}")
            metadata_lines.append(f"║    └─ Journal: {journal}")

            score = ctx.get("vec_score") or ctx.get("hy_score")
            all_chunks = ctx.get("evidence_chunks", [])

        # PROTOCOL 타입 감지
        elif "protocol" in ctx:
            ctx_type = "PROTOCOL"
            protocol = ctx.get("protocol", {})
            protocol_title = protocol.get("title", "N/A")
            source_article = ctx.get("source_article", {})
            source_title = source_article.get("title", "N/A")
            experiment = ctx.get("experiment", {})
            method_name = experiment.get("method_name", "N/A")

            metadata_lines.append(f"║    └─ Protocol: {protocol_title}")
            metadata_lines.append(f"║    └─ Source Article: {source_title}")
            metadata_lines.append(f"║    └─ Experiment Method: {method_name}")

            score = ctx.get("vec_score") or ctx.get("hy_score")

            # Protocol은 두 종류의 청크가 있을 수 있음
            protocol_chunks = ctx.get("evidence_protocol_chunks", [])
            paper_chunks = ctx.get("evidence_paper_chunks", [])
            all_chunks = protocol_chunks  # 일단 protocol 청크만 출력

        # CLINICAL 타입 감지
        elif "trial" in ctx or "node" in ctx:
            ctx_type = "CLINICAL"
            trial = ctx.get("trial") or ctx.get("node", {})
            nct_id = trial.get("nct_id", "N/A")
            phase = trial.get("phase", "N/A")
            title = trial.get("title", "N/A")

            metadata_lines.append(f"║    └─ NCT ID: {nct_id}")
            metadata_lines.append(f"║    └─ Phase: {phase}")
            metadata_lines.append(f"║    └─ Title: {title}")

            score = ctx.get("vec_score") or ctx.get("hy_score")
            all_chunks = ctx.get("evidence", []) or ctx.get("evidence_chunks", [])

        # Fallback: 직접 content 필드가 있는 경우 (backward compatibility)
        elif "content" in ctx or "text" in ctx:
            ctx_type = "DIRECT"
            content = ctx.get("content") or ctx.get("text", "")
            chunk_id = ctx.get("chunk_id") or ctx.get("chunking_id") or "N/A"
            domain = ctx.get("domain", "N/A")

            metadata_lines.append(f"║    └─ Chunk ID: {chunk_id}")
            metadata_lines.append(f"║    └─ Domain: {domain}")

            score = ctx.get("score") or ctx.get("similarity")
            all_chunks = [{"chunk_id": chunk_id, "text": content}]

        # 헤더 출력
        print(f"╔{'═'*59}")
        print(f"║ 📄 청크 #{i} [{ctx_type}]")
        print(f"╠{'═'*59}")
        print(f"║ 📌 근거 파일(Graph Node):")
        for line in metadata_lines:
            print(line)
        print(f"║")

        if score is not None:
            print(f"║ ⭐ Retrieval Score: {score:.4f}" if isinstance(score, float) else f"║ ⭐ Retrieval Score: {score}")

        print(f"║")
        print(f"║ 📦 Evidence Chunks: {len(all_chunks)}개")
        print(f"║")
        print(f"╠{'─'*59}")
        print(f"║ 📖 청크 실제 내용:")
        print(f"╠{'─'*59}")
        print(f"║")

        # 각 청크 내용 출력
        for chunk in all_chunks:
            if isinstance(chunk, dict):
                chunk_id = chunk.get("chunk_id") or chunk.get("chunking_id", "")
                chunk_text = chunk.get("text", str(chunk))

                if chunk_id:
                    print(f"║ [Chunk ID: {chunk_id}]")

                # 텍스트 줄바꿈 처리
                text_lines = chunk_text.split('\n')
                for line in text_lines:
                    # 긴 줄은 자동 줄바꿈 (57자 기준)
                    if len(line) <= 57:
                        print(f"║ {line}")
                    else:
                        while len(line) > 57:
                            print(f"║ {line[:57]}")
                            line = line[57:]
                        if line:
                            print(f"║ {line}")
                print(f"║")
            else:
                # chunk가 문자열인 경우
                print(f"║ {str(chunk)}")
                print(f"║")

        print(f"╚{'═'*59}\n")


# ============================================
# BIO_Q 리트리버 노드 (RAG 파이프라인 연동)
# ============================================

def retriever_bio_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    BIO_Q 용 리트리버 노드.

    - rag/retriver/retriever_runner.py 의 파이프라인을 호출해서
      rewrite / route / retrieval_plan / embeddings / contexts 를 생성
    - LangGraph 에서 사용하던 state 필드(retrieval_results, entities 등)에 매핑
    """

    print(f"\n{'='*60}")
    print(f"[RETRIEIVER_BIO NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")

    question = state.get("question", "") or ""

    try:
        rag_state = run_rag_retrieval_pipeline(question)
    except Exception as e:
        # RAG 파이프라인 오류 시, 이후 노드에서 graceful 하게 처리할 수 있도록
        # 최소 구조만 채워서 반환
        print(f"[BIO Retriever] RAG 파이프라인 실행 중 오류 발생: {e}")
        state.setdefault("retrieval_results", [])
        state.setdefault("entities", [])
        state.setdefault("used_search_db", "graph_rag_error")
        return state

    # -----------------------------
    # RAG Pipeline -> LangGraph State 매핑
    # -----------------------------

    # 1) Rewrite 관련 필드 (RAG 파이프라인 결과)
    rewrite = rag_state.get("rewrite") or {}
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = rag_state.get("rewrite_json_min", "")
    state["rewrite_input_text"] = rag_state.get("rewrite_input_text", question)
    state["route"] = rag_state.get("route") or {}

    # 기존 문자열 기반 rewritten_query 와 최대한 호환
    normalized_q = rewrite.get("normalized_question") or question
    state["rewritten_query"] = normalized_q

    # 2) Retrieval Plan / Embeddings / Contexts
    state["retrieval_params"] = rag_state.get("retrieval_params") or {}
    state["retrieval_plan"] = rag_state.get("retrieval_plan") or []
    state["embeddings"] = rag_state.get("embeddings") or {}

    contexts: List[Dict[str, Any]] = rag_state.get("contexts") or []
    state["contexts"] = contexts
    state["contexts_count"] = int(rag_state.get("contexts_count", len(contexts)))

    # LangGraph 의 downstream 노드들이 사용하던 필드에 그대로 연결
    state["retrieval_results"] = contexts
    state["used_search_db"] = "graph_rag"

    # 3) Entity 리스트
    #   - LangGraph rewrite_query.py 에서는 엔티티를 추출하지 않는다.
    #   - 필요하다면 RAG 쪽 rewrite["entities"] 를 간단한 문자열 리스트로 변환해서 사용.
    entities_from_rewrite = rewrite.get("entities") or []
    entities: List[str] = []
    for ent in entities_from_rewrite:
        try:
            name = ent.get("name") or ent.get("label") or ent.get("id")
            entities.append(str(name) if name is not None else str(ent))
        except Exception:
            entities.append(str(ent))
    state["entities"] = entities

    print(f"\n[RETRIEIVER_BIO NODE] 완료")
    print(f"  contexts: {len(contexts)}개")
    print(f"  entities: {len(entities)}개")

    # 🎯 Contexts 상세 로그 출력
    _log_contexts_pretty(contexts)

    print(f"{'='*60}\n")

    return state


# ============================================
# PROTOCOL_Q 리트리버 노드 (RAG 파이프라인 재사용)
# ============================================

def retriever_protocol_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    PROTOCOL_Q 용 리트리버 노드.

    현재는 BIO_Q 와 동일하게 retriever_runner 파이프라인을 호출하고,
    결과를 그대로 매핑한다.
    (추후 필요 시 RAG 쪽 Router / Orchestrator 정책에서
     protocol 도메인 전용 플랜을 세우도록 확장 가능)
    """

    print(f"\n{'='*60}")
    print(f"[RETRIEIVER_PROTOCOL NODE] 시작")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query(before): {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"{'='*60}\n")

    question = state.get("question", "") or ""

    try:
        rag_state = run_rag_retrieval_pipeline(question)
    except Exception as e:
        print(f"[PROTOCOL Retriever] RAG 파이프라인 실행 중 오류 발생: {e}")
        state.setdefault("retrieval_results", [])
        state.setdefault("entities", [])
        state.setdefault("used_search_db", "graph_rag_error")
        return state

    # Rewrite / Route
    rewrite = rag_state.get("rewrite") or {}
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = rag_state.get("rewrite_json_min", "")
    state["rewrite_input_text"] = rag_state.get("rewrite_input_text", question)
    state["route"] = rag_state.get("route") or {}

    normalized_q = rewrite.get("normalized_question") or question
    state["rewritten_query"] = normalized_q

    # Retrieval Plan / Embeddings / Contexts
    state["retrieval_params"] = rag_state.get("retrieval_params") or {}
    state["retrieval_plan"] = rag_state.get("retrieval_plan") or []
    state["embeddings"] = rag_state.get("embeddings") or {}

    contexts: List[Dict[str, Any]] = rag_state.get("contexts") or []
    state["contexts"] = contexts
    state["contexts_count"] = int(rag_state.get("contexts_count", len(contexts)))

    state["retrieval_results"] = contexts
    state["used_search_db"] = "graph_rag"

    # Entity 리스트
    entities_from_rewrite = rewrite.get("entities") or []
    entities: List[str] = []
    for ent in entities_from_rewrite:
        try:
            name = ent.get("name") or ent.get("label") or ent.get("id")
            entities.append(str(name) if name is not None else str(ent))
        except Exception:
            entities.append(str(ent))
    state["entities"] = entities

    print(f"\n[RETRIEIVER_PROTOCOL NODE] 완료")
    print(f"  contexts: {len(contexts)}개")
    print(f"  entities: {len(entities)}개")

    # 🎯 Contexts 상세 로그 출력
    _log_contexts_pretty(contexts)

    print(f"{'='*60}\n")

    return state    