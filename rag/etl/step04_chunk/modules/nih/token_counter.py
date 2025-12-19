"""
토큰 카운터 모듈 (token_counter.py)
==================================
이 모듈은 텍스트를 토큰 단위로 계산하는 기능을 제공합니다.
tiktoken 라이브러리를 사용하여 정확한 토큰 수를 계산합니다.

사용 방법:
    from token_counter import init_tokenizer, count_tokens
    
    # 프로그램 시작 시 한 번 호출
    init_tokenizer()
    
    # 텍스트의 토큰 수 계산
    tokens = count_tokens("Hello, world!")
"""

import os
import sys
from pathlib import Path

# rag/etl/common 디렉토리 경로를 sys.path에 추가
current_dir = Path(__file__).resolve().parent
common_dir = current_dir.parent.parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

from config import TOKEN_ENCODING, TOKENS_PER_CHAR

# 전역 변수: 토크나이저 인스턴스
_tokenizer = None


def init_tokenizer():
    """
    토크나이저를 초기화합니다.
    
    tiktoken 라이브러리가 있으면 사용하고,
    없으면 간단한 근사치 계산 방식을 사용합니다.
    
    이 함수는 프로그램 시작 시 한 번만 호출하면 됩니다.
    """
    global _tokenizer
    
    try:
        import tiktoken
        _tokenizer = tiktoken.get_encoding(TOKEN_ENCODING)
        print("✓ tiktoken 토크나이저 초기화 완료")
    except ImportError:
        print("경고: tiktoken 라이브러리가 없습니다. 근사치 방식으로 토큰을 계산합니다.")
        print("      정확한 토큰 수를 원하면 'pip install tiktoken'을 실행하세요.")
        _tokenizer = None
    except Exception as e:
        print(f"경고: 토크나이저 초기화 실패: {e}")
        print("      근사치 방식으로 토큰을 계산합니다.")
        _tokenizer = None


def count_tokens(text):
    """
    텍스트의 토큰 수를 계산합니다.
    
    Args:
        text (str): 토큰 수를 계산할 텍스트
        
    Returns:
        int: 토큰 수
        
    예시:
        >>> count_tokens("Hello, world!")
        3  # 대략적인 값
    """
    if not text or not isinstance(text, str):
        return 0
    
    # tiktoken이 있으면 정확한 토큰 수 계산
    if _tokenizer is not None:
        try:
            return len(_tokenizer.encode(text))
        except Exception:
            # 오류 발생 시 근사치 방식으로 fallback
            pass
    
    # tiktoken이 없거나 오류 발생 시 근사치 계산
    # 평균적으로 1 토큰 ≈ 4 문자
    return len(text) // TOKENS_PER_CHAR if TOKENS_PER_CHAR > 0 else len(text) // 4

