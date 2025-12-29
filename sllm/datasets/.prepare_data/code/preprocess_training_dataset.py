"""
Training Dataset Preprocessing
==============================

목적:
    1. system 메시지를 전역으로 한 번만 선언
    2. user 메시지에서 중복 문장 제거
    3. user와 assistant만 포함하는 새로운 형식으로 저장

입력:
    - training_dataset_full_*.jsonl

출력:
    - training_dataset_preprocessed_*.jsonl
      - system 메시지는 전역으로 한 번만 선언
      - user와 assistant만 포함
      - user 메시지의 중복 문장 제거
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
from collections import OrderedDict


class TrainingDatasetPreprocessor:
    """Training dataset 전처리 클래스"""

    def __init__(self):
        """초기화"""
        pass

    def extract_system_message(self, data_list: List[Dict]) -> str:
        """
        데이터셋에서 system 메시지 추출 (모든 항목에서 동일한 것으로 가정)
        
        Args:
            data_list: 데이터 리스트
            
        Returns:
            system 메시지 내용
        """
        if not data_list:
            raise ValueError("Empty data list")
        
        # 첫 번째 항목에서 system 메시지 추출
        first_item = data_list[0]
        messages = first_item.get('messages', [])
        
        for msg in messages:
            if msg.get('role') == 'system':
                return msg.get('content', '')
        
        raise ValueError("System message not found in data")


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


    def preprocess_dataset(
        self,
        input_jsonl: Path,
        output_jsonl: Path
    ) -> Dict:
        """
        데이터셋 전처리
        
        Args:
            input_jsonl: 입력 JSONL 파일 경로
            output_jsonl: 출력 JSONL 파일 경로
            
        Returns:
            전처리 통계 정보
        """
        print(f"\n[Loading] dataset from: {input_jsonl.name}")
        
        # 데이터 로드
        data_list = []
        with open(input_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data_list.append(json.loads(line))
        
        print(f"   Total samples: {len(data_list)}")
        
        # System 메시지 추출
        system_message = self.extract_system_message(data_list)
        print(f"\n[System] Extracted system message (length: {len(system_message)} chars)")

        # 전처리된 데이터 생성
        preprocessed_data = []
        stats = {
            'total_samples': len(data_list),
            'processed_samples': 0,
            'user_message_length_before': [],
            'user_message_length_after': [],
            'duplicates_removed': 0
        }

        print(f"\n[Processing] {len(data_list)} samples...")
        try:
            from tqdm import tqdm
            iterator = tqdm(data_list, desc="Preprocessing")
        except ImportError:
            iterator = data_list
        
        for item in iterator:
            messages = item.get('messages', [])
            
            # user와 assistant 메시지 추출
            user_msg = None
            assistant_msg = None
            
            for msg in messages:
                if msg.get('role') == 'user':
                    user_msg = msg.get('content', '')
                elif msg.get('role') == 'assistant':
                    assistant_msg = msg.get('content', '')
            
            if not user_msg or not assistant_msg:
                print(f"[Warning] Missing user or assistant message for {item.get('fig_id', 'unknown')}, skipping")
                continue
            
            # 중복 제거 전 길이 기록
            original_length = len(user_msg)
            stats['user_message_length_before'].append(original_length)

            # user 메시지 정리 (instruction 제거 + 중복 제거)
            cleaned_user_msg = self.clean_user_message(user_msg)

            # assistant 메시지 정리 ("not stated" 필드 제거)
            cleaned_assistant_msg = self.clean_assistant_message(assistant_msg)

            # 정리 후 길이 기록
            new_length = len(cleaned_user_msg)
            stats['user_message_length_after'].append(new_length)

            if original_length > new_length:
                stats['duplicates_removed'] += 1

            # 새로운 형식으로 데이터 생성 (system은 제외, user와 assistant만)
            preprocessed_item = {
                "fig_id": item.get('fig_id', ''),
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
            
            preprocessed_data.append(preprocessed_item)
            stats['processed_samples'] += 1
        
        # System 메시지를 별도 파일로 저장 (전역 선언용)
        system_file = output_jsonl.parent / f"system_message_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        with open(system_file, 'w', encoding='utf-8') as f:
            f.write(system_message)
        print(f"\n[Saved] system message to: {system_file.name}")

        # 전처리된 데이터 저장
        print(f"\n[Saving] preprocessed dataset to: {output_jsonl.name}")
        with open(output_jsonl, 'w', encoding='utf-8') as f:
            for item in preprocessed_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 통계 계산
        if stats['user_message_length_before']:
            avg_before = sum(stats['user_message_length_before']) / len(stats['user_message_length_before'])
            avg_after = sum(stats['user_message_length_after']) / len(stats['user_message_length_after'])
            stats['avg_user_message_length_before'] = avg_before
            stats['avg_user_message_length_after'] = avg_after
            stats['avg_reduction'] = avg_before - avg_after
        
        print(f"[Success] Saved {len(preprocessed_data)} preprocessed samples")
        
        return stats


def main(input_jsonl_pattern: str = None):
    """
    메인 실행 함수
    
    Args:
        input_jsonl_pattern: 입력 JSONL 파일 패턴 (None = 가장 최근 파일)
    """
    # 경로 설정
    BASE_DIR = Path(__file__).parent.parent
    DATA_DATASET_DIR = BASE_DIR / "data" / "dataset"
    DATA_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 입력 파일 찾기
    if input_jsonl_pattern:
        input_jsonl = DATA_DATASET_DIR / input_jsonl_pattern
        if not input_jsonl.exists():
            raise FileNotFoundError(f"Input JSONL file not found: {input_jsonl}")
    else:
        # 가장 최근 training_dataset_full_*.jsonl 파일 찾기
        pattern = "training_dataset_full_*.jsonl"
        jsonl_files = list(DATA_DATASET_DIR.glob(pattern))
        
        if not jsonl_files:
            raise FileNotFoundError(f"No {pattern} files found in {DATA_DATASET_DIR}")
        
        # 가장 최근 파일 선택
        input_jsonl = max(jsonl_files, key=lambda x: x.stat().st_mtime)
        print(f"[Using] most recent file: {input_jsonl.name}")

    # 출력 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_jsonl = DATA_DATASET_DIR / f"training_dataset_preprocessed_{timestamp}.jsonl"

    print("\n" + "="*60)
    print("Training Dataset Preprocessing")
    print("="*60)
    print(f"Input JSONL:  {input_jsonl.name}")
    print(f"Output JSONL: {output_jsonl.name}")
    print("="*60)
    
    # 전처리 실행
    preprocessor = TrainingDatasetPreprocessor()
    stats = preprocessor.preprocess_dataset(input_jsonl, output_jsonl)
    
    # 결과 출력
    print("\n" + "="*60)
    print("Preprocessing Complete!")
    print("="*60)
    print(f"Statistics:")
    print(f"   Total samples: {stats['total_samples']}")
    print(f"   Processed samples: {stats['processed_samples']}")
    print(f"   Samples with duplicates removed: {stats['duplicates_removed']}")
    if 'avg_user_message_length_before' in stats:
        print(f"   Avg user message length (before): {stats['avg_user_message_length_before']:.1f} chars")
        print(f"   Avg user message length (after): {stats['avg_user_message_length_after']:.1f} chars")
        print(f"   Avg reduction: {stats['avg_reduction']:.1f} chars")
    print(f"\nOutput files:")
    print(f"   - Preprocessed dataset: {output_jsonl.name}")
    print(f"   - System message: system_message_*.txt")
    print("="*60)


# ============================================================================
# 스크립트 실행 시
# ============================================================================
if __name__ == "__main__":
    # ========================================
    # [CONFIG] 여기서 설정 변경
    # ========================================
    
    INPUT_JSONL_PATTERN = None  # None = 가장 최근 파일, 또는 "training_dataset_full_20251226124500.jsonl"
    
    # ========================================
    
    main(input_jsonl_pattern=INPUT_JSONL_PATTERN)

