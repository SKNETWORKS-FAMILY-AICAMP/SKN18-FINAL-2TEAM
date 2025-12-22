import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from typing import Any, Callable, Dict, List, Optional, Tuple
from rag_state import PipelineRAGState  # [New]

# -----------------------------
# Helpers
# -----------------------------

def safe_json_loads(raw: str) -> Dict[str, Any]:
    """LLM 출력에서 JSON만 최대한 안전하게 파싱."""
    if raw is None:
        raise ValueError("LLM returned None")
    s = raw.strip()

    # 1) 바로 파싱
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            raise ValueError("JSON is not an object")
        return obj
    except Exception:
        pass

    # 2) 문자열 내부에서 첫 { ... } 블록 추출
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
    must/must_not에 'a|b' 같은 OR 패턴이 있으면 CONTAINS 필터용으로 분해.
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

    # 중복 제거(순서 유지)
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
    downstream(검색/라우터)로 넘길 compact text (토큰 절약).
    """
    track = rewrite.get("track")
    intent = rewrite.get("intent")
    domains = rewrite.get("domains")
    nq = rewrite.get("normalized_question", "")
    must = rewrite.get("must", [])
    should = rewrite.get("should", [])
    must_not = rewrite.get("must_not", [])
    f = rewrite.get("filters", {})
    r = rewrite.get("retrieval", {})

    # 너무 길어지지 않게 상한
    if isinstance(should, list):
        should = should[:15]
    if isinstance(must, list):
        must = must[:3]
    if isinstance(must_not, list):
        must_not = must_not[:5]

    return (
        f"t={track};i={intent};d={domains};q={nq};"
        f"m={must};s={should};n={must_not};"
        f"f={f};r={r}"
    )


# -----------------------------
# Soft-enforce core
# -----------------------------

def _count_hits(q: str, trigs: List[str]) -> int:
    ql = (q or "").lower()
    return sum(1 for t in trigs if t in ql)


def _rule_track_score(question: str) -> Dict[str, float]:
    """
    질문 텍스트만으로 track별 '강도' 점수(0~1)를 만든다(soft 보정용).
    """
    q = (question or "").lower()

    corpus_list_phrases = ["논문 리스트", "실험 리스트", "프로토콜 리스트", "임상 리스트"]

    t2_trigs = [
        "찾아줘", "검색해줘", "검색", "추출해줘", "발췌해줘", "발췌", "추출", "뽑아줘",
        "근거 문장", "해당 문장", "값만", "수치만", "p-value", "p value", "hr", "hazard ratio", "endpoint",
        "표에서", "figure에서", "그림에서"
    ] + corpus_list_phrases

    t3_trigs = [
        "비교", " vs ", "vs", "전략", "추천", "제안", "해석", "의미", "의사결정", "타당",
        "우선순위", "trade-off", "tradeoff", "장단점", "top", "선정", "추천 리스트"
    ]

    t1_trigs = [
        "정의", "뜻", "의미", "차이", "뭐야", "뭐임", "what is", "meaning of",
        "용어", "개념", "약어", "풀네임", "stands for", "abbr",
        "종류", "타입", "카테고리", "목록", "조성", "버퍼", "농도", "ph", "공식", "계산", "단위"
    ]

    # hit 수를 0~1로 squash
    t2 = min(1.0, _count_hits(q, t2_trigs) / 3.0)
    t3 = min(1.0, _count_hits(q, t3_trigs) / 3.0)
    t1 = min(1.0, _count_hits(q, t1_trigs) / 2.0)

    # T2가 매우 강하면 다른 트랙 약간 감쇠
    if t2 >= 0.67:
        t1 *= 0.6
        t3 *= 0.8

    return {"T1": t1, "T2": t2, "T3": t3}


def _pick_rule_track(question: str, draft: str) -> Tuple[str, float]:
    scores = _rule_track_score(question)
    best_track, best_score = max(scores.items(), key=lambda x: x[1])

    # 룰이 약하면 draft 유지 신호
    if best_score < 0.45:
        return (draft or "T2"), best_score
    return best_track, best_score


def _soft_choose(
    llm_value: str,
    rule_value: str,
    llm_conf: float,
    rule_conf: float,
    llm_threshold: float = 0.78,
    rule_threshold: float = 0.65,
) -> Tuple[str, str]:
    """
    최종 선택 + why 리턴.
    """
    llm_conf = float(llm_conf or 0.0)
    rule_conf = float(rule_conf or 0.0)

    if llm_value == rule_value:
        return llm_value, "agree"

    # LLM 강 / 룰 약
    if llm_conf >= llm_threshold and rule_conf < rule_threshold:
        return llm_value, "llm_high_rule_low"

    # 룰 강 / LLM 약
    if rule_conf >= rule_threshold and llm_conf < llm_threshold:
        return rule_value, "rule_high_llm_low"

    # 둘 다 강한데 충돌 -> 룰 우선(일관성)
    if llm_conf >= llm_threshold and rule_conf >= rule_threshold:
        return rule_value, "both_high_conflict_rule_wins"

    # 둘 다 약한데 충돌 -> LLM 유지(생성 품질)
    return llm_value, "both_low_conflict_llm_wins"


# -----------------------------
# Domain detection (rule signals)
# -----------------------------

def _domain_strength(question: str) -> Dict[str, float]:
    q = (question or "").lower()

    def s(trigs: List[str]) -> float:
        return min(1.0, _count_hits(q, trigs) / 2.0)

    paper_trigs = ["논문", "paper", "pmid", "doi", "abstract", "근거", "문헌", "reference", "citation"]
    clinical_trigs = ["임상", "clinical", "trial", "nct", "phase", "endpoint", "hr", "hazard ratio",
                    "adverse", "ae", "sae", "이상반응", "부작용", "recruit", "recruitment"]
    protocol_trigs = ["프로토콜", "protocol", "steps", "how to", "실험방법", "실험 절차", "method",
                    "materials", "equipment", "buffer", "농도", "ph", "recipe", "시약", "장비"]

    # KG(PPI 포함)
    rel_words = ["연관", "관련", "관계", "association", "link", "연결", "경로", "path", "네트워크", "network", "graph"]
    bio_nodes = ["유전자", "gene", "단백질", "protein", "질병", "disease", "pathway", "signaling", "signal",
                "target", "표적", "타깃", "기전", "mechanism", "mutation", "variant", "변이"]
    safety = ["부작용", "이상반응", "adverse", "ae", "sae", "toxicity", "독성", "off-target", "오프타깃"]
    ppi_words = ["상호작용", "결합", "바인딩", "binding", "interaction", "interact", "ppi",
                "protein-protein", "complex", "복합체", "dimer", "interface", "인터페이스"]

    paper = s(paper_trigs)
    clinical = s(clinical_trigs)
    protocol = s(protocol_trigs)

    kg_on = (
        any(t in q for t in bio_nodes) or
        (any(t in q for t in rel_words) and any(t in q for t in bio_nodes)) or
        (any(t in q for t in safety) and any(t in q for t in bio_nodes)) or
        (any(t in q for t in ppi_words) and any(t in q for t in bio_nodes))
    )
    kg = 0.9 if kg_on else 0.0

    return {"paper": paper, "clinical": clinical, "protocol": protocol, "kg": kg}


def soft_enforce_intent_domains_track(
    question: str,
    llm_intent: str,
    llm_domains: Any,
    llm_track: str,
    llm_conf: float,
) -> Tuple[str, Optional[List[str]], str, Dict[str, Any]]:
    """
    - multi_domain은 '명시적 cross-domain' 또는 '강한 도메인 2개 이상'일 때만 룰로 강하게 켬.
    - LLM confidence가 높으면 LLM intent를 더 존중(soft).
    returns: (intent, domains_or_none, track, debug)
    """
    ql = (question or "").lower()
    ds = _domain_strength(question)
    strong_domains = [d for d, sc in ds.items() if sc >= 0.6]
    any_domains = [d for d, sc in ds.items() if sc >= 0.35]

    # LLM domains가 리스트면 후보로 섞기
    doms: List[str] = []
    if isinstance(llm_domains, list):
        doms.extend([d for d in llm_domains if d in ("paper", "protocol", "clinical", "kg")])
    doms.extend([d for d in any_domains if d in ("paper", "protocol", "clinical", "kg")])

    # uniq preserve order
    seen = set()
    doms = [d for d in doms if not (d in seen or seen.add(d))]

    explicit_multi = any(x in ql for x in ["종합", "한번에", "같이", "연결", "cross-domain", "멀티도메인", "모두"])
    rule_wants_multi = explicit_multi or (len(strong_domains) >= 2)

    # 룰 intent 후보(단일 도메인)
    if ds["clinical"] >= 0.6:
        rule_intent = "clinical_search"
    elif ds["protocol"] >= 0.6:
        rule_intent = "protocol_search"
    else:
        rule_intent = "evidence_search"

    # 룰 multi 후보
    if rule_wants_multi:
        rule_intent = "multi_domain"
        rule_track = "T4"
        rule_domains = doms if len(doms) >= 2 else ["paper", "protocol"]
        rule_conf = 0.80
    else:
        rule_track = llm_track or "T2"
        rule_domains = None
        # 도메인 신호가 강하면 intent 룰 confidence를 높임
        rule_conf = 0.75 if (ds["clinical"] >= 0.6 or ds["protocol"] >= 0.6) else 0.45

    final_intent, why_intent = _soft_choose(
        llm_value=(llm_intent or "evidence_search"),
        rule_value=rule_intent,
        llm_conf=llm_conf,
        rule_conf=rule_conf,
    )

    # intent에 따른 정합성 보정
    if final_intent == "multi_domain":
        final_track = "T4"
        final_domains = rule_domains  # multi는 domains 필수 -> 룰/감지 기반
    else:
        final_domains = None
        final_track = llm_track or "T2"

    debug = {
        "domain_strength": ds,
        "strong_domains": strong_domains,
        "any_domains": any_domains,
        "explicit_multi": explicit_multi,
        "rule_wants_multi": rule_wants_multi,
        "llm_conf": float(llm_conf or 0.0),
        "why_intent": why_intent,
        "rule_intent": rule_intent,
    }
    return final_intent, final_domains, final_track, debug


# -----------------------------
# Main node (soft)
# -----------------------------

def query_rewrite_node(
    state: PipelineRAGState,   # [수정] Dict[str, Any] -> PipelineRAGState
    llm_call: Callable[[str], str],
    ) -> PipelineRAGState:
    
    question = (state.get("question") or "").strip()
    if not question:
        raise ValueError("state['question'] is empty.")

    # [수정됨] 프롬프트 내 normalized_question 지시사항 변경
    # "concise Korean" -> "Translate to English if mixed..."
    prompt = f"""
Return ONLY JSON. No markdown.

Role: senior bio/pharma researcher + IR engineer.
Task: normalize question + decide track/intent + extract biomedical MUST/SHOULD keywords used in journals/protocols.

Output schema (ALL keys required, keep types):
{{"track":"T1|T2|T3|T4","intent":"evidence_search|protocol_search|clinical_search|multi_domain","domains":null,"confidence":0.0,"reason_short":"","normalized_question":"","entities":[{{"name":"","type":"concept|protein|gene|disease|drug|assay|method|material|equipment|journal|trial_id|other","id":null}}],"must":[],"should":[],"must_not":[],"filters":{{"year_from":null,"year_to":null,"journal":null,"study_type":null,"domain":null}},"retrieval":{{"k_seed":300,"k_final":40,"hop_limit":2,"fanout_limit":200}}}}

Track:
- T1=definition/taxonomy ("~가 뭐야/종류/카테고리")
- T2=evidence lookup/listing ("근거 문장/표/수치/논문/프로토콜/임상 찾아줘")
- T3=compare/recommend/prioritize ("비교/추천/우선순위/선정 기준")
- T4=cross-domain synthesis across >=2 of ["paper","protocol","clinical","kg"] (then domains=list; else domains=null)
KG include if side-effect/toxicity/off-target + target/pathway OR PPI/binding/complex OR explicit KG/Neo4j/PrimeKG.

Intent:
protocol_search if steps/how-to/material/equipment/buffer/recipe. -> 토큰수 한토큰 짧게, json말고 -> / 로 받고 코드처리 ->
clinical_search if trial/NCT/phase/endpoint/HR/AE/recruitment.
multi_domain if needs >=2 domains; else evidence_search.

Biomedical keyword extraction:
- entities<=6 (prefer Target/Drug/Disease/Assay/Trial_ID); keep real paper tokens (gene symbols, hyphens, Greek letters).
- MUST: 1~3 highly discriminative terms (target/gene/protein, drug, mutation/variant, trial ID; add core assay/endpoint ONLY if central; add disease ONLY if narrows). No generic words. Allow "a|b" only for common aliases.
- SHOULD: 5~15 recall boosters derived from MUST: synonyms/aliases/abbrev expansions, spelling variants, close related concepts (pathway/mechanism/readout), method variants. No duplicates, no broad drift (don’t expand to whole families unless question is review/compare).
- MUST_NOT: 0~5 homonyms/confounders if needed.

confidence 0~1; reason_short very short (Korean OK).
normalized_question: Translate to English if the question mixes Korean and English terms. Otherwise, keep it concise. Keep technical tokens un-translated.

Question: {question}
""".strip()


    raw = llm_call(prompt)
    rewrite = safe_json_loads(raw)

    # ---- 최소 스키마 보정(키 누락 방지) ----
    rewrite.setdefault("track", "T2")
    rewrite.setdefault("intent", "evidence_search")
    rewrite.setdefault("domains", None)
    rewrite.setdefault("confidence", 0.0)
    rewrite.setdefault("reason_short", "")
    rewrite.setdefault("normalized_question", question)
    rewrite.setdefault("entities", [])
    rewrite.setdefault("must", [])
    rewrite.setdefault("should", [])
    rewrite.setdefault("must_not", [])
    rewrite.setdefault("filters", {"year_from": None, "year_to": None, "journal": None, "study_type": None, "domain": None})
    rewrite.setdefault("retrieval", {"k_seed": 300, "k_final": 40, "hop_limit": 2, "fanout_limit": 200})

    # ---- Soft Track ----
    llm_track = rewrite.get("track", "T2") or "T2"
    llm_conf = float(rewrite.get("confidence", 0.0) or 0.0)

    rule_track, rule_conf = _pick_rule_track(question, llm_track)
    final_track, why_track = _soft_choose(
        llm_value=llm_track,
        rule_value=rule_track,
        llm_conf=llm_conf,
        rule_conf=rule_conf,
    )
    rewrite["track"] = final_track
    rewrite["track_debug"] = {
        "llm_track": llm_track,
        "rule_track": rule_track,
        "rule_conf": float(rule_conf),
        "llm_conf": float(llm_conf),
        "why": why_track,
    }

    # ---- Soft Intent/Domains (+ T4 승격은 '강할 때만') ----
    llm_intent = rewrite.get("intent", "evidence_search") or "evidence_search"
    llm_domains = rewrite.get("domains", None)

    final_intent, final_domains, final_track2, intent_debug = soft_enforce_intent_domains_track(
        question=question,
        llm_intent=llm_intent,
        llm_domains=llm_domains,
        llm_track=rewrite["track"],
        llm_conf=llm_conf,
    )
    rewrite["intent"] = final_intent
    rewrite["domains"] = final_domains
    # multi_domain이면 track은 T4로 강제(정합성)
    if final_intent == "multi_domain":
        rewrite["track"] = "T4"
    else:
        # multi가 아니면 기존 soft track 유지
        rewrite["track"] = rewrite["track"]

    rewrite["intent_debug"] = intent_debug

    # ---- must/must_not OR 패턴 분해본 저장 (CONTAINS 필터용) ----
    must_terms = regex_list_to_terms(rewrite.get("must") or [])
    must_not_terms = regex_list_to_terms(rewrite.get("must_not") or [])
    rewrite["must_terms_expanded"] = must_terms
    rewrite["must_not_terms_expanded"] = must_not_terms

# state 저장
    state["rewrite"] = rewrite
    state["rewrite_json_min"] = minify_json(rewrite)
    state["rewrite_input_text"] = build_input_text(rewrite)

    # Route Info 타입에 맞춰 저장
    state["route"] = {
        "track": rewrite.get("track", "T2"),
        "intent": rewrite.get("intent", "evidence_search"),
        "domains": rewrite.get("domains", None),
        "confidence": float(rewrite.get("confidence", 0.0) or 0.0),
        "reason_short": rewrite.get("reason_short", ""),
        "track_why": (rewrite.get("track_debug") or {}).get("why"),
        "intent_why": (rewrite.get("intent_debug") or {}).get("why_intent"),
    }
    return state