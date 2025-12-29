import json
import re
from typing import Any, Callable, Dict, List, Optional

from rag_state_v2 import PipelineRAGState  # [New]

# -----------------------------
# Helpers
# -----------------------------


def safe_json_loads(raw: str) -> Dict[str, Any]:
    """LLM 출력에서 JSON 객체를 안전하게 파싱."""
    if raw is None:
        raise ValueError("LLM returned None")
    s = raw.strip()

    # 1) 바로 파싱 시도
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            raise ValueError("JSON is not an object")
        return obj
    except Exception:
        pass

    # 2) 문자열 안에서 { ... } 블록만 추출해서 재시도
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if not isinstance(obj, dict):
                raise ValueError("JSON is not an object")
            return obj
        except Exception:
            pass

    raise ValueError(f"Failed to parse JSON from LLM output: {raw[:2000]}")


def minify_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def regex_list_to_terms(patterns: List[str]) -> List[str]:
    """
    must/must_not 안의 'a|b' 같은 OR 패턴을 CONTAINS 용 단일 토큰 리스트로 풀어줌.
    예: ["glycosyl|glycan", "fc"] -> ["glycosyl","glycan","fc"]
    """
    out: List[str] = []
    for p in patterns or []:
        if not isinstance(p, str):
            continue
        p = p.strip()
        if not p:
            continue
        parts = [x.strip() for x in p.split("|") if x.strip()]
        out.extend(parts if parts else [p])

    # 중복 제거 (소문자 기준)
    seen = set()
    uniq = []
    for t in out:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq


def build_input_text(rewrite: Dict[str, Any]) -> str:
    """
    downstream(예: rerank) 에 넘길 compact text 표현.
    """
    intent = rewrite.get("intent")
    domains = rewrite.get("domains")
    question_type = rewrite.get("question_type")
    need_kg = rewrite.get("need_kg")
    needs_chunks = rewrite.get("needs_chunks")
    nq = rewrite.get("normalized_question", "")
    must = rewrite.get("must", [])
    should = rewrite.get("should", [])
    must_not = rewrite.get("must_not", [])
    f = rewrite.get("filters", {})
    r = rewrite.get("retrieval", {})

    # 너무 길어지지 않도록 자르기
    if isinstance(should, list):
        should = should[:15]
    if isinstance(must, list):
        must = must[:3]
    if isinstance(must_not, list):
        must_not = must_not[:5]

    return (
        f"i={intent};d={domains};qt={question_type};kg={need_kg};chunks={needs_chunks};q={nq};"
        f"m={must};s={should};n={must_not};f={f};r={r}"
    )


# -----------------------------
# Domain / KG heuristic
# -----------------------------


def _count_hits(q: str, trigs: List[str]) -> int:
    ql = (q or "").lower()
    return sum(1 for t in trigs if t and t.lower() in ql)


def _domain_strength(question: str) -> Dict[str, float]:
    """
    간단 규칙 기반으로 paper / clinical / protocol / kg 신호 세기(0~1) 추정.
    """
    q = (question or "").lower()

    def s(trigs: List[str]) -> float:
        return min(1.0, _count_hits(q, trigs) / 2.0)

    paper_trigs = [
        "논문", "paper", "pmid", "doi", "abstract", "근거", "문헌", "reference",
        "citation", "figure", "table",
    ]
    clinical_trigs = [
        "임상", "clinical", "trial", "nct", "phase", "endpoint", "hr", "hazard ratio",
        "adverse", "ae", "sae", "이상반응", "부작용", "recruit", "recruitment",
    ]
    protocol_trigs = [
        "프로토콜", "protocol", "steps", "how to", "실험방법", "실험 절차",
        "method", "materials", "equipment", "buffer", "recipe", "ph", "용액",
    ]

    # KG (PrimeKG) 관련 신호: 관계/경로 + 생물학 엔티티 조합 등
    rel_words = [
        "상관", "관계", "연관", "association", "link", "interaction",
        "network", "graph", "pathway", "경로",
    ]
    bio_nodes = [
        "유전자", "gene", "단백질", "protein", "질병", "disease",
        "target", "표적", "pathway", "signaling", "mutation", "variant",
    ]
    safety_words = [
        "부작용", "이상반응", "adverse", "toxicity", "독성", "off-target",
    ]
    ppi_words = [
        "ppi", "binding", "결합", "복합체", "complex", "dimer", "interaction",
    ]

    paper = s(paper_trigs)
    clinical = s(clinical_trigs)
    protocol = s(protocol_trigs)

    kg_on = (
        any(t.lower() in q for t in bio_nodes)
        or (any(t.lower() in q for t in rel_words) and any(t.lower() in q for t in bio_nodes))
        or (any(t.lower() in q for t in safety_words) and any(t.lower() in q for t in bio_nodes))
        or (any(t.lower() in q for t in ppi_words) and any(t.lower() in q for t in bio_nodes))
        or ("primekg" in q or "neo4j" in q or "knowledge graph" in q)
    )
    kg = 0.9 if kg_on else 0.0

    return {"paper": paper, "clinical": clinical, "protocol": protocol, "kg": kg}


def _infer_domains(question: str, llm_domains: Any) -> List[str]:
    """
    LLM이 준 domains + 규칙 기반 strong signal을 합쳐 최종 도메인 리스트 생성.
    """
    ds = _domain_strength(question)
    doms: List[str] = []

    # LLM이 이미 list로 줬다면 우선 반영
    if isinstance(llm_domains, list):
        for d in llm_domains:
            if d in ("paper", "clinical", "protocol", "kg") and d not in doms:
                doms.append(d)

    # 규칙 기반 보정
    for name in ("paper", "clinical", "protocol"):
        if ds[name] >= 0.4 and name not in doms:
            doms.append(name)

    # 아무 것도 없으면 paper 기본
    if not doms:
        doms = ["paper"]

    # KG는 별도로 need_kg 플래그로 제어하므로 여기서는 굳이 넣지 않아도 됨
    return doms


def _infer_question_type(question: str, llm_qt: Optional[str]) -> str:
    """
    질문 텍스트와 LLM 힌트로 question_type(chunk|list|filter) 결정.
    """
    qt = (llm_qt or "").strip().lower()
    q = (question or "").lower()

    if qt not in ("chunk", "list", "filter"):
        # 필터형: 조건/where/상태/기간 등
        if any(w in q for w in ["조건", "filter", "where", "status", "phase", "연도", "기간", "이상", "이하"]):
            return "filter"
        # 리스트/추천형
        if any(w in q for w in ["리스트", "목록", "top", "추천", "비슷한", "유사한", "비교", "similar"]):
            return "list"
        return "chunk"
    return qt


def _infer_need_kg(question: str, llm_need_kg: Any) -> bool:
    """
    PrimeKG / KG 필요 여부 추정.
    """
    if isinstance(llm_need_kg, bool):
        base = llm_need_kg
    else:
        base = False

    ds = _domain_strength(question)
    # 규칙: KG 신호가 충분히 크면 True로 올려줌
    if ds.get("kg", 0.0) >= 0.6:
        return True
    return base


def _infer_needs_chunks(question_type: str, llm_needs_chunks: Any) -> bool:
    """
    question_type에 따라 기본값 결정.
    """
    if isinstance(llm_needs_chunks, bool):
        return llm_needs_chunks
    # filter / list 는 기본적으로 청크 evidence가 필수는 아님
    if question_type in ("filter", "list"):
        return False
    return True


# -----------------------------
# Main node
# -----------------------------


def query_rewrite_node(
    state: PipelineRAGState,
    llm_call: Callable[[str], str],
) -> PipelineRAGState:

    question = (state.get("question") or "").strip()
    if not question:
        raise ValueError("state['question'] is empty.")

    # LLM 프롬프트: track 제거, 새로운 스키마 사용
    prompt = f"""
Return ONLY JSON. No markdown.

Role: senior bio/pharma researcher + IR engineer.
Task: normalize question + detect domains + question_type + KG need + extract biomedical MUST/SHOULD keywords.

Output schema (ALL keys required, keep types):
{{
  "domains": [],
  "question_type": "chunk|list|filter",
  "need_kg": false,
  "needs_chunks": true,
  "intent": "evidence_search|protocol_search|clinical_search",
  "confidence": 0.0,
  "reason_short": "",
  "normalized_question": "",
  "entities": [
    {{
      "name": "",
      "type": "concept|protein|gene|disease|drug|assay|method|material|equipment|journal|trial_id|other",
      "id": null
    }}
  ],
  "must": [],
  "should": [],
  "must_not": [],
  "filters": {{"year_from": null, "year_to": null, "journal": null, "study_type": null, "domain": null}},
  "retrieval": {{"k_seed": 300, "k_final": 40, "hop_limit": 2, "fanout_limit": 200}}
}}

Domains:
- Include any of ["paper","clinical","protocol"] that are needed for answering.
- Do NOT include "kg" here; use need_kg instead.

Question type:
- "chunk": needs evidence chunks (본문 인용, 문장/단락).
- "list": list/recommendation style (비슷한 논문/임상/방법 목록 등).
- "filter": 조건 기반 조회 (phase, status, condition, intervention, 기간 등으로 필터링).

KG (PrimeKG):
- Set need_kg=true only if mechanistic / network / off-target / safety / PPI / pathway-level reasoning is clearly useful.

Biomedical keyword extraction:
- entities<=6 (prefer Target/Drug/Disease/Assay/Trial_ID); keep real tokens (gene symbols, hyphens, Greek letters).
- MUST: 1~3 highly discriminative terms (target/gene/protein, drug, mutation/variant, trial ID; add core assay/endpoint ONLY if central; add disease ONLY if narrows). No generic words.
- SHOULD: 5~15 recall boosters from MUST: synonyms/aliases/abbrev expansions, spelling variants, closely related concepts (pathway/mechanism/readout), method variants. No duplicates.
- MUST_NOT: 0~5 homonyms/confounders if needed.

confidence: 0~1; reason_short: very short (Korean OK).
normalized_question: Translate to English if the question mixes Korean and English terms. Otherwise, keep it concise. Keep technical tokens un-translated.

Question: {question}
""".strip()

    raw = llm_call(prompt)
    rewrite = safe_json_loads(raw)

    # ---- 기본 값 보정 ----
    rewrite.setdefault("domains", [])
    rewrite.setdefault("question_type", None)
    rewrite.setdefault("need_kg", False)
    rewrite.setdefault("needs_chunks", True)
    rewrite.setdefault("intent", "evidence_search")
    rewrite.setdefault("confidence", 0.0)
    rewrite.setdefault("reason_short", "")
    rewrite.setdefault("normalized_question", question)
    rewrite.setdefault("entities", [])
    rewrite.setdefault("must", [])
    rewrite.setdefault("should", [])
    rewrite.setdefault("must_not", [])
    rewrite.setdefault(
        "filters",
        {"year_from": None, "year_to": None, "journal": None, "study_type": None, "domain": None},
    )
    rewrite.setdefault(
        "retrieval",
        {"k_seed": 300, "k_final": 40, "hop_limit": 2, "fanout_limit": 200},
    )

    # ---- 규칙 기반 보정: domains / question_type / KG ----
    domains = _infer_domains(question, rewrite.get("domains"))
    question_type = _infer_question_type(question, rewrite.get("question_type"))
    need_kg = _infer_need_kg(question, rewrite.get("need_kg"))
    needs_chunks = _infer_needs_chunks(question_type, rewrite.get("needs_chunks"))

    rewrite["domains"] = domains
    rewrite["question_type"] = question_type
    rewrite["need_kg"] = need_kg
    rewrite["needs_chunks"] = needs_chunks

    # ---- must/must_not OR 패턴 분해 ----
    must_terms = regex_list_to_terms(rewrite.get("must") or [])
    must_not_terms = regex_list_to_terms(rewrite.get("must_not") or [])
    rewrite["must_terms_expanded"] = must_terms
    rewrite["must_not_terms_expanded"] = must_not_terms

    # state에 저장
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = minify_json(rewrite)
    state["rewrite_input_text"] = build_input_text(rewrite)

    # Route Info (track 제거, 새 필드만 요약)
    intent_debug = rewrite.get("intent_debug") or {}
    state["route"] = {
        "intent": rewrite.get("intent", "evidence_search"),
        "domains": domains,
        "question_type": question_type,
        "need_kg": bool(need_kg),
        "needs_chunks": bool(needs_chunks),
        "confidence": float(rewrite.get("confidence", 0.0) or 0.0),
        "reason_short": rewrite.get("reason_short", ""),
        "intent_why": intent_debug.get("why_intent"),
    }
    return state
