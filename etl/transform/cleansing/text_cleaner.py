"""
텍스트 정리 모듈 (text_cleaner.py)
===================================
이 모듈은 텍스트에서 불필요한 문자를 제거하는 기능을 제공합니다.
HTML 태그, URL, 특수문자 등을 제거합니다.

사용 방법:
    from text_cleaner import clean_text
    
    cleaned = clean_text("원본 텍스트")
"""

import re
from config import REMOVE_SPECIAL_CHARS, REMOVE_URL_PATTERN


def clean_text(text):
    """
    텍스트에서 불필요한 문자를 제거합니다.
    
    제거하는 항목:
    - HTML 태그
    - URL (http://, https://)
    - 줄바꿈 문자 (\n, \r, \t 등)
    - 특수문자 ({}, [], <>, ", ', *, `, !, ?, ^, ~, ©, ®, ™, …, •, · 등)
    
    Args:
        text (str): 정리할 텍스트
        
    Returns:
        str: 정리된 텍스트
        
    예시:
        >>> clean_text("<p>Hello https://example.com</p>")
        'Hello'
        >>> clean_text("Text with {special} chars!")
        'Text with special chars'
    """
    if not text:
        return ""
    
    # 문자열로 변환
    text = str(text)
    
    # 1. HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. URL 제거
    text = re.sub(REMOVE_URL_PATTERN, '', text)
    
    # 3. 줄바꿈 문자 및 제어 문자 제거 (\n, \r, \t 등)
    # \n\n 같은 연속된 줄바꿈도 제거
    text = re.sub(r'[\n\r\t]+', ' ', text)
    
    # 4. 특수문자 제거
    text = re.sub(REMOVE_SPECIAL_CHARS, '', text)
    
    # 5. 연속된 공백을 하나로 변환
    text = re.sub(r'\s+', ' ', text)
    
    # 6. 앞뒤 공백 제거
    text = text.strip()
    
    return text


if __name__ == "__main__":
    """
    텍스트 정리 모듈 단독 실행 시 테스트를 수행합니다.
    """
    print("=" * 60)
    print("텍스트 정리 모듈 테스트")
    print("=" * 60)
    
    # 테스트 텍스트들
    test_cases = [
        "<p>Hello https://example.com</p>",
        "Text with {special} chars!",
        "Multiple\n\n\nline breaks\tand\ttabs",
        "URL: https://test.com and http://another.com",
        "Normal text without issues"
    ]
    
    print("\n텍스트 정리 테스트:")
    for original in test_cases:
        cleaned = clean_text(original)
        print(f"  원본: {original}")
        print(f"  정리: {cleaned}")
        print()
    
    print("✓ 테스트 완료")
    print("=" * 60)
