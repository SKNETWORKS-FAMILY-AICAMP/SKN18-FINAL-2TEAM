"""
파일 처리 모듈 (file_handler.py)
================================
이 모듈은 파일을 읽고 쓰는 기능을 제공합니다.
JSON 파일 읽기, CSV 파일 쓰기 등을 처리합니다.

사용 방법:
    from file_handler import load_json_file, save_chunks_to_csv, save_metadata_to_csv
    
    data = load_json_file("input.json")
    save_chunks_to_csv(chunks, "output_chunks.csv")
"""

import json
import csv
import re
import os
import sys
from pathlib import Path

# common/nih_config import
current_dir = Path(__file__).resolve().parent
common_dir = current_dir.parent.parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

try:
    from nih_config import (
        CHUNK_SEPARATOR, NO_DATA_MARKER, CSV_ENCODING,
        CHUNK_OUTPUT_FILE, METADATA_OUTPUT_FILE
    )
except ImportError:
    # 기본값 사용
    CHUNK_SEPARATOR = " ||| "
    NO_DATA_MARKER = "No Data"
    CSV_ENCODING = "utf-8-sig"
    CHUNK_OUTPUT_FILE = "chunked_for_embedding.csv"
    METADATA_OUTPUT_FILE = "chunked_metadata.csv"


def load_json_file(file_path):
    """
    JSON 파일을 읽어서 Python 딕셔너리로 반환합니다.
    
    Args:
        file_path (str): 읽을 JSON 파일의 경로
        
    Returns:
        dict: JSON 파일 내용
        
    Raises:
        FileNotFoundError: 파일을 찾을 수 없을 때
        json.JSONDecodeError: JSON 형식이 잘못되었을 때
        
    예시:
        >>> data = load_json_file("data.json")
        >>> studies = data.get("studies", [])
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    # JSON 파일 읽기 시도
    try:
        with open(file_path, "r", encoding="utf-8", errors='replace') as f:
            # 파일 크기가 크면 스트리밍 방식으로 읽기 시도
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError as e:
                # 오류 발생 위치 주변 텍스트 출력
                print(f"JSON 파싱 오류 상세 정보:")
                print(f"  위치: line {e.lineno}, column {e.colno}")
                print(f"  메시지: {e.msg}")
                
                # 오류 위치 주변 라인 읽기
                f.seek(0)
                lines = f.readlines()
                if e.lineno <= len(lines):
                    start = max(0, e.lineno - 3)
                    end = min(len(lines), e.lineno + 2)
                    print(f"\n오류 위치 주변 (line {start+1}-{end}):")
                    for i in range(start, end):
                        marker = ">>> " if i == e.lineno - 1 else "    "
                        print(f"{marker}{i+1}: {lines[i][:200].rstrip()}")
                
                raise
    except UnicodeDecodeError as e:
        # 인코딩 오류 시 다른 인코딩 시도
        print(f"인코딩 오류 발생, 다른 인코딩 시도 중...")
        try:
            with open(file_path, "r", encoding="utf-8-sig", errors='replace') as f:
                data = json.load(f)
                return data
        except Exception:
            raise e


def extract_studies_from_json(data):
    """
    JSON 데이터에서 studies 배열을 추출합니다.
    
    Args:
        data (dict): JSON 파일에서 읽은 데이터
        
    Returns:
        list: study 객체들의 리스트
        
    예시:
        >>> data = {"studies": [...]}
        >>> studies = extract_studies_from_json(data)
        >>> len(studies)
        10
    """
    # studies 배열이 있으면 사용
    studies = data.get("studies", [])
    
    if not studies:
        # studies가 없으면 단일 study로 처리
        if "protocolSection" in data:
            studies = [data]
        else:
            raise ValueError("JSON 파일에 studies 또는 protocolSection을 찾을 수 없습니다.")
    
    return studies


def get_value_or_no_data(value):
    """
    값이 비어있으면 "No Data"로 표시, 있으면 그대로 반환합니다.
    
    Args:
        value: 체크할 값 (문자열, 리스트 등)
        
    Returns:
        str: 값이 있으면 원래 값(문자열), 없으면 "No Data"
        
    예시:
        >>> get_value_or_no_data("Hello")
        'Hello'
        >>> get_value_or_no_data("")
        'No Data'
        >>> get_value_or_no_data([])
        'No Data'
    """
    if isinstance(value, list):
        if not value:
            return NO_DATA_MARKER
        return CHUNK_SEPARATOR.join(str(v) for v in value if v)
    
    value_str = str(value).strip() if value else ''
    return NO_DATA_MARKER if not value_str else value_str


def parse_chunk_text_to_sentences(chunk_text):
    """
    청크 텍스트를 문장 단위로 분리하여 JSON 배열 형식으로 변환합니다.
    
    Args:
        chunk_text (str): 청크 텍스트
        
    Returns:
        str: JSON 배열 형식의 문자열 (문장들의 배열)
        
    예시:
        >>> parse_chunk_text_to_sentences("문장1. 문장2. 문장3.")
        '["문장1.", "문장2.", "문장3."]'
    """
    if not chunk_text or not chunk_text.strip():
        return "[]"
    
    import sys
    from pathlib import Path
    
    # common 디렉토리 경로 추가 (nltk_setup용)
    current_dir = Path(__file__).resolve().parent
    common_dir = current_dir.parent.parent.parent / "common"
    if str(common_dir) not in sys.path:
        sys.path.insert(0, str(common_dir))
    
    try:
        from nltk_setup import split_sentences
    except ImportError:
        # nltk_setup이 없으면 기본 구현 사용
        def split_sentences(text):
            """문장 분리 (간단한 구현)"""
            if not text:
                return []
            import re
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]
    
    # 문장 단위로 분리
    sentences = split_sentences(chunk_text.strip())
    
    # 빈 문장 제거 및 정리
    clean_sentences = [s.strip() for s in sentences if s.strip()]
    
    # JSON 배열 형식으로 변환
    return json.dumps(clean_sentences, ensure_ascii=False)


def save_chunks_to_csv(all_chunks, output_file=None):
    """
    청크 데이터를 CSV 파일로 저장합니다.
    청크는 문장 단위로 분리되어 JSON 배열 형식으로 저장됩니다.
    
    생성되는 파일 형식:
    - nctid: 연구 ID
    - chunk_id: 청크 고유 번호 (chi_1, chi_2, ...)
    - chunk: JSON 배열 형식의 문장들 (자연스러운 문장 형태)
    
    Args:
        all_chunks (list): 청크 데이터 리스트
        output_file (str, optional): 출력 파일명. 기본값: config.CHUNK_OUTPUT_FILE
        
    예시:
        >>> chunks = [{"chunk_id": "chi_1", "nctId": "NCT123", "chunk_text": "문장1. 문장2."}]
        >>> save_chunks_to_csv(chunks, "output.csv")
    """
    if output_file is None:
        output_file = CHUNK_OUTPUT_FILE
    
    chunk_fields = ['nctid', 'chunk_id', 'chunk']
    
    with open(output_file, 'w', newline='', encoding=CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=chunk_fields, extrasaction='ignore')
        writer.writeheader()
        
        for chunk_data in all_chunks:
            nct_id = chunk_data.get('nctId', '').strip()
            chunk_text = chunk_data.get('chunk_text', '').strip()
            
            # 청크 텍스트를 문장 단위 JSON 배열로 변환
            chunk_json = parse_chunk_text_to_sentences(chunk_text)
            
            row = {
                'nctid': get_value_or_no_data(nct_id),
                'chunk_id': get_value_or_no_data(chunk_data.get('chunk_id', '')),
                'chunk': chunk_json
            }
            writer.writerow(row)
    
    print(f"✓ 핵심 청킹 CSV 생성 완료: {output_file}")
    print(f"  - 3개 컬럼: nctid, chunk_id (chi_형식), chunk (JSON 배열 형식, 문장 단위)")


def save_metadata_to_csv(all_chunks, output_file=None):
    """
    메타데이터를 CSV 파일로 저장합니다.
    같은 study의 메타데이터는 한 번만 저장합니다 (중복 제거).
    
    Args:
        all_chunks (list): 청크 데이터 리스트 (각 청크에 metadata 포함)
        output_file (str, optional): 출력 파일명. 기본값: config.METADATA_OUTPUT_FILE
        
    예시:
        >>> chunks = [{"metadata": {...}}]
        >>> save_metadata_to_csv(chunks, "metadata.csv")
    """
    if output_file is None:
        output_file = METADATA_OUTPUT_FILE
    
    metadata_fields = [
        'nctId', 'officialTitle', 'briefSummary', 'conditions', 'keywords',
        'interventions', 'studyType', 'phases', 'primaryPurpose', 'overallStatus',
        'enrollmentCount', 'startDate', 'completionDate', 'leadSponsor',
        'country', 'armLabel'
    ]
    
    # study 단위로 메타데이터 수집 (중복 제거)
    seen_studies = {}
    
    for chunk in all_chunks:
        metadata = chunk.get('metadata', {})
        study_id = metadata.get('nctId', '')
        if study_id and study_id not in seen_studies:
            seen_studies[study_id] = metadata
    
    with open(output_file, 'w', newline='', encoding=CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=metadata_fields, extrasaction='ignore')
        writer.writeheader()
        
        for study_id, metadata in seen_studies.items():
            row = {
                'nctId': get_value_or_no_data(metadata.get('nctId', '')),
                'officialTitle': get_value_or_no_data(metadata.get('officialTitle', '')),
                'briefSummary': get_value_or_no_data(metadata.get('briefSummary', '')),
                'conditions': get_value_or_no_data(metadata.get('conditions', [])),
                'keywords': get_value_or_no_data(metadata.get('keywords', [])),
                'interventions': get_value_or_no_data(metadata.get('interventions', [])),
                'studyType': get_value_or_no_data(metadata.get('studyType', '')),
                'phases': get_value_or_no_data(metadata.get('phases', [])),
                'primaryPurpose': get_value_or_no_data(metadata.get('primaryPurpose', '')),
                'overallStatus': get_value_or_no_data(metadata.get('overallStatus', '')),
                'enrollmentCount': get_value_or_no_data(metadata.get('enrollmentCount', '')),
                'startDate': get_value_or_no_data(metadata.get('startDate', '')),
                'completionDate': get_value_or_no_data(metadata.get('completionDate', '')),
                'leadSponsor': get_value_or_no_data(metadata.get('leadSponsor', '')),
                'country': get_value_or_no_data(metadata.get('country', '')),
                'armLabel': get_value_or_no_data(metadata.get('armLabel', ''))
            }
            writer.writerow(row)
    
    print(f"✓ 메타데이터 CSV 생성 완료: {output_file}")
    print(f"  - 16개 컬럼, study 단위 중복 제거")





