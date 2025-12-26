"""
Protocols.io Ingest Lambda Handler - Cell keyword
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
ingest_module = importlib.import_module("rag.etl.step01_ingest.ingest_protocols")
run = ingest_module.run

from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    upload_directory_to_s3
)


def lambda_handler(event, context):
    keyword = "Cell"
    raw_dir = event.get("raw_dir", "data/raw")
    s3_prefix = event.get("s3_prefix", f"{raw_dir}/protocols")
    
    print(f"[Lambda][Protocols][{keyword}] Processing started", flush=True)
    
    try:
        if is_lambda_environment():
            local_raw_dir = ensure_local_path(raw_dir)
            os.makedirs(local_raw_dir, exist_ok=True)
            download_directory_from_s3(s3_prefix, local_raw_dir)
        else:
            local_raw_dir = raw_dir
        
        run(raw_dir=local_raw_dir, keyword=keyword)
        
        if is_lambda_environment():
            today = datetime.now().strftime("%Y%m%d")
            upload_prefix = f"{s3_prefix}/{today}"
            upload_source = Path(local_raw_dir) / "protocols" / today
            if upload_source.exists():
                upload_directory_to_s3(str(upload_source), upload_prefix)
            else:
                print(f"[Lambda][Protocols][{keyword}] 업로드할 파일이 없습니다: {upload_source}", flush=True)
        
        return {
            "statusCode": 200,
            "body": {"message": f"Successfully processed keyword: {keyword}", "keyword": keyword}
        }
    except Exception as e:
        print(f"[Lambda][Protocols][{keyword}] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e), "keyword": keyword}
        }

