"""
임베딩 유틸리티 함수
"""

from typing import List, Union
import numpy as np


def get_embedding(text: Union[str, List[str]], model=None) -> Union[List[float], List[List[float]]]:
    """
    텍스트를 임베딩 벡터로 변환
    
    Args:
        text: 변환할 텍스트 또는 텍스트 리스트
        model: 임베딩 모델 (None이면 기본 모델 사용)
        
    Returns:
        임베딩 벡터 또는 벡터 리스트
    """
    # TODO: 실제 임베딩 모델 구현
    # 예: sentence-transformers, OpenAI API 등
    pass


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    두 벡터 간의 코사인 유사도 계산
    
    Args:
        vec1: 첫 번째 벡터
        vec2: 두 번째 벡터
        
    Returns:
        코사인 유사도 값 (0~1)
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))

