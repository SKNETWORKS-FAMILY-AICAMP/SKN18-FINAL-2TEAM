"""
청킹 모듈 (chunker.py)
=====================
이 모듈은 긴 텍스트를 작은 조각(청크)으로 나누는 기능을 제공합니다.
의미 단위(문장 기준)로 나누며, 이전 청크와 다음 청크가 일부 겹치도록 합니다.

사용 방법:
    from chunker import create_chunks_with_overlap
    from nih_config import CHUNK_SIZE_MIN, CHUNK_SIZE_MAX, OVERLAP_MIN, OVERLAP_MAX
    
    chunks = create_chunks_with_overlap(
        text="긴 텍스트...",
        chunk_size_min=CHUNK_SIZE_MIN,
        chunk_size_max=CHUNK_SIZE_MAX,
        overlap_min=OVERLAP_MIN,
        overlap_max=OVERLAP_MAX
    )
"""

import sys
from pathlib import Path

# 상위 디렉토리를 경로에 추가
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# step02_normalize의 modules/nih 경로 추가 (token_counter용)
step02_dir = parent_dir.parent.parent / "step02_normalize" / "modules"
if str(step02_dir) not in sys.path:
    sys.path.insert(0, str(step02_dir))

# common 디렉토리 경로 추가 (nltk_setup용)
common_dir = parent_dir.parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

# nltk_setup에서 split_sentences import (common에서)
try:
    from nltk_setup import split_sentences
except ImportError:
    # nltk_setup이 없으면 기본 구현 사용
    def split_sentences(text):
        """문장 분리 (간단한 구현)"""
        if not text:
            return []
        # 간단한 문장 분리 (. ! ? 기준)
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

# token_counter는 step02_normalize에서 가져오거나 기본 구현 사용
try:
    from nih.token_counter import count_tokens
except ImportError:
    def count_tokens(text):
        """토큰 수 계산 (간단한 근사치)"""
        return len(text) // 4 if text else 0

# common/nih_config import
try:
    from nih_config import CHUNK_SIZE_MIN, CHUNK_SIZE_MAX, OVERLAP_MIN, OVERLAP_MAX
except ImportError:
    # 기본값 사용
    CHUNK_SIZE_MIN = 600
    CHUNK_SIZE_MAX = 600
    OVERLAP_MIN = 120
    OVERLAP_MAX = 120


def create_chunks_with_overlap(text, chunk_size_min=None, chunk_size_max=None, 
                                overlap_min=None, overlap_max=None):
    """
    텍스트를 의미 단위(문장 기준)로 지정된 크기의 청크로 분할합니다.
    이전 청크와 다음 청크가 일부 겹치도록 하여 문맥이 끊기지 않게 합니다.
    
    청킹이란?
    - 긴 텍스트를 작은 조각으로 나누는 작업
    - 각 조각을 "청크(chunk)"라고 부름
    - 예: 1000자 텍스트 → 300자씩 3-4개의 청크
    
    오버랩이란?
    - 이전 청크의 마지막 부분과 다음 청크의 시작 부분이 겹치는 것
    - 예: 청크1 = "1 2 3 4", 청크2 = "3 4 5 6" (3과 4가 겹침)
    - 문맥을 잃지 않기 위해 필요
    
    Args:
        text (str): 청킹할 텍스트
        chunk_size_min (int): 최소 청크 크기 (토큰 단위). 기본값: config.CHUNK_SIZE_MIN
        chunk_size_max (int): 최대 청크 크기 (토큰 단위). 기본값: config.CHUNK_SIZE_MAX
        overlap_min (int): 최소 오버랩 크기 (토큰 단위). 기본값: config.OVERLAP_MIN
        overlap_max (int): 최대 오버랩 크기 (토큰 단위). 기본값: config.OVERLAP_MAX
        
    Returns:
        list: 청크 텍스트들의 리스트
        
    예시:
        >>> chunks = create_chunks_with_overlap("긴 텍스트...", 600, 600, 120, 120)
        >>> len(chunks)
        5  # 5개의 청크로 나뉨
    """
    # 설정값이 주어지지 않으면 기본값 사용 (chunk_size=600, overlap=120)
    if chunk_size_min is None:
        chunk_size_min = CHUNK_SIZE_MIN  # 600
    if chunk_size_max is None:
        chunk_size_max = CHUNK_SIZE_MAX  # 600
    if overlap_min is None:
        overlap_min = OVERLAP_MIN  # 120
    if overlap_max is None:
        overlap_max = OVERLAP_MAX  # 120
    
    # 빈 텍스트는 빈 리스트 반환
    if not text or not text.strip():
        return []
    
    chunks = []  # 최종 결과를 담을 리스트
    sentences = split_sentences(text)  # 텍스트를 문장 단위로 분리
    
    current_chunk = []  # 현재 만들고 있는 청크의 문장들
    current_token_count = 0  # 현재 청크의 토큰 수
    
    # 각 문장을 순회하면서 청크 생성
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue  # 빈 문장은 건너뛰기
        
        # 이 문장의 토큰 수 계산
        sentence_tokens = count_tokens(sentence)
        
        # 문장이 너무 길어서 최대 크기를 초과하는 경우
        # 이 문장을 강제로 나누어서 여러 청크로 분할
        if sentence_tokens > chunk_size_max:
            # 현재 청크가 있으면 먼저 저장
            if current_chunk:
                chunk_text = ' '.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
            
            # 긴 문장을 강제로 나누기 (단어 단위로 나누되, 최대 크기를 초과하지 않도록)
            words = sentence.split()
            current_long_chunk = []
            current_long_token_count = 0
            
            for word in words:
                word_tokens = count_tokens(word)
                
                # 단어를 추가하면 최대 크기를 초과하는 경우
                if current_long_token_count + word_tokens > chunk_size_max and current_long_chunk:
                    # 현재 청크 저장
                    long_chunk_text = ' '.join(current_long_chunk).strip()
                    if long_chunk_text:
                        chunks.append(long_chunk_text)
                    
                    # 새 청크 시작 (오버랩 없이)
                    current_long_chunk = [word]
                    current_long_token_count = word_tokens
                else:
                    # 현재 청크에 단어 추가
                    current_long_chunk.append(word)
                    current_long_token_count += word_tokens
            
            # 마지막 긴 청크 처리
            if current_long_chunk:
                long_chunk_text = ' '.join(current_long_chunk).strip()
                if long_chunk_text:
                    # 최소 크기 이상이거나, 이전 청크가 없으면 추가
                    if current_long_token_count >= chunk_size_min or not chunks:
                        chunks.append(long_chunk_text)
                    elif chunks:  # 최소 크기 미만이지만 이전 청크가 있으면 마지막에 병합
                        chunks[-1] = chunks[-1] + ' ' + long_chunk_text
            
            # 긴 문장 처리 완료 후 다음 문장으로
            current_chunk = []
            current_token_count = 0
            continue
        
        # 조건: 최소 크기 이상이고, 이 문장을 추가하면 최대 크기를 초과하는 경우
        if (current_token_count >= chunk_size_min and 
            current_token_count + sentence_tokens > chunk_size_max and 
            current_chunk):
            
            # 현재 청크를 저장
            chunk_text = ' '.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
            
            # 오버랩을 위한 문장 선택 (뒤에서부터)
            overlap_tokens = 0
            overlap_sentences = []
            
            for s in reversed(current_chunk):
                s = s.strip()
                if not s:
                    continue
                s_tokens = count_tokens(s)
                
                # 최대 오버랩을 초과하지 않도록 ################################
                if overlap_tokens + s_tokens <= overlap_max:
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens
                    # 최소 오버랩 확보되면 중단 가능
                    if overlap_tokens >= overlap_min:
                        break
                else:
                    # 최대 오버랩을 초과하면 중단
                    break
            
            # 최소 오버랩 미확보 시 강제로 마지막 문장 하나라도 포함
            if overlap_tokens < overlap_min and current_chunk:
                for s in reversed(current_chunk):
                    if s in overlap_sentences:
                        continue
                    s = s.strip()
                    if not s:
                        continue
                    s_tokens = count_tokens(s)
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens
                    break
            
            # 새 청크 시작 (오버랩 문장 + 현재 문장)
            # 첫 문장은 무조건 문장으로 시작 (오버랩 문장이 있으면 그것부터, 없으면 현재 문장부터)
            current_chunk = overlap_sentences + [sentence] if overlap_sentences else [sentence]
            current_token_count = overlap_tokens + sentence_tokens if overlap_sentences else sentence_tokens
        else:
            # 현재 청크에 문장 추가
            # 첫 청크인 경우 무조건 문장으로 시작
            if not current_chunk:
                current_chunk = [sentence]
                current_token_count = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_token_count += sentence_tokens
    
    # 마지막 청크 추가
    if current_chunk:
        chunk_text = ' '.join(current_chunk).strip()
        if chunk_text:
            # 최소 크기 이상이거나, 이전 청크가 없으면 추가
            if current_token_count >= chunk_size_min or not chunks:
                chunks.append(chunk_text)
            elif chunks:  # 최소 크기 미만이지만 이전 청크가 있으면 마지막에 병합
                chunks[-1] = chunks[-1] + ' ' + chunk_text
    
    return chunks


if __name__ == "__main__":
    """
    청킹 모듈 단독 실행 시 테스트를 수행합니다.
    """
    import sys
    import os
    
    # 상위 디렉토리를 경로에 추가 (다른 모듈 import를 위해)
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    from cleansing.nltk_setup import setup_nltk, split_sentences
    from token_counter import init_tokenizer
    
    print("=" * 60)
    print("청킹 모듈 테스트")
    print("=" * 60)
    
    # 초기화
    setup_nltk()
    init_tokenizer()
    
    # 테스트 텍스트 (긴 텍스트 생성)
    test_text = """
    This is the first sentence. This is the second sentence. 
    This is the third sentence. This is the fourth sentence.
    This is the fifth sentence. This is the sixth sentence.
    This is the seventh sentence. This is the eighth sentence.
    This is the ninth sentence. This is the tenth sentence.
    This is the eleventh sentence. This is the twelfth sentence.
    This is the thirteenth sentence. This is the fourteenth sentence.
    This is the fifteenth sentence. This is the sixteenth sentence.
    This is the seventeenth sentence. This is the eighteenth sentence.
    This is the nineteenth sentence. This is the twentieth sentence.
    """
    
    print("\n청킹 테스트:")
    print(f"  원본 텍스트 길이: {len(test_text)} 문자")
    
    chunks = create_chunks_with_overlap(
        test_text,
        chunk_size_min=CHUNK_SIZE_MIN,
        chunk_size_max=CHUNK_SIZE_MAX,
        overlap_min=OVERLAP_MIN,
        overlap_max=OVERLAP_MAX
    )
    
    print(f"  생성된 청크 수: {len(chunks)}")
    for i, chunk in enumerate(chunks, 1):
        from token_counter import count_tokens
        tokens = count_tokens(chunk)
        print(f"    청크 {i}: {tokens} tokens, {len(chunk)} 문자")
        print(f"      미리보기: {chunk[:80]}...")
    
    print("\n✓ 테스트 완료")
    print("=" * 60)





