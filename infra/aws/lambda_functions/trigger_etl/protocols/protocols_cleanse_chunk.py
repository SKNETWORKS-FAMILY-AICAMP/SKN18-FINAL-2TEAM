"""
Protocols.io Cleansing + Chunking Lambda Handler
"""
import sys
import os
import importlib
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

common_path = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(common_path))

# 숫자로 시작하는 모듈은 importlib로 동적 import
normalize_module = importlib.import_module("rag.etl.step02_normalize.03_normalize_protocols")
normalize_run = normalize_module.run

chunker_module = importlib.import_module("rag.etl.step04_chunk.chunker_protocols")
chunk_process_file = chunker_module.process_file

from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    upload_directory_to_s3
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - Protocols Cleansing + Chunking
    
    이벤트 형식:
    {
        "raw_dir": "data/raw",           # 선택: 기본값 "data/raw"
        "processed_dir": "data/processed", # 선택: 기본값 "data/processed"
        "keyword": "Protein",             # 선택: 특정 키워드만 처리 (None이면 모든 키워드)
        "s3_raw_prefix": "data/raw/protocols",      # 선택: S3 raw 데이터 접두사
        "s3_processed_prefix": "data/processed/protocols"  # 선택: S3 processed 데이터 접두사
    }
    """
    raw_dir = event.get("raw_dir", "data/raw")
    processed_dir = event.get("processed_dir", "data/processed")
    keyword = event.get("keyword")  # None이면 모든 키워드 처리
    s3_raw_prefix = event.get("s3_raw_prefix", f"{raw_dir}/protocols")
    s3_processed_prefix = event.get("s3_processed_prefix", f"{processed_dir}/protocols")
    
    print(f"[Lambda][Protocols][Cleanse+Chunk] Processing started", flush=True)
    start_time = datetime.now()
    
    try:
        # Lambda 환경에서 /tmp 경로 사용 및 S3에서 데이터 다운로드
        if is_lambda_environment():
            local_raw_dir = ensure_local_path(raw_dir)
            local_processed_dir = ensure_local_path(processed_dir)
            os.makedirs(local_raw_dir, exist_ok=True)
            os.makedirs(local_processed_dir, exist_ok=True)
            
            # S3에서 raw 데이터 다운로드
            print(f"[Lambda][Protocols] S3에서 raw 데이터 다운로드 중...", flush=True)
            download_directory_from_s3(s3_raw_prefix, local_raw_dir)
        else:
            local_raw_dir = raw_dir
            local_processed_dir = processed_dir
        
        # 1. Cleansing (Normalize)
        print(f"[Lambda][Protocols][Step 1/2] Cleansing started", flush=True)
        normalize_run(raw_dir=local_raw_dir, processed_dir=local_processed_dir)
        print(f"[Lambda][Protocols][Step 1/2] Cleansing completed", flush=True)
        
        # 2. Chunking
        print(f"[Lambda][Protocols][Step 2/2] Chunking started", flush=True)
        # INPUT_ROOT와 OUTPUT_ROOT를 동적으로 설정
        chunk_input_root = Path(local_processed_dir) / "protocols" / "success"
        
        if keyword:
            # 특정 키워드만 처리
            input_files = sorted(chunk_input_root.glob(f"**/stage=cleaned/protocol_cleaned_{keyword}.csv"))
        else:
            # 모든 키워드 처리
            input_files = sorted(chunk_input_root.glob("**/stage=cleaned/protocol_cleaned_*.csv"))
        
        if not input_files:
            print(f"[Lambda][Protocols][Step 2/2] No cleaned files found", flush=True)
            return {
                "statusCode": 200,
                "body": {"message": "No cleaned files to chunk"}
            }
        
        # OUTPUT_ROOT 설정을 위해 모듈의 전역 변수 업데이트
        chunker_module.OUTPUT_ROOT = Path(local_processed_dir) / "protocols"
        # INPUT_ROOT도 설정 필요
        chunker_module.INPUT_ROOT = Path(local_processed_dir) / "protocols" / "success"

        for csv_path in input_files:
            chunk_process_file(csv_path)
        print(f"[Lambda][Protocols][Step 2/2] Chunking completed", flush=True)
        
        # Lambda 환경에서 처리된 파일을 S3에 업로드
        if is_lambda_environment():
            print(f"[Lambda][Protocols] 처리된 데이터를 S3에 업로드 중...", flush=True)
            upload_directory_to_s3(local_processed_dir, s3_processed_prefix)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "statusCode": 200,
            "body": {
                "message": "Successfully completed cleansing + chunking",
                "duration_seconds": duration,
                "processed_files": len(input_files)
            }
        }
    except Exception as e:
        print(f"[Lambda][Protocols][Cleanse+Chunk] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e)}
        }
