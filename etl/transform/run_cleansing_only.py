"""
클렌징만 수행하는 스크립트
=======================
JSON 파일을 읽어서 텍스트를 정리하고 저장합니다.
"""

import os
import sys
import json
from pathlib import Path

# ============================================
# 설정 변수 (상단에 변수로 세팅)
# ============================================
INPUT_PATH = os.path.join("..", "data", "nih", "raw")  # 입력 JSON 파일 경로 또는 폴더 경로
CLEANED_OUTPUT_PATH = None  # 클렌징된 데이터 출력 파일 경로 (None이면 기본 경로 사용)
# ============================================

# 프로젝트 루트 경로를 시스템 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 필요한 모듈 임포트
from cleansing.nltk_setup import setup_nltk
from cleansing.text_cleaner import clean_text
from chunking.file_handler import load_json_file, extract_studies_from_json
from chunking.data_extractor import extract_metadata, extract_core_fields, combine_core_fields


def find_json_files(input_path):
    """
    입력 경로에서 모든 JSON 파일을 찾습니다.
    
    Args:
        input_path (str): 파일 경로 또는 폴더 경로
        
    Returns:
        list: JSON 파일 경로 리스트
    """
    input_path = Path(input_path)
    
    # 파일인 경우
    if input_path.is_file():
        if input_path.suffix.lower() == '.json':
            return [str(input_path)]
        else:
            return []
    
    # 폴더인 경우 재귀적으로 모든 JSON 파일 찾기
    if input_path.is_dir():
        json_files = []
        for json_file in input_path.rglob('*.json'):
            json_files.append(str(json_file))
        return sorted(json_files)
    
    return []


def run_cleansing_only(json_files, output_file=None):
    """
    클렌징만 수행합니다. JSON 파일을 읽어서 텍스트를 정리하고 저장합니다.
    
    Args:
        json_files (list): 처리할 JSON 파일 경로 리스트
        output_file (str, optional): 출력 파일 경로 (JSON 형식)
        
    Returns:
        str: 클렌징된 데이터가 저장된 파일 경로
    """
    if output_file is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_file = os.path.join(base_dir, "data", "nih", "processed", "cleaned", "cleaned_data.json")
    
    # 출력 디렉토리 생성
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print("=" * 60)
    print("[클렌징 단계] 텍스트 정리 시작")
    print("=" * 60)
    
    all_cleaned_studies = []
    total_studies = 0
    
    for file_idx, json_file in enumerate(json_files, 1):
        print(f"\n[{file_idx}/{len(json_files)}] 처리 중: {os.path.basename(json_file)}")
        
        try:
            # JSON 파일 읽기
            data = load_json_file(json_file)
            studies = extract_studies_from_json(data)
            print(f"✓ {len(studies)}개의 study를 찾았습니다.")
            total_studies += len(studies)
            
            # 각 study의 텍스트 클렌징
            for study in studies:
                # 메타데이터 추출
                metadata = extract_metadata(study)
                
                # 핵심 필드 추출
                core_fields = extract_core_fields(study)
                
                # 핵심 필드들을 하나의 텍스트로 합치기
                combined_text = combine_core_fields(core_fields)
                
                # 텍스트 클렌징
                cleaned_text = clean_text(combined_text) if combined_text else ""
                
                # 클렌징된 데이터 저장
                cleaned_study = {
                    "metadata": metadata,
                    "cleaned_text": cleaned_text,
                    "source_file": os.path.basename(json_file)
                }
                all_cleaned_studies.append(cleaned_study)
                
        except Exception as e:
            print(f"경고: 파일 처리 중 오류 발생 ({json_file}): {e}")
            continue
    
    # 클렌징된 데이터를 JSON 파일로 저장
    output_data = {
        "total_studies": total_studies,
        "cleaned_studies": all_cleaned_studies
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n" + "=" * 60)
    print("[클렌징 완료]")
    print("=" * 60)
    print(f"✓ 총 {total_studies}개의 study를 클렌징했습니다.")
    print(f"✓ 클렌징된 데이터 저장: {output_file}")
    print("=" * 60)
    
    return output_file


def main():
    """
    메인 함수: 클렌징만 실행합니다.
    """
    # 설정 변수 사용
    input_path = INPUT_PATH
    cleaned_output = CLEANED_OUTPUT_PATH
    
    # 1단계: 라이브러리 초기화
    print("\n[1단계] 라이브러리 초기화 중...")
    setup_nltk()
    
    # 2단계: 입력 경로 처리
    if not os.path.isabs(input_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if os.path.exists(input_path):
            input_path = os.path.abspath(input_path)
        else:
            input_path = os.path.join(base_dir, input_path)
    
    json_files = find_json_files(input_path)
    if not json_files:
        print(f"오류: 입력 경로에서 JSON 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)
    
    # 3단계: 클렌징 실행
    cleaned_file = run_cleansing_only(json_files, cleaned_output)
    print(f"\n✓ 클렌징 완료: {cleaned_file}")


if __name__ == "__main__":
    main()