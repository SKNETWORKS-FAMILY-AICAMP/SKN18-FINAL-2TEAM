"""
S3 유틸리티 모듈
Lambda 환경에서 파일을 S3에 업로드/다운로드하는 공통 함수들
"""
import os
import boto3
from pathlib import Path
from typing import Optional, List
from botocore.exceptions import ClientError
import shutil


def is_lambda_environment() -> bool:
    """Lambda 환경인지 확인"""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def get_s3_client():
    """S3 클라이언트 생성"""
    return boto3.client('s3')


def get_s3_bucket() -> str:
    """환경 변수에서 S3 버킷 이름 가져오기"""
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        raise ValueError("S3_BUCKET_NAME 환경 변수가 설정되지 않았습니다.")
    return bucket


def get_base_path() -> Path:
    """기본 경로 반환 (Lambda면 /tmp, 아니면 프로젝트 루트)"""
    if is_lambda_environment():
        return Path("/tmp")
    else:
        # 프로젝트 루트 찾기
        current_file = Path(__file__)
        # common/ 에서 프로젝트 루트까지: 6단계 위로
        return current_file.parent.parent.parent.parent.parent.parent


def upload_file_to_s3(local_path: str, s3_key: str, bucket: Optional[str] = None) -> bool:
    """
    로컬 파일을 S3에 업로드
    
    Args:
        local_path: 로컬 파일 경로
        s3_key: S3 키 (경로)
        bucket: S3 버킷 이름 (None이면 환경 변수에서 가져옴)
    
    Returns:
        성공 여부
    """
    try:
        if not os.path.exists(local_path):
            print(f"[S3] 파일이 존재하지 않습니다: {local_path}", flush=True)
            return False
        
        s3_client = get_s3_client()
        bucket = bucket or get_s3_bucket()
        
        print(f"[S3] 업로드 중: {local_path} -> s3://{bucket}/{s3_key}", flush=True)
        s3_client.upload_file(local_path, bucket, s3_key)
        print(f"[S3] 업로드 완료: s3://{bucket}/{s3_key}", flush=True)
        return True
    except ClientError as e:
        print(f"[S3] 업로드 실패: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[S3] 업로드 중 오류 발생: {e}", flush=True)
        return False


def download_file_from_s3(s3_key: str, local_path: str, bucket: Optional[str] = None) -> bool:
    """
    S3에서 파일 다운로드
    
    Args:
        s3_key: S3 키 (경로)
        local_path: 로컬 저장 경로
        bucket: S3 버킷 이름 (None이면 환경 변수에서 가져옴)
    
    Returns:
        성공 여부
    """
    try:
        s3_client = get_s3_client()
        bucket = bucket or get_s3_bucket()
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        print(f"[S3] 다운로드 중: s3://{bucket}/{s3_key} -> {local_path}", flush=True)
        s3_client.download_file(bucket, s3_key, local_path)
        print(f"[S3] 다운로드 완료: {local_path}", flush=True)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"[S3] 파일을 찾을 수 없습니다: s3://{bucket}/{s3_key}", flush=True)
        else:
            print(f"[S3] 다운로드 실패: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[S3] 다운로드 중 오류 발생: {e}", flush=True)
        return False


def upload_directory_to_s3(local_dir: str, s3_prefix: str, bucket: Optional[str] = None) -> int:
    """
    디렉토리 전체를 S3에 업로드
    
    Args:
        local_dir: 로컬 디렉토리 경로
        s3_prefix: S3 접두사 (경로)
        bucket: S3 버킷 이름
    
    Returns:
        업로드된 파일 수
    """
    uploaded_count = 0
    local_path = Path(local_dir)
    
    if not local_path.exists():
        print(f"[S3] 디렉토리가 존재하지 않습니다: {local_dir}", flush=True)
        return 0
    
    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")
            
            if upload_file_to_s3(str(file_path), s3_key, bucket):
                uploaded_count += 1
    
    print(f"[S3] 총 {uploaded_count}개 파일 업로드 완료", flush=True)
    return uploaded_count


def list_s3_files(s3_prefix: str, bucket: Optional[str] = None) -> List[str]:
    """
    S3 접두사로 시작하는 모든 파일의 키 목록을 반환 (다운로드하지 않음)
    
    Args:
        s3_prefix: S3 접두사 (경로)
        bucket: S3 버킷 이름
    
    Returns:
        S3 키 리스트
    """
    try:
        s3_client = get_s3_client()
        bucket = bucket or get_s3_bucket()
        
        file_keys = []
        paginator = s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=bucket, Prefix=s3_prefix):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                s3_key = obj['Key']
                # 디렉토리가 아닌 파일만 추가
                if not s3_key.endswith('/'):
                    file_keys.append(s3_key)
        
        print(f"[S3] 총 {len(file_keys)}개 파일 목록 조회 완료", flush=True)
        return file_keys
    except Exception as e:
        print(f"[S3] 파일 목록 조회 중 오류 발생: {e}", flush=True)
        return []


def download_directory_from_s3(s3_prefix: str, local_dir: str, bucket: Optional[str] = None) -> int:
    """
    S3 접두사로 시작하는 모든 파일을 다운로드
    (기존 함수 유지 - 호환성)
    
    Args:
        s3_prefix: S3 접두사 (경로)
        local_dir: 로컬 저장 디렉토리
        bucket: S3 버킷 이름
    
    Returns:
        다운로드된 파일 수
    """
    try:
        s3_client = get_s3_client()
        bucket = bucket or get_s3_bucket()
        
        downloaded_count = 0
        paginator = s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=bucket, Prefix=s3_prefix):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                s3_key = obj['Key']
                # 접두사 제거하고 로컬 경로 생성
                relative_path = s3_key[len(s3_prefix):].lstrip('/')
                local_path = os.path.join(local_dir, relative_path)
                
                if download_file_from_s3(s3_key, local_path, bucket):
                    downloaded_count += 1
        
        print(f"[S3] 총 {downloaded_count}개 파일 다운로드 완료", flush=True)
        return downloaded_count
    except Exception as e:
        print(f"[S3] 디렉토리 다운로드 중 오류 발생: {e}", flush=True)
        return 0


def sync_to_s3_after_processing(local_path: str, s3_key: str, bucket: Optional[str] = None) -> bool:
    """
    처리 후 파일을 S3에 동기화 (Lambda 환경에서만)
    
    Args:
        local_path: 로컬 파일 경로
        s3_key: S3 키
        bucket: S3 버킷 이름
    
    Returns:
        성공 여부
    """
    if not is_lambda_environment():
        print(f"[S3] 로컬 환경이므로 S3 업로드를 건너뜁니다.", flush=True)
        return True
    
    return upload_file_to_s3(local_path, s3_key, bucket)


def ensure_local_path(path: str) -> str:
    """
    로컬 경로를 보장 (Lambda면 /tmp 사용)
    
    Args:
        path: 상대 경로 (예: "data/raw/protocols")
    
    Returns:
        절대 경로
    """
    if is_lambda_environment():
        return str(Path("/tmp") / path)
    else:
        base = get_base_path()
        return str(base / path)


def cleanup_tmp_directory(path: str = "/tmp/data") -> None:
    """
    Lambda 환경에서 /tmp 디렉토리 정리
    
    Args:
        path: 정리할 경로 (기본값: /tmp/data)
    """
    if not is_lambda_environment():
        return
    
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"[S3] /tmp 디렉토리 정리 완료: {path}", flush=True)
    except Exception as e:
        print(f"[S3] /tmp 디렉토리 정리 중 오류: {e}", flush=True)

