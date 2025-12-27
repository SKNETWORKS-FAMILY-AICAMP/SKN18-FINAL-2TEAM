"""
Protocols.io Upsert Lambda Handler
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

# upsert_protocols 모듈 import
upsert_module = importlib.import_module("rag.etl.step06_upsert.upsert_protocols")
upsert_run = upsert_module.run

from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    upload_directory_to_s3
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - Protocols Upsert (PostgreSQL에 임베딩 저장)
    
    이벤트 형식:
    {
        "embeddings_dir": "data/embeddings",        # 선택: 기본값 "data/embeddings"
        "s3_embeddings_prefix": "data/embeddings/protocols"  # 선택: S3 embeddings 데이터 접두사
    }
    """
    embeddings_dir = event.get("embeddings_dir", "data/embeddings")
    s3_embeddings_prefix = event.get("s3_embeddings_prefix", f"{embeddings_dir}/protocols")
    
    print(f"[Lambda][Protocols][Upsert] Processing started", flush=True)
    start_time = datetime.now()
    
    try:
        # Lambda 환경에서 /tmp 경로 사용 및 S3에서 데이터 다운로드
        if is_lambda_environment():
            local_embeddings_dir = ensure_local_path(embeddings_dir)
            os.makedirs(local_embeddings_dir, exist_ok=True)
            
            # S3에서 embeddings 데이터 다운로드
            print(f"[Lambda][Protocols][Upsert] S3에서 embeddings 데이터 다운로드 중...", flush=True)
            download_directory_from_s3(s3_embeddings_prefix, local_embeddings_dir)
        else:
            local_embeddings_dir = embeddings_dir
        
        # Upsert 실행 (PostgreSQL에 저장)
        print(f"[Lambda][Protocols][Upsert] PostgreSQL 업서트 시작...", flush=True)
        # embeddings_dir을 절대 경로로 전달
        upsert_run(embeddings_dir=str(Path(local_embeddings_dir).resolve()))
        print(f"[Lambda][Protocols][Upsert] PostgreSQL 업서트 완료", flush=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "statusCode": 200,
            "body": {
                "message": "Successfully completed upsert to PostgreSQL",
                "duration_seconds": duration
            }
        }
    except Exception as e:
        print(f"[Lambda][Protocols][Upsert] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e)}
        }

