"""
Protocols.io Embedding Lambda Handler
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

# embed_protocols 모듈 import
embed_module = importlib.import_module("rag.etl.step05_embed.embed_protocols")
embed_main = embed_module.main
embed_run = embed_module.run

from s3_utils import (
    is_lambda_environment,
    ensure_local_path,
    download_directory_from_s3,
    upload_directory_to_s3
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - Protocols Embedding
    
    이벤트 형식:
    {
        "processed_dir": "data/processed",           # 선택: 기본값 "data/processed"
        "chunks_dir": "data/chunks",                # 선택: 기본값 "data/chunks" (분할된 청크 파일)
        "embeddings_dir": "data/embeddings",        # 선택: 기본값 "data/embeddings"
        "s3_processed_prefix": "data/processed/protocols",      # 선택: S3 processed 데이터 접두사
        "s3_chunks_prefix": "data/chunks/protocols",            # 선택: S3 chunks 데이터 접두사
        "s3_embeddings_prefix": "data/embeddings/protocols",     # 선택: S3 embeddings 데이터 접두사
        "chunk_file": "data/chunks/protocols/20251226_0611/Protein/protocol_chunked_Protein_part001.csv",  # Step Functions에서 전달: 특정 파일만 처리
        "keyword": "Protein",                        # Step Functions에서 전달: 키워드
        "date_time": "20251226_0611"                 # Step Functions에서 전달: 날짜_시분
    }
    
    Step Functions에서 호출될 때는 chunk_file, keyword, date_time이 전달되어 특정 파일만 처리합니다.
    """
    processed_dir = event.get("processed_dir", "data/processed")
    chunks_dir = event.get("chunks_dir", "data/chunks")
    embeddings_dir = event.get("embeddings_dir", "data/embeddings")
    s3_processed_prefix = event.get("s3_processed_prefix", f"{processed_dir}/protocols")
    s3_chunks_prefix = event.get("s3_chunks_prefix", f"{chunks_dir}/protocols")
    s3_embeddings_prefix = event.get("s3_embeddings_prefix", f"{embeddings_dir}/protocols")
    
    # Step Functions에서 특정 파일만 처리하는 경우
    chunk_file = event.get("chunk_file")
    keyword = event.get("keyword")
    date_time = event.get("date_time")
    
    print(f"[Lambda][Protocols][Embed] Processing started", flush=True)
    start_time = datetime.now()
    
    try:
        # Step Functions에서 특정 파일만 처리하는 경우
        if chunk_file:
            # 특정 분할 파일만 처리 (전체 디렉토리 다운로드 불필요)
            from rag.etl.step05_embed.embed_protocols import process_file
            from s3_utils import get_s3_client, get_s3_bucket, download_file_from_s3
            
            if is_lambda_environment():
                local_chunks_dir = ensure_local_path(chunks_dir)
                local_embeddings_dir = ensure_local_path(embeddings_dir)
                os.makedirs(local_chunks_dir, exist_ok=True)
                os.makedirs(local_embeddings_dir, exist_ok=True)
            else:
                local_chunks_dir = chunks_dir
                local_embeddings_dir = embeddings_dir
            
            # 로컬 파일 경로 생성
            local_chunk_file = Path(local_chunks_dir) / chunk_file.replace(f"{chunks_dir}/", "")
            local_chunk_file.parent.mkdir(parents=True, exist_ok=True)
            
            # S3에서 특정 파일만 다운로드
            print(f"[Lambda][Protocols][Embed] S3에서 파일 다운로드: {chunk_file}", flush=True)
            download_file_from_s3(chunk_file, str(local_chunk_file))
            
            # 특정 파일만 처리
            print(f"[Lambda][Protocols][Embed] Embedding 시작: {local_chunk_file}", flush=True)
            process_file(local_chunk_file, embeddings_base_dir=Path(local_embeddings_dir).resolve())
            
            # 생성된 임베딩 파일을 S3에 업로드
            if is_lambda_environment():
                from s3_utils import upload_directory_to_s3
                print(f"[Lambda][Protocols][Embed] 처리된 embeddings 데이터를 S3에 업로드 중...", flush=True)
                upload_directory_to_s3(local_embeddings_dir, s3_embeddings_prefix)
        else:
            # 모든 파일 처리 (기존 방식)
            if is_lambda_environment():
                local_processed_dir = ensure_local_path(processed_dir)
                local_chunks_dir = ensure_local_path(chunks_dir)
                local_embeddings_dir = ensure_local_path(embeddings_dir)
                os.makedirs(local_processed_dir, exist_ok=True)
                os.makedirs(local_chunks_dir, exist_ok=True)
                os.makedirs(local_embeddings_dir, exist_ok=True)
                
                # S3에서 chunks 데이터 다운로드 (분할된 청크 파일 우선)
                print(f"[Lambda][Protocols][Embed] S3에서 chunks 데이터 다운로드 중...", flush=True)
                download_directory_from_s3(s3_chunks_prefix, local_chunks_dir)
                
                # S3에서 processed 데이터 다운로드 (fallback용, 분할 파일이 없을 경우)
                print(f"[Lambda][Protocols][Embed] S3에서 processed 데이터 다운로드 중...", flush=True)
                download_directory_from_s3(s3_processed_prefix, local_processed_dir)
            else:
                local_processed_dir = processed_dir
                local_chunks_dir = chunks_dir
                local_embeddings_dir = embeddings_dir
            
            # Embedding 실행
            print(f"[Lambda][Protocols][Embed] Embedding 시작...", flush=True)
            embed_main(embeddings_dir=str(Path(local_embeddings_dir).resolve()))
        
        print(f"[Lambda][Protocols][Embed] Embedding 완료", flush=True)
        
        # Lambda 환경에서 생성된 embeddings 파일을 S3에 업로드 (모든 파일 처리 모드에서만)
        if is_lambda_environment() and not chunk_file:
            print(f"[Lambda][Protocols][Embed] 처리된 embeddings 데이터를 S3에 업로드 중...", flush=True)
            upload_directory_to_s3(local_embeddings_dir, s3_embeddings_prefix)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "statusCode": 200,
            "body": {
                "message": "Successfully completed embedding",
                "duration_seconds": duration
            }
        }
    except Exception as e:
        print(f"[Lambda][Protocols][Embed] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": {"error": str(e)}
        }

