"""
S3 유틸리티 모듈
Django 앱에서 파일을 S3에 업로드하는 공통 함수들
"""
import os
import uuid
import boto3
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from botocore.exceptions import ClientError
from django.core.files.uploadedfile import UploadedFile


def get_s3_client(region_name: Optional[str] = None):
    """
    S3 클라이언트 생성
    
    Args:
        region_name: AWS 리전 (기본값: 환경 변수에서 가져옴)
    
    Returns:
        boto3 S3 클라이언트
    """
    aws_region = region_name or os.getenv('AWS_REGION', 'ap-northeast-2')
    return boto3.client('s3', region_name=aws_region)


def get_s3_bucket() -> str:
    """
    S3 버킷 이름 가져오기
    
    Returns:
        S3 버킷 이름
    """
    return os.getenv('S3_BUCKET_NAME', 'skn18-file-uploads')


def get_s3_url(s3_key: str, bucket: Optional[str] = None, region: Optional[str] = None) -> str:
    """
    S3 URL 생성
    
    Args:
        s3_key: S3 키 (경로)
        bucket: S3 버킷 이름 (기본값: 환경 변수에서 가져옴)
        region: AWS 리전 (기본값: 환경 변수에서 가져옴)
    
    Returns:
        S3 URL (CloudFront가 설정되어 있으면 CloudFront URL, 아니면 직접 S3 URL)
    """
    s3_bucket = bucket or get_s3_bucket()
    aws_region = region or os.getenv('AWS_REGION', 'ap-northeast-2')
    
    # CloudFront URL이 설정되어 있다면 사용
    cloudfront_domain = os.getenv('CLOUDFRONT_DOMAIN')
    if cloudfront_domain:
        return f'https://{cloudfront_domain}/{s3_key}'
    
    # 직접 S3 URL
    return f'https://{s3_bucket}.s3.{aws_region}.amazonaws.com/{s3_key}'


def upload_file_to_s3(
    file: UploadedFile,
    s3_key: str,
    bucket: Optional[str] = None,
    region: Optional[str] = None,
    content_type: Optional[str] = None,
    acl: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    파일을 S3에 업로드 (스트리밍 방식, 메모리 효율적)
    
    Args:
        file: Django UploadedFile 객체
        s3_key: S3 키 (경로)
        bucket: S3 버킷 이름 (기본값: 환경 변수에서 가져옴)
        region: AWS 리전 (기본값: 환경 변수에서 가져옴)
        content_type: 파일의 Content-Type (기본값: file.content_type)
        acl: S3 ACL 설정 (기본값: None, ACL 비활성화된 버킷의 경우 버킷 정책 사용)
    
    Returns:
        (성공 여부, 에러 메시지) 튜플
        성공 시: (True, None)
        실패 시: (False, 에러 메시지)
    """
    try:
        s3_bucket = bucket or get_s3_bucket()
        aws_region = region or os.getenv('AWS_REGION', 'ap-northeast-2')
        
        # S3 클라이언트 생성
        s3_client = get_s3_client(aws_region)
        
        # 파일 포인터를 처음으로 이동
        file.seek(0)
        
        # Content-Type 설정
        file_content_type = content_type or file.content_type
        
        # ExtraArgs 구성 (ACL은 선택적)
        extra_args = {
            'ContentType': file_content_type
        }
        
        # ACL이 제공된 경우에만 추가 (ACL 비활성화된 버킷에서는 제외)
        if acl:
            extra_args['ACL'] = acl
        
        # S3에 스트리밍 업로드 (메모리 효율적)
        s3_client.upload_fileobj(
            file,
            s3_bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        
        return True, None
    except ClientError as e:
        error_msg = f'S3 업로드 실패: {str(e)}'
        return False, error_msg
    except Exception as e:
        error_msg = f'업로드 중 오류 발생: {str(e)}'
        return False, error_msg


def generate_s3_key(prefix: str, user_id: str, filename: str, use_email: bool = False, email: Optional[str] = None) -> str:
    """
    S3 키 생성 헬퍼 함수
    
    Args:
        prefix: S3 경로 접두사 (예: 'profiles', 'documents')
        user_id: 사용자 ID
        filename: 원본 파일명
        use_email: 이메일을 파일명에 사용할지 여부
        email: 사용자 이메일 (use_email=True일 때 필요)
    
    Returns:
        S3 키 (경로)
    """
    file_ext = Path(filename).suffix.lower()
    
    if use_email and email:
        # 이메일에서 @ 이전 부분만 사용하고 특수문자 제거
        email_part = email.split('@')[0].replace('.', '_').replace('+', '_')
        file_name = f'{email_part}{file_ext}'
    else:
        # 원본 파일명 사용 (특수문자 제거)
        file_name = Path(filename).stem.replace(' ', '_').replace('.', '_')
        file_name = ''.join(c for c in file_name if c.isalnum() or c in ('_', '-'))
        file_name = f'{file_name}{file_ext}'
    
    return f'{prefix}/{user_id}/{file_name}'


def generate_note_attachment_s3_key(user_id: str, original_filename: str) -> str:
    """
    노트 첨부 파일용 S3 키 생성
    형식: notes/attatchment/u/{user_id}/dt={날짜}/{uuid}_{origFilename}
    
    Args:
        user_id: 사용자 ID
        original_filename: 원본 파일명
    
    Returns:
        S3 키 (경로)
    """
    # 날짜 형식: YYYYMMDD
    date_str = datetime.now().strftime('%Y%m%d')
    
    # UUID 생성
    file_uuid = str(uuid.uuid4())
    
    # 원본 파일명에서 특수문자 제거 (경로 보안)
    safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in ('_', '-', '.'))
    
    # S3 키 생성
    s3_key = f'notes/attatchment/u/{user_id}/dt={date_str}/{file_uuid}_{safe_filename}'
    
    return s3_key

