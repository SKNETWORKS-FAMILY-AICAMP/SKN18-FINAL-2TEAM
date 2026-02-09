#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared chunking and helper utilities for PMC embedding pipeline.
"""
from pathlib import Path
from pathlib import Path
import os
import re
# [수정됨] Dict, Any 를 추가해야 합니다.
from typing import List, Tuple, Set, Generator, Dict, Any 
from dotenv import load_dotenv

# [NEW] pmc_processing_utils 경로 설정을 위한 sys 모듈 임포트
import sys

# [PATH FIX]
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent
utils_path = project_root / "data_preprocessing" / "pmc_etl" # <-- 사용자님의 오타 경로

if utils_path.exists():
    sys.path.insert(0, str(utils_path))
else:
    # 혹시 경로가 data_preprocessing일 경우를 대비해 루트 경로도 추가
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


# [IMPORT FIX] pmc_processing_utils에서 필요한 모든 유틸리티 함수 임포트
from rag.etl.step02_normalize.pmc_nomalize_common.pmc_processing_utils import (
    clean_content,
    extract_reference_markers,
    remove_reference_markers,
    extract_figure_table_markers, # <--- 이 함수를 찾지 못하는 것이 아래의 ImportError 원인
    # 필요하다면 다른 유틸리티도 추가
)

from rag.etl.step04_chunk.pmc_chunk_common.pmc_chunk_csv_utils import load_existing_chunk_ids
# -------------------
# Config & env
# -------------------
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIM = 1536
DEFAULT_CHUNK_SIZE = 600
DEFAULT_OVERLAP = 120
RATE_LIMIT_DELAY = float(os.getenv("EMBED_RATE_DELAY", "0.2"))
# 임베딩 시 최소 문장 개수 (예: 2문장)
MIN_SENTENCES = 2

# .env 로드
SCRIPT_DIR = Path(__file__).resolve().parent
env_path = SCRIPT_DIR / ".env"
if not env_path.exists():
    env_path = SCRIPT_DIR.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Azure OpenAI 설정 (선택사항)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")


# -------------------
# Helpers
# -------------------

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def make_chunk_id(section_id: str, seq: int) -> str:
    return f"SEC{section_id}_C{seq:02d}"

def process_section_text_for_chunking(raw_text: str) -> Dict[str, Any]:
    """
    [NEW] 섹션의 RAW 텍스트를 받아 참조 마커를 추출하고 제거하는 통합 함수.
    (chunk_generator.py의 _clean_and_extract_section 역할을 이관)
    """
    
    # 1차 공백/개행 정리
    text_clean = clean_content(raw_text) 
    
    # 1. Figure/Table 참조 추출 (제거 전에 수행)
    fig_ref_markers = extract_figure_table_markers(text_clean)
    
    # 2. Bibliography ID 추출
    ref_ids = extract_reference_markers(text_clean)
    
    # 3. 모든 참조 마커 제거 (청크 텍스트 품질 확보)
    text_no_refs = remove_reference_markers(text_clean)
    
    return {
        "clean_text": text_no_refs,
        "ref_ids": ref_ids,
        "fig_ref_markers": fig_ref_markers,
    }

def split_into_sentences(text: str) -> List[Tuple[int, int]]:
    """
    URL, 학명(E. coli), 약어 등을 보호하며 문장을 분리하는 함수.
    """
    sentences: List[Tuple[int, int]] = []
    n = len(text)
    if n == 0:
        return []

    # 분리하지 말아야 할 일반적인 약어 리스트 (소문자 기준)
    abbrevs = {
        "fig.", "figs.", "eq.", "eqs.", "al.", "vs.", 
        "i.e.", "e.g.", "etc.", "vol.", "ed.", "no.", "dr.", "prof.",
        "mr.", "mrs.", "ms.", "st.", "jr.", "spp."
    }

    start = 0
    depth = 0  # 괄호 깊이 추적
    
    # 괄호 짝 정의
    parens_open = "([{"
    parens_close = ")]}"
    
    i = 0
    while i < n:
        char = text[i]
        
        # 1. 괄호 깊이 추적
        if char in parens_open:
            depth += 1
        elif char in parens_close:
            if depth > 0:
                depth -= 1
        
        # 2. 문장 종결 후보 확인 (. ! ?)
        if char in ".!?。！？" and depth == 0:
            is_real_end = True
            
            # https://dictionary.reverso.net/korean-english/%EB%B3%B4%ED%98%B8
            if char == '.':
                if i + 1 < n:
                    next_char = text[i+1]
                    if next_char not in " \n\r\t\"')]}": 
                        is_real_end = False
            
            # [Figure/Table Reference Protection] (마침표 뒤에 대괄호 또는 소괄호가 이어지는 경우)
            if is_real_end and char == '.':
                m = re.search(r"^\s*[\"']*\s*([\[\(])", text[i+1:])
                if m:
                    is_real_end = False
            
            # [약어 예외처리 A] 
            if is_real_end and char == '.':
                word_end = i
                word_start = i - 1
                while word_start >= start and text[word_start] == ' ':
                    word_start -= 1
                curr_w_end = word_start
                while word_start >= start and text[word_start].isalnum():
                    word_start -= 1
                
                raw_prev_word = text[word_start+1 : curr_w_end+1]
                prev_word = raw_prev_word.lower() + "."
                
                # 1) 사전에 있는 약어인가?
                if prev_word in abbrevs:
                    is_real_end = False
                
                # [학명 보호] (E. coli, S. aureus)
                if is_real_end and len(raw_prev_word) == 1 and raw_prev_word.isupper():
                    next_idx = i + 1
                    while next_idx < n and text[next_idx] in " \t":
                        next_idx += 1
                    
                    if next_idx < n and text[next_idx].islower():
                        is_real_end = False

            # [숫자 예외처리 B] 소수점 
            if is_real_end and char == '.' and i + 1 < n and text[i+1].isdigit():
                is_real_end = False

            # [숫자 예외처리 C] 숫자 목록 번호
            if is_real_end and char == '.':
                back_idx = i - 1
                while back_idx >= start and text[back_idx] == ' ':
                    back_idx -= 1
                if back_idx >= start and text[back_idx].isdigit():
                    is_real_end = False

            # [확정] 진짜 문장 끝이라면
            if is_real_end:
                sentences.append((start, i + 1))
                start = i + 1
        
        i += 1

    # 남은 텍스트 처리
    if start < n:
        seg = text[start:n].strip()
        if seg:
            sentences.append((start, n))
            
    # [수정됨] 3. Post-processing: 단독으로 남겨진 괄호형 참조를 앞 문장으로 병합
    if len(sentences) > 1:
        i = 1
        while i < len(sentences):
            start_idx, end_idx = sentences[i]
            current_segment = text[start_idx:end_idx].strip()

            # 현재 문장이 공백을 건너뛰고 바로 여는 괄호/대괄호로 시작하는 경우 (참조일 확률 높음)
            # if current_segment.startswith('(') or current_segment.startswith('['): # 단순 시작 체크는 부정확함
            # 더 안전하게, 공백 건너뛰고 첫 문자가 여는 괄호인지 체크
            
            non_space_index = 0
            while non_space_index < len(current_segment) and current_segment[non_space_index].isspace():
                non_space_index += 1
            
            first_char = current_segment[non_space_index] if non_space_index < len(current_segment) else ''
            
            if first_char in '([':
                # 단독 참조로 판단되면, 앞 문장 끝 인덱스를 현재 문장 끝으로 확장하여 병합
                prev_start, _ = sentences[i-1]
                sentences[i-1] = (prev_start, end_idx) # 이전 문장의 끝을 현재 문장 끝으로 확장
                sentences.pop(i) # 현재 문장 제거 (병합 완료)
                # i는 증가시키지 않음 (다음 문장이 현재 i 자리로 이동)
                continue 

            i += 1
            
    return sentences


def sentence_chunks(
    text: str,
    max_len: int,
    overlap: int,
) -> Generator[Tuple[int, int, str], None, None]:
    """
    텍스트를 문장 단위로 끊어 청킹하는 제너레이터 함수.
    """
    text = text or ""
    n = len(text)
    if n == 0:
        return

    sents = split_into_sentences(text)
    if not sents:
        yield (0, n, text)
        return

    i = 0
    while i < len(sents):
        start_idx = sents[i][0]
        
        end_idx = sents[i][1]
        j = i + 1
        
        # [MIN_SENTENCES] 최소 문장 개수 강제 포함
        while j < len(sents) and (j - i) < MIN_SENTENCES:
            end_idx = sents[j][1] 
            j += 1
            
        while j < len(sents):
            cand_end = sents[j][1]
            if cand_end - start_idx <= max_len:
                end_idx = cand_end
                j += 1
            else:
                break

        chunk_text = text[start_idx:end_idx]
        yield (start_idx, end_idx, chunk_text)

        if j >= len(sents):
            break

        target_start_char = max(0, end_idx - overlap)
        new_i = i
        found_next = False
        for k in range(i, j):
            if sents[k][0] >= target_start_char:
                new_i = k
                found_next = True
                break
        
        if new_i <= i:
            new_i = i + 1
        i = new_i

def to_pgvector_literal(vec: List[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"