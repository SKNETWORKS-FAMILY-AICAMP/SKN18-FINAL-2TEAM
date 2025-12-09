"""
NIH Ingest Lambda Handler
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import shutil

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

common_path = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(common_path))

from rag.etl.step01_ingest.ingest_nih import fetch_all_conditions
from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    upload_directory_to_s3,
    cleanup_tmp_directory
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - NIH Ingest Only
    
    이벤트 형식:
    {
        "raw_dir": "data/raw",           # 선택: 기본값 "data/raw"
        "s3_raw_prefix": "data/raw/nih",  # 선택: S3 raw 데이터 접두사
        "trigger_cleansing": true,        # 선택: Ingest 완료 후 Cleansing Lambda 호출 여부 (기본값: true)
    }
    """
    raw_dir = event.get("raw_dir", "data/raw")
    s3_raw_prefix = event.get("s3_raw_prefix", f"{raw_dir}/nih")
    trigger_cleansing = event.get("trigger_cleansing", True)  # 기본값: true
    
    print(f"[Lambda][NIH][Ingest] Processing started", flush=True)
    start_time = datetime.now()
    
    try:
        # Lambda 환경에서 /tmp 디렉토리 정리 (이전 실행의 데이터 제거)
        if is_lambda_environment():
            print(f"[Lambda][NIH] /tmp 디렉토리 정리 중...", flush=True)
            cleanup_tmp_directory("/tmp/data")
        
        # Lambda 환경에서는 /tmp를 사용하도록 경로 조정
        if is_lambda_environment():
            output_folder = ensure_local_path(f"{raw_dir}/nih")
            print(f"[Lambda][NIH] Ingest: API에서 새 데이터 수집 (S3 다운로드 불필요)", flush=True)
        else:
            from rag.etl.step02_normalize.02_normalize_nih import get_project_root
            base_dir = get_project_root()
            output_folder = os.path.join(base_dir, raw_dir, "nih")
        
        os.makedirs(output_folder, exist_ok=True)
        
        # OUTPUT_FOLDER 환경 변수 설정 (02_ingest_nih.py에서 사용)
        original_output_folder = os.environ.get("OUTPUT_FOLDER")
        os.environ["OUTPUT_FOLDER"] = output_folder
        
        try:
            # NIH ingest 실행
            results = fetch_all_conditions()
            print(f"[Lambda][NIH][Ingest] Ingest completed", flush=True)
        finally:
            # 환경 변수 복원
            if original_output_folder:
                os.environ["OUTPUT_FOLDER"] = original_output_folder
            elif "OUTPUT_FOLDER" in os.environ:
                del os.environ["OUTPUT_FOLDER"]
        
        # Lambda 환경에서 처리된 파일을 S3에 업로드
        today = None
        if is_lambda_environment():
            print(f"[Lambda][NIH] 처리된 데이터를 S3에 업로드 중...", flush=True)
            today = datetime.now().strftime("%Y%m%d")
            upload_directory_to_s3(output_folder, f"{s3_raw_prefix}/{today}")
            
            # 업로드 완료 후 로컬 파일 삭제
            print(f"[Lambda][NIH] 로컬 파일 정리 중...", flush=True)
            if os.path.exists(output_folder):
                shutil.rmtree(output_folder)
            print(f"[Lambda][NIH] 로컬 파일 정리 완료", flush=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            "statusCode": 200,
            "body": {
                "message": "Successfully completed ingest",
                "duration_seconds": duration,
                "s3_prefix": f"{s3_raw_prefix}/{today}" if is_lambda_environment() else None
            }
        }
        
        # Ingest 완료 후 Cleansing Lambda 호출 (Lambda 환경에서만, trigger_cleansing이 true일 때)
        if is_lambda_environment() and trigger_cleansing:
            try:
                import boto3
                lambda_client = boto3.client('lambda')
                
                # Cleansing Lambda 함수 이름 (환경 변수에서 가져오거나 하드코딩)
                cleanse_chunk_function_name = os.environ.get(
                    'CLEANSE_CHUNK_FUNCTION_NAME',
                    'skn18-nih-cleanse-chunk'  # 기본값
                )
                
                cleanse_chunk_event = {
                    "raw_dir": "data/raw",
                    "processed_dir": "data/processed",
                    "input_date": today,  # 오늘 날짜의 데이터 처리
                    "s3_raw_prefix": s3_raw_prefix,
                    "s3_processed_prefix": "data/processed/nih"
                }
                
                print(f"[Lambda][NIH][Ingest] Cleansing Lambda 호출 중: {cleanse_chunk_function_name}", flush=True)
                response = lambda_client.invoke(
                    FunctionName=cleanse_chunk_function_name,
                    InvocationType='Event',  # 비동기 실행 (Fire and Forget)
                    Payload=json.dumps(cleanse_chunk_event)
                )
                
                print(f"[Lambda][NIH][Ingest] Cleansing Lambda 호출 완료 (StatusCode: {response['StatusCode']})", flush=True)
                
                # 결과에 Cleansing Lambda 호출 정보 추가
                result['body']['cleansing_triggered'] = True
                result['body']['cleansing_function'] = cleanse_chunk_function_name
                
            except Exception as e:
                # Cleansing Lambda 호출 실패는 Ingest 성공을 막지 않음
                print(f"[Lambda][NIH][Ingest] ⚠️  Cleansing Lambda 호출 실패 (무시): {e}", flush=True)
                import traceback
                traceback.print_exc()
                result['body']['cleansing_triggered'] = False
                result['body']['cleansing_error'] = str(e)
        
        return result
        
    except Exception as e:
        print(f"[Lambda][NIH][Ingest] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e)}
        }
