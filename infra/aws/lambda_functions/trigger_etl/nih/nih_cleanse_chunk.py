"""
NIH Cleansing + Chunking Lambda Handler
"""
import sys
import os
import json
import boto3
from pathlib import Path
from datetime import datetime
import shutil
from botocore.exceptions import ClientError

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

common_path = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(common_path))

from rag.etl.step02_normalize.normalize_nih import (
    run_cleansing_only, 
    find_json_files, 
    get_project_root, 
    setup_nltk
)
from rag.etl.step04_chunk.chunker_nih import (
    run_chunking_only, 
    initialize_csv_files, 
    get_output_path as get_chunk_output_path,
    init_tokenizer
)
from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    download_file_from_s3,
    list_s3_files,
    upload_file_to_s3,
    cleanup_tmp_directory
)


def check_if_already_processed(input_date: str, s3_processed_prefix: str) -> bool:
    """
    해당 날짜의 데이터가 이미 처리되었는지 확인
    
    Args:
        input_date: 처리할 날짜 (YYYYMMDD 형식)
        s3_processed_prefix: S3 processed 데이터 접두사
    
    Returns:
        이미 처리되었으면 True, 아니면 False
    """
    if not is_lambda_environment():
        return False  # 로컬 환경에서는 체크하지 않음
    
    try:
        s3_client = boto3.client('s3')
        bucket = os.environ.get("S3_BUCKET_NAME")
        
        if not bucket:
            print(f"[Lambda][NIH] S3_BUCKET_NAME 환경 변수가 없어 중복 체크를 건너뜁니다.", flush=True)
            return False
        
        # 날짜에서 year, month, day 추출
        year = input_date[:4]
        month = input_date[4:6]
        day = input_date[6:8]
        
        # Chunking 결과 파일 경로 (최종 결과물)
        chunk_s3_key = f"{s3_processed_prefix}/success/year={year}/month={month}/day={day}/stage=chunked/chunk.csv"
        
        # S3에서 파일 존재 여부 확인
        try:
            s3_client.head_object(Bucket=bucket, Key=chunk_s3_key)
            print(f"[Lambda][NIH] ⚠️  이미 처리된 데이터입니다: {input_date} (S3 키: {chunk_s3_key})", flush=True)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # 파일이 없으면 처리되지 않은 것
                print(f"[Lambda][NIH] 처리되지 않은 데이터입니다: {input_date}", flush=True)
                return False
            else:
                # 다른 오류는 무시하고 처리 진행
                print(f"[Lambda][NIH] 중복 체크 중 오류 발생 (무시하고 진행): {e}", flush=True)
                return False
    except Exception as e:
        # 오류 발생 시 안전하게 처리 진행
        print(f"[Lambda][NIH] 중복 체크 중 예외 발생 (무시하고 진행): {e}", flush=True)
        return False


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - NIH Cleansing + Chunking
    
    이벤트 형식:
    {
        "raw_dir": "data/raw",           # 선택: 기본값 "data/raw"
        "processed_dir": "data/processed", # 선택: 기본값 "data/processed"
        "input_date": "20250115",         # 선택: None이면 오늘 날짜 사용
        "s3_raw_prefix": "data/raw/nih",  # 선택: S3 raw 데이터 접두사
        "s3_processed_prefix": "data/processed/nih"  # 선택: S3 processed 데이터 접두사
        "skip_if_exists": true,           # 선택: 이미 처리된 데이터면 스킵 (기본값: true)
    }
    """
    raw_dir = event.get("raw_dir", "data/raw")
    processed_dir = event.get("processed_dir", "data/processed")
    input_date = event.get("input_date")  # None이면 오늘 날짜
    s3_raw_prefix = event.get("s3_raw_prefix", f"{raw_dir}/nih")
    s3_processed_prefix = event.get("s3_processed_prefix", f"{processed_dir}/nih")
    skip_if_exists = event.get("skip_if_exists", True)  # 기본값: true
    
    print(f"[Lambda][NIH][Cleanse+Chunk] Processing started", flush=True)
    start_time = datetime.now()
    
    try:
        # 입력 날짜 결정
        if input_date is None:
            input_date = datetime.now().strftime("%Y%m%d")
        
        # 중복 실행 방지: 이미 처리된 데이터인지 확인
        if skip_if_exists and check_if_already_processed(input_date, s3_processed_prefix):
            print(f"[Lambda][NIH][Cleanse+Chunk] 이미 처리된 데이터입니다. 스킵합니다.", flush=True)
            return {
                "statusCode": 200,
                "body": {
                    "message": "Already processed - skipped",
                    "input_date": input_date,
                    "skipped": True,
                    "duration_seconds": 0
                }
            }
        
        # Lambda 환경에서 /tmp 디렉토리 정리 (이전 실행의 데이터 제거)
        if is_lambda_environment():
            print(f"[Lambda][NIH] /tmp 디렉토리 정리 중...", flush=True)
            cleanup_tmp_directory("/tmp/data")
        
        # 프로젝트 루트 경로 설정
        base_dir = get_project_root()
        
        # 1. Cleansing
        print(f"[Lambda][NIH][Step 1/2] Cleansing started", flush=True)
        
        # NLTK 초기화
        setup_nltk()
        
        # 입력 경로 설정
        if is_lambda_environment():
            input_path = ensure_local_path(f"{raw_dir}/nih/{input_date}")
            
            # S3에서 파일 목록만 먼저 가져오기
            if not os.path.exists(input_path) or not any(Path(input_path).glob("*.json")):
                print(f"[Lambda][NIH] S3에서 오늘 날짜({input_date}) raw 데이터 파일 목록 조회 중...", flush=True)
                date_prefix = f"{s3_raw_prefix}/{input_date}"
                
                # 파일 목록만 가져오기
                s3_file_keys = list_s3_files(date_prefix)
                
                if not s3_file_keys:
                    raise ValueError(f"No files found in S3 prefix: {date_prefix}")
                
                print(f"[Lambda][NIH] S3에서 {len(s3_file_keys)}개 파일 발견. 스트리밍 방식으로 처리합니다.", flush=True)
                
                # 임시 디렉토리 생성
                os.makedirs(input_path, exist_ok=True)
                
                # 각 파일을 하나씩 다운로드 → cleansing → 삭제
                all_cleaned_files = []  # 모든 cleansing 결과 저장
                for idx, s3_key in enumerate(s3_file_keys, 1):
                    # S3 키에서 로컬 파일명 추출
                    relative_path = s3_key[len(date_prefix):].lstrip('/')
                    local_file_path = os.path.join(input_path, relative_path)
                    
                    # 디렉토리 생성
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    
                    # 파일 다운로드
                    print(f"[Lambda][NIH] 다운로드 중: {os.path.basename(local_file_path)} ({idx}/{len(s3_file_keys)})", flush=True)
                    if download_file_from_s3(s3_key, local_file_path):
                        print(f"[Lambda][NIH] 다운로드 완료: {os.path.basename(local_file_path)}", flush=True)
                        
                        # 즉시 cleansing 처리
                        try:
                            cleaned_result = run_cleansing_only([local_file_path], output_file=None, success=True)
                            if isinstance(cleaned_result, dict) and cleaned_result.get("type") == "s3_keys":
                                all_cleaned_files.extend(cleaned_result["keys"])
                            else:
                                all_cleaned_files.append(cleaned_result)
                        finally:
                            # 처리 후 즉시 삭제
                            if os.path.exists(local_file_path):
                                os.remove(local_file_path)
                                # 빈 디렉토리도 삭제
                                try:
                                    parent_dir = os.path.dirname(local_file_path)
                                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                                        os.rmdir(parent_dir)
                                except:
                                    pass
                    else:
                        print(f"[Lambda][NIH] 다운로드 실패: {os.path.basename(local_file_path)}", flush=True)
                
                # 모든 cleansing 결과를 하나로 합침
                if all_cleaned_files:
                    cleaned_file = {
                        "type": "s3_keys",
                        "keys": all_cleaned_files,
                        "count": len(all_cleaned_files)
                    }
                    print(f"[Lambda][NIH][Step 1/2] Cleansing completed", flush=True)
                else:
                    raise ValueError("No files were successfully processed")
            else:
                # 로컬에 파일이 있는 경우 (일반적으로는 발생하지 않음)
                input_path = os.path.join(base_dir, raw_dir, "nih", input_date)
                
                if not os.path.exists(input_path):
                    raise FileNotFoundError(f"Input path not found: {input_path}")
                
                # JSON 파일 찾기
                json_files = find_json_files(input_path)
                if not json_files:
                    raise ValueError(f"No JSON files found in: {input_path}")
                
                print(f"[Lambda][NIH] Found {len(json_files)} JSON files", flush=True)
                
                # Cleansing 실행
                cleaned_file = run_cleansing_only(json_files, output_file=None, success=True)
                print(f"[Lambda][NIH][Step 1/2] Cleansing completed", flush=True)
                
                # Lambda 환경에서 cleansing 후 원본 파일 삭제 (디스크 공간 확보)
                if is_lambda_environment():
                    print(f"[Lambda][NIH] Cleansing 완료 후 원본 파일 삭제 중...", flush=True)
                    deleted_count = 0
                    for json_file in json_files:
                        try:
                            if os.path.exists(json_file):
                                os.remove(json_file)
                                deleted_count += 1
                                # 빈 디렉토리도 삭제 시도
                                try:
                                    parent_dir = os.path.dirname(json_file)
                                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                                        os.rmdir(parent_dir)
                                except OSError:
                                    pass  # 디렉토리가 비어있지 않으면 무시
                        except Exception as e:
                            print(f"[Lambda][NIH] 파일 삭제 중 오류 (무시): {e}", flush=True)
                    print(f"[Lambda][NIH] 원본 파일 {deleted_count}개 삭제 완료", flush=True)
        else:
            # 로컬 환경
            input_path = os.path.join(base_dir, raw_dir, "nih", input_date)
            
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input path not found: {input_path}")
            
            # JSON 파일 찾기
            json_files = find_json_files(input_path)
            if not json_files:
                raise ValueError(f"No JSON files found in: {input_path}")
            
            print(f"[Lambda][NIH] Found {len(json_files)} JSON files", flush=True)
            
            # Cleansing 실행
            cleaned_file = run_cleansing_only(json_files, output_file=None, success=True)
            print(f"[Lambda][NIH][Step 1/2] Cleansing completed", flush=True)
        
        # 2. Chunking
        print(f"[Lambda][NIH][Step 2/2] Chunking started", flush=True)
        
        # 토크나이저 초기화
        init_tokenizer()
        
        # 출력 경로 생성 (Lambda 환경에서는 /tmp 사용)
        if is_lambda_environment():
            tmp_base = Path("/tmp")
            # input_date에서 year, month, day 추출
            year = int(input_date[:4])
            month = int(input_date[4:6])
            day = int(input_date[6:8])
            chunk_output = tmp_base / "data" / "processed" / "nih" / "success" / f"year={year}" / f"month={month:02d}" / f"day={day:02d}" / "stage=chunked" / "chunk.csv"
            metadata_output = tmp_base / "data" / "processed" / "nih" / "success" / f"year={year}" / f"month={month:02d}" / f"day={day:02d}" / "stage=chunked" / "metadata.csv"
            chunk_output.parent.mkdir(parents=True, exist_ok=True)
        else:
            chunk_output = get_chunk_output_path(base_dir, success=True, file_type="chunk")
            metadata_output = get_chunk_output_path(base_dir, success=True, file_type="metadata")
        
        # CSV 파일 초기화
        chunk_writer, metadata_writer, chunk_file, metadata_file = initialize_csv_files(
            chunk_output, metadata_output
        )
        
        try:
            # cleaned_file이 S3 키 리스트인 경우 처리
            if isinstance(cleaned_file, dict) and cleaned_file.get("type") == "s3_keys":
                s3_keys = cleaned_file["keys"]
                print(f"[Lambda][NIH] S3에서 {len(s3_keys)}개 파일 다운로드 및 처리 중...", flush=True)
                
                import boto3
                s3_client = boto3.client('s3')
                bucket = os.environ.get("S3_BUCKET_NAME", "skn18-etl-data-dev")
                
                # 임시 디렉토리에 파일 다운로드
                temp_dir = Path("/tmp/data/processed/nih/temp_cleaned")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                total_chunks = 0
                total_studies = 0
                chunk_success = True
                
                for idx, s3_key in enumerate(s3_keys, 1):
                    print(f"[Lambda][NIH] 파일 {idx}/{len(s3_keys)} 다운로드 중: {os.path.basename(s3_key)}", flush=True)
                    
                    # S3 키가 상대 경로인지 확인 (버킷 이름이 포함되어 있지 않은 경우)
                    if not s3_key.startswith("s3://"):
                        # 상대 경로인 경우 버킷 이름과 조합
                        full_s3_key = s3_key
                    else:
                        # s3:// 버킷/키 형식인 경우 파싱
                        full_s3_key = s3_key.replace(f"s3://{bucket}/", "")
                    
                    # 임시 파일 경로
                    temp_file = temp_dir / os.path.basename(s3_key)
                    
                    # S3에서 다운로드
                    try:
                        s3_client.download_file(bucket, full_s3_key, str(temp_file))
                        print(f"[Lambda][NIH] 다운로드 완료: {os.path.basename(s3_key)}", flush=True)
                    except Exception as download_error:
                        print(f"[Lambda][NIH] 다운로드 실패: {os.path.basename(s3_key)} - {download_error}", flush=True)
                        # 파일이 없으면 건너뛰기
                        continue
                    
                    # Chunking 실행
                    try:
                        chunks, studies, success = run_chunking_only(
                            str(temp_file), chunk_writer, metadata_writer, success=True
                        )
                        total_chunks += chunks
                        total_studies += studies
                        if not success:
                            chunk_success = False
                    finally:
                        # 처리 후 임시 파일 삭제
                        if temp_file.exists():
                            temp_file.unlink()
                
                # 임시 디렉토리 삭제
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                
                print(f"[Lambda][NIH][Step 2/2] Chunking completed: {total_chunks} chunks, {total_studies} studies", flush=True)
            else:
                # 기존 로직 (단일 파일)
                total_chunks, total_studies, chunk_success = run_chunking_only(
                    cleaned_file, chunk_writer, metadata_writer, success=True
                )
                print(f"[Lambda][NIH][Step 2/2] Chunking completed", flush=True)
        finally:
            # 파일 닫기
            chunk_file.close()
            metadata_file.close()
        
        # Lambda 환경에서 처리된 파일을 S3에 업로드
        if is_lambda_environment():
            print(f"[Lambda][NIH] 처리된 데이터를 S3에 업로드 중...", flush=True)
            
            # input_date에서 year, month, day 추출
            year = int(input_date[:4])
            month = int(input_date[4:6])
            day = int(input_date[6:8])
            
            # Cleansing 결과는 이미 S3에 업로드됨 (여러 파일로 분할된 경우)
            if isinstance(cleaned_file, dict) and cleaned_file.get("type") == "s3_keys":
                print(f"[Lambda][NIH] Cleansing 결과는 이미 S3에 업로드됨 ({len(cleaned_file['keys'])}개 파일)", flush=True)
            elif isinstance(cleaned_file, str) and os.path.exists(cleaned_file):
                # 단일 파일인 경우에만 업로드
                cleaned_s3_key = f"{s3_processed_prefix}/success/year={year}/month={month:02d}/day={day:02d}/stage=cleaned/{os.path.basename(cleaned_file)}"
                upload_file_to_s3(cleaned_file, cleaned_s3_key)
            
            # Chunking 결과 업로드
            if os.path.exists(str(chunk_output)):
                chunk_s3_key = f"{s3_processed_prefix}/success/year={year}/month={month:02d}/day={day:02d}/stage=chunked/chunk.csv"
                upload_file_to_s3(str(chunk_output), chunk_s3_key)
            
            if os.path.exists(str(metadata_output)):
                metadata_s3_key = f"{s3_processed_prefix}/success/year={year}/month={month:02d}/day={day:02d}/stage=chunked/metadata.csv"
                upload_file_to_s3(str(metadata_output), metadata_s3_key)
            
            # 업로드 완료 후 로컬 파일 삭제
            print(f"[Lambda][NIH] 로컬 파일 정리 중...", flush=True)
            if os.path.exists(input_path):
                shutil.rmtree(input_path)
            # cleaned_file이 로컬 파일인 경우에만 삭제
            if isinstance(cleaned_file, str) and os.path.exists(cleaned_file):
                if os.path.exists(str(Path(cleaned_file).parent)):
                    shutil.rmtree(str(Path(cleaned_file).parent))
            if os.path.exists(str(chunk_output.parent)):
                shutil.rmtree(str(chunk_output.parent))
            print(f"[Lambda][NIH] 로컬 파일 정리 완료", flush=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "statusCode": 200,
            "body": {
                "message": "Successfully completed cleansing + chunking",
                "duration_seconds": duration,
                "total_chunks": total_chunks,
                "total_studies": total_studies,
                "chunk_output": str(chunk_output),
                "metadata_output": str(metadata_output),
                "input_date": input_date
            }
        }
    except Exception as e:
        print(f"[Lambda][NIH][Cleanse+Chunk] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e)}
        }
