"""
설정 파일 (config.py)
====================
이 파일은 데이터 클렌징 과정에서 사용되는 모든 설정값들을 관리합니다.
설정값을 변경하면 전체 프로세스에 반영됩니다.

사용 방법:
    1. 이 파일을 열어서 원하는 설정값을 변경하세요
    2. 변경 후 저장하고 main.py를 실행하세요
"""

# ============================
# 청킹 설정 (Chunking Settings)
# ============================
# 텍스트를 나눌 때 사용하는 크기 설정

# 청크 크기 (토큰 단위) - 통일된 값: 600
# chunk_size = 600으로 고정
CHUNK_SIZE_MIN = 600
CHUNK_SIZE_MAX = 600

# 오버랩 크기 (토큰 단위) - 통일된 값: 120
# 오버랩: 이전 청크와 다음 청크가 겹치는 부분
# overlap = 120으로 고정
OVERLAP_MIN = 120
OVERLAP_MAX = 120

# ============================
# 파일명 설정 (File Name Settings)
# ============================
# 생성될 파일의 이름 설정

# 청크 파일명 (핵심 데이터가 들어갈 파일)
CHUNK_OUTPUT_FILE = "test_chunk6.csv"

# 메타데이터 파일명 (부가 정보가 들어갈 파일)
METADATA_OUTPUT_FILE = "test_metadata6.csv"

# ============================
# 데이터 구분자 설정 (Separator Settings)
# ============================
# 한 컬럼에 여러 정보가 들어갈 때 구분하는 문자

# 여러 정보를 구분하는 특수 문자
# 예: "정보1 ||| 정보2 ||| 정보3"
CHUNK_SEPARATOR = " ||| "

# 빈 데이터 표시 (데이터가 없을 때 표시되는 문구)
NO_DATA_MARKER = "No Data"

# ============================
# 청크 ID 설정 (Chunk ID Settings)
# ============================
# 각 청크에 부여되는 고유 번호 형식

# 청크 ID 접두사 (prefix)
# 예: "chi_1", "chi_2", "chi_3" ...
CHUNK_ID_PREFIX = "chi_"

# ============================
# 텍스트 클렌징 설정 (Text Cleaning Settings)
# ============================
# 불필요한 문자 제거 규칙

# 제거할 특수문자 (정규식 패턴)
# {}[]<>"'*\`!?^~©®™…•· 등의 특수문자 제거
REMOVE_SPECIAL_CHARS = r'[{}\[\]<>\"\'\\*=`!?\^~©®™…•·]'

# 제거할 URL 패턴
# http:// 또는 https://로 시작하는 모든 URL 제거
REMOVE_URL_PATTERN = r'https?://\S+'

# ============================
# 토큰 계산 설정 (Token Counting Settings)
# ============================
# 텍스트를 토큰 단위로 계산할 때 사용하는 설정

# 토큰 인코딩 방식
# tiktoken 라이브러리에서 사용하는 인코딩 이름
TOKEN_ENCODING = "cl100k_base"

# tiktoken이 없을 때 사용하는 근사치
# 평균적으로 1 토큰 ≈ 4 문자로 계산
TOKENS_PER_CHAR = 4

# ============================
# 출력 형식 설정 (Output Format Settings)
# ============================
# 결과를 어떤 형식으로 저장할지 설정

# 출력 형식: "csv" 또는 "json"
OUTPUT_FORMAT = "csv"

# CSV 인코딩 (한글 깨짐 방지)
CSV_ENCODING = "utf-8-sig"


if __name__ == "__main__":
    """
    설정 파일 단독 실행 시 현재 설정값을 출력합니다.
    """
    print("=" * 60)
    print("현재 설정값")
    print("=" * 60)
    print(f"청크 크기: {CHUNK_SIZE_MIN}-{CHUNK_SIZE_MAX} tokens")
    print(f"오버랩: {OVERLAP_MIN}-{OVERLAP_MAX} tokens")
    print(f"청크 출력 파일: {CHUNK_OUTPUT_FILE}")
    print(f"메타데이터 출력 파일: {METADATA_OUTPUT_FILE}")
    print(f"구분자: '{CHUNK_SEPARATOR}'")
    print(f"빈 데이터 표시: '{NO_DATA_MARKER}'")
    print(f"출력 형식: {OUTPUT_FORMAT}")
    print(f"CSV 인코딩: {CSV_ENCODING}")
    print("=" * 60)

