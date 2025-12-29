"""
Phase 2: Create Fine-tuning Training Dataset (System Separation + User/Assistant Format)
=========================================================================================

목적:
    Phase 1에서 생성된 structured_json을 읽어 파인튜닝용 Chat 형식(JSONL)로 변환
    System message는 전역으로 분리하고 user와 assistant만 포함

입력:
    - Phase 1 완료된 CSV (structured_json 컬럼 포함)
      t_figures_with_result_desc_v4.csv

처리:
    - CSV에서 structured_json 읽기
    - User 메시지에서 instruction 제거 (핵심 result_desc만)
    - Assistant 메시지에서 빈 필드 제거 ("", [], {}, "not stated")
    - System message는 전역으로 분리

출력:
    - training_dataset_YYYYMMDDHHMMSS.jsonl
      (user + assistant만 포함, system 제외)
    - system_message_YYYYMMDDHHMMSS.txt
      (전역 시스템 메시지)

설정:
    - SAMPLE_SIZE: 처리할 샘플 개수 (None = 전체)
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import glob


class TrainingDatasetCreator:
    """구조화된 JSON을 파인튜닝용 Chat 형식으로 변환 + 전처리하는 클래스"""

    def __init__(self):
        """초기화"""
        # System message: 파인튜닝 시 모델이 학습할 역할
        self.system_message = """You are a biomedical research analysis assistant.

Your task is to decompose experimental results text into structured reasoning units.

Key principles:
1. Extract ONLY what is explicitly stated - no interpretation or inference
2. Identify the boundary between observable facts and mechanistic interpretation
3. Structure information into clear reasoning units

Output format: JSON with experimental_context, observation, comparison, temporal_or_dose_dimension, statistical_claim, and interpretation_boundary fields."""

        # User prompt template (전처리 시 제거될 instruction 부분)
        self.user_prompt_template = """Analyze the following experimental results text and decompose it into structured reasoning units.

Results text:
{result_desc}

Provide a JSON output with the following structure:
- experimental_context: model and assay information
- observation: measurement, direction, and magnitude
- comparison: groups being compared
- temporal_or_dose_dimension: time and dose information
- statistical_claim: statistical significance
- interpretation_boundary: what can and cannot be concluded"""

    def clean_user_message(self, result_desc: str) -> str:
        """
        User 메시지 생성: result_desc만 반환 (instruction 제거)
        Phase 1에서 이미 중복 제거가 완료되었으므로 여기서는 그대로 사용

        Args:
            result_desc: 실험 결과 텍스트 (Phase 1에서 중복 제거 완료)

        Returns:
            정리된 실험 결과 텍스트 (instruction 없이, Phase 1 중복 제거 유지)
        """
        # Phase 1에서 이미 중복 제거가 완료되었으므로 그대로 반환
        return result_desc.strip()

    def clean_assistant_message(self, json_str: str) -> str:
        """
        Assistant 메시지에서 빈 필드 제거
        - 빈 문자열 "", 빈 배열 [], 빈 객체 {} 제거
        - "not stated" 값도 제거

        Args:
            json_str: JSON 문자열

        Returns:
            정리된 JSON 문자열 (값이 있는 필드만 포함)
        """
        try:
            data = json.loads(json_str)

            # 빈 값을 재귀적으로 제거
            def remove_empty_values(obj):
                if isinstance(obj, dict):
                    cleaned = {}
                    for k, v in obj.items():
                        cleaned_v = remove_empty_values(v)
                        # 빈 값이 아닌 경우만 포함
                        if cleaned_v != "" and cleaned_v != [] and cleaned_v != {} and cleaned_v != "not stated" and cleaned_v is not None:
                            cleaned[k] = cleaned_v
                    return cleaned
                elif isinstance(obj, list):
                    # 리스트의 각 항목에 대해 재귀 적용
                    cleaned_list = [remove_empty_values(item) for item in obj]
                    # 빈 값이 아닌 항목만 포함
                    return [item for item in cleaned_list if item != "" and item != [] and item != {} and item != "not stated" and item is not None]
                else:
                    return obj

            cleaned_data = remove_empty_values(data)

            # 깔끔한 JSON 문자열로 변환
            return json.dumps(cleaned_data, ensure_ascii=False, indent=2)

        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 반환
            return json_str

    def structured_to_chat_format(
        self,
        fig_id: str,
        structured_json: Dict,
        result_desc: str
    ) -> Dict:
        """
        구조화된 JSON을 Chat 형식으로 변환
        System message는 제외하고 user와 assistant만 포함

        Args:
            fig_id: Figure ID
            structured_json: 구조화된 JSON (experimental_context, observation, ...)
            result_desc: result_desc 텍스트 (Phase 1에서 중복 제거 완료)

        Returns:
            Chat 형식 데이터 (user, assistant만)
        """
        # User: result_desc만 (instruction 제거)
        user_content = self.clean_user_message(result_desc)

        # Assistant: 빈 필드 제거된 JSON
        assistant_content_json = json.dumps(structured_json, ensure_ascii=False, indent=2)
        assistant_content = self.clean_assistant_message(assistant_content_json)

        # System message 제외, user와 assistant만
        chat_sample = {
            "fig_id": fig_id,
            "messages": [
                {
                    "role": "user",
                    "content": user_content
                },
                {
                    "role": "assistant",
                    "content": assistant_content
                }
            ]
        }

        return chat_sample

    def convert_to_training_dataset(
        self,
        input_csv: str,
        output_jsonl: str,
        system_message_file: str,
        sample_size: Optional[int] = None
    ) -> Dict:
        """
        Phase 1 완료된 CSV에서 structured_json을 읽어 파인튜닝 데이터셋으로 변환
        System message는 전역으로 분리

        Args:
            input_csv: Phase 1 완료된 CSV (structured_json 컬럼 포함)
            output_jsonl: 출력 JSONL (training_dataset_preprocessed_*.jsonl)
            system_message_file: System message 저장 파일 경로
            sample_size: 처리할 샘플 개수 (None = 전체)

        Returns:
            처리 통계 정보
        """
        import pandas as pd

        # CSV 로드
        print(f"\n📂 Loading CSV: {Path(input_csv).name}")
        df = pd.read_csv(input_csv)

        # 첫 번째 컬럼이 무명 인덱스인 경우 fig_id로 변환
        if df.columns[0] == 'Unnamed: 0' or df.columns[0] == '':
            df.rename(columns={df.columns[0]: 'fig_id'}, inplace=True)

        # structured_json이 있는 데이터만 필터링
        df_with_json = df[df['structured_json'].notna() & (df['structured_json'] != '')].copy()
        print(f"   Total rows with structured_json: {len(df_with_json)}")

        # 샘플 크기 제한
        if sample_size:
            df_with_json = df_with_json.head(sample_size)
            print(f"   Processing sample: {len(df_with_json)} samples")

        # Chat 형식으로 변환
        print(f"\n🔄 Converting to training dataset format (user + assistant only)...")
        training_dataset = []
        stats = {
            'total_input': len(df_with_json),
            'processed': 0,
            'skipped': 0
        }

        try:
            from tqdm import tqdm
            iterator = tqdm(df_with_json.iterrows(), total=len(df_with_json), desc="Processing")
        except ImportError:
            iterator = df_with_json.iterrows()

        for idx, row in iterator:
            fig_id = row['fig_id']
            result_desc = row['result_desc']
            structured_json_str = row['structured_json']

            # structured_json 파싱
            try:
                structured_json = json.loads(structured_json_str)
            except json.JSONDecodeError:
                print(f"\n⚠️  Warning: {fig_id} has invalid JSON, skipping")
                stats['skipped'] += 1
                continue

            # Chat 형식으로 변환
            chat_sample = self.structured_to_chat_format(
                fig_id=fig_id,
                structured_json=structured_json,
                result_desc=result_desc
            )

            training_dataset.append(chat_sample)
            stats['processed'] += 1

        # System message를 별도 파일로 저장
        print(f"\n💾 Saving system message to: {Path(system_message_file).name}")
        with open(system_message_file, 'w', encoding='utf-8') as f:
            f.write(self.system_message)

        # JSONL 저장 (각 줄이 하나의 JSON 객체)
        print(f"\n💾 Saving training dataset to: {Path(output_jsonl).name}")
        with open(output_jsonl, 'w', encoding='utf-8') as f:
            for sample in training_dataset:
                # 각 샘플을 한 줄로 저장 (JSONL 형식)
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')

        print(f"✅ Saved {len(training_dataset)} training samples (JSONL format)")

        stats['output_samples'] = len(training_dataset)
        return stats


def validate_training_dataset(jsonl_path: str, sample_size: int = 3, preprocessed: bool = True):
    """
    생성된 파인튜닝 데이터셋 검증 및 샘플 출력

    Args:
        jsonl_path: training_dataset_*.jsonl 경로
        sample_size: 출력할 샘플 개수
        preprocessed: 전처리된 데이터셋 여부 (True: user+assistant / False: system+user+assistant)
    """
    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found")
        return

    print("\n" + "="*60)
    print("📊 TRAINING DATASET VALIDATION")
    print("="*60)

    # JSONL 파일 로드 (각 줄이 하나의 JSON 객체)
    data_list = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  # 빈 줄 제외
                data_list.append(json.loads(line))

    print(f"Total training samples: {len(data_list)}")
    print(f"Format: {'Preprocessed (user + assistant)' if preprocessed else 'Original (system + user + assistant)'}")

    # 샘플 출력
    print(f"\n--- Sample {min(sample_size, len(data_list))} entries ---")
    for i, data in enumerate(data_list[:sample_size]):
        print(f"\n[Sample {i+1}]")
        print(f"Fig ID: {data.get('fig_id', 'N/A')}")

        messages = data.get('messages', [])
        print(f"Number of messages: {len(messages)}")

        for j, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            # Role에 따라 출력 길이 조정
            if role == 'system':
                preview_len = 150
            elif role == 'user':
                preview_len = 200
            else:  # assistant
                preview_len = 300

            print(f"\n{role.upper()} message (first {preview_len} chars):")
            print(f"  {content[:preview_len]}...")

    # 메시지 구조 검증
    print("\n--- Message Structure Check ---")
    valid_count = 0
    expected_roles = ['user', 'assistant'] if preprocessed else ['system', 'user', 'assistant']
    expected_len = 2 if preprocessed else 3

    for data in data_list:
        messages = data.get('messages', [])
        if len(messages) == expected_len:
            roles = [m.get('role') for m in messages]
            if roles == expected_roles:
                valid_count += 1

    print(f"Valid message structure ({expected_roles}): {valid_count}/{len(data_list)} ({valid_count/len(data_list)*100:.1f}%)")

    print("="*60)


# ============================================================================
# 실행 스크립트
# ============================================================================
def main(
    sample_size: Optional[int] = None
):
    """
    메인 실행 함수

    Args:
        sample_size: 처리할 샘플 개수 (None = 전체)
    """
    # 경로 설정
    BASE_DIR = Path(__file__).parent.parent
    DATASET_DIR = BASE_DIR / "data" / "dataset"
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    INPUT_CSV = BASE_DIR / "data" / "raw" / "t_figures_with_result_desc_v4.csv"

    # CSV 파일 존재 확인
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"CSV file not found: {INPUT_CSV}\n"
            f"Please run Phase 1 first (phase_1_result_desc_to_json.py)"
        )

    # 출력 파일명에 타임스탬프 추가 (JSONL 형식)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    OUTPUT_JSONL = DATASET_DIR / f"training_dataset_{timestamp}.jsonl"
    SYSTEM_MESSAGE_FILE = DATASET_DIR / f"system_message_{timestamp}.txt"

    # 처리기 초기화
    print("\n" + "="*60)
    print("🚀 Phase 2: Create Training Dataset (System Separation)")
    print("="*60)
    print(f"Input CSV:        {INPUT_CSV.name}")
    print(f"Output JSONL:     {OUTPUT_JSONL.name}")
    print(f"System Message:   {SYSTEM_MESSAGE_FILE.name}")
    print(f"Sample Size:      {sample_size if sample_size else 'ALL'}")
    print("="*60)

    creator = TrainingDatasetCreator()

    # 변환 실행
    stats = creator.convert_to_training_dataset(
        input_csv=str(INPUT_CSV),
        output_jsonl=str(OUTPUT_JSONL),
        system_message_file=str(SYSTEM_MESSAGE_FILE),
        sample_size=sample_size
    )

    # 데이터셋 검증
    if os.path.exists(OUTPUT_JSONL):
        validate_training_dataset(str(OUTPUT_JSONL), sample_size=3, preprocessed=True)

    # 통계 출력
    print("\n" + "="*60)
    print("📊 Processing Statistics")
    print("="*60)
    print(f"Total input samples:    {stats['total_input']}")
    print(f"Processed samples:      {stats['processed']}")
    print(f"Skipped samples:        {stats['skipped']}")
    print(f"Output samples:         {stats['output_samples']}")
    print("="*60)

    print("\n" + "="*60)
    print("✅ Phase 2 완료!")
    print("="*60)
    print(f"📦 Training Dataset:    {OUTPUT_JSONL.name}")
    print(f"📄 System Message:      {SYSTEM_MESSAGE_FILE.name}")
    print("="*60)
    print("\n다음 단계:")
    print("1. 데이터셋 품질 검증")
    print("2. Colab T4 GPU에서 Gemma-3-1B-IT QLoRA 파인튜닝 실행")
    print("3. System message는 파인튜닝 시 전역으로 설정")


# ============================================================================
# 스크립트 실행 시
# ============================================================================
if __name__ == "__main__":
    # ========================================
    # 🔧 여기서 설정 변경
    # ========================================

    SAMPLE_SIZE = None              # None = 전체 처리

    # ========================================

    main(sample_size=SAMPLE_SIZE)
