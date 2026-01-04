import os
import re
import json
import csv
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import requests
import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

load_dotenv()


# =========================
# Config
# =========================

API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

TIMEOUT_SEC = int(os.getenv("LLM_TIMEOUT_SEC", "60"))
RETRY = int(os.getenv("LLM_RETRY", "2"))
SLEEP_BETWEEN = float(os.getenv("SLEEP_BETWEEN", "0.2"))

# If you want a "pure code only" run (no LLM), set:
USE_LLM_JUDGE = os.getenv("USE_LLM_JUDGE", "1") == "1"

# =========================
# Input schema (loose)
# =========================

class InterpretationBoundary(BaseModel):
    can_conclude: List[str] = Field(default_factory=list)
    cannot_conclude: List[str] = Field(default_factory=list)

class DatasetInput(BaseModel):
    observations: List[str] = Field(default_factory=list)
    question: str = ""
    interpretation_boundary: InterpretationBoundary = Field(default_factory=InterpretationBoundary)

class DatasetOutput(BaseModel):
    interpretation: List[str] = Field(default_factory=list)
    interpretation_limits: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)

class DatasetSample(BaseModel):
    instruction: str = ""
    input: DatasetInput
    output: DatasetOutput


# =========================
# LLM Judge schema (strict)
# =========================

class JudgeResult(BaseModel):
    final_score: int = Field(ge=0, le=100)
    verdict: str = Field(pattern=r"^(PASS|FAIL)$")
    breakdown: Dict[str, int]  # keys: integrity, alignment, faithfulness, boundary, atomicity
    key_issues: List[str]
    recommended_action: str = Field(pattern=r"^(KEEP AS-IS|USE AFTER REVISION|REMOVE FROM TRAINING SET)$")


# =========================
# Deterministic hard rules
# =========================

FORBIDDEN_MECH_PATTERNS = [
    r"\bmechanism\b", r"\bcaus(e|al|ality)\b", r"\bcataly(tic|ze)\b",
    r"\bexplains?\b", r"\btherefore\b", r"\bthus\b", r"\bdue to\b",
    r"\bindicates?\b.*\bmechanis",  # "indicates mechanism"
    r"\bsuggests?\b.*\bmechanis",
]

# These are "likely overreach" words if cannot_conclude bans mechanisms etc.
SOFT_OVERREACH_WORDS = [
    "likely", "potential", "may", "could", "suggest", "imply",
]

def normalize_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def hard_fail_checks(sample: DatasetSample) -> Tuple[bool, List[str]]:
    """
    Returns (is_hard_fail, reasons[])
    """
    reasons = []

    obs = [normalize_text(x) for x in sample.input.observations if normalize_text(x)]
    if len(obs) == 0:
        reasons.append("observations_empty")

    # If cannot_conclude contains broad bans, enforce stricter pattern checks on output.
    cannot = " ".join(sample.input.interpretation_boundary.cannot_conclude).lower()
    output_text = " ".join(sample.output.interpretation + sample.output.interpretation_limits +
                           sample.output.cautions + sample.output.suggested_next_steps).lower()

    # If cannot_conclude forbids mechanisms/causal, detect mechanistic language in output.
    if "mechan" in cannot or "causal" in cannot or "explan" in cannot:
        for pat in FORBIDDEN_MECH_PATTERNS:
            if re.search(pat, output_text, flags=re.IGNORECASE):
                reasons.append(f"cannot_conclude_violation:{pat}")
                break

    # Question-answerability heuristic:
    # If question introduces entities not present anywhere in observations (very rough),
    # flag as potential hard fail only if extremely mismatched.
    q = normalize_text(sample.input.question).lower()
    obs_blob = " ".join(obs).lower()
    # Extract "keywords" (naive): tokens >= 5 chars excluding stop-ish terms.
    tokens = [t for t in re.findall(r"[a-zA-Z0-9\-_]{5,}", q) if t not in {"compare", "between", "effects", "effect", "difference"}]
    missing = [t for t in tokens if t not in obs_blob]
    if len(tokens) >= 6 and len(missing) >= max(4, int(0.7 * len(tokens))):
        reasons.append("question_misaligned_with_observations")

    return (len(reasons) > 0), reasons


# =========================
# LLM Judge prompt
# =========================

JUDGE_PROMPT = """You are a strict biomedical dataset quality auditor.
Evaluate ONE dataset sample for LLM fine-tuning quality.

You must follow these rules:
- Use ONLY the provided JSON content.
- Do NOT fix the data.
- Be conservative: prefer FAIL when uncertain.
- Score 0–100 with the rubric below.
- Hard FAIL if:
  (1) observations are empty
  (2) output violates cannot_conclude constraints
  (3) question cannot be answered from observations
  (4) multiple unrelated tasks are mixed

Rubric (sum to 100):
- integrity (0–30): observations are non-empty, result-like, not background/methods, not interpretive.
- alignment (0–20): question answerable from observations only.
- faithfulness (0–25): output statements supported by observations; no new entities/scope.
- boundary (0–15): output does not violate cannot_conclude.
- atomicity (0–10): single focused task; not mixing unrelated domains.

Return STRICT JSON with this schema:
{
  "final_score": int 0..100,
  "verdict": "PASS" or "FAIL",
  "breakdown": {"integrity":int, "alignment":int, "faithfulness":int, "boundary":int, "atomicity":int},
  "key_issues": [string, ...],
  "recommended_action": "KEEP AS-IS" | "USE AFTER REVISION" | "REMOVE FROM TRAINING SET"
}

Now evaluate this dataset sample JSON:
"""


def call_llm_judge(sample_json: Dict[str, Any]) -> JudgeResult:
    if not API_KEY:
        raise RuntimeError("LLM_API_KEY is empty. Set it in env or .env")

    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": JUDGE_PROMPT + json.dumps(sample_json, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }

    last_err = None
    for _ in range(RETRY + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return JudgeResult(**parsed)
        except Exception as e:
            last_err = e
            time.sleep(0.8)
    raise RuntimeError(f"LLM judge failed: {last_err}")


# =========================
# Final decision combiner
# =========================

@dataclass
class FinalEvaluation:
    idx: int
    verdict: str
    score: int
    breakdown_integrity: int
    breakdown_alignment: int
    breakdown_faithfulness: int
    breakdown_boundary: int
    breakdown_atomicity: int
    hard_fail: bool
    hard_fail_reasons: List[str]
    key_issues: List[str]
    recommended_action: str


def evaluate_one(idx: int, raw: Dict[str, Any]) -> FinalEvaluation:
    sample = DatasetSample(**raw)

    hard_fail, hard_reasons = hard_fail_checks(sample)

    if not USE_LLM_JUDGE:
        # Pure deterministic fallback scoring (rough)
        # If hard_fail -> score <= 40, else 70 baseline adjusted by soft overreach
        output_text = " ".join(sample.output.interpretation).lower()
        soft_penalty = sum(1 for w in SOFT_OVERREACH_WORDS if w in output_text) * 3
        score = 35 if hard_fail else max(0, min(100, 78 - soft_penalty))
        verdict = "FAIL" if (hard_fail or score < 70) else "PASS"
        return FinalEvaluation(
            idx=idx,
            verdict=verdict,
            score=score,
            breakdown_integrity=0,
            breakdown_alignment=0,
            breakdown_faithfulness=0,
            breakdown_boundary=0,
            breakdown_atomicity=0,
            hard_fail=hard_fail,
            hard_fail_reasons=hard_reasons,
            key_issues=["LLM_JUDGE_DISABLED"],
            recommended_action=("REMOVE FROM TRAINING SET" if verdict == "FAIL" else "KEEP AS-IS"),
        )

    # LLM judge
    jr = call_llm_judge(raw)

    # Combine: any hard_fail forces FAIL + clamp score
    final_verdict = jr.verdict
    final_score = jr.final_score

    if hard_fail:
        final_verdict = "FAIL"
        final_score = min(final_score, 49)

    # Ensure PASS respects threshold
    if final_verdict == "PASS" and final_score < 70:
        final_verdict = "FAIL"

    bd = jr.breakdown
    return FinalEvaluation(
        idx=idx,
        verdict=final_verdict,
        score=final_score,
        breakdown_integrity=bd.get("integrity", 0),
        breakdown_alignment=bd.get("alignment", 0),
        breakdown_faithfulness=bd.get("faithfulness", 0),
        breakdown_boundary=bd.get("boundary", 0),
        breakdown_atomicity=bd.get("atomicity", 0),
        hard_fail=hard_fail,
        hard_fail_reasons=hard_reasons,
        key_issues=jr.key_issues,
        recommended_action=jr.recommended_action,
    )


# =========================
# IO (JSONL -> CSV/JSON)
# =========================

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def write_csv(path: str, evaluations: List[FinalEvaluation]) -> None:
    fieldnames = list(asdict(evaluations[0]).keys()) if evaluations else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for e in evaluations:
            d = asdict(e)
            d["hard_fail_reasons"] = "|".join(d["hard_fail_reasons"])
            d["key_issues"] = "|".join(d["key_issues"])
            w.writerow(d)

def write_json(path: str, evaluations: List[FinalEvaluation]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in evaluations], f, ensure_ascii=False, indent=2)

def write_final_jsonl(path: str, raw_samples: List[Dict[str, Any]],
                      evaluations: List[FinalEvaluation]) -> None:
    """
    PASS된 샘플만 필터링하여 최종 JSONL 저장
    evaluation의 idx는 1-based이므로 raw_samples는 0-based 접근
    """
    passed_samples = []
    for ev in evaluations:
        if ev.verdict == "PASS":
            # idx는 1-based, raw_samples는 0-based
            original_idx = ev.idx - 1
            if 0 <= original_idx < len(raw_samples):
                passed_samples.append(raw_samples[original_idx])

    with open(path, "w", encoding="utf-8") as f:
        for sample in passed_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

def append_pass_sample(path: str, sample: Dict[str, Any]) -> None:
    """
    PASS된 샘플을 즉시 파일에 추가 (스트리밍 방식, 메모리 효율적)
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

def init_csv_file(path: str, fieldnames: List[str]) -> None:
    """
    CSV 파일 초기화 (헤더만 작성)
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

def append_csv_row(path: str, evaluation: FinalEvaluation, fieldnames: List[str]) -> None:
    """
    CSV 파일에 평가 결과를 즉시 추가 (스트리밍 방식)
    """
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        d = asdict(evaluation)
        d["hard_fail_reasons"] = "|".join(d["hard_fail_reasons"])
        d["key_issues"] = "|".join(d["key_issues"])
        w.writerow(d)

def append_json_line(path: str, evaluation: FinalEvaluation) -> None:
    """
    JSON Lines 형식으로 평가 결과를 즉시 추가 (스트리밍 방식)
    각 줄은 하나의 JSON 객체
    """
    with open(path, "a", encoding="utf-8") as f:
        json.dump(asdict(evaluation), f, ensure_ascii=False)
        f.write("\n")

def main():
    import argparse
    from datetime import datetime

    # 타임스탬프 생성 (yymmdd_hhmm)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")

    p = argparse.ArgumentParser()
    p.add_argument("--in_jsonl", required=True, help="Input JSONL file path")
    p.add_argument("--out_csv", default=f"sllm/datasets/audit_results_{timestamp}.csv")
    p.add_argument("--out_json", default=f"sllm/datasets/audit_results_{timestamp}.json")
    p.add_argument("--out_final_jsonl", default=f"sllm/datasets/final_sft_dataset_{timestamp}.jsonl",
                   help="Final filtered JSONL with only PASS samples")
    # 기본값: 스트리밍 모드 활성화 (메모리 효율적)
    # --no_stream_save 플래그로 비활성화 가능
    p.add_argument("--no_stream_save", dest="stream_save", action="store_false", default=True,
                   help="Disable streaming save (save all at once at the end). Default: streaming enabled")
    args = p.parse_args()

    # 출력 디렉토리 생성
    from pathlib import Path
    for out_path in [args.out_csv, args.out_json, args.out_final_jsonl]:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    # raw_samples는 여전히 메모리에 로드 (인덱싱을 위해 필요)
    # 하지만 PASS 샘플은 즉시 저장하므로 메모리 부담 감소
    raw_samples = read_jsonl(args.in_jsonl)
    evals: List[FinalEvaluation] = []
    pass_count = 0
    csv_fieldnames = None
    csv_initialized = False

    # 스트리밍 모드인 경우 파일 초기화
    if args.stream_save:
        # final_jsonl 파일 초기화
        with open(args.out_final_jsonl, "w", encoding="utf-8") as f:
            pass  # 빈 파일 생성
        # JSON Lines 파일 초기화 (기존 JSON 파일을 JSONL 형식으로 사용)
        jsonl_path = args.out_json.replace(".json", ".jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            pass  # 빈 파일 생성

    for i, raw in enumerate(raw_samples, start=1):
        try:
            ev = evaluate_one(i, raw)
            evals.append(ev)
            
            # 스트리밍 모드: 모든 파일에 즉시 저장
            if args.stream_save:
                # CSV: 첫 번째 평가에서 헤더 작성
                if not csv_initialized:
                    csv_fieldnames = list(asdict(ev).keys())
                    init_csv_file(args.out_csv, csv_fieldnames)
                    csv_initialized = True
                
                # CSV에 즉시 추가
                append_csv_row(args.out_csv, ev, csv_fieldnames)
                
                # JSON Lines에 즉시 추가
                jsonl_path = args.out_json.replace(".json", ".jsonl")
                append_json_line(jsonl_path, ev)
                
                # PASS된 샘플을 final_jsonl에 즉시 저장
                if ev.verdict == "PASS":
                    append_pass_sample(args.out_final_jsonl, raw)
                    pass_count += 1
            
            print(f"[{i}/{len(raw_samples)}] {ev.verdict} score={ev.score} hard_fail={ev.hard_fail}")
            time.sleep(SLEEP_BETWEEN)
        except ValidationError as ve:
            print(f"[{i}] Schema validation error: {ve}")
        except Exception as e:
            print(f"[{i}] Error: {e}")

    if evals:
        # 스트리밍 모드가 아닌 경우에만 한 번에 저장
        if not args.stream_save:
            write_csv(args.out_csv, evals)
            write_json(args.out_json, evals)
            write_final_jsonl(args.out_final_jsonl, raw_samples, evals)
            pass_count = sum(1 for e in evals if e.verdict == "PASS")
        else:
            # 스트리밍 모드: JSON Lines를 JSON 배열로 변환 (선택적)
            # JSON Lines 파일이 이미 생성되었으므로, 필요시 변환 가능
            jsonl_path = args.out_json.replace(".json", ".jsonl")
            if Path(jsonl_path).exists():
                # JSON Lines를 읽어서 JSON 배열로 변환
                jsonl_data = []
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            jsonl_data.append(json.loads(line))
                with open(args.out_json, "w", encoding="utf-8") as f:
                    json.dump(jsonl_data, f, ensure_ascii=False, indent=2)
        
        # Summary 출력에 통과 샘플 수 추가
        if args.stream_save:
            print(f"\n✅ Saved {pass_count} PASS samples to {args.out_final_jsonl} (streaming mode)")
            print(f"✅ All evaluation results saved incrementally")
        else:
            print(f"\n✅ Saved {pass_count} PASS samples to {args.out_final_jsonl}")

        df = pd.DataFrame([asdict(e) for e in evals])
        # quick summary
        print("\n=== Summary ===")
        print(df.groupby("verdict")["idx"].count())
        print("\nTop FAIL reasons:")
        fail_df = df[df["verdict"] == "FAIL"]
        if len(fail_df) > 0:
            # explode reasons
            all_reasons = []
            for rs in fail_df["hard_fail_reasons"]:
                all_reasons.extend(rs)
            # reasons already list; but pandas may store as list -> keep simple print
            print(fail_df[["idx","score","hard_fail","hard_fail_reasons","recommended_action"]].head(15))
    else:
        print("No valid evaluations produced.")

if __name__ == "__main__":
    main()
