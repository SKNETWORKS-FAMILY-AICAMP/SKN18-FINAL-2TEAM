"""
NIH 청킹 모듈 패키지
"""

# chunker 모듈에서 함수 import
from .chunker import create_chunks_with_overlap

# file_handler 모듈에서 함수 import
from .file_handler import (
    load_json_file,
    save_chunks_to_csv,
    save_metadata_to_csv
)

# common/nih_config 사용 (공통 설정)
import sys
import os
from pathlib import Path

# common 디렉토리 경로 추가
current_dir = Path(__file__).resolve().parent
common_dir = current_dir.parent.parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

try:
    from nih_config import (
        CHUNK_SIZE_MIN,
        CHUNK_SIZE_MAX,
        OVERLAP_MIN,
        OVERLAP_MAX,
        CHUNK_OUTPUT_FILE,
        METADATA_OUTPUT_FILE,
        OUTPUT_FORMAT,
        CSV_ENCODING,
        CHUNK_SEPARATOR,
        NO_DATA_MARKER
    )
except ImportError:
    # config가 없으면 기본값 사용
    CHUNK_SIZE_MIN = 600
    CHUNK_SIZE_MAX = 600
    OVERLAP_MIN = 120
    OVERLAP_MAX = 120
    CHUNK_OUTPUT_FILE = "chunk.csv"
    METADATA_OUTPUT_FILE = "metadata.csv"
    OUTPUT_FORMAT = "csv"
    CSV_ENCODING = "utf-8-sig"
    CHUNK_SEPARATOR = " ||| "
    NO_DATA_MARKER = "No Data"

# token_counter는 step02_normalize에서 가져오거나 기본 구현 사용
try:
    # step02_normalize의 modules/nih 경로 추가
    step02_dir = current_dir.parent.parent.parent / "step02_normalize" / "modules"
    if str(step02_dir) not in sys.path:
        sys.path.insert(0, str(step02_dir))
    from nih.token_counter import init_tokenizer, count_tokens
except ImportError:
    # token_counter가 없으면 간단한 구현 사용
    def init_tokenizer():
        """토크나이저 초기화 (간단한 구현)"""
        pass
    
    def count_tokens(text):
        """토큰 수 계산 (간단한 근사치)"""
        # 평균적으로 1 토큰 ≈ 4 문자
        return len(text) // 4 if text else 0

__all__ = [
    # chunker
    'create_chunks_with_overlap',
    # file_handler
    'load_json_file',
    'save_chunks_to_csv',
    'save_metadata_to_csv',
    # config
    'CHUNK_SIZE_MIN',
    'CHUNK_SIZE_MAX',
    'OVERLAP_MIN',
    'OVERLAP_MAX',
    'CHUNK_OUTPUT_FILE',
    'METADATA_OUTPUT_FILE',
    'OUTPUT_FORMAT',
    'CSV_ENCODING',
    'CHUNK_SEPARATOR',
    'NO_DATA_MARKER',
    # token_counter
    'init_tokenizer',
    'count_tokens',
]
