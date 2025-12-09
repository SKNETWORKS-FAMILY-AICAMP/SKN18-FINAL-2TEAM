"""
NLTK 설정 모듈 (nltk_setup.py)
==============================
이 모듈은 NLTK (Natural Language Toolkit) 라이브러리를 초기화합니다.
NLTK는 문장 분리 등의 자연어 처리 기능을 제공합니다.

사용 방법:
    from nltk_setup import setup_nltk
    
    # 프로그램 시작 시 한 번 호출
    setup_nltk()
"""

import ssl
import nltk
from nltk.tokenize import sent_tokenize


def setup_nltk():
    """
    NLTK 라이브러리를 초기화하고 필요한 데이터를 찾습니다.
    
    AWS Lambda 환경 지원:
    - 배포 패키지 내 nltk_data 확인
    - 없으면 /tmp/nltk_data에 다운로드
    """
    import os
    from pathlib import Path
    
    # AWS Lambda 환경 감지
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    
    if is_lambda:
        # 배포 패키지 내 nltk_data 확인
        possible_paths = [
            '/var/task/nltk_data',  # 배포 패키지 내 (최우선)
            os.path.join(os.getcwd(), 'nltk_data'),
        ]
        
        nltk_data_path = None
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                nltk_data_path = path
                os.environ['NLTK_DATA'] = nltk_data_path
                # NLTK 검색 경로에 명시적으로 추가
                if path not in nltk.data.path:
                    nltk.data.path.insert(0, path)
                print(f"✓ Using NLTK data from: {nltk_data_path}")
                break
        
        # 없으면 /tmp/nltk_data 사용 (최후의 수단)
        if nltk_data_path is None:
            # /tmp 공간이 부족할 수 있으므로 경고
            print("⚠️  Warning: NLTK data not found in package. Will use /tmp (may cause disk space issues)")
            nltk_data_path = '/tmp/nltk_data'
            os.environ['NLTK_DATA'] = nltk_data_path
            try:
                os.makedirs(nltk_data_path, exist_ok=True)
                # NLTK 검색 경로에 명시적으로 추가
                if nltk_data_path not in nltk.data.path:
                    nltk.data.path.insert(0, nltk_data_path)
                print(f"✓ Using /tmp/nltk_data (will download if needed)")
            except OSError as e:
                if e.errno == 28:  # No space left on device
                    print(f"❌ Error: /tmp 디스크 공간 부족. NLTK 데이터를 빌드 시 패키지에 포함해야 합니다.")
                    raise
                raise
    else:
        # 로컬 환경에서는 기본 경로 사용
        nltk_data_path = None
    
    # SSL 인증서 오류 방지 (로컬 환경에서만)
    if not is_lambda:
        try:
            _create_unverified_https_context = ssl._create_unverified_context
            ssl._create_default_https_context = _create_unverified_https_context
        except Exception:
            pass
    
    # punkt tokenizer 확인
    try:
        nltk.data.find('tokenizers/punkt')
        print("✓ NLTK punkt tokenizer 준비 완료")
    except LookupError:
        print("punkt tokenizer 다운로드 중...")
        try:
            if is_lambda and nltk_data_path:
                nltk.download('punkt', download_dir=nltk_data_path, quiet=False)
            else:
                nltk.download('punkt', quiet=False)
            print("✓ punkt tokenizer 다운로드 완료")
        except Exception as e:
            print(f"경고: punkt tokenizer 다운로드 실패: {e}")
    
    # punkt_tab tokenizer 확인
    try:
        nltk.data.find('tokenizers/punkt_tab/english')
        print("✓ NLTK punkt_tab tokenizer 준비 완료")
    except LookupError:
        try:
            print("punkt_tab tokenizer 다운로드 중...")
            if is_lambda and nltk_data_path:
                nltk.download('punkt_tab', download_dir=nltk_data_path, quiet=False)
            else:
                nltk.download('punkt_tab', quiet=False)
            print("✓ punkt_tab tokenizer 다운로드 완료")
        except Exception as e:
            print(f"경고: punkt_tab 다운로드 실패 (무시 가능): {e}")


def split_sentences(text):
    """
    텍스트를 문장 단위로 분리합니다.
    NLTK의 기본 문장 분리 기능만 사용하여 자연스러운 문장 형태를 유지합니다.
    
    Args:
        text (str): 분리할 텍스트
        
    Returns:
        list: 문장들의 리스트
        
    예시:
        >>> split_sentences("Hello. How are you? I'm fine.")
        ['Hello.', 'How are you?', "I'm fine."]
    """
    if not text:
        return []
    
    # NLTK로 기본 문장 분리 (자연스러운 문장 단위로만 분리)
    sentences = sent_tokenize(text)
    
    # 빈 문장 제거 및 앞뒤 공백 정리
    result = [s.strip() for s in sentences if s.strip()]
    
    return result
