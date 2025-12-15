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
    NLTK 라이브러리를 초기화하고 필요한 데이터를 다운로드합니다.
    
    이 함수는 프로그램 시작 시 한 번만 호출하면 됩니다.
    필요한 데이터가 없으면 자동으로 다운로드합니다.
    
    AWS Lambda 환경 지원:
    - Lambda Layer에 NLTK 데이터를 포함하는 것을 권장
    - 없으면 /tmp/nltk_data에 다운로드 (Lambda는 /tmp만 쓰기 가능)
    """
    import os
    
    # AWS Lambda 환경 감지
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    
    # Lambda 환경에서는 /tmp/nltk_data 사용
    if is_lambda:
        nltk_data_path = '/tmp/nltk_data'
        os.environ['NLTK_DATA'] = nltk_data_path
        # 디렉토리가 없으면 생성
        os.makedirs(nltk_data_path, exist_ok=True)
    
    # SSL 인증서 오류 방지 (일부 환경에서 필요)
    # Lambda에서는 일반적으로 SSL이 정상 작동하므로 선택적으로만 적용
    if not is_lambda:
        try:
            _create_unverified_https_context = ssl._create_unverified_context
            ssl._create_default_https_context = _create_unverified_https_context
        except Exception:
            pass
    
    # punkt tokenizer 다운로드 (문장 분리에 필요)
    try:
        nltk.data.find('tokenizers/punkt')
        print("✓ NLTK punkt tokenizer 준비 완료")
    except LookupError:
        print("punkt tokenizer 다운로드 중...")
        try:
            # Lambda 환경에서는 /tmp에 다운로드
            if is_lambda:
                nltk.download('punkt', download_dir='/tmp/nltk_data', quiet=False)
            else:
                nltk.download('punkt', quiet=False)
            print("✓ punkt tokenizer 다운로드 완료")
        except Exception as e:
            print(f"경고: punkt tokenizer 다운로드 실패: {e}")
            if is_lambda:
                print("  Lambda Layer에 NLTK 데이터를 포함하는 것을 권장합니다.")
    
    # 영어용 punkt_tab 다운로드 (최신 NLTK 버전에서 필요)
    try:
        nltk.data.find('tokenizers/punkt_tab/english')
        print("✓ NLTK punkt_tab tokenizer 준비 완료")
    except LookupError:
        try:
            print("punkt_tab tokenizer 다운로드 중...")
            if is_lambda:
                nltk.download('punkt_tab', download_dir='/tmp/nltk_data', quiet=False)
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





