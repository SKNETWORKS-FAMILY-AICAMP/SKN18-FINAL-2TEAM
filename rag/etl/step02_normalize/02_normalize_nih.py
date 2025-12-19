"""
클렌징만 수행하는 스크립트
=======================
JSON 파일을 읽어서 텍스트를 정리하고 저장합니다.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ============================================
# 설정 변수
# ============================================
INPUT_DATE = None
CLEANED_OUTPUT_PATH = None
BATCH_SIZE = 10  # 배치 크기
MAX_STUDIES_PER_FILE = 100  # 200에서 100으로 감소 (더 작은 파일로 분할)
MIN_FREE_SPACE_MB = 100  # 최소 여유 공간 (100MB 미만이면 파일 업로드)
# ============================================

# 프로젝트 루트 경로를 시스템 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# modules 디렉토리를 시스템 경로에 추가 (패키지 구조를 위해)
modules_dir = os.path.join(current_dir, "modules")
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# common 디렉토리를 시스템 경로에 추가 (nltk_setup 등 공통 모듈용)
common_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "common")
if common_dir not in sys.path:
    sys.path.insert(0, common_dir)

# 필요한 모듈 임포트 (패키지 구조를 활용)
from nih.text_cleaner import clean_text
from nih.data_extractor import extract_metadata, extract_core_fields, combine_core_fields
from nltk_setup import setup_nltk  # common에서 import

# file_handler 함수들 (modules/nih에 없으면 여기에 정의)
def load_json_file(json_file_path):
    """
    JSON 파일을 읽어서 파이썬 딕셔너리로 반환합니다.
    큰 파일의 경우 메모리 효율적으로 처리합니다.
    
    Args:
        json_file_path (str): JSON 파일 경로
        
    Returns:
        dict: JSON 파일 내용
    """
    file_size = os.path.getsize(json_file_path)
    # 50MB 이상인 경우 경고 출력
    if file_size > 50 * 1024 * 1024:  # 50MB
        print(f"   ⚠️  큰 파일 감지: {file_size / (1024*1024):.1f}MB - 메모리 사용량 주의")
    
    # 파일 크기에 따라 처리 방식 선택
    # 100MB 이상이면 청크 단위로 읽기 시도
    if file_size > 100 * 1024 * 1024:  # 100MB
        print(f"   📦 큰 파일 스트리밍 처리 중...")
        # 큰 파일의 경우 기본 json.load 사용하되, 메모리 모니터링
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                # 파일을 청크 단위로 읽어서 메모리 압박 완화
                # JSON은 전체를 파싱해야 하므로 완전한 스트리밍은 어렵지만,
                # 파일 읽기 자체는 버퍼링하여 처리
                return json.load(f)
        except MemoryError:
            print(f"   ❌ 메모리 부족 오류 발생. 파일이 너무 큽니다: {file_size / (1024*1024):.1f}MB")
            raise
    else:
        # 작은 파일은 기존 방식 사용
        with open(json_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def extract_studies_from_json(data):
    """
    JSON 데이터에서 studies 배열을 추출합니다.
    
    Clinical Trials API 응답 형식:
    - {"studies": [...]} 형태
    - 또는 직접 배열 형태
    
    Args:
        data (dict or list): JSON 파일에서 읽은 데이터
        
    Returns:
        list: study 객체들의 리스트
    """
    # studies 키가 있으면 해당 배열 반환
    if isinstance(data, dict) and "studies" in data:
        return data["studies"]
    # 직접 배열인 경우
    elif isinstance(data, list):
        return data
    # 빈 딕셔너리인 경우
    else:
        return []


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


def get_project_root():
    """
    프로젝트 루트 디렉토리를 찾습니다.
    
    현재 파일 위치: rag/etl/step02_normalize/02_normalize_nih.py
    프로젝트 루트: SKN18-FINAL-2TEAM (data 폴더가 있는 위치)
    Lambda 환경: /tmp 반환
    
    Returns:
        str: 프로젝트 루트 디렉토리 경로
    """
    # Lambda 환경 감지
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp"
    
    current_file = os.path.abspath(__file__)
    # rag/etl/step02_normalize/02_normalize_nih.py
    # 4번 dirname을 하면 프로젝트 루트에 도달
    # step02_normalize -> etl -> rag -> 프로젝트 루트
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    return project_root


def get_output_path(base_dir, success=True):
    """
    출력 경로를 생성합니다.
    
    형식: data/processed/nih/{success|fail}/year=YYYY/month=MM/day=DD/stage=cleaned/파일명
    
    Args:
        base_dir: 프로젝트 루트 디렉토리
        success: 성공 여부 (True면 success, False면 fail)
        
    Returns:
        str: 출력 파일 경로
    """
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    
    # 서브 디렉토리: success or fail
    sub_dir = "success" if success else "fail"
    
    # 경로 구성: data/processed/nih/{success|fail}/year=YYYY/month=MM/day=DD/stage=cleaned/
    output_dir = os.path.join(
        base_dir,  # 프로젝트 루트
        "data",
        "processed",
        "nih",
        sub_dir,
        f"year={year}",
        f"month={month:02d}",
        f"day={day:02d}",
        "stage=cleaned"
    )
    
    # 파일명: cleaned_data_YYYYMMDD_HHMMSS.json
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"cleaned_data_{timestamp}.json"
    
    output_file = os.path.join(output_dir, filename)
    return output_file


def run_cleansing_only(json_files, output_file=None, success=True):
    """
    클렌징만 수행합니다. 파일을 작은 단위로 분할하고, Lambda 환경에서는 즉시 S3에 업로드.
    """
    # 시작 시간 기록
    start_time = datetime.now()
    print(f"\n{'=' * 60}")
    print(f"🚀 Normalize 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")
    
    # Lambda 환경 감지
    is_lambda = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    
    # 파일 분할을 위한 변수
    file_index = 0
    studies_in_current_file = 0
    current_output_file = None
    output_files = []  # 생성된 모든 파일 경로 저장
    
    # 출력 파일 경로 생성 함수 (파일 인덱스 포함)
    def get_output_file_path(file_idx):
        base_dir = get_project_root()
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day
        sub_dir = "success" if success else "fail"
        output_dir = os.path.join(
            base_dir, "data", "processed", "nih", sub_dir,
            f"year={year}", f"month={month:02d}", f"day={day:02d}", "stage=cleaned"
        )
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"cleaned_data_{timestamp}_part{file_idx:03d}.json"
        return os.path.join(output_dir, filename)
    
    # 첫 번째 파일 생성
    if output_file is None:
        current_output_file = get_output_file_path(file_index)
    else:
        current_output_file = output_file
    
    # output_files에 추가하지 않음 (S3 업로드 후에만 추가)
    # output_files.append(current_output_file)  # 이 줄 제거
    os.makedirs(os.path.dirname(current_output_file), exist_ok=True)
    
    # 첫 번째 파일 초기화
    with open(current_output_file, 'w', encoding='utf-8') as f:
        f.write('{\n  "total_studies": 0,\n  "cleaned_studies": [\n')
    
    total_studies = 0
    processed_files = 0
    failed_files = 0
    written_count = 0
    batch_buffer = []
    is_first_item = True
    
    # S3 업로드 및 파일 삭제 함수
    def upload_file_to_s3_and_delete(file_path, s3_key_prefix="data/processed/nih"):
        """파일을 S3에 업로드하고 로컬 파일 삭제, S3 키 반환"""
        if not is_lambda:
            return file_path
        
        try:
            import boto3
            s3_client = boto3.client('s3')
            bucket = os.environ.get("S3_BUCKET_NAME", "skn18-etl-data-dev")
            
            # S3 키 생성
            now = datetime.now()
            year = now.year
            month = now.month
            day = now.day
            sub_dir = "success" if success else "fail"
            s3_key = f"{s3_key_prefix}/{sub_dir}/year={year}/month={month:02d}/day={day:02d}/stage=cleaned/{os.path.basename(file_path)}"
            
            # S3에 업로드
            s3_client.upload_file(file_path, bucket, s3_key)
            print(f"   ✓ 파일 S3 업로드 완료: {s3_key}", flush=True)
            
            # 로컬 파일 삭제
            os.remove(file_path)
            print(f"   ✓ 로컬 파일 삭제 완료: {os.path.basename(file_path)}", flush=True)
            
            return s3_key  # S3 키 반환
        except Exception as e:
            print(f"   ❌ S3 업로드 실패 (파일 유지): {e}", flush=True)
            return file_path
    
    # 디스크 공간 체크 함수
    def check_disk_space():
        """디스크 공간 확인"""
        if not is_lambda:
            return True
        
        try:
            stat = shutil.disk_usage("/tmp")
            free_space_mb = stat.free / (1024 * 1024)
            return free_space_mb >= MIN_FREE_SPACE_MB
        except:
            return True
    
    try:
        for file_idx, json_file in enumerate(json_files, 1):
            file_start_time = datetime.now()
            print(f"\n{'─' * 60}")
            print(f"[{file_idx}/{len(json_files)}] 파일 처리 시작: {os.path.basename(json_file)}")
            print(f"   전체 진행률: {file_idx}/{len(json_files)} ({file_idx*100//len(json_files)}%)")
            
            try:
                # JSON 파일 읽기
                print(f"   📖 JSON 파일 읽는 중...")
                data = load_json_file(json_file)
                studies = extract_studies_from_json(data)
                print(f"   ✓ {len(studies)}개의 study를 찾았습니다.")
                total_studies += len(studies)
                
                if len(studies) == 0:
                    print(f"   ⚠️  경고: 이 파일에는 study가 없습니다.")
                    processed_files += 1
                    continue
                
                # 각 study의 텍스트 클렌징
                print(f"   🔄 {len(studies)}개의 study 클렌징 중...")
                study_count = 0
                
                # 메모리 효율성을 위해 원본 데이터 참조 제거
                # data 변수는 더 이상 필요 없으므로 메모리에서 해제
                del data
                
                for study_idx, study in enumerate(studies, 1):
                    # 진행률 표시 (10개마다 또는 마지막)
                    if study_idx % 10 == 0 or study_idx == len(studies):
                        progress_pct = (study_idx * 100) // len(studies) if len(studies) > 0 else 0
                        print(f"      진행: {study_idx}/{len(studies)} ({progress_pct}%)", end='\r')
                    
                    try:
                        # 메타데이터 추출
                        metadata = extract_metadata(study)
                        
                        # 핵심 필드 추출
                        core_fields = extract_core_fields(study)
                        
                        # 핵심 필드들을 하나의 텍스트로 합치기
                        combined_text = combine_core_fields(core_fields)
                        
                        # 텍스트 클렌징
                        cleaned_text = clean_text(combined_text) if combined_text else ""
                        
                        # 클렌징된 데이터 저장
                        # - combined_text, core_fields를 함께 저장하여
                        #   이후 청킹 단계에서 필드별 위치 기반 core_fields 매핑이 가능하도록 함
                        cleaned_study = {
                            "metadata": metadata,
                            "core_fields": core_fields,
                            "combined_text": combined_text,
                            "cleaned_text": cleaned_text,
                            "source_file": os.path.basename(json_file)
                        }
                        
                        batch_buffer.append(cleaned_study)
                        study_count += 1
                        written_count += 1
                        studies_in_current_file += 1
                        
                        # 배치 크기에 도달하면 파일에 쓰기
                        if len(batch_buffer) >= BATCH_SIZE:
                            _write_batch_to_file(current_output_file, batch_buffer, is_first_item)
                            batch_buffer.clear()
                            is_first_item = False
                            
                            # 디스크 공간 체크
                            if is_lambda:
                                if not check_disk_space():
                                    print(f"   ⚠️  디스크 공간 부족 감지, 현재 파일을 S3에 업로드 중...", flush=True)
                                    # 현재 파일 마무리
                                    _finalize_json_file(current_output_file, studies_in_current_file)
                                    # S3에 업로드하고 삭제
                                    s3_key = upload_file_to_s3_and_delete(current_output_file)
                                    output_files.append(s3_key)  # S3 키 저장
                                    
                                    # 새 파일 생성
                                    file_index += 1
                                    studies_in_current_file = 0
                                    is_first_item = True
                                    current_output_file = get_output_file_path(file_index)
                                    os.makedirs(os.path.dirname(current_output_file), exist_ok=True)
                                    with open(current_output_file, 'w', encoding='utf-8') as f:
                                        f.write('{\n  "total_studies": 0,\n  "cleaned_studies": [\n')
                                    
                                    print(f"   📦 새 파일 생성: {os.path.basename(current_output_file)}", flush=True)
                                
                                # 파일당 최대 study 수 체크
                                elif studies_in_current_file >= MAX_STUDIES_PER_FILE:
                                    print(f"   📦 파일 크기 제한 도달 ({MAX_STUDIES_PER_FILE}개 study), 새 파일 생성...", flush=True)
                                    # 현재 파일 마무리
                                    _finalize_json_file(current_output_file, studies_in_current_file)
                                    # Lambda 환경에서는 S3에 업로드하고 삭제
                                    s3_key = upload_file_to_s3_and_delete(current_output_file)
                                    output_files.append(s3_key)
                                    
                                    # 새 파일 생성
                                    file_index += 1
                                    studies_in_current_file = 0
                                    is_first_item = True
                                    current_output_file = get_output_file_path(file_index)
                                    os.makedirs(os.path.dirname(current_output_file), exist_ok=True)
                                    with open(current_output_file, 'w', encoding='utf-8') as f:
                                        f.write('{\n  "total_studies": 0,\n  "cleaned_studies": [\n')
                                    
                                    print(f"   📦 새 파일 생성: {os.path.basename(current_output_file)}", flush=True)
                            
                            # 메모리 정리
                            if study_idx % (BATCH_SIZE * 2) == 0:
                                import gc
                                gc.collect()
                    
                    except Exception as study_error:
                        print(f"\n      ⚠️  Study {study_idx} 처리 중 오류: {study_error}")
                        continue
                
                print(f"      ✓ {study_count}/{len(studies)}개 study 처리 완료")
                
                file_end_time = datetime.now()
                file_elapsed = file_end_time - file_start_time
                print(f"   ⏱️  파일 처리 시간: {file_elapsed}")
                processed_files += 1
                
            except Exception as e:
                print(f"\n❌ 처리 중 치명적 오류 발생: {e}")
                
                # 디스크 공간 부족 오류인 경우 특별 처리
                if isinstance(e, OSError) and e.errno == 28:
                    print(f"   ⚠️  디스크 공간 부족으로 인한 오류", flush=True)
                    # Lambda 환경에서는 S3에 직접 업로드 시도
                    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                        try:
                            import boto3
                            s3_client = boto3.client('s3')
                            bucket = os.environ.get("S3_BUCKET_NAME")
                            if bucket and os.path.exists(output_file):
                                # 현재까지 처리된 파일을 S3에 업로드
                                s3_key = f"data/processed/nih/partial/{os.path.basename(output_file)}"
                                s3_client.upload_file(output_file, bucket, s3_key)
                                print(f"   ✓ 부분 결과를 S3에 업로드: {s3_key}", flush=True)
                        except Exception as upload_error:
                            print(f"   ❌ S3 업로드 실패: {upload_error}", flush=True)
                
                # 실패한 경우 fail 폴더로 이동 (디스크 공간이 있으면)
                try:
                    base_dir = get_project_root()
                    fail_output_file = get_output_path(base_dir, success=False)
                    fail_dir = os.path.dirname(fail_output_file)
                    os.makedirs(fail_dir, exist_ok=True)
                    
                    if os.path.exists(output_file):
                        import shutil
                        shutil.move(output_file, fail_output_file)
                        output_file = fail_output_file
                except OSError as move_error:
                    if move_error.errno == 28:
                        print(f"   ❌ 디스크 공간 부족으로 fail 폴더 이동 실패", flush=True)
                    else:
                        raise
                
                raise
        
        # 남은 버퍼 데이터 쓰기
        if batch_buffer:
            _write_batch_to_file(current_output_file, batch_buffer, is_first_item)
        
        # 마지막 파일 마무리
        _finalize_json_file(current_output_file, studies_in_current_file)
        
        # Lambda 환경에서 마지막 파일도 S3에 업로드
        if is_lambda and os.path.exists(current_output_file):
            s3_key = upload_file_to_s3_and_delete(current_output_file)
            output_files.append(s3_key)  # S3 키 저장
        elif not is_lambda:
            # 로컬 환경에서는 파일 경로 저장
            output_files.append(current_output_file)
        
        # Lambda 환경에서는 S3 키 리스트를 반환 (여러 파일로 분할된 경우)
        if is_lambda and len(output_files) > 0:
            # S3 키 리스트를 딕셔너리로 반환하여 구분
            output_file = {
                "type": "s3_keys",
                "keys": output_files,
                "count": len(output_files)
            }
            print(f"   📦 총 {len(output_files)}개 파일로 분할되어 S3에 업로드됨", flush=True)
        else:
            # 로컬 환경이거나 파일이 하나인 경우
            output_file = current_output_file if not is_lambda else output_files[0] if output_files else current_output_file
    
    except OSError as e:
        if e.errno == 28:  # No space left on device
            print(f"   ❌ 디스크 공간 부족 오류 발생", flush=True)
            # 현재까지 처리된 파일들을 S3에 업로드 시도
            if is_lambda:
                for file_path in output_files:
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        try:
                            upload_file_to_s3_and_delete(file_path)
                        except:
                            pass
                # 현재 파일도 시도
                if current_output_file and os.path.exists(current_output_file):
                    try:
                        _finalize_json_file(current_output_file, studies_in_current_file)
                        upload_file_to_s3_and_delete(current_output_file)
                    except:
                        pass
            raise
        else:
            raise
    
    print(f"\n{'─' * 60}")
    print(f"📊 파일 처리 요약:")
    print(f"   ✓ 성공: {processed_files}개")
    if failed_files > 0:
        print(f"   ❌ 실패: {failed_files}개")
    print(f"    총 study 수: {total_studies}개")
    print(f"   💾 저장된 study 수: {written_count}개")
    print(f"{'─' * 60}\n")
    
    # 성공 여부에 따라 출력 경로 결정
    is_success = processed_files > 0 and failed_files == 0
    
    # Lambda 환경에서 딕셔너리를 반환한 경우, 파일 크기 체크와 fail 폴더 이동 로직 건너뛰기
    if isinstance(output_file, dict) and output_file.get("type") == "s3_keys":
        # S3 키 리스트인 경우 파일 크기 정보는 제공하지 않음
        save_end_time = datetime.now()
        save_elapsed = save_end_time - start_time
        
        print(f"✓ 저장 완료 (총 소요 시간: {save_elapsed}, {output_file['count']}개 파일로 분할)")
        
        # 종료 시간 및 총 소요 시간
        end_time = datetime.now()
        total_elapsed = end_time - start_time
        
        print(f"\n{'=' * 60}")
        print(f"✅ Normalize 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  총 소요 시간: {total_elapsed}")
        print(f"📊 처리 결과:")
        print(f"   - 처리된 파일: {processed_files}/{len(json_files)}개")
        print(f"   - 총 study 수: {total_studies}개")
        print(f"   - 저장된 study: {written_count}개")
        print(f"   - 출력 파일: {output_file['count']}개 파일로 분할 (S3에 저장됨)")
        print(f"{'=' * 60}\n")
        
        return output_file
    
    # 성공 여부에 따라 최종 경로 조정 (로컬 파일인 경우만)
    if not is_success and success:
        # 실패한 경우 fail 폴더로 이동
        base_dir = get_project_root()
        fail_output_file = get_output_path(base_dir, success=False)
        fail_dir = os.path.dirname(fail_output_file)
        os.makedirs(fail_dir, exist_ok=True)
        
        import shutil
        if os.path.exists(output_file):
            shutil.move(output_file, fail_output_file)
            output_file = fail_output_file
            print(f"⚠️  일부 실패로 인해 fail 폴더로 이동: {output_file}")
    
    save_end_time = datetime.now()
    save_elapsed = save_end_time - start_time
    
    # output_file이 실제 파일 경로인 경우에만 파일 크기 체크
    if isinstance(output_file, str) and os.path.exists(output_file):
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"✓ 저장 완료 (총 소요 시간: {save_elapsed}, 파일 크기: {file_size_mb:.2f} MB)")
    else:
        print(f"✓ 저장 완료 (총 소요 시간: {save_elapsed})")
    
    # 종료 시간 및 총 소요 시간
    end_time = datetime.now()
    total_elapsed = end_time - start_time
    
    print(f"\n{'=' * 60}")
    print(f"✅ Normalize 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  총 소요 시간: {total_elapsed}")
    print(f"📊 처리 결과:")
    print(f"   - 처리된 파일: {processed_files}/{len(json_files)}개")
    print(f"   - 총 study 수: {total_studies}개")
    print(f"   - 저장된 study: {written_count}개")
    print(f"   - 출력 파일: {output_file}")
    print(f"{'=' * 60}\n")
    
    return output_file


def _write_batch_to_file(output_file, batch_buffer, is_first_item):
    """
    배치 데이터를 파일에 추가합니다.
    """
    import shutil
    
    # Lambda 환경에서 디스크 공간 체크
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        stat = shutil.disk_usage("/tmp")
        free_space_mb = stat.free / (1024 * 1024)
        if free_space_mb < MIN_FREE_SPACE_MB:
            print(f"   ⚠️  디스크 공간 부족: {free_space_mb:.1f}MB 남음", flush=True)
            # 디스크 공간이 부족하면 예외 발생
            if free_space_mb < 10:  # 10MB 미만이면 즉시 중단
                raise OSError(28, "No space left on device", "/tmp")
    
    try:
        with open(output_file, 'a', encoding='utf-8') as f:
            for study in batch_buffer:
                if not is_first_item:
                    f.write(',\n')
                study_json = json.dumps(study, ensure_ascii=False, indent=2)
                indented_lines = ['    ' + line for line in study_json.split('\n')]
                f.write('\n'.join(indented_lines))
                is_first_item = False
    except OSError as e:
        if e.errno == 28:  # No space left on device
            print(f"   ❌ 파일 쓰기 중 디스크 공간 부족", flush=True)
            raise
        else:
            raise


def _finalize_json_file(output_file, total_studies):
    """
    JSON 파일을 마무리합니다 (배열 닫기 및 total_studies 업데이트).
    
    Args:
        output_file: 출력 파일 경로
        total_studies: 총 study 수
    """
    # 파일을 읽어서 total_studies 업데이트
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # total_studies 값 업데이트
    import re
    content = re.sub(r'"total_studies":\s*\d+', f'"total_studies": {total_studies}', content)
    
    # 배열 닫기 및 파일 닫기
    if not content.rstrip().endswith(']'):
        content = content.rstrip() + '\n  ]\n}'
    else:
        content = content.rstrip() + '\n}'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    """
    메인 함수: 클렌징만 실행합니다.
    """
    print("=" * 60)
    print("NIH 데이터 Normalize 시작")
    print("=" * 60)
    
    # 설정 변수 사용
    input_date = INPUT_DATE
    cleaned_output = CLEANED_OUTPUT_PATH
    
    # 1단계: 라이브러리 초기화
    print("\n[1단계] 라이브러리 초기화 중...")
    init_start = datetime.now()
    setup_nltk()
    init_end = datetime.now()
    print(f"✓ 라이브러리 초기화 완료 (소요 시간: {init_end - init_start})")
    
    # 2단계: 입력 경로 처리
    print(f"\n[2단계] 입력 경로 처리 중...")
    
    base_dir = get_project_root()
    
    # 입력 날짜 결정
    if input_date is None:
        input_date = datetime.now().strftime("%Y%m%d")
    
    # 입력 경로: data/raw/nih/{날짜}
    input_path = os.path.join(base_dir, "data", "raw", "nih", input_date)
    
    print(f"   프로젝트 루트: {base_dir}")
    print(f"   입력 날짜: {input_date}")
    print(f"   입력 경로: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"❌ 오류: 입력 경로가 존재하지 않습니다: {input_path}")
        # 사용 가능한 날짜 폴더 목록 표시
        nih_raw_dir = os.path.join(base_dir, "data", "raw", "nih")
        if os.path.exists(nih_raw_dir):
            available_dates = [d for d in os.listdir(nih_raw_dir) 
                             if os.path.isdir(os.path.join(nih_raw_dir, d)) and d.isdigit()]
            if available_dates:
                print(f"   사용 가능한 날짜 폴더: {', '.join(sorted(available_dates)[-5:])}")  # 최근 5개만 표시
        sys.exit(1)
    
    print(f"   📂 JSON 파일 검색 중...")
    json_files = find_json_files(input_path)
    
    if not json_files:
        print(f"❌ 오류: 입력 경로에서 JSON 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)
    
    print(f"✓ {len(json_files)}개의 JSON 파일을 찾았습니다.")
    
    # 3단계: 클렌징 실행
    print(f"\n[3단계] 클렌징 실행")
    cleaned_file = run_cleansing_only(json_files, cleaned_output, success=True)
    
    if cleaned_file:
        print(f"\n✅ 전체 프로세스 완료!")
        print(f"   최종 출력 파일: {cleaned_file}")
    else:
        print(f"\n❌ 프로세스 실패")
        sys.exit(1)


def run(raw_dir: str, processed_dir: str) -> None:
    """
    pipeline_runner에서 호출하는 진입점.
    
    Args:
        raw_dir: raw 데이터 루트 디렉토리 (예: 'data/raw')
        processed_dir: 정규화된 데이터 루트 디렉토리 (예: 'data/processed')
        
    현재 구현은 내부에서 사용하는 디렉토리 구조
    (get_project_root() 기준 data/raw/nih, data/processed/nih)를 그대로 사용하며,
    인자로 전달된 경로는 주로 로그용으로만 활용합니다.
    """
    print("=" * 60)
    print("NIH Normalize (pipeline_runner 호출)")
    print(f"RAW DIR (arg): {raw_dir}")
    print(f"PROCESSED DIR (arg): {processed_dir}")
    print("=" * 60)
    
    # 기존 main 로직 재사용
    main()


if __name__ == "__main__":
    main()