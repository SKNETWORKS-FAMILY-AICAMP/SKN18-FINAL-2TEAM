"""
메인 실행 파일 (main.py)
=======================
이 파일은 전체 데이터 클렌징 및 청킹 프로세스를 실행합니다.
cleansing 모드: run_cleansing_only.py 실행
chunking 모드: run_chunking_only.py 실행
full 모드: 클렌징 + 청킹 전체 실행

"""

import os
import sys
from pathlib import Path

# ============================================
# 설정 변수 (상단에 변수로 세팅)
# ============================================
MODE = 'full'  # 'full', 'cleansing', 'chunking'
INPUT_PATH = os.path.join("..", "data", "nih", "raw")  # 입력 JSON 파일 경로 또는 폴더 경로
OUTPUT_FORMAT_OVERRIDE = None  # 출력 포맷 ('json' 또는 'csv', None이면 config의 OUTPUT_FORMAT 사용)
OUTPUT_CHUNK_FILE = None  # 청크 출력 파일명 (None이면 config.CHUNK_OUTPUT_FILE 사용)
OUTPUT_METADATA_FILE = None  # 메타데이터 출력 파일명 (None이면 config.METADATA_OUTPUT_FILE 사용)
# ============================================

# 프로젝트 루트 경로를 시스템 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 필요한 모듈 임포트
from cleansing.nltk_setup import setup_nltk
from cleansing.text_cleaner import clean_text
from token_counter import init_tokenizer
from config import (
    CHUNK_SIZE_MIN, CHUNK_SIZE_MAX, OVERLAP_MIN, OVERLAP_MAX,
    CHUNK_OUTPUT_FILE, METADATA_OUTPUT_FILE, OUTPUT_FORMAT, CHUNK_SEPARATOR
)
from chunking.file_handler import load_json_file, extract_studies_from_json, save_chunks_to_csv, save_metadata_to_csv
from chunking.data_extractor import extract_metadata, extract_core_fields, combine_core_fields
from chunking.chunker import create_chunks_with_overlap


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


def process_studies(studies, global_chunk_counter_start=0):
    """
    모든 study를 처리하여 청크 데이터를 생성합니다. (전체 실행용)
    
    Args:
        studies (list): study 객체들의 리스트
        global_chunk_counter_start (int): 청크 카운터 시작 번호
        
    Returns:
        tuple: (청크 데이터 리스트, 다음 청크 카운터 번호)
    """
    all_chunks = []
    global_chunk_counter = global_chunk_counter_start
    
    print(f"\n총 {len(studies)}개의 study를 처리합니다...")
    
    # 각 study를 하나씩 처리
    for study_idx, study in enumerate(studies, 1):
        if study_idx % 10 == 0:
            print(f"  진행 중: {study_idx}/{len(studies)}개 처리 완료...")
        
        # 1단계: 메타데이터 추출
        metadata = extract_metadata(study)
        
        # 2단계: 핵심 필드 추출
        core_fields = extract_core_fields(study)
        
        # 3단계: 핵심 필드들을 하나의 텍스트로 합치기
        combined_text = combine_core_fields(core_fields)
        
        # 4단계: 텍스트 클렌징
        cleaned_text = clean_text(combined_text) if combined_text else ""
        
        # 5단계: 합쳐진 텍스트를 청크로 분할
        if cleaned_text:
            text_chunks = create_chunks_with_overlap(
                cleaned_text,
                chunk_size_min=CHUNK_SIZE_MIN,
                chunk_size_max=CHUNK_SIZE_MAX,
                overlap_min=OVERLAP_MIN,
                overlap_max=OVERLAP_MAX
            )
        else:
            text_chunks = []
        
        # 6단계: 각 청크에 대해 데이터 생성
        for chunk_text in text_chunks:
            if not chunk_text or not chunk_text.strip():
                continue
            
            # 청크 ID 생성 (chi_1, chi_2, ...)
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
    
    print(f"✓ 총 {len(all_chunks)}개의 청크가 생성되었습니다.\n")
    
    return all_chunks, global_chunk_counter


def run_full(json_files):
    """
    전체 프로세스를 실행합니다 (클렌징 + 청킹).
    
    Args:
        json_files (list): 처리할 JSON 파일 경로 리스트
        
    Returns:
        tuple: (청크 데이터 리스트, 총 study 개수)
    """
    print("=" * 60)
    print("[전체 실행] 클렌징 + 청킹 시작")
    print("=" * 60)
    
    all_chunks = []
    total_studies = 0
    global_chunk_counter = 0
    
    for file_idx, json_file in enumerate(json_files, 1):
        print(f"\n{'='*60}")
        print(f"[{file_idx}/{len(json_files)}] 처리 중: {os.path.basename(json_file)}")
        print(f"{'='*60}")
        
        try:
            # JSON 파일 읽기
            data = load_json_file(json_file)
            studies = extract_studies_from_json(data)
            print(f"✓ {len(studies)}개의 study를 찾았습니다.")
            total_studies += len(studies)
            
            # 데이터 처리 및 청킹
            chunks, global_chunk_counter = process_studies(studies, global_chunk_counter)
            all_chunks.extend(chunks)
            
        except Exception as e:
            print(f"경고: 파일 처리 중 오류 발생 ({json_file}): {e}")
            import traceback
            traceback.print_exc()
            print("다음 파일로 계속 진행합니다...\n")
            continue
    
    return all_chunks, total_studies


def main():
    """
    메인 함수: 전체 프로세스를 실행합니다.
    """
    # 설정 변수 사용
    mode = MODE
    input_path = INPUT_PATH
    output_format = OUTPUT_FORMAT_OVERRIDE if OUTPUT_FORMAT_OVERRIDE else OUTPUT_FORMAT
    output_chunk = OUTPUT_CHUNK_FILE
    output_metadata = OUTPUT_METADATA_FILE
    
    # 모드에 따라 실행
    if mode == 'cleansing':
        # 클렌징만 실행 - run_cleansing_only.py 모듈 사용
        from run_cleansing_only import main as run_cleansing_main
        run_cleansing_main()
        
    elif mode == 'chunking':
        # 청킹만 실행 - run_chunking_only.py 모듈 사용
        from run_chunking_only import main as run_chunking_main
        run_chunking_main()
        
    else:  # mode == 'full'
        # 전체 실행
        # 1단계: 라이브러리 초기화
        print("\n[1단계] 라이브러리 초기화 중...")
        setup_nltk()
        init_tokenizer()
        
        # 입력 경로 처리
        if not os.path.isabs(input_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if os.path.exists(input_path):
                input_path = os.path.abspath(input_path)
            else:
                input_path = os.path.join(base_dir, input_path)
        
        json_files = find_json_files(input_path)
        if not json_files:
            print(f"오류: 입력 경로에서 JSON 파일을 찾을 수 없습니다: {input_path}")
            print(f"\n현재 작업 디렉토리: {os.getcwd()}")
            sys.exit(1)
        
        print("=" * 60)
        print("데이터 클렌징 및 청킹 시작")
        print("=" * 60)
        print(f"입력 경로: {input_path}")
        print(f"발견된 JSON 파일: {len(json_files)}개")
        if len(json_files) <= 10:
            for f in json_files:
                print(f"  - {f}")
        else:
            for f in json_files[:5]:
                print(f"  - {f}")
            print(f"  ... 외 {len(json_files) - 5}개 파일")
        print(f"출력 형식: {output_format}")
        print(f"청크 크기: {CHUNK_SIZE_MIN}-{CHUNK_SIZE_MAX} tokens")
        print(f"오버랩: {OVERLAP_MIN}-{OVERLAP_MAX} tokens")
        print("=" * 60)
        
        # 2단계: 모든 JSON 파일 처리
        print("\n[2단계] JSON 파일 읽기 및 처리 중...")
        all_chunks, total_studies = run_full(json_files)
        
        if not all_chunks:
            print("\n오류: 처리된 청크가 없습니다.")
            sys.exit(1)
        
        # 3단계: 결과 저장
        print("\n" + "=" * 60)
        print("[3단계] 결과 파일 저장 중...")
        print("=" * 60)
        try:
            if output_format == 'csv':
                # 출력 파일명 결정
                chunk_output = output_chunk if output_chunk else CHUNK_OUTPUT_FILE
                metadata_output = output_metadata if output_metadata else METADATA_OUTPUT_FILE
                
                # CSV 형식으로 저장
                save_chunks_to_csv(all_chunks, output_file=chunk_output)
                save_metadata_to_csv(all_chunks, output_file=metadata_output)
                
                print(f"\n" + "=" * 60)
                print("완료!")
                print("=" * 60)
                print(f"✓ 처리된 파일: {len(json_files)}개")
                print(f"✓ 총 {total_studies}개의 study에서 {len(all_chunks)}개의 청크가 생성되었습니다.")
                print(f"✓ 생성된 파일:")
                print(f"  - {chunk_output} (핵심 청킹 데이터)")
                print(f"  - {metadata_output} (메타데이터)")
                from config import NO_DATA_MARKER
                print(f"\n※ 빈 데이터는 '{NO_DATA_MARKER}'로 표시됩니다.")
                print(f"※ 청크 크기: {CHUNK_SIZE_MIN}-{CHUNK_SIZE_MAX} tokens")
                print(f"※ 오버랩: {OVERLAP_MIN}-{OVERLAP_MAX} tokens (semantic chunking, 점 기준)")
                print(f"※ 여러 정보 구분자: {CHUNK_SEPARATOR}")
                print("=" * 60)
            else:
                print("JSON 형식 저장은 현재 지원되지 않습니다. CSV 형식을 사용해주세요.")
                
        except Exception as e:
            print(f"오류: 파일 저장 중 문제가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()