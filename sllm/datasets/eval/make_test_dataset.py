r'''
실제 실험결과가 있는 이미지 데이터에서 실험 결과를 추출하여 테스트 데이터셋을 만드는 스크립트
0. CONFIG 설정
- 원본 csv 경로: sllm\datasets\eval\t_figures_with_result_desc_v4 - t_figures_with_result_desc_v4.csv
- 출력 JSON 경로: sllm\datasets\eval\final_test_dataset_yymmdd_hhmm.jsonl
- LLM 모델: 단계별로 다른 모델 사용하는것 지정하도록
- 처리할 csv 행 수: 50

1. 이미지(fig_caption, fig_url)가 실험결과를 나타낸 표, 그래프 등의 이미지 이면 true, 아니면 false
-> fig_caption과 fig_url를 gpt-4o-mini 모델에 전달하여 이미지가 실험결과를 나타낸 표, 그래프 등의 이미지인지 판단
-> 원본 csv에 'is_ecperiment' 칼럼 추가하여 거기에 True/False 추가'
-> 이미지는 실제 이미지 파일이 아닌 이미지 url을 사용(fig_url 컬럼)
-> LLM 모델: gpt-4o-mini


2. is_ecperiment == true인 경우
-> fig_caption과 fig_url를 gpt-4o-mini 모델에 전달하여 실험결과를 추출
-> 원본 csv에 'experiment_result' 칼럼 추가하여 거기에 실험결과 추출 결과 추가
-> - LLM 모델: gpt-4o

실험 추출 결과는 json 형식으로 다음과 같은 형식으로 추출
{
  "assay": "IHC",
  "target": "Hyaluronan",
  "dose": "0.0375 mpk",
  "time_points": ["0.5h", "1h", "2h", "4h"],
  "groups": ["Vehicle", "L19", "L19-WT", "L19-63", "WT-Fc", "63-Fc"],
  "o   "time": "2h",
      "group": "L19-WT",
      "HA_positive_pixels": "~3%",
      "significance_vs_vehicle": "*"
    }
  ]
}

3. 예시 정답을 추가하여 테스트 데이터셋을 만들기
- 예시 정답은 원본 csv에 'example_answer' 칼럼 추가하여 거기에 추가
- LLM 모델: gpt-4o
- 예시 정답은 다음과 같은 지시사항에 따라 만들기기

system_prompt = """
You are a biomedical research assistant.
You must write a reference answer strictly grounded in the provided experimental results JSON.
No mechanisms. No hypotheses. No causal language. No external knowledge.
Return ONLY valid JSON matching the required schema.
"""
user_prompt = """
Given the following experimental results JSON, produce a reference conclusion JSON with this schema:

{
  "interpretation": [ ... ],
  "interpretation_limits": [ ... ],
  "cautions": [ ... ],
  "suggested_next_steps": [ ... ]
}

Rules:
- Use ONLY information present in the provided JSON.
- "interpretation": effect-level summaries only (what increased/decreased/differed/was significant).
- "interpretation_limits": limits of comparisons/conditions/time points/groups/dose; mention missing info explicitly (e.g., "other groups not reported").
- "cautions": generalizability constraints; avoid clinical claims.
- "suggested_next_steps": ONLY controlled extensions of the same experiment (dose/time/replicates/quantification/controls). No new mechanisms.
- Keep each list 2–6 bullets.
- If key fields are missing/unclear, say so instead of guessing.

Experimental results JSON:
<experiment_result JSON here>

"""

4. 최종 데이터셋 만들기 jsonl 형식으로 추가
- "instruction": "You are a biomedical research assistant.\nInterpret the experimental results strictly based on the provided observations.\nDo not infer mechanisms or conclusions beyond the data.\nClearly state interpretation limits."
- "input": "experiment_result"
- "output": "example_answer"
- 중간 출력 JSON 경로: sllm\datasets\eval\middle_test_dataset_yymmdd_hhmm.jsonl

5. 인풋과 아웃풋의 적절성 따져서 최종 데이터셋 만들기
- sllm\training\dataset_auditor.py 기능 사용하여 통과한 데이터셋만 최종 데이터셋으로 정리리
- 최종 출력 JSON 경로: sllm\datasets\eval\final_test_dataset_yymmdd_hhmm.jsonl


유의사항
- 이미지는 실제 이미지 파일이 아닌 이미지 url을 사용(fig_url 컬럼)
'''

import os
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv
import subprocess
import sys
import io

# Windows 환경 UTF-8 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# =========================
# CONFIG
# =========================

# API 설정
API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
TIMEOUT_SEC = int(os.getenv("LLM_TIMEOUT_SEC", "120"))
RETRY = int(os.getenv("LLM_RETRY", "3"))
SLEEP_BETWEEN = float(os.getenv("SLEEP_BETWEEN", "0.5"))

# 단계별 모델 지정
MODEL_STEP1_IS_EXPERIMENT = "gpt-4o-mini"  # Step 1: 실험 이미지 판단
MODEL_STEP2_EXTRACT_RESULT = "gpt-4o"      # Step 2: 실험 결과 추출
MODEL_STEP3_EXAMPLE_ANSWER = "gpt-4o"      # Step 3: 예시 정답 생성

# 경로 설정
BASE_DIR = Path(r"c:\dev\ai_camp\SKN18-FINAL-2TEAM")
CSV_PATH = BASE_DIR / "sllm" / "datasets" / "eval" / "t_figures_with_result_desc_v4 - t_figures_with_result_desc_v4.csv"
OUTPUT_DIR = BASE_DIR / "sllm" / "datasets" / "eval"
DATASET_AUDITOR_PATH = BASE_DIR / "sllm" / "training" / "dataset_auditor.py"

# 처리할 행 수
MAX_ROWS = 50

# 타임스탬프 생성
TIMESTAMP = datetime.now().strftime("%y%m%d_%H%M")

# 출력 파일 경로
OUTPUT_CSV = OUTPUT_DIR / f"t_figures_processed_{TIMESTAMP}.csv"
MIDDLE_JSONL = OUTPUT_DIR / f"middle_test_dataset_{TIMESTAMP}.jsonl"
FINAL_JSONL = OUTPUT_DIR / f"final_test_dataset_{TIMESTAMP}.jsonl"


# =========================
# LLM 호출 함수
# =========================

def call_llm(messages: list, model: str = "gpt-4o-mini",
             temperature: float = 0, response_format: Optional[Dict] = None) -> str:
    """LLM API 호출"""
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }

    if response_format:
        payload["response_format"] = response_format

    last_err = None
    for attempt in range(RETRY + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            last_err = e
            if attempt < RETRY:
                print(f"  ⚠️  Retry {attempt + 1}/{RETRY}: {e}")
                time.sleep(1.5)

    raise RuntimeError(f"LLM call failed after {RETRY} retries: {last_err}")


def call_llm_with_image(caption: str, image_url: str, system_prompt: str,
                        user_prompt: str, model: str = "gpt-4o-mini",
                        response_format: Optional[Dict] = None) -> str:
    """이미지와 텍스트를 함께 LLM에 전달"""
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt + f"\n\nFigure caption: {caption}"},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]

    return call_llm(messages, model=model, temperature=0, response_format=response_format)


# =========================
# Step 1: 실험 이미지 판단
# =========================

def is_experiment_image(row: pd.Series) -> bool:
    """이미지가 실험 결과를 나타내는지 판단 (gpt-4o-mini 사용)"""
    caption = row['fig_caption']
    image_url = row['fig_url']

    if pd.isna(caption) or pd.isna(image_url):
        return False

    system_prompt = """You are an expert in biomedical research image analysis.
Your task is to determine if an image shows experimental results (data tables, graphs, charts, etc.)."""

    user_prompt = """Does this image show experimental results such as:
- Data tables with measurements
- Bar charts, line graphs, scatter plots
- Heatmaps, western blots, microscopy with quantification
- Any visual representation of experimental data

Answer with ONLY a JSON object: {"is_experiment": true} or {"is_experiment": false}"""

    try:
        response = call_llm_with_image(
            caption, image_url, system_prompt, user_prompt,
            model=MODEL_STEP1_IS_EXPERIMENT,
            response_format={"type": "json_object"}
        )
        result = json.loads(response)
        return result.get("is_experiment", False)
    except Exception as e:
        print(f"  ❌ Error checking experiment image: {e}")
        return False


# =========================
# Step 2: 실험 결과 추출
# =========================

def extract_experiment_result(row: pd.Series) -> Optional[Dict[str, Any]]:
    """실험 결과를 JSON 형식으로 추출 (gpt-4o 사용)"""
    caption = row['fig_caption']
    image_url = row['fig_url']

    system_prompt = """You are an expert in extracting structured experimental data from biomedical images.
Extract ONLY the information visible in the image. Do not infer or add external knowledge."""

    user_prompt = """Extract experimental results from this image in the following JSON schema:

{
  "assay": "string (e.g., IHC, Western blot, ELISA, qPCR)",
  "target": "string (what is being measured)",
  "dose": "string (if mentioned)",
  "time_points": ["array of time points"],
  "groups": ["array of experimental groups/conditions"],
  "observations": [
    {
      "description": "what is observed",
      "value": "numerical or qualitative value",
      "significance": "statistical significance if shown (e.g., *, p<0.05)"
    }
  ]
}

Rules:
- Extract ONLY what is visible in the image
- Use "not specified" if information is missing
- Keep observations as factual as possible
- Include statistical significance markers if shown

Return ONLY valid JSON."""

    try:
        response = call_llm_with_image(
            caption, image_url, system_prompt, user_prompt,
            model=MODEL_STEP2_EXTRACT_RESULT,
            response_format={"type": "json_object"}
        )
        result = json.loads(response)
        return result
    except Exception as e:
        print(f"  ❌ Error extracting experiment result: {e}")
        return None


# =========================
# Step 3: 예시 정답 생성
# =========================

def generate_example_answer(experiment_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """실험 결과를 바탕으로 예시 정답 생성 (gpt-4o 사용)"""
    system_prompt = """You are a biomedical research assistant.
You must write a reference answer strictly grounded in the provided experimental results JSON.
No mechanisms. No hypotheses. No causal language. No external knowledge.
Return ONLY valid JSON matching the required schema."""

    user_prompt = f"""Given the following experimental results JSON, produce a reference conclusion JSON with this schema:

{{
  "interpretation": [ ... ],
  "interpretation_limits": [ ... ],
  "cautions": [ ... ],
  "suggested_next_steps": [ ... ]
}}

Rules:
- Use ONLY information present in the provided JSON.
- "interpretation": effect-level summaries only (what increased/decreased/differed/was significant).
- "interpretation_limits": limits of comparisons/conditions/time points/groups/dose; mention missing info explicitly (e.g., "other groups not reported").
- "cautions": generalizability constraints; avoid clinical claims.
- "suggested_next_steps": ONLY controlled extensions of the same experiment (dose/time/replicates/quantification/controls). No new mechanisms.
- Keep each list 2–6 bullets.
- If key fields are missing/unclear, say so instead of guessing.

Experimental results JSON:
{json.dumps(experiment_result, ensure_ascii=False, indent=2)}
"""

    try:
        response = call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_STEP3_EXAMPLE_ANSWER,
            response_format={"type": "json_object"}
        )
        result = json.loads(response)
        return result
    except Exception as e:
        print(f"  ❌ Error generating example answer: {e}")
        return None


# =========================
# Main Processing
# =========================

def process_csv():
    """CSV 파일 처리"""
    print(f"📁 Reading CSV from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding='utf-8')

    # 처리할 행 수 제한
    df = df.head(MAX_ROWS)
    print(f"📊 Processing {len(df)} rows")
    print(f"📝 Model configuration:")
    print(f"   Step 1 (is_experiment): {MODEL_STEP1_IS_EXPERIMENT}")
    print(f"   Step 2 (extract_result): {MODEL_STEP2_EXTRACT_RESULT}")
    print(f"   Step 3 (example_answer): {MODEL_STEP3_EXAMPLE_ANSWER}")

    # 새로운 컬럼 추가
    df['is_experiment'] = False
    df['experiment_result'] = None
    df['example_answer'] = None

    # Step 1 & 2 & 3: 각 행 처리
    for idx, row in df.iterrows():
        print(f"\n[{idx + 1}/{len(df)}] Processing fig_id: {row['fig_id']}")

        # Step 1: 실험 이미지 판단 (gpt-4o-mini)
        print(f"  🔍 Step 1: Checking if experiment image (model: {MODEL_STEP1_IS_EXPERIMENT})...")
        is_exp = is_experiment_image(row)
        df.at[idx, 'is_experiment'] = is_exp
        print(f"  {'✅' if is_exp else '❌'} is_experiment: {is_exp}")

        if is_exp:
            # Step 2: 실험 결과 추출 (gpt-4o)
            print(f"  📊 Step 2: Extracting experiment results (model: {MODEL_STEP2_EXTRACT_RESULT})...")
            exp_result = extract_experiment_result(row)
            if exp_result:
                df.at[idx, 'experiment_result'] = json.dumps(exp_result, ensure_ascii=False)
                print(f"  ✅ Extracted result")

                # Step 3: 예시 정답 생성 (gpt-4o)
                print(f"  💡 Step 3: Generating example answer (model: {MODEL_STEP3_EXAMPLE_ANSWER})...")
                example_ans = generate_example_answer(exp_result)
                if example_ans:
                    df.at[idx, 'example_answer'] = json.dumps(example_ans, ensure_ascii=False)
                    print(f"  ✅ Generated answer")

            time.sleep(SLEEP_BETWEEN)

    # CSV 저장
    print(f"\n💾 Saving processed CSV to: {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')

    return df


def create_middle_dataset(df: pd.DataFrame):
    """중간 데이터셋 생성 (JSONL 형식)"""
    print(f"\n📝 Step 4: Creating middle dataset: {MIDDLE_JSONL}")

    instruction = """You are a biomedical research assistant.
Interpret the experimental results strictly based on the provided observations.
Do not infer mechanisms or conclusions beyond the data.
Clearly state interpretation limits."""

    count = 0
    with open(MIDDLE_JSONL, 'w', encoding='utf-8') as f:
        for idx, row in df.iterrows():
            if row['is_experiment'] and pd.notna(row['experiment_result']) and pd.notna(row['example_answer']):
                try:
                    exp_result = json.loads(row['experiment_result'])
                    example_ans = json.loads(row['example_answer'])

                    sample = {
                        "instruction": instruction,
                        "input": exp_result,
                        "output": example_ans
                    }

                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')
                    count += 1
                except Exception as e:
                    print(f"  ⚠️  Row {idx} skipped: {e}")

    print(f"✅ Created {count} samples in middle dataset")
    return count


def audit_and_create_final_dataset():
    """dataset_auditor.py를 사용하여 최종 데이터셋 생성"""
    print(f"\n🔍 Step 5: Auditing dataset with dataset_auditor.py...")

    try:
        # dataset_auditor.py 실행
        cmd = [
            sys.executable,
            str(DATASET_AUDITOR_PATH),
            "--in_jsonl", str(MIDDLE_JSONL),
            "--out_final_jsonl", str(FINAL_JSONL)
        ]

        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            print("✅ Dataset audit completed successfully")
            print(result.stdout)
        else:
            print(f"❌ Dataset audit failed")
            print(result.stderr)
            return False

        return True
    except Exception as e:
        print(f"❌ Error running dataset_auditor: {e}")
        return False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 Starting Test Dataset Creation Process")
    print("=" * 60)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1, 2, 3: CSV 처리
    df = process_csv()

    # Step 4: 중간 데이터셋 생성
    sample_count = create_middle_dataset(df)

    if sample_count == 0:
        print("\n⚠️  No valid samples found. Exiting.")
        return

    # Step 5: 최종 데이터셋 생성 (audit)
    success = audit_and_create_final_dataset()

    if success:
        print("\n" + "=" * 60)
        print("✅ Test Dataset Creation Completed Successfully!")
        print("=" * 60)
        print(f"\n📁 Output files:")
        print(f"  - Processed CSV: {OUTPUT_CSV}")
        print(f"  - Middle JSONL: {MIDDLE_JSONL}")
        print(f"  - Final JSONL: {FINAL_JSONL}")
    else:
        print("\n⚠️  Dataset creation completed with warnings")
        print(f"  - Processed CSV: {OUTPUT_CSV}")
        print(f"  - Middle JSONL: {MIDDLE_JSONL}")


if __name__ == "__main__":
    main()
