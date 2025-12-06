"""
청킹만 수행하는 스크립트
=======================
클렌징된 데이터를 읽어서 청크로 분할합니다.
"""

import os
import sys
import json

# ============================================
# 설정 변수 (상단에 변수로 세팅)
# ============================================
CLEANED_DATA_PATH = None  # 클렌징된 데이터 파일 경로 (None이면 기본 경로 사용)
OUTPUT_FORMAT_OVERRIDE = None  # 출력 포맷 ('json' 또는 'csv', None이면 config의 OUTPUT_FORMAT 사용)
OUTPUT_CHUNK_FILE = None  # 청크 출력 파일명 (None이면 config.CHUNK_OUTPUT_FILE 사용)
OUTPUT_METADATA_FILE = None  # 메타데이터 출력 파일명 (None이면 config.METADATA_OUTPUT_FILE 사용)
# ============================================

# 프로젝트 루트 경로를 시스템 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 필요한 모듈 임포트
from token_counter import init_tokenizer
from config import (
    CHUNK_SIZE_MIN, CHUNK_SIZE_MAX, OVERLAP_MIN, OVERLAP_MAX,
    CHUNK_OUTPUT_FILE, METADATA_OUTPUT_FILE, OUTPUT_FORMAT
)
from chunking.file_handler import save_chunks_to_csv, save_metadata_to_csv
from chunking.chunker import create_chunks_with_overlap


def run_chunking_only(cleaned_data_file, global_chunk_counter_start=0):
    """
    청킹만 수행합니다. 클렌징된 데이터를 읽어서 청크로 분할합니다.
    
    Args:
        cleaned_data_file (str): 클렌징된 데이터 파일 경로
        global_chunk_counter_start (int): 청크 카운터 시작 번호
        
    Returns:
        tuple: (청크 데이터 리스트, 다음 청크 카운터 번호)
    """
    print("=" * 60)
    print("[청킹 단계] 텍스트 청킹 시작")
    print("=" * 60)
    
    # 클렌징된 데이터 읽기
    if not os.path.exists(cleaned_data_file):
        raise FileNotFoundError(f"클렌징된 데이터 파일을 찾을 수 없습니다: {cleaned_data_file}")
    
    with open(cleaned_data_file, 'r', encoding='utf-8') as f:
        cleaned_data = json.load(f)
    
    cleaned_studies = cleaned_data.get("cleaned_studies", [])
    print(f"✓ {len(cleaned_studies)}개의 클렌징된 study를 찾았습니다.")
    
    all_chunks = []
    global_chunk_counter = global_chunk_counter_start
    
    # 각 클렌징된 study를 청크로 분할
    for study_idx, study in enumerate(cleaned_studies, 1):
        if study_idx % 10 == 0:
            print(f"  진행 중: {study_idx}/{len(cleaned_studies)}개 처리 완료...")
        
        cleaned_text = study.get("cleaned_text", "")
        metadata = study.get("metadata", {})
        
        if not cleaned_text or not cleaned_text.strip():
            continue
        
        # 텍스트를 청크로 분할
        text_chunks = create_chunks_with_overlap(
            cleaned_text,
            chunk_size_min=CHUNK_SIZE_MIN,
            chunk_size_max=CHUNK_SIZE_MAX,
            overlap_min=OVERLAP_MIN,
            overlap_max=OVERLAP_MAX
        )
        
        # 각 청크에 대해 데이터 생성
        for chunk_text in text_chunks:
            if not chunk_text or not chunk_text.strip():
                continue
            
            # 청크 ID 생성
            global_chunk_counter += 1
            chunk_id = f"chi_{global_chunk_counter}"
            
            # 청크 데이터 구성
            chunk_data = {
                "chunk_id": chunk_id,
                "nctId": metadata.get('nctId', ''),
                "chunk_text": chunk_text.strip(),
                "metadata": metadata
            }
            
            all_chunks.append(chunk_data)
    
    print(f"\n✓ 총 {len(all_chunks)}개의 청크가 생성되었습니다.")
    print("=" * 60)
    
    return all_chunks, global_chunk_counter


def main():
    """
    메인 함수: 청킹만 실행합니다.
    """
    # 설정 변수 사용
    cleaned_data = CLEANED_DATA_PATH
    output_format = OUTPUT_FORMAT_OVERRIDE if OUTPUT_FORMAT_OVERRIDE else OUTPUT_FORMAT
    output_chunk = OUTPUT_CHUNK_FILE
    output_metadata = OUTPUT_METADATA_FILE
    
    # 1단계: 라이브러리 초기화
    print("\n[1단계] 라이브러리 초기화 중...")
    init_tokenizer()
    
    # 2단계: 클렌징된 데이터 파일 경로 처리
    if not cleaned_data:
        # 기본 경로 사용 - 프로젝트 루트까지 올라가기 (3번)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cleaned_data_file = os.path.join(base_dir, "data", "nih", "processed", "cleaned", "cleaned_data.json")
    else:
        cleaned_data_file = cleaned_data
        if not os.path.isabs(cleaned_data_file):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if os.path.exists(cleaned_data_file):
                cleaned_data_file = os.path.abspath(cleaned_data_file)
            else:
                cleaned_data_file = os.path.join(base_dir, cleaned_data_file)
    
    # 3단계: 청킹 실행
    all_chunks, _ = run_chunking_only(cleaned_data_file)
    
    # 4단계: 결과 저장
    if output_format == 'csv':
        # 출력 디렉토리 설정 (프로젝트 루트의 data/nih/processed/chunked)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_dir, "data", "nih", "processed", "chunked")
        os.makedirs(output_dir, exist_ok=True)
        
        # 출력 파일 경로 설정
        if output_chunk:
            chunk_output = output_chunk if os.path.isabs(output_chunk) else os.path.join(output_dir, os.path.basename(output_chunk))
        else:
            chunk_output = os.path.join(output_dir, "chunked_for_embedding.csv")
        
        if output_metadata:
            metadata_output = output_metadata if os.path.isabs(output_metadata) else os.path.join(output_dir, os.path.basename(output_metadata))
        else:
            metadata_output = os.path.join(output_dir, "chunked_metadata.csv")
        
        save_chunks_to_csv(all_chunks, output_file=chunk_output)
        save_metadata_to_csv(all_chunks, output_file=metadata_output)
        
        print(f"\n" + "=" * 60)
        print("완료!")
        print("=" * 60)
        print(f"✓ 총 {len(all_chunks)}개의 청크가 생성되었습니다.")
        print(f"✓ 생성된 파일:")
        print(f"  - {chunk_output} (핵심 청킹 데이터)")
        print(f"  - {metadata_output} (메타데이터)")
        print("=" * 60)
    else:
        print("JSON 형식 저장은 현재 지원되지 않습니다. CSV 형식을 사용해주세요.")


if __name__ == "__main__":
    main()