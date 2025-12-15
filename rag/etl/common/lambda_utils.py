"""
Lambda 환경 유틸리티 모듈
로컬과 Lambda 환경 모두에서 동작하도록 경로를 처리하는 공통 함수들
"""
import os
from pathlib import Path


def is_lambda_environment() -> bool:
    """Lambda 환경인지 확인"""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def ensure_lambda_path(path: str | Path) -> Path:
    """
    경로를 Lambda 환경에 맞게 조정
    
    Args:
        path: 상대 경로 (예: "data/raw/protocols")
    
    Returns:
        Lambda 환경이면 /tmp를 기준으로, 아니면 프로젝트 루트를 기준으로 절대 경로 반환
    """
    path_str = str(path)
    
    # 이미 절대 경로면 그대로 반환
    if os.path.isabs(path_str):
        return Path(path_str)
    
    # Lambda 환경이면 /tmp 사용
    if is_lambda_environment():
        return Path("/tmp") / path_str
    
    # 로컬 환경이면 프로젝트 루트 기준
    # 현재 파일 위치에서 프로젝트 루트 찾기
    current_file = Path(__file__).resolve()
    # common/ 에서 프로젝트 루트까지: 3단계 위로
    project_root = current_file.parent.parent.parent.parent
    return project_root / path_str


def get_project_root() -> Path:
    """
    프로젝트 루트 디렉토리를 반환
    
    Returns:
        Lambda 환경이면 /tmp, 아니면 실제 프로젝트 루트
    """
    if is_lambda_environment():
        return Path("/tmp")
    
    current_file = Path(__file__).resolve()
    # common/ 에서 프로젝트 루트까지: 3단계 위로
    return current_file.parent.parent.parent.parent

