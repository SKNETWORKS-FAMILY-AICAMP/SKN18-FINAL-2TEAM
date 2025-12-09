"""
Protocols.io Ingest Lambda Handler - Protein keyword
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
# trigger_etl/protocols/ 에서 프로젝트 루트까지: 5단계 위로
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# common 모듈 경로 추가
common_path = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(common_path))

from rag.etl.step01_ingest.03_ingest_protocols import run, KEYWORDS
from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    upload_directory_to_s3,
    sync_to_s3_after_processing
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - Protein 키워드 처리
    
    이벤트 형식:
    {
        "raw_dir": "data/raw",           # 선택: 기본값 "data/raw"
        "s3_prefix": "data/raw/protocols" # 선택: S3 접두사
    }
    """
    keyword = "Protein"
    raw_dir = event.get("raw_dir", "data/raw")
    s3_prefix = event.get("s3_prefix", f"{raw_dir}/protocols")
    
    print(f"[Lambda][Protocols][{keyword}] Processing started", flush=True)
    
    try:
        # Lambda 환경에서 /tmp 경로 사용
        if is_lambda_environment():
            local_raw_dir = ensure_local_path(raw_dir)
            os.makedirs(local_raw_dir, exist_ok=True)
            
            # S3에서 이전 데이터 다운로드 (있는 경우)
            print(f"[Lambda][Protocols][{keyword}] S3에서 이전 데이터 다운로드 중...", flush=True)
            download_directory_from_s3(s3_prefix, local_raw_dir)
        else:
            local_raw_dir = raw_dir
        
        # Ingest 실행
        run(raw_dir=local_raw_dir, keyword=keyword)
        
        # Lambda 환경에서 처리된 파일을 S3에 업로드
        if is_lambda_environment():
            print(f"[Lambda][Protocols][{keyword}] 처리된 데이터를 S3에 업로드 중...", flush=True)
            today = datetime.now().strftime("%Y%m%d")
            upload_prefix = f"{s3_prefix}/{today}"
            uploaded_count = upload_directory_to_s3(local_raw_dir, upload_prefix)
            print(f"[Lambda][Protocols][{keyword}] {uploaded_count}개 파일 업로드 완료", flush=True)
        
        return {
            "statusCode": 200,
            "body": {
                "message": f"Successfully processed keyword: {keyword}",
                "keyword": keyword
            }
        }
    except Exception as e:
        print(f"[Lambda][Protocols][{keyword}] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "keyword": keyword
            }
        }

