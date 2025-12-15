"""
NIH 데이터 정규화 모듈 패키지
"""

import sys
import os
from pathlib import Path

# common 디렉토리 경로 추가
current_dir = Path(__file__).resolve().parent
common_dir = current_dir.parent.parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

from nltk_setup import setup_nltk  # common에서 import
from .text_cleaner import clean_text
from .data_extractor import extract_metadata, extract_core_fields, combine_core_fields

__all__ = [
    'setup_nltk',
    'clean_text',
    'extract_metadata',
    'extract_core_fields',
    'combine_core_fields',
]

