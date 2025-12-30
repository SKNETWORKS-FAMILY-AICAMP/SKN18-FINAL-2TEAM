'''
1. 완성된 annotation json 데이터 만들기
-   annotation.json 파일 만들기 (저장경로 : sllm\datasets )

``` # 1. json 파일 예시
{
  "observations": [
    "Proteomic analysis identified 1,427 differentially expressed proteins in MALT1-knockout cells",
    "Overlap of proteomic and FACS data revealed 16 proteins that modulate GPX4 protein levels",
    "RC3H1 protein expression increased in MALT1-deficient cells with reduced cleavage",
    "RC3H1 physically interacts with GPX4",
    "RC3H1 knockdown increases GPX4 protein levels and reduces GPX4 ubiquitination",
    "RC3H1 overexpression promotes ubiquitin-dependent GPX4 degradation",
    "Interference with RC3H1 reverses GPX4 degradation in MALT1-deficient cells"
  ],
  "question": "What mechanism explains how MALT1 regulates GPX4 ubiquitination and protein stability?",
  "conclusion": {
  "interpretation": [
    "MALT1 suppresses GPX4 ubiquitination by cleaving the E3 ubiquitin ligase RC3H1.",
    "RC3H1 directly promotes ubiquitin-dependent degradation of GPX4."
  ],
  "interpretation_limits": [
    "The precise ubiquitination sites on GPX4 are not identified.",
    "Other E3 ligases regulating GPX4 were not evaluated."
  ],
  "cautions": [
    "These findings are based on in vitro liver cancer cell models.",
    "Temporal dynamics beyond the tested conditions are not assessed."
  ],
  "suggested_next_steps": [
    "Map ubiquitination sites on GPX4 mediated by RC3H1.",
    "Test whether other E3 ligases compensate for RC3H1 loss."
  ]
}

  "interpretation_boundary": {
    "can_conclude": [
      "RC3H1 promotes ubiquitin-dependent degradation of GPX4",
      "MALT1 negatively regulates RC3H1 through proteolytic cleavage",
      "MALT1 indirectly stabilizes GPX4 protein levels"
    ],
    "cannot_conclude": [
      "Exact molecular details of RC3H1-mediated ubiquitination of GPX4",
      "Whether other E3 ligases regulate GPX4",
      "Clinical implications of the MALT1–RC3H1–GPX4 axis"
    ]
  }
}



2. 완성된 annotation json 데이터를 sft 데이터셋으로 변환하기
1에서 만든 json 데이터에서 instruction, input, output 으로 이루어진 JSONL 형식의 데이터셋 만들기. 
이름은 sft_dataset.jsonl 파일로 저장하기 (저장경로 : sllm\datasets )
- instruction: 항상 고정문구
- input: json 데이터에서 conclution을 제외한 필드
- output: json 데이터에서 conclusion의 값
(예시)
input = {
  "observations": [
    "Proteomic analysis identified 1,427 differentially expressed proteins in MALT1-knockout cells",
    "Overlap of proteomic and FACS data revealed 16 proteins that modulate GPX4 protein levels",
    "RC3H1 protein expression increased in MALT1-deficient cells with reduced cleavage",
    "RC3H1 physically interacts with GPX4",
    "RC3H1 knockdown increases GPX4 protein levels and reduces GPX4 ubiquitination",
    "RC3H1 overexpression promotes ubiquitin-dependent GPX4 degradation",
    "Interference with RC3H1 reverses GPX4 degradation in MALT1-deficient cells"
  ],
  "question": "What mechanism explains how MALT1 regulates GPX4 ubiquitination and protein stability?",
  "interpretation_boundary": {
    "can_conclude": [
      "RC3H1 promotes ubiquitin-dependent degradation of GPX4",
      "MALT1 negatively regulates RC3H1 through proteolytic cleavage",
      "MALT1 indirectly stabilizes GPX4 protein levels"
    ],
    "cannot_conclude": [
      "Exact molecular details of RC3H1-mediated ubiquitination of GPX4",
      "Whether other E3 ligases regulate GPX4",
      "Clinical implications of the MALT1–RC3H1–GPX4 axis"
    ]
  }
}


output = {
  "interpretation": [
    "MALT1 suppresses GPX4 ubiquitination by cleaving the E3 ubiquitin ligase RC3H1.",
    "RC3H1 directly promotes ubiquitin-dependent degradation of GPX4."
  ],
  "interpretation_limits": [
    "The precise ubiquitination sites on GPX4 are not identified.",
    "Other E3 ligases regulating GPX4 were not evaluated."
  ],
  "cautions": [
    "These findings are based on in vitro liver cancer cell models.",
    "Temporal dynamics beyond the tested conditions are not assessed."
  ],
  "suggested_next_steps": [
  "Suggest follow-up experiments WITHOUT proposing mechanisms.",
  "Experiments should aim to reproduce, validate, or test generality of the observed effects only."
  ]
}




'''

################ config ################
PROCESS_ROWS = 10  # 처리할 데이터 row 개수
CSV_PATH = r"c:\dev\ai_camp\SKN18-FINAL-2TEAM\sllm\datasets\section_category_result.csv"

# 타임스탬프는 실행 시 동적으로 생성됨
ANNOTATION_OUTPUT = None  # create_annotation_json()에서 설정
SFT_OUTPUT = None  # create_sft_dataset()에서 설정



################ 1. annotation.json ################

import pandas as pd
from openai import OpenAI
import json
import os
from tqdm import tqdm
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

client = OpenAI()




SYSTEM_PROMPT = """
You are a scientific Results-section data extractor.

Your role is NOT to explain mechanisms or propose hypotheses.
Your role is to strictly separate:
1) experimentally observed facts
2) minimal, non-mechanistic effect-level summaries

CRITICAL RULES (VIOLATION = FAILURE):
- NEVER propose or imply molecular, structural, catalytic, or mechanistic explanations.
- NEVER use causal or speculative words such as:
  "mechanism", "mechanistic", "likely", "suggest", "indicate", 
  "facilitate", "contribute", "due to", "because", "implies", "potential".
- If a causal or mechanistic explanation is not explicitly proven in the Results text,
  it MUST be treated as NOT CONCLUDABLE.

Your output will be used for small language model training.
Over-interpretation is considered a critical error.
If you are unsure whether a statement is interpretive, restate the observation verbatim or state that the comparison cannot be made.
"""




def build_user_prompt(result_text: str) -> str:
    return f"""
From the following Results-section text, extract a STRICTLY LIMITED dataset.

Results text:
\"\"\"
{result_text}
\"\"\"

IMPORTANT GOAL:
This task evaluates whether you can STOP at the level of experimental evidence.
Any mechanistic or causal reasoning is a FAILURE.

CRITICAL: Remove any sentences that have Methods, Review, or Introduction characteristics.
- Methods: descriptions of procedures, protocols, experimental setups
- Review: background information, literature references, general knowledge
- Introduction: context-setting, hypothesis statements, research questions
- Keep ONLY Results-section content: experimental findings and data.

Output JSON schema (MUST FOLLOW EXACTLY):

{{
  "observations": [
    "ONLY experimentally observed facts directly stated in the Results section.",
    "MUST contain: numbers, comparisons, increase/decrease indicators, OR accessibility indicators.",
    "If an observation lacks ALL of these, DELETE it.",
    "NO background knowledge.",
    "NO explanations.",
    "NO causes.",
    "NO textbook statements."
  ],

  "question": "ONE neutral comparison statement describing the experimental contrast (X vs Y), without asking why or how. MUST end with a question mark (?)."

  "conclusion": {{
    "interpretation": [
      "Effect-level summaries ONLY.",
      "Describe WHAT changed, increased, decreased, differed, or was associated.",
      "NO mechanisms, NO hypotheses, NO causal language.",
      "If unsure, restate the observation in compact form or state that the comparison cannot be made."
    ],
    "interpretation_limits": [
      "State limits of the reported comparisons or measurements.",
      "Mention if only specific conditions, cell lines, time points, or concentrations were tested.",
      "Do NOT introduce new concepts or mechanisms."
    ],
    "cautions": [
      "Highlight experimental context and limitations.",
      "Note any constraints on generalizability."
    ],
    "suggested_next_steps": [
      "Suggest ONLY follow-up experiments that repeat or extend the same comparison under controlled variations (e.g., different concentrations, temperatures, or time points).",
      "Do NOT introduce new explanatory variables or mechanisms."
    ]
  }},

  "interpretation_boundary": {{
    "can_conclude": [
      "Statements that are DIRECT restatements of observed effects."
    ],
    "cannot_conclude": [
      "ANY molecular, structural, catalytic, physiological, or clinical explanations.",
      "ANY causal or mechanistic claims not explicitly demonstrated.",
      "Paraphrasing is allowed ONLY if numerical or directional meaning is preserved.",
      "No abstraction beyond the observed comparison is allowed."
    ]
  }}
}}
"""




def extract_dataset_from_result(result_text: str):
    """OpenAI API를 사용하여 결과 텍스트에서 구조화된 데이터 추출"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # $99.57 -> 99.56 (10개)
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(result_text)}
            ],
            response_format={"type": "json_object"},
            max_tokens=1024
        )
        content = response.choices[0].message.content

        # 마크다운 코드블록 제거 (```json ... ``` 형태 처리)
        content = content.strip()
        if content.startswith("```"):
            # 첫 번째 줄(```json) 제거
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1]) if len(lines) > 2 else content
            content = content.strip()

        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Content received: {content[:200]}...")  # 처음 200자만 출력
        return None
    except Exception as e:
        print(f"Error extracting data: {e}")
        return None


def create_annotation_json():
    """CSV에서 데이터를 읽어 annotation.json 생성 (1건씩 저장)"""
    # 타임스탬프 생성 (YYMMDDHHMMSS 형식)
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    annotation_output = rf"c:\dev\ai_camp\SKN18-FINAL-2TEAM\sllm\datasets\annotation_v1_{timestamp}.json"

    print(f"📂 Loading CSV from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    # PROCESS_ROWS만큼만 처리
    df_subset = df.head(PROCESS_ROWS)
    print(f"📊 Processing {len(df_subset)} rows...")

    # 기존 파일이 있으면 로드, 없으면 빈 리스트
    if os.path.exists(annotation_output):
        print(f"📖 Loading existing annotation.json...")
        with open(annotation_output, 'r', encoding='utf-8') as f:
            annotations = json.load(f)
        print(f"   Found {len(annotations)} existing entries")
    else:
        annotations = []

    for idx, row in tqdm(df_subset.iterrows(), total=len(df_subset), desc="Extracting data"):
        section_text = row['section_text']
        section_id = row['section_id']

        # 이미 처리된 section_id는 건너뛰기
        if any(ann.get('section_id') == section_id for ann in annotations):
            print(f"⏭️  Skipping already processed section_id: {section_id}")
            continue

        # OpenAI API로 구조화된 데이터 추출
        structured_data = extract_dataset_from_result(section_text)

        if structured_data:
            # sid는 1부터 시작하는 자동 증가 ID
            annotation_entry = {
                "sid": len(annotations) + 1,
                "section_id": section_id,
                **structured_data  # observations, question, conclusion, interpretation_boundary 추가
            }
            annotations.append(annotation_entry)

            # 1건씩 즉시 저장
            with open(annotation_output, 'w', encoding='utf-8') as f:
                json.dump(annotations, f, indent=2, ensure_ascii=False)

            print(f"💾 Saved entry {len(annotations)}: section_id={section_id}")
        else:
            print(f"⚠️  Failed to extract data for section_id: {section_id}")

    print(f"✅ Successfully created {annotation_output} with {len(annotations)} entries")
    return annotations, annotation_output




################ 2. sft_dataset.jsonl ################

INSTRUCTION = """You are a biomedical research assistant.
Interpret the experimental results strictly based on the provided observations.
Do not infer mechanisms or conclusions beyond the data.
Clearly state interpretation limits."""


def create_sft_dataset(annotation_output):
    """annotation.json을 읽어 SFT dataset JSONL 생성"""
    # 타임스탬프 생성 (YYMMDDHHMMSS 형식)
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    sft_output = rf"c:\dev\ai_camp\SKN18-FINAL-2TEAM\sllm\datasets\sft_dataset_v1_{timestamp}.jsonl"

    print(f"\n📂 Loading annotation.json from: {annotation_output}")

    # annotation.json 로드
    with open(annotation_output, 'r', encoding='utf-8') as f:
        annotations = json.load(f)

    print(f"📊 Processing {len(annotations)} annotations...")

    # SFT 데이터셋 생성
    sft_dataset = []

    for annotation in tqdm(annotations, desc="Creating SFT dataset"):
        # input: conclusion을 제외한 모든 필드
        input_data = {
            "observations": annotation.get("observations", []),
            "question": annotation.get("question", ""),
            "interpretation_boundary": annotation.get("interpretation_boundary", {})
        }

        # output: conclusion 값만
        output_data = annotation.get("conclusion", "")

        # SFT 형식으로 데이터 구성 (section_id, sid 제외)
        sft_entry = {
            "instruction": INSTRUCTION,
            "input": input_data,
            "output": output_data
        }

        sft_dataset.append(sft_entry)

    # JSONL 파일로 저장 (한 줄에 하나의 JSON)
    print(f"💾 Saving SFT dataset to: {sft_output}")
    with open(sft_output, 'w', encoding='utf-8') as f:
        for entry in sft_dataset:
            json_line = json.dumps(entry, ensure_ascii=False)
            f.write(json_line + '\n')

    print(f"✅ Successfully created {sft_output} with {len(sft_dataset)} entries")
    return sft_dataset, sft_output




################ main ################

def main():
    """전체 파이프라인 실행: annotation.json 생성 → SFT dataset 생성"""
    print("=" * 60)
    print("🚀 Starting SFT Dataset Creation Pipeline")
    print("=" * 60)

    try:
        # Step 1: annotation.json 생성
        print("\n[Step 1/2] Creating annotation.json...")
        annotations, annotation_output = create_annotation_json()

        # Step 2: SFT dataset 생성
        print("\n[Step 2/2] Creating SFT dataset JSONL...")
        sft_dataset, sft_output = create_sft_dataset(annotation_output)

        print("\n" + "=" * 60)
        print("✅ Pipeline completed successfully!")
        print(f"   - Annotation JSON: {annotation_output}")
        print(f"   - SFT Dataset JSONL: {sft_output}")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\n❌ Error: File not found - {e}")
        print("   Please check the file paths in the config section.")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
