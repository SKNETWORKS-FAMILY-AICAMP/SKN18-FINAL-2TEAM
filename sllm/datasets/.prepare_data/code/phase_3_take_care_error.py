"""
Phase 3: Error Recovery and Merge
==================================

목적:
    1. structured_results_*.json에서 "error" 키를 가진 항목만 재처리
    2. 재처리 결과를 plus_error.json으로 저장
    3. 최근의 error_*.json과 structured_results_*.json을 합쳐서 full.json 생성

입력:
    - structured_results_*.json (Phase 1에서 생성된 파일)
    - 원본 CSV 파일 (result_desc 가져오기용)

출력:
    - plus_error.json (재처리된 error 항목들)
    - full.json (error_*.json + structured_results_*.json 병합)

설정:
    - INPUT_JSON_PATTERN: 입력 JSON 파일 패턴 (None = 가장 최근 파일)
    - INPUT_CSV_FILENAME: 원본 CSV 파일명
    - LLM_MODEL: 사용할 OpenAI 모델 (기본: gpt-4o-mini)
"""

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import glob

import dotenv
dotenv.load_dotenv()

from phase_1_result_desc_to_json import ResultDescToStructuredConverter
from phase_2_create_training_dataset import TrainingDatasetCreator


class ErrorRecoveryProcessor:
    """Error 항목 재처리 및 파일 병합 클래스"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 (기본값: gpt-4o-mini)
        """
        self.converter = ResultDescToStructuredConverter(api_key=api_key, model=model)
        self.model = model

    def find_latest_file(self, pattern: str, directory: Path) -> Optional[Path]:
        """
        디렉토리에서 패턴에 맞는 가장 최근 파일 찾기
        
        Args:
            pattern: 파일 패턴 (예: "structured_results_*.json")
            directory: 검색할 디렉토리
            
        Returns:
            가장 최근 파일 경로, 없으면 None
        """
        files = list(directory.glob(pattern))
        if not files:
            return None
        
        # 수정 시간 기준으로 정렬 (가장 최근 파일)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return files[0]

    def extract_error_items(self, json_file: Path) -> List[Dict]:
        """
        JSON 파일에서 "error" 키를 가진 항목만 추출
        
        Args:
            json_file: 입력 JSON 파일 경로
            
        Returns:
            error 항목 리스트
        """
        print(f"\n📂 Loading JSON file: {json_file.name}")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"   Total items: {len(data)}")
        
        # "error" 키를 가진 항목만 필터링
        error_items = [item for item in data if 'error' in item]
        print(f"   Error items: {len(error_items)}")
        
        return error_items

    def reprocess_errors(
        self,
        error_items: List[Dict],
        csv_file: Path,
        output_json: Path
    ) -> List[Dict]:
        """
        Error 항목들을 재처리하여 plus_error.json 생성
        
        Args:
            error_items: error 항목 리스트 (fig_id 포함)
            csv_file: 원본 CSV 파일 (result_desc 가져오기용)
            output_json: 출력 JSON 파일 경로
            
        Returns:
            재처리된 항목 리스트
        """
        if not error_items:
            print("⚠️  No error items to reprocess!")
            return []
        
        # CSV 로드
        print(f"\n📂 Loading CSV file: {csv_file.name}")
        df = pd.read_csv(csv_file)
        
        # 첫 번째 컬럼이 무명 인덱스인 경우 fig_id로 변환
        if df.columns[0] == 'Unnamed: 0' or df.columns[0] == '':
            df.rename(columns={df.columns[0]: 'fig_id'}, inplace=True)
        
        # fig_id를 인덱스로 설정 (빠른 검색용)
        df_indexed = df.set_index('fig_id')
        
        # 재처리된 항목 저장용
        reprocessed_items = []
        
        print(f"\n🔄 Reprocessing {len(error_items)} error items...")
        from tqdm import tqdm
        
        for item in tqdm(error_items, desc="Reprocessing"):
            fig_id = item.get('fig_id')
            if not fig_id:
                print(f"⚠️  Warning: Item without fig_id, skipping")
                continue
            
            # CSV에서 result_desc 가져오기
            if fig_id not in df_indexed.index:
                print(f"⚠️  Warning: {fig_id} not found in CSV, skipping")
                continue
            
            result_desc = df_indexed.loc[fig_id, 'result_desc']
            
            # result_desc가 비어있으면 스킵
            if pd.isna(result_desc) or result_desc == '':
                print(f"⚠️  Warning: {fig_id} has empty result_desc, skipping")
                continue
            
            # 구조화 실행 (Rate limit 처리 포함)
            structured_json = self.converter.structure_result_desc(result_desc)
            
            # error가 여전히 있으면 스킵
            if 'error' in structured_json:
                print(f"⚠️  Warning: {fig_id} still has error after reprocessing: {structured_json.get('error', 'Unknown')}")
                continue
            
            # 재처리된 항목 생성
            reprocessed_item = {
                "fig_id": fig_id,
                **structured_json
            }
            reprocessed_items.append(reprocessed_item)
        
        # plus_error.json 저장
        print(f"\n💾 Saving reprocessed items to: {output_json.name}")
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(reprocessed_items, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved {len(reprocessed_items)} reprocessed items")
        
        return reprocessed_items

    def merge_files(
        self,
        structured_json_file: Path,
        error_json_file: Optional[Path],
        output_json: Path
    ) -> List[Dict]:
        """
        structured_results_*.json과 error_*.json을 합쳐서 full.json 생성
        
        Args:
            structured_json_file: structured_results_*.json 파일 경로
            error_json_file: error_*.json 파일 경로 (None이면 스킵)
            output_json: 출력 JSON 파일 경로
            
        Returns:
            병합된 데이터 리스트
        """
        print(f"\n📂 Merging files...")
        
        # structured_results_*.json 로드
        print(f"   Loading: {structured_json_file.name}")
        with open(structured_json_file, 'r', encoding='utf-8') as f:
            structured_data = json.load(f)
        print(f"   Items: {len(structured_data)}")
        
        # error_*.json 로드 (있는 경우)
        error_data = []
        if error_json_file and error_json_file.exists():
            print(f"   Loading: {error_json_file.name}")
            with open(error_json_file, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
            print(f"   Items: {len(error_data)}")
        
        # error 항목 제거 (structured_data에서)
        structured_data_clean = [item for item in structured_data if 'error' not in item]
        print(f"   Clean structured items (no error): {len(structured_data_clean)}")
        
        # 병합 (error_data가 있으면 추가)
        merged_data = structured_data_clean + error_data
        
        # fig_id 기준으로 중복 제거 (나중 항목 우선)
        seen = {}
        for item in merged_data:
            fig_id = item.get('fig_id')
            if fig_id:
                seen[fig_id] = item
        
        merged_data_unique = list(seen.values())
        
        # full.json 저장
        print(f"\n💾 Saving merged data to: {output_json.name}")
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(merged_data_unique, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved {len(merged_data_unique)} unique items")
        
        return merged_data_unique


def main(
    input_json_pattern: Optional[str] = None,
    input_csv_filename: str = "t_figures_with_result_desc_v3.csv",
    model: str = "gpt-4o-mini"
):
    """
    Phase 3 메인 실행 함수
    
    Args:
        input_json_pattern: 입력 JSON 파일 패턴 (None = 가장 최근 파일)
        input_csv_filename: 원본 CSV 파일명
        model: 사용할 OpenAI 모델
    """
    # OpenAI API 키 설정
    API_KEY = os.getenv("OPENAI_API_KEY")
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # 경로 설정
    BASE_DIR = Path(__file__).parent.parent
    DATA_RAW_DIR = BASE_DIR / "data" / "raw"
    DATA_DATASET_DIR = BASE_DIR / "data" / "dataset"
    DATA_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 입력 파일 찾기
    if input_json_pattern:
        input_json_file = DATA_DATASET_DIR / input_json_pattern
        if not input_json_file.exists():
            raise FileNotFoundError(f"Input JSON file not found: {input_json_file}")
    else:
        # 가장 최근 structured_results_*.json 파일 찾기
        processor = ErrorRecoveryProcessor(API_KEY, model)
        input_json_file = processor.find_latest_file("structured_results_*.json", DATA_DATASET_DIR)
        if not input_json_file:
            raise FileNotFoundError("No structured_results_*.json files found in data/dataset/")
    
    # CSV 파일 확인
    csv_file = DATA_RAW_DIR / input_csv_filename
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")
    
    # 출력 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    plus_error_json = DATA_DATASET_DIR / f"plus_error_{timestamp}.json"
    full_json = DATA_DATASET_DIR / f"full_{timestamp}.json"
    
    print("\n" + "="*60)
    print("🚀 Phase 3: Error Recovery and Merge")
    print("="*60)
    print(f"Input JSON: {input_json_file.name}")
    print(f"Input CSV: {csv_file.name}")
    print(f"Model: {model}")
    print("="*60)
    
    # Error Recovery Processor 초기화
    processor = ErrorRecoveryProcessor(API_KEY, model)
    
    # 1. 가장 최근 plus_error_*.json 파일 찾기
    latest_plus_error_json = processor.find_latest_file("plus_error_*.json", DATA_DATASET_DIR)
    
    if not latest_plus_error_json:
        print("⚠️  No plus_error_*.json files found. Proceeding with error recovery...")
        # Error 항목 추출 및 재처리
        error_items = processor.extract_error_items(input_json_file)
        
        if error_items:
            reprocessed_items = processor.reprocess_errors(
                error_items,
                csv_file,
                plus_error_json
            )
            print(f"\n✅ Reprocessed {len(reprocessed_items)}/{len(error_items)} error items")
            latest_plus_error_json = plus_error_json
        else:
            print("\n✅ No error items to reprocess!")
            latest_plus_error_json = None
    else:
        print(f"📂 Found existing plus_error file: {latest_plus_error_json.name}")
    
    # 2. 파일 병합 (structured_results_*.json + plus_error_*.json)
    merged_data = processor.merge_files(
        input_json_file,
        latest_plus_error_json,
        full_json
    )
    
    # 3. 병합된 full.json을 training_dataset_full.jsonl로 변환
    print("\n" + "="*60)
    print("🔄 Converting merged data to training dataset format...")
    print("="*60)
    
    training_dataset_creator = TrainingDatasetCreator()
    training_dataset_jsonl = DATA_DATASET_DIR / f"training_dataset_full_{timestamp}.jsonl"
    
    training_dataset = training_dataset_creator.convert_to_training_dataset(
        input_json=str(full_json),
        output_json=str(training_dataset_jsonl),
        csv_file=str(csv_file),
        sample_size=None  # 전체 처리
    )
    
    print("\n" + "="*60)
    print("✅ Phase 3 완료!")
    if latest_plus_error_json:
        with open(latest_plus_error_json, 'r', encoding='utf-8') as f:
            plus_error_data = json.load(f)
        print(f"📦 plus_error.json: {latest_plus_error_json.name}")
        print(f"   - {len(plus_error_data)} items")
    print(f"📦 structured_results.json: {input_json_file.name}")
    print(f"📦 full.json: {full_json.name}")
    print(f"   - {len(merged_data)} total items")
    print(f"📦 training_dataset_full.jsonl: {training_dataset_jsonl.name}")
    print(f"   - {len(training_dataset)} training samples")
    print("="*60)


# ============================================================================
# 스크립트 실행 시
# ============================================================================
if __name__ == "__main__":
    # ========================================
    # 🔧 여기서 설정 변경
    # ========================================
    
    INPUT_JSON_PATTERN = None  # None = 가장 최근 파일, 또는 "structured_results_20251226120821.json"
    INPUT_CSV_FILENAME = "t_figures_with_result_desc_v3.csv"  # 원본 CSV 파일명
    MODEL = "gpt-4o-mini"  # 사용할 모델
    
    # ========================================
    
    main(
        input_json_pattern=INPUT_JSON_PATTERN,
        input_csv_filename=INPUT_CSV_FILENAME,
        model=MODEL
    )

