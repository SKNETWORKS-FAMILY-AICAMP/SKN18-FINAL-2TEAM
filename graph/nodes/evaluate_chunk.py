"""
evaluate_chunk.py
--------------------
검색된 문서(chunk)들이 질문에 얼마나 관련 있는지 LLM으로 평가하는 노드들.

- BIO_Q: OpenAI 기반 LLM 사용 (evaluate_chunk_bio_node_llm)
- PROTOCOL_Q: sLLM 또는 별도 LLM 사용 (evaluate_chunk_protocol_node_llm)

변경 사항(중요):
- 엔티티 기반 Coarse Filter(Stage 1)는 참고용만 사용하고,
  엔티티가 안 보이더라도 항상 Stage 2(정밀 평가)를 수행한다.
- Stage 2는 "그래프 관계 근거(Path/Triple/Hub 연결)"를 명시적으로 평가축에 포함한다.
- Stage 2 출력은 Strict JSON이며, JSON 파싱 기반으로 selected_chunks를 결정한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import json
import re

from graph.llm_config import (
    evaluate_chunk_bio_node_llm,
    evaluate_chunk_protocol_node_llm,
    get_model_name,
)

# ============================================
# JSON 파서(안전)
# ============================================

def _safe_json_loads(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    s = raw.strip()

    # 1) 바로 파싱
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) 문자열 내부에서 첫 { ... } 블록만 추출
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


# ============================================
# Helper: Coarse Filter 프롬프트
# ============================================

def _coarse_filter_prompt(question: str, entities: List[str]) -> str:
    """
    Stage 1: Coarse Filter
    - 특정 엔티티가 문서에 등장하는지 빠르게 스크리닝하는 용도 (참고용).
    """
    entity_list = " / ".join(entities[:10]) if entities else "the entities in the question"

    return f"""Quick screening: Does ANY of the following chunks mention at least one of these entities?

Entities to check: {entity_list}

Question for context: {question}

Instructions:
- Answer "YES" if ANY chunk mentions at least one entity
- Answer "NO" if NO chunks mention any entities

Response format:
Answer: [YES/NO]
"""


# ============================================
# Candidate 포맷팅: 그래프 근거를 최대한 포함
# ============================================

_LUCENE_SPECIALS = r'+-&&||!(){}[]^"~*?:\\/'

def _shorten(text: str, n: int) -> str:
    t = (text or "").strip()
    return t if len(t) <= n else t[:n] + "..."

def _pick_candidate_id(res: Any, i: int) -> str:
    if isinstance(res, dict):
        for k in ("candidate_id", "chunk_id", "protocol_chunk_id", "chunking_id", "id", "uid"):
            v = res.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (int, float)):
                return str(v)
    return f"cand_{i}"

def _pick_candidate_type(res: Any) -> str:
    if isinstance(res, dict):
        t = res.get("type") or res.get("candidate_type")
        if isinstance(t, str) and t.strip():
            return t.strip()
        # 휴리스틱
        if "protocol" in (res.get("source") or "").lower():
            return "Chunk"
    return "Chunk"

def _extract_text(res: Any) -> str:
    if isinstance(res, dict):
        for k in ("text", "content", "chunk_text", "body"):
            v = res.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # evidence 리스트가 들어오는 경우
        ev = res.get("evidence")
        if isinstance(ev, list) and ev:
            # evidence item이 dict면 text 추출
            if isinstance(ev[0], dict) and isinstance(ev[0].get("text"), str):
                return "\n".join([e.get("text", "") for e in ev if isinstance(e, dict)][:3])
            if isinstance(ev[0], str):
                return "\n".join(ev[:3])
    return str(res)

def _extract_graph_evidence(res: Any) -> Dict[str, Any]:
    """
    retrieval 결과 dict가 어떤 형태든 '그래프 관계성' 판단에 도움 되는 필드를 최대한 뽑는다.
    """
    out: Dict[str, Any] = {}
    if not isinstance(res, dict):
        return out

    # 엔티티/메서드 허브
    for k in ("entities", "entity_names", "entity_ids", "method_entity", "method_entities"):
        v = res.get(k)
        if v:
            out[k] = v

    # 트리플/패스 (있으면 그대로)
    for k in ("triples", "triple", "paths", "path", "graph_paths", "graph_triples"):
        v = res.get(k)
        if v:
            out[k] = v

    # 루트/출처(Protocol/Article 등)
    for k in ("root", "root_type", "root_id", "protocol", "article", "source_article", "protocol_title", "paper_title"):
        v = res.get(k)
        if v:
            out[k] = v

    # 점수(벡터/FT/hybrid 등)
    for k in ("score", "vec_score", "ft_score", "hy_score"):
        v = res.get(k)
        if v is not None:
            out[k] = v

    return out

def _format_candidate_block(res: Any, i: int) -> Tuple[str, str, str]:
    """
    returns: (candidate_id, raw_text, formatted_block)
    """
    cid = _pick_candidate_id(res, i)
    ctype = _pick_candidate_type(res)
    text = _extract_text(res)
    gev = _extract_graph_evidence(res)

    # graph evidence는 너무 길어질 수 있으니 요약
    gev_compact = {}
    for k, v in gev.items():
        if isinstance(v, str):
            gev_compact[k] = _shorten(v, 180)
        elif isinstance(v, list):
            # 리스트는 앞부분만
            gev_compact[k] = v[:3]
        elif isinstance(v, dict):
            # dict는 key 일부만
            gev_compact[k] = {kk: v[kk] for kk in list(v.keys())[:5]}
        else:
            gev_compact[k] = v

    block = (
        f"ID: {cid}\n"
        f"TYPE: {ctype}\n"
        f"TEXT_SNIPPET:\n{_shorten(text, 700)}\n"
        f"GRAPH_EVIDENCE (if any):\n{json.dumps(gev_compact, ensure_ascii=False)}\n"
    )
    return cid, text, block


# ============================================
# Stage 2: Graph-Grounded Relevance Prompt
# ============================================

def _build_evaluation_prompt(
    question: str,
    candidates_block: str,
    entities: List[str] | None = None,
) -> str:
    """
    Stage 2: Graph-Grounded Relevance Evaluation (Neo4j-only Strategy)

    변경 포인트:
    - '텍스트 유사도'만 보지 말고, GRAPH_EVIDENCE(Path/Triple/Hub)를 근거로
      "연결 타당성"을 점수에 반영하도록 강제.
    - 후보별로 kept/dropped를 분리하는 Strict JSON.
    """

    focus_instruction = ""
    if entities:
        entity_list = ", ".join(entities[:10])
        focus_instruction = (
            f"Focus on mechanisms/methods/interactions involving these entities when possible: [{entity_list}].\n"
            f"However, if an entity is missing in TEXT, you may still KEEP a candidate if GRAPH_EVIDENCE shows a valid connection.\n"
        )

    return f"""
You are a 'Scientific Graph Evaluator'. You filter and score retrieved candidates from a Biomedical Knowledge Graph (Neo4j).
User question: "{question}"

{focus_instruction}

### Candidate Format
Each candidate includes:
- ID
- TYPE (Chunk|Triple|Path)
- TEXT_SNIPPET
- GRAPH_EVIDENCE (optional): may contain entities/method_entity, triples, paths, root/protocol/article metadata, and retrieval scores.

### What "Graph-Grounded" means (IMPORTANT)
A candidate is graph-grounded if at least one of these is true:
1) TEXT_SNIPPET explicitly mentions key entities/terms relevant to the question, OR
2) GRAPH_EVIDENCE contains an explicit Path/Triple that connects question entities to the candidate's root (e.g., Entity -> USED_METHOD -> Protocol, Entity -> USED_METHOD <- Experiment <- Article), OR
3) It contains protocol/method evidence that is citeable even if it is only a usage mention.

### Scoring Logic (must follow)
For EACH candidate, assign:
- text_relevance: 0.0~1.0 (semantic relevance from TEXT_SNIPPET)
- graph_support: 0.0~1.0 (strength of connection from GRAPH_EVIDENCE; Path/Triple > metadata-only > none)
- final score = 0.55 * text_relevance + 0.45 * graph_support
(Clamp to 0.0~1.0)

### Evidence Level
- High: steps/conditions/parameters OR quantitative results OR explicit multi-hop path shown.
- Medium: clear method mention / standard description without detailed steps.
- Low: weak association; keep only if not noise.

### Dropping Rule (STRICT)
Drop ONLY if:
- It is completely irrelevant to the question AND
- GRAPH_EVIDENCE does not provide any plausible linkage.

### Output (STRICT JSON ONLY)
Return only a valid JSON object:
{{
  "kept": [
    {{
      "id": "candidate_id",
      "type": "Chunk|Triple|Path",
      "score": 0.0,
      "text_relevance": 0.0,
      "graph_support": 0.0,
      "reason": "short, concrete",
      "evidence_level": "High|Medium|Low",
      "risk_flag": "None|Causality_mismatch|Weak_link"
    }}
  ],
  "dropped": [
    {{
      "id": "candidate_id",
      "reason": "why completely irrelevant"
    }}
  ],
  "coverage_gaps": []
}}

### Retrieved Candidates
---
{candidates_block}
---
Generate the JSON evaluation now.
""".strip()


def _parse_stage2_json(result: str) -> Tuple[bool, float, List[str], str]:
    """
    Stage2 JSON을 파싱해 전체 관련성/점수/선정 chunk/요약이유를 만든다.
    returns: (is_relevant, score, kept_ids_sorted, reason_short)
    """
    obj = _safe_json_loads(result)
    if not obj:
        return False, 0.0, [], _shorten(result or "", 200)

    kept = obj.get("kept") or []
    if not isinstance(kept, list):
        kept = []

    # 점수 정렬
    kept_sorted = []
    for item in kept:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id", "")).strip()
        sc = item.get("score", 0.0)
        try:
            sc = float(sc)
        except Exception:
            sc = 0.0
        kept_sorted.append((cid, max(0.0, min(1.0, sc)), item.get("reason", "")))

    kept_sorted.sort(key=lambda x: x[1], reverse=True)

    # 전체 관련성 판단: 최고점 기준
    top_score = kept_sorted[0][1] if kept_sorted else 0.0
    is_relevant = top_score >= 0.55  # 임계값 (필요시 조정)

    kept_ids = [cid for cid, _, _ in kept_sorted if cid]
    reason_short = kept_sorted[0][2] if kept_sorted else "No kept candidates."

    return is_relevant, top_score, kept_ids, _shorten(str(reason_short), 200)


# ============================================
# 공용: evaluate node 본체
# ============================================

def _run_evaluate_node(
    state: Dict[str, Any],
    llm_call,
    tag: str,
) -> Dict[str, Any]:
    llm_model_name = llm_call.__name__

    print("\n" + "=" * 60)
    print(f"[{tag}] 시작")
    print(f"  LLM 모델: {llm_model_name}")
    print(f"  question: {str(state.get('question', ''))[:30]}...")
    print(f"  rewritten_query: {str(state.get('rewritten_query', ''))[:30]}...")
    print(f"  retrieval_results: {len(state.get('retrieval_results', []))}개")
    print(f"  reranked_results: {len(state.get('reranked_results', []))}개")
    print("=" * 60 + "\n")

    search_query = (state.get("rewritten_query") or state.get("question") or "").strip()
    question = (state.get("question") or "").strip()
    retrieval_results = state.get("retrieval_results") or []
    reranked_results = state.get("reranked_results") or retrieval_results

    if not search_query or not retrieval_results:
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []
        print(f"[{tag}] 검색 결과 없음 → 웹 검색으로 이동")
        return state

    entities = state.get("entities") or []

    # Stage 1: Coarse Filter (참고용만)
    if entities:
        print(f"[{tag}] Stage 1: Coarse Filter (엔티티 등장 여부 체크)...")
        context_preview = "\n\n".join(
            [
                f"[문서 {i}] "
                f"{_shorten(_extract_text(res), 220)}"
                for i, res in enumerate(reranked_results[:5], 1)
            ]
        )
        coarse_prompt = _coarse_filter_prompt(search_query, entities)
        coarse_prompt += f"\n\nChunks to check:\n---\n{context_preview}\n---"

        try:
            coarse_result = llm_call(coarse_prompt)
            print(f"[{tag}] Coarse Filter 결과: {str(coarse_result)[:120]}")
            if "no" in str(coarse_result).lower():
                print(f"[{tag}] Stage 1: 엔티티 미등장 → 그래도 Stage 2로 계속 진행")
            else:
                print(f"[{tag}] Stage 1: 엔티티 등장/부분 관련 → Stage 2로 진행")
        except Exception as e:
            print(f"[{tag}] Coarse Filter 예외 (계속 진행): {e}")

    # Stage 2: Graph-Grounded 평가
    print(f"[{tag}] Stage 2: Graph-Grounded Relevance 평가...")

    # 후보 블록 생성(그래프 근거 포함)
    id_to_text: Dict[str, str] = {}
    blocks: List[str] = []
    for i, res in enumerate(reranked_results[:8], 1):
        cid, raw_text, block = _format_candidate_block(res, i)
        id_to_text[cid] = raw_text
        blocks.append(block)

    candidates_block = "\n---\n".join(blocks)
    prompt = _build_evaluation_prompt(question or search_query, candidates_block, entities)

    try:
        model_name = get_model_name(llm_call)
        print(f"[{tag}] 사용 모델: {model_name}")

        result = llm_call(prompt)

        is_relevant, top_score, kept_ids_sorted, reason_short = _parse_stage2_json(result)

        print(f"\n[{tag}] LLM 평가 결과(JSON 기반):")
        print(f"  관련성: {'높음' if is_relevant else '낮음'}")
        print(f"  점수(top): {top_score}")
        print(f"  이유: {reason_short}\n")

        selected_chunks: List[str] = []
        if kept_ids_sorted:
            # kept 상위 3개만 추출
            for cid in kept_ids_sorted[:3]:
                txt = id_to_text.get(cid)
                if txt:
                    selected_chunks.append(txt)

        state["chunk_is_relevant"] = bool(is_relevant)
        state["chunk_relevance_score"] = float(top_score)
        state["selected_chunks"] = selected_chunks

    except Exception as e:
        print(f"[{tag}] Stage 2 평가 중 예외: {e}")
        state["chunk_is_relevant"] = False
        state["chunk_relevance_score"] = 0.0
        state["selected_chunks"] = []

    print(f"\n[{tag}] 종료")
    print(f"  chunk_is_relevant: {state.get('chunk_is_relevant')}")
    print(f"  chunk_relevance_score: {state.get('chunk_relevance_score')}")
    print(f"  selected_chunks: {len(state.get('selected_chunks', []))}개")
    print("=" * 60 + "\n")

    return state


# ============================================
# BIO_Q / PROTOCOL_Q 노드
# ============================================

def bio_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return _run_evaluate_node(state, evaluate_chunk_bio_node_llm, tag="BIO_EVALUATE_CHUNK NODE")


def protocol_evaluate_chunk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return _run_evaluate_node(state, evaluate_chunk_protocol_node_llm, tag="PROTOCOL_EVALUATE_CHUNK NODE")
