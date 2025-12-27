"""
Protocols.io 분할 청크 파일 목록 조회 Lambda Handler
S3에서 분할된 청크 파일 목록을 조회하여 Step Functions에 전달
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

common_path = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(common_path))

from s3_utils import (
    is_lambda_environment,
    get_s3_client,
    get_s3_bucket
)


def lambda_handler(event, context):
    """
    AWS Lambda 핸들러 - Protocols 분할 청크 파일 목록 조회
    
    이벤트 형식:
    {
        "chunks_dir": "data/chunks",                # 선택: 기본값 "data/chunks"
        "keyword": "Protein",                       # 선택: 특정 키워드만 조회 (None이면 모든 키워드)
        "date_time_dir": "20251226_0611"            # 선택: 특정 날짜_시분 디렉토리만 조회
    }
    
    반환 형식:
    {
        "files": [
            {
                "s3_key": "data/chunks/protocols/20251226_0611/Protein/protocol_chunked_Protein_part001.csv",
                "keyword": "Protein",
                "date_time": "20251226_0611",
                "file_name": "protocol_chunked_Protein_part001.csv"
            },
            ...
        ]
    }
    """
    chunks_dir = event.get("chunks_dir", "data/chunks")
    keyword = event.get("keyword")  # None이면 모든 키워드
    date_time_dir = event.get("date_time_dir")  # None이면 모든 날짜_시분 디렉토리
    
    print(f"[Lambda][Protocols][ChunkFileList] Processing started", flush=True)
    print(f"[Lambda][Protocols][ChunkFileList] chunks_dir: {chunks_dir}, keyword: {keyword}, date_time_dir: {date_time_dir}", flush=True)
    
    try:
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket()
        
        # S3 경로: data/chunks/protocols/
        s3_prefix = f"{chunks_dir}/protocols/"
        
        files = []
        
        # 날짜_시분 디렉토리 목록 조회
        if date_time_dir:
            # 특정 날짜_시분 디렉토리만 조회
            date_time_prefixes = [f"{s3_prefix}{date_time_dir}/"]
        else:
            # 모든 날짜_시분 디렉토리 조회
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=s3_prefix,
                Delimiter="/"
            )
            date_time_prefixes = []
            if "CommonPrefixes" in response:
                for prefix_info in response["CommonPrefixes"]:
                    prefix = prefix_info["Prefix"]
                    # 날짜_시분 디렉토리 형식 확인 (예: 20251226_0611/)
                    dir_name = prefix.replace(s3_prefix, "").rstrip("/")
                    if "_" in dir_name and len(dir_name) == 13:  # YYYYMMDD_HHMM 형식
                        date_time_prefixes.append(prefix)
        
        print(f"[Lambda][Protocols][ChunkFileList] 발견된 날짜_시분 디렉토리: {len(date_time_prefixes)}개", flush=True)
        
        # 각 날짜_시분 디렉토리에서 키워드별 파일 조회
        for date_time_prefix in date_time_prefixes:
            date_time = date_time_prefix.replace(s3_prefix, "").rstrip("/")
            
            # 키워드 디렉토리 목록 조회
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=date_time_prefix,
                Delimiter="/"
            )
            
            keyword_prefixes = []
            if "CommonPrefixes" in response:
                for prefix_info in response["CommonPrefixes"]:
                    keyword_prefix = prefix_info["Prefix"]
                    keyword_name = keyword_prefix.replace(date_time_prefix, "").rstrip("/")
                    
                    # 특정 키워드만 필터링
                    if keyword and keyword_name != keyword:
                        continue
                    
                    keyword_prefixes.append((keyword_name, keyword_prefix))
            
            # 각 키워드 디렉토리에서 분할 파일 조회
            for keyword_name, keyword_prefix in keyword_prefixes:
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=keyword_prefix,
                    Delimiter="/"
                )
                
                if "Contents" in response:
                    for obj in response["Contents"]:
                        s3_key = obj["Key"]
                        file_name = Path(s3_key).name
                        
                        # 분할 파일만 필터링 (protocol_chunked_*_part*.csv)
                        if "protocol_chunked_" in file_name and "_part" in file_name and file_name.endswith(".csv"):
                            files.append({
                                "s3_key": s3_key,
                                "keyword": keyword_name,
                                "date_time": date_time,
                                "file_name": file_name
                            })
        
        # 파일명으로 정렬
        files.sort(key=lambda x: x["file_name"])
        
        print(f"[Lambda][Protocols][ChunkFileList] 발견된 분할 파일: {len(files)}개", flush=True)
        
        # Step Functions에서 사용할 수 있도록 files만 반환
        return {
            "files": files
        }
        
    except Exception as e:
        print(f"[Lambda][Protocols][ChunkFileList] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Step Functions에서 오류 처리할 수 있도록 빈 files 반환
        return {
            "files": [],
            "error": str(e)
        }

