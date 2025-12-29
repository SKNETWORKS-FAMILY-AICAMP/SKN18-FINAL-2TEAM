"""
Phase 1: Result Description → Structured JSON (with Sentence Deduplication)
===========================================================================

목적:
    그래프/표 Figure의 result_desc를 구조화된 사고 단위(JSON)로 분해
    중복 문장 제거를 통한 데이터 정제

입력:
    - t_figures_with_result_desc_v4.csv (Phase 0 완료된 파일)
      필요 컬럼: [fig_id, is_experiment_result, result_desc]

처리:
    - is_experiment_result=true인 Figure만 처리
    - result_desc에서 중복 문장 제거
    - GPT-4o-mini Text API로 정제된 result_desc를 구조화된 JSON으로 변환
    - Results 문장을 사고 단위로 분해:
      * experimental_context (모델, 분석법)
      * observation (측정 대상, 방향, 크기)
      * comparison (그룹 비교)
      * temporal_or_dose_dimension (시간, 농도)
      * statistical_claim (통계적 유의성)
      * interpretation_boundary (가능한 결론, 불가능한 결론)

출력:
    - 원본 CSV 파일에 structured_json 컬럼 추가
      (중복 제거된 result_desc 기반 구조화 데이터)

설정:
    - SAMPLE_SIZE: 처리할 샘플 개수 (None = 전체)
    - MODEL: 사용할 OpenAI 모델 (기본: gpt-4o-mini)

핵심 설계 원칙 (README.md 기반):
    ✅ Results 문장 4조각 분해: observation, comparison, direction, confidence
    ✅ 해석 경계 설정: can_conclude vs cannot_conclude
    ✅ 사고 단위 추출: 6개 필수 필드
    ❌ 기전 추론 금지
    ❌ 과장된 일반화 금지
"""

import os
import json
import pandas as pd
from openai import OpenAI
from typing import Dict, List, Optional
import time
import re
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from collections import OrderedDict

import dotenv
dotenv.load_dotenv()


class ResultDescToStructuredConverter:
    """result_desc 텍스트를 구조화된 추론 단위로 변환하는 클래스"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 (기본값: gpt-4o-mini)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        print(f"✅ Using model: {self.model}")

        # 시스템 프롬프트 (README.md 기반)
        self.system_prompt = """You are a biomedical research assistant.

Your task is NOT to interpret beyond the text.
Your task is to extract the explicit reasoning units that a researcher confirms
when reading a Results section while looking at the corresponding figure.

Rules:
- Do NOT add assumptions.
- Do NOT infer mechanisms.
- Do NOT generalize beyond what is stated.
- If information is missing, explicitly mark it as "not stated".
- Stay strictly within the Results text.

Output must be valid JSON only, with no additional text."""

        # 유저 프롬프트 템플릿 (README.md 기반)
        self.user_prompt_template = """Given the following Results sentence(s), decompose them into
explicit reasoning units that reflect what a researcher confirms
from the figure.

Extract the following fields:

1. experimental_context
   - model (e.g., mouse, cell line) or "not stated"
   - assay / measurement method (e.g., IHC, IVIS) or "not stated"

2. observation
   - what was measured
   - direction of change (increase / decrease / no change / not stated)
   - approximate magnitude or qualitative description

3. comparison
   - treatment vs control
   - group vs group
   - time or dose comparison

4. temporal_or_dose_dimension
   - time point(s)
   - dose / concentration (if stated)

5. statistical_claim
   - significant / not significant / trend / not stated

6. interpretation_boundary
   - what can be concluded based ONLY on this result
   - what cannot be concluded based on this result

Output strictly in JSON.
Do not add explanations outside the JSON.

Results text:
{result_desc}"""

    def deduplicate_sentences(self, text: str) -> str:
        """
        result_desc 텍스트에서 중복 문장 제거
        - 줄바꿈 문자를 공백으로 변환
        - 중복 문장 제거

        Args:
            text: 원본 result_desc 텍스트

        Returns:
            중복 제거된 실험 결과 텍스트
        """
        # 1. 줄바꿈 문자를 공백으로 변환 (데이터 정리)
        results_text = text.replace('\n\n', ' ').replace('\n', ' ')

        # 2. 연속된 공백을 하나로 정리
        results_text = re.sub(r'\s+', ' ', results_text).strip()

        # 3. 마침표와 쉼표를 기준으로 문장 분리
        sentences = re.split(r'\.,|\.\s+', results_text)

        seen_normalized = set()
        deduplicated_sentences = []

        for sentence in sentences:
            clean_sentence = sentence.strip()
            if not clean_sentence:
                continue

            # 비교용 데이터 정규화
            normalized = re.sub(r'\s+', ' ', clean_sentence.lower().rstrip('.'))

            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                deduplicated_sentences.append(clean_sentence.rstrip('.'))

        # 4. 문장 재구성
        final_results = '. '.join(deduplicated_sentences)

        if results_text.rstrip().endswith('.'):
            final_results += '.'

        return final_results

    def clean_user_message(self, text: str) -> str:
        """
        User 메시지에서 instruction 제거 및 중복 문장 정리
        - Instruction prefix/suffix 제거
        - 줄바꿈 문자를 공백으로 변환
        - 중복 문장 제거

        Args:
            text: 원본 user 메시지

        Returns:
            정리된 실험 결과 텍스트 (instruction 없이)
        """
        prompt_prefix = "Analyze the following experimental results text and decompose it into structured reasoning units.\n\nResults text:\n"
        prompt_suffix = "\n\nProvide a JSON output with the following structure:\n- experimental_context: model and assay information\n- observation: measurement, direction, and magnitude\n- comparison: groups being compared\n- temporal_or_dose_dimension: time and dose information\n- statistical_claim: statistical significance\n- interpretation_boundary: what can and cannot be concluded"

        # 1. 본문 추출 (instruction 제거)
        if text.startswith(prompt_prefix) and text.endswith(prompt_suffix):
            results_text = text[len(prompt_prefix):-len(prompt_suffix)]
        else:
            results_text = text

        # 2. 줄바꿈 문자를 공백으로 변환 (데이터 정리)
        results_text = results_text.replace('\n\n', ' ').replace('\n', ' ')

        # 3. 연속된 공백을 하나로 정리
        results_text = re.sub(r'\s+', ' ', results_text).strip()

        # 4. 마침표와 쉼표를 기준으로 문장 분리
        sentences = re.split(r'\.,|\.\s+', results_text)

        seen_normalized = set()
        deduplicated_sentences = []

        for sentence in sentences:
            clean_sentence = sentence.strip()
            if not clean_sentence:
                continue

            # 비교용 데이터 정규화
            normalized = re.sub(r'\s+', ' ', clean_sentence.lower().rstrip('.'))

            if normalized not in seen_normalized:
                seen_normalized.add(normalized)
                deduplicated_sentences.append(clean_sentence.rstrip('.'))

        # 5. 문장 재구성
        final_results = '. '.join(deduplicated_sentences)

        if results_text.rstrip().endswith('.'):
            final_results += '.'

        return final_results

    def clean_assistant_message(self, json_str: str) -> str:
        """
        Assistant 메시지에서 "not stated" 필드 제거

        Args:
            json_str: JSON 문자열

        Returns:
            정리된 JSON 문자열 (값이 있는 필드만 포함)
        """
        try:
            data = json.loads(json_str)

            # "not stated" 값을 가진 필드를 재귀적으로 제거
            def remove_not_stated(obj):
                if isinstance(obj, dict):
                    return {
                        k: remove_not_stated(v)
                        for k, v in obj.items()
                        if v != "not stated" and v != "" and v is not None
                    }
                elif isinstance(obj, list):
                    return [remove_not_stated(item) for item in obj]
                else:
                    return obj

            cleaned_data = remove_not_stated(data)

            # 깔끔한 JSON 문자열로 변환 (들여쓰기 2칸)
            return json.dumps(cleaned_data, ensure_ascii=False, indent=2)

        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 반환
            return json_str

    def _parse_retry_after(self, error_message: str) -> Optional[float]:
        """
        Rate limit 에러 메시지에서 대기 시간(ms)을 파싱
        
        Args:
            error_message: 에러 메시지
            
        Returns:
            대기 시간(초), 파싱 실패 시 None
        """
        # "Please try again in 319ms" 형식 찾기
        pattern = r'Please try again in (\d+(?:\.\d+)?)\s*ms'
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            ms = float(match.group(1))
            return ms / 1000.0  # 초로 변환
        
        # "retry-after: 60" 형식 찾기 (초 단위)
        pattern = r'retry[_-]after[:\s]+(\d+(?:\.\d+)?)'
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        return None

    def structure_result_desc(self, result_desc: str, max_retries: int = 5) -> Dict:
        """
        result_desc 텍스트를 구조화된 JSON으로 변환
        중복 문장 제거 후 구조화 수행
        Rate limit 발생 시 Exponential backoff with retry 적용

        Args:
            result_desc: Results 섹션 텍스트
            max_retries: 최대 재시도 횟수

        Returns:
            구조화된 추론 단위 딕셔너리
        """
        # 1. 중복 문장 제거
        deduplicated_desc = self.deduplicate_sentences(result_desc)

        # 2. 유저 프롬프트 생성
        user_prompt = self.user_prompt_template.format(
            result_desc=deduplicated_desc
        )

        # Exponential backoff with retry
        for attempt in range(max_retries):
            try:
                # GPT-4o-mini Text API 호출
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    max_tokens=1500,
                    temperature=0,
                    response_format={"type": "json_object"}
                )

                # 응답에서 JSON 추출
                json_response = response.choices[0].message.content.strip()
                structured_data = json.loads(json_response)

                return structured_data

            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                return {
                    "error": "JSON parsing failed",
                    "raw_response": response.choices[0].message.content if response else None
                }
            except Exception as e:
                error_str = str(e)
                
                # Rate limit (429) 에러인지 확인
                is_rate_limit = (
                    '429' in error_str or 
                    'rate_limit' in error_str.lower() or
                    'rate limit' in error_str.lower()
                )
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Rate limit 에러 메시지에서 대기 시간 파싱
                    retry_after = self._parse_retry_after(error_str)
                    
                    if retry_after:
                        # 파싱된 대기 시간 사용 (최소 1초, 최대 60초)
                        wait_time = max(1.0, min(retry_after + 0.5, 60.0))
                        print(f"⚠️  Rate limit (429) detected. Waiting {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    else:
                        # Exponential backoff: 2^attempt 초 (최대 32초)
                        wait_time = min(2 ** attempt, 32.0)
                        print(f"⚠️  Rate limit (429) detected. Waiting {wait_time:.1f}s (exponential backoff, attempt {attempt + 1}/{max_retries})...")
                    
                    time.sleep(wait_time)
                    continue  # 재시도
                else:
                    # Rate limit이 아니거나 최대 재시도 횟수 초과
                    if is_rate_limit:
                        print(f"❌ Rate limit (429) - Max retries ({max_retries}) exceeded")
                    else:
                        print(f"Error structuring text: {error_str}")
                    return {
                        "error": error_str
                    }
        
        # 모든 재시도 실패
        return {
            "error": f"Max retries ({max_retries}) exceeded"
        }

    def process_batch(
        self,
        input_csv: str,
        output_csv: str,
        output_jsonl: Optional[str] = None,
        sample_size: Optional[int] = None,
        resume: bool = True
    ) -> pd.DataFrame:
        """
        Phase 0 완료된 CSV를 배치 처리하여:
        1. 구조화된 JSON 생성 (중복 문장 제거 포함)
        2. Training dataset 형식으로 변환 및 전처리
        3. CSV에 structured_json 컬럼 추가

        Args:
            input_csv: Phase 0 완료된 CSV (t_figures_with_result_desc_v4.csv)
            output_csv: 출력 CSV (원본에 structured_json 컬럼 추가)
            output_jsonl: 출력 JSONL 파일 경로 (training_dataset_preprocessed_*.jsonl)
            sample_size: 처리할 샘플 개수 (None = 전체)
            resume: True면 기존 결과 파일에서 이어서 진행

        Returns:
            결과 DataFrame
        """
        
        # Phase 0 결과 로드
        print(f"\n📂 Loading data from: {input_csv}")
        df = pd.read_csv(input_csv)

        # 첫 번째 컬럼이 무명 인덱스인 경우 fig_id로 변환
        if df.columns[0] == 'Unnamed: 0' or df.columns[0] == '':
            df.rename(columns={df.columns[0]: 'fig_id'}, inplace=True)

        # fig_id 컬럼이 없으면 생성
        if 'fig_id' not in df.columns:
            raise ValueError("CSV file must have a fig_id column or unnamed index column")

        print(f"   Total figures: {len(df)}")

        # is_experiment_result 컬럼 확인
        if 'is_experiment_result' not in df.columns:
            raise ValueError(
                "Missing 'is_experiment_result' column. "
                "Please run Phase 0 first (phase_0_figure_classification.py)"
            )

        # structured_json 컬럼 추가 (없으면)
        if 'structured_json' not in df.columns:
            df['structured_json'] = None
            print(f"   Added column: structured_json")

        # is_experiment_result=True인 것만 필터링
        target_df = df[df['is_experiment_result'] == True].copy()
        print(f"   Experimental result data: {len(target_df)}")

        # result_desc가 있는 것만 처리
        target_df = target_df[target_df['result_desc'].notna() & (target_df['result_desc'] != '')].copy()
        print(f"   With result_desc: {len(target_df)}")

        if len(target_df) == 0:
            print("⚠️  No data to process!")
            return df

        # 샘플 크기 제한
        if sample_size:
            target_indices = target_df.head(sample_size).index
            print(f"   Processing sample: {len(target_indices)} figures")
        else:
            target_indices = target_df.index

        # 미처리 데이터 필터링 (resume)
        # is_experiment_result=true이면서 structured_json이 비어있는 것만 처리
        if resume:
            # CSV에서 structured_json이 비어있는 것만
            unprocessed_mask = df.loc[target_indices, 'structured_json'].isna() | (df.loc[target_indices, 'structured_json'] == '')
            unprocessed_indices = target_indices[unprocessed_mask]
            processed_count = len(target_indices) - len(unprocessed_indices)
            if processed_count > 0:
                print(f"   Resuming: {processed_count} figures already processed (skipping)")
            indices_to_process = unprocessed_indices
            print(f"   Remaining: {len(indices_to_process)} figures to process")
        else:
            # resume=False일 때도 structured_json이 비어있는 것만 처리
            unprocessed_mask = df.loc[target_indices, 'structured_json'].isna() | (df.loc[target_indices, 'structured_json'] == '')
            indices_to_process = target_indices[unprocessed_mask]
            if len(indices_to_process) < len(target_indices):
                print(f"   Skipping {len(target_indices) - len(indices_to_process)} already processed figures")
            print(f"   Processing: {len(indices_to_process)} figures with empty structured_json")

        if len(indices_to_process) == 0:
            print("✅ All data already processed!")
            if output_jsonl and os.path.exists(output_jsonl):
                with open(output_jsonl, 'r', encoding='utf-8') as f:
                    existing_count = sum(1 for line in f if line.strip())
                print(f"   Loaded existing {existing_count} samples from JSONL")
            return df

        # Training dataset 저장용 리스트
        all_training_samples = []

        # 기존 JSONL 파일이 있으면 로드
        if output_jsonl and os.path.exists(output_jsonl):
            with open(output_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_training_samples.append(json.loads(line))
            print(f"   Loaded {len(all_training_samples)} existing samples from JSONL")

        # User prompt template (training dataset 생성용)
        user_prompt_template = """Analyze the following experimental results text and decompose it into structured reasoning units.

Results text:
{result_desc}

Provide a JSON output with the following structure:
- experimental_context: model and assay information
- observation: measurement, direction, and magnitude
- comparison: groups being compared
- temporal_or_dose_dimension: time and dose information
- statistical_claim: statistical significance
- interpretation_boundary: what can and cannot be concluded"""

        # 실패한 항목 추적용 리스트
        failed_items = []

        # 각 result_desc 처리
        print("\n🔄 Processing result_desc to structured JSON and creating training dataset...")
        for idx in tqdm(indices_to_process, desc="Progress"):
            row = df.loc[idx]
            fig_id = row['fig_id']
            result_desc = row['result_desc']

            # 구조화 실행 (내부에서 중복 제거 수행)
            structured_json = self.structure_result_desc(result_desc)

            # 에러가 있으면 실패 항목으로 추가 (Phase 3에서 처리)
            if 'error' in structured_json:
                print(f"⚠️  Warning: {fig_id} has error, skipping (will be handled in Phase 3)")
                failed_items.append({
                    'fig_id': fig_id,
                    'result_desc': result_desc,
                    'error': structured_json.get('error', 'Unknown error')
                })
                continue

            # CSV에 structured_json 저장 (먼저 저장하여 중단 시에도 보존)
            df.loc[idx, 'structured_json'] = json.dumps(structured_json, ensure_ascii=False)
            
            # CSV 즉시 저장 (중단 시에도 데이터 보존)
            try:
                df.to_csv(output_csv, index=False)
            except Exception as e:
                print(f"⚠️  Warning: Failed to save CSV: {e}")

            # Training dataset 형식으로 변환
            # User prompt 생성
            user_content = user_prompt_template.format(result_desc=result_desc)
            
            # Assistant response (구조화된 JSON을 문자열로)
            assistant_content = json.dumps(structured_json, ensure_ascii=False, indent=2)

            # 전처리 적용
            # User 메시지 정리 (instruction 제거 + 중복 제거)
            cleaned_user_msg = self.clean_user_message(user_content)
            
            # Assistant 메시지 정리 ("not stated" 필드 제거)
            cleaned_assistant_msg = self.clean_assistant_message(assistant_content)

            # Training dataset 샘플 생성 (system은 제외, user와 assistant만)
            training_sample = {
                "fig_id": fig_id,
                "messages": [
                    {
                        "role": "user",
                        "content": cleaned_user_msg
                    },
                    {
                        "role": "assistant",
                        "content": cleaned_assistant_msg
                    }
                ]
            }

            # Training dataset 리스트에 추가
            all_training_samples.append(training_sample)

            # JSONL 저장 (매 건마다, 중단 시에도 보존)
            if output_jsonl:
                try:
                    with open(output_jsonl, 'w', encoding='utf-8') as f:
                        for sample in all_training_samples:
                            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
                except Exception as e:
                    print(f"⚠️  Warning: Failed to save JSONL: {e}")

            # API Rate limit 방지 (1.5초 대기)
            time.sleep(1.5)

        # 실패한 항목을 true_fail.csv로 저장
        if failed_items:
            fail_csv_path = Path(input_csv).parent / 'true_fail.csv'
            fail_df = pd.DataFrame(failed_items)
            fail_df.to_csv(fail_csv_path, index=False, encoding='utf-8')
            print(f"\n⚠️  실패한 항목 저장: {fail_csv_path.name} ({len(failed_items)}개)")

        # 최종 저장 (처리된 항목이 있는 경우)
        if output_jsonl and len(all_training_samples) > 0:
            print(f"\n💾 Saving final training dataset to: {output_jsonl}")
            with open(output_jsonl, 'w', encoding='utf-8') as f:
                for sample in all_training_samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')
            print(f"✅ Saved {len(all_training_samples)} training samples to: {output_jsonl}")
        elif output_jsonl:
            print(f"\n⚠️  Warning: No training samples to save. File will not be created: {output_jsonl}")

        # System 메시지를 별도 파일로 저장 (전역 선언용)
        if output_jsonl:
            system_file = Path(output_jsonl).parent / f"system_message_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
            training_system_message = "You are a biomedical research assistant specialized in analyzing experimental results. Your task is to decompose Results sections into structured reasoning units. Extract only explicit facts from the text - do not infer mechanisms, do not make assumptions, and do not generalize beyond what is stated. Always specify what can and cannot be concluded based on the results provided."
            with open(system_file, 'w', encoding='utf-8') as f:
                f.write(training_system_message)
            print(f"[Saved] system message to: {system_file.name}")

        print(f"\n✅ Phase 1 완료!")
        print(f"   - Training dataset samples: {len(all_training_samples)}개")
        print(f"   - CSV structured_json: {len(df[df['structured_json'].notna() & (df['structured_json'] != '')])}개")
        
        # 처리 완료된 항목 수 출력
        processed_count = len(df[df['structured_json'].notna() & (df['structured_json'] != '')])
        total_experimental = len(df[df['is_experiment_result'] == True])
        remaining_count = total_experimental - processed_count
        if remaining_count > 0:
            print(f"   - Remaining to process: {remaining_count} figures (is_experiment_result=true with empty structured_json)")

        return df



def validate_json_dataset(json_path: str, sample_size: int = 3):
    """
    생성된 JSON 데이터셋 검증 및 샘플 출력

    Args:
        json_path: training_dataset_*.json 경로
        sample_size: 출력할 샘플 개수
    """
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        return

    print("\n" + "="*60)
    print("📊 DATASET VALIDATION")
    print("="*60)

    # JSON 배열 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        data_list = json.load(f)

    print(f"Total training samples: {len(data_list)}")

    # 샘플 출력
    print(f"\n--- Sample {min(sample_size, len(data_list))} entries ---")
    for i, data in enumerate(data_list[:sample_size]):
        print(f"\n[Sample {i+1}]")
        print(f"Fig ID: {data.get('fig_id', 'N/A')}")
        print(f"Structured JSON:")

        # fig_id 제외한 나머지 출력
        sample_without_id = {k: v for k, v in data.items() if k != 'fig_id'}
        print(json.dumps(sample_without_id, indent=2, ensure_ascii=False)[:800])
        if len(json.dumps(sample_without_id, indent=2, ensure_ascii=False)) > 800:
            print("  ...")

    # 필드 완성도 체크
    print("\n--- Field Completeness Check ---")
    required_fields = [
        'experimental_context',
        'observation',
        'comparison',
        'temporal_or_dose_dimension',
        'statistical_claim',
        'interpretation_boundary'
    ]

    field_counts = {field: 0 for field in required_fields}

    for data in data_list:
        for field in required_fields:
            if field in data:
                field_counts[field] += 1

    for field, count in field_counts.items():
        percentage = count / len(data_list) * 100
        print(f"  {field}: {count}/{len(data_list)} ({percentage:.1f}%)")

    print("="*60)


# ============================================================================
# 실행 스크립트
# ============================================================================
def main(
    sample_size: Optional[int] = 50,
    model: str = "gpt-4o-mini",
    resume: bool = True
):
    """
    메인 실행 함수

    Args:
        sample_size: 처리할 샘플 개수 (None = 전체, 기본값: 50)
        model: 사용할 OpenAI 모델 (기본값: gpt-4o-mini)
        resume: 중단된 작업 이어서 실행 여부 (기본값: True)
    """
    # OpenAI API 키 설정
    API_KEY = os.getenv("OPENAI_API_KEY")
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # 경로 설정
    BASE_DIR = Path(__file__).parent.parent
    INPUT_CSV = BASE_DIR / "data" / "raw" / "t_figures_with_result_desc_v4.csv"
    OUTPUT_CSV = INPUT_CSV  # 같은 파일에 structured_json 컬럼 추가

    # JSON 파일 경로 (검증용)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    DATASET_DIR = BASE_DIR / "data" / "dataset"
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON = DATASET_DIR / f"structured_results_{timestamp}.json"

    # 입력 파일 존재 확인
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_CSV}\n"
            f"Please run Phase 0 first (phase_0_figure_classification.py)"
        )

    # 처리기 초기화
    print("\n" + "="*60)
    print("🚀 Phase 1: Result Desc to Structured JSON (with Deduplication)")
    print("="*60)
    print(f"Input CSV:  {INPUT_CSV.name}")
    print(f"Output CSV: {OUTPUT_CSV.name}")
    print(f"Output JSON: {OUTPUT_JSON.name}")
    print(f"Model:  {model}")
    print(f"Sample: {sample_size if sample_size else 'ALL'}")
    print(f"Resume: {resume}")
    print("="*60)

    converter = ResultDescToStructuredConverter(
        api_key=API_KEY,
        model=model
    )

    # 출력 JSONL 파일 경로 (전처리된 형태)
    OUTPUT_JSONL = DATASET_DIR / f"training_dataset_preprocessed_{timestamp}.jsonl"

    # 배치 처리 실행
    result_df = converter.process_batch(
        input_csv=str(INPUT_CSV),
        output_csv=str(OUTPUT_CSV),
        output_jsonl=str(OUTPUT_JSONL),
        sample_size=sample_size,
        resume=resume
    )

    print("\n" + "="*60)
    print("✅ Phase 1 완료!")
    print(f"📊 CSV 파일: {OUTPUT_CSV}")
    print(f"   - structured_json 컬럼 추가됨 (중복 제거된 result_desc 기반)")
    if os.path.exists(OUTPUT_JSONL):
        with open(OUTPUT_JSONL, 'r', encoding='utf-8') as f:
            sample_count = sum(1 for line in f if line.strip())
        print(f"📦 Training Dataset (JSONL): {OUTPUT_JSONL.name}")
        print(f"   - {sample_count} training samples")
    print("="*60)
    print("\n다음 단계:")
    print("1. 데이터셋 품질 검증")
    print("2. Phase 3에서 에러 항목 처리 (필요시)")
    print("3. Colab T4 GPU에서 Gemma-3-1B-IT QLoRA 파인튜닝 실행")
    print("4. 파인튜닝된 모델 평가 및 배포")


# ============================================================================
# 스크립트 실행 시
# ============================================================================
if __name__ == "__main__":
    # ========================================
    # 🔧 여기서 설정 변경
    # ========================================

    SAMPLE_SIZE = 10        # 처리할 샘플 개수 (None = 전체)
    MODEL = "gpt-4o-mini"   # 사용할 모델 (gpt-4o-mini, gpt-4o 등)
    RESUME = True           # 중단된 작업 이어서 실행 여부

    # ========================================

    main(
        sample_size=SAMPLE_SIZE,
        model=MODEL,
        resume=RESUME
    )
