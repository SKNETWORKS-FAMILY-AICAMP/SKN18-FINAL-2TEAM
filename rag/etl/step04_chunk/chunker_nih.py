"""
청킹만 수행하는 스크립트
=======================
클렌징된 데이터를 읽어서 청크로 분할합니다.
"""

import os
import sys
import json
import csv
import re
from datetime import datetime

# ============================================
# 설정 변수 (상단에 변수로 세팅)
# ============================================
CLEANED_DATA_PATH = None  # 클렌징된 데이터 파일 경로 (None이면 기본 경로 사용)
OUTPUT_FORMAT_OVERRIDE = None  # 출력 포맷 ('json' 또는 'csv', None이면 config의 OUTPUT_FORMAT 사용)
OUTPUT_CHUNK_FILE = None  # 청크 출력 파일명 (None이면 config.CHUNK_OUTPUT_FILE 사용)
OUTPUT_METADATA_FILE = None  # 메타데이터 출력 파일명 (None이면 config.METADATA_OUTPUT_FILE 사용)

IS_LAMBDA = False

# 환경에 따른 배치 크기 설정 (Lambda는 메모리 제한 때문에 작게)
BATCH_SIZE = 70 if IS_LAMBDA else 200  # Lambda: 50, 로컬: 200
GC_BATCH_INTERVAL = 2 if IS_LAMBDA else 5  # Lambda: 2배치마다, 로컬: 5배치마다
GC_STUDY_INTERVAL = 50 if IS_LAMBDA else 500  # Lambda: 50개마다, 로컬: 500개마다
# ============================================

# 프로젝트 루트 경로를 시스템 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# modules 디렉토리를 시스템 경로에 추가 (패키지 구조를 위해)
modules_dir = os.path.join(current_dir, "modules")
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 필요한 모듈 임포트 (명시적으로 step04_chunk의 nih 모듈 사용)
# 상대 import를 사용하여 명확하게 지정
from rag.etl.step04_chunk.modules.nih import (
    create_chunks_with_overlap,
    init_tokenizer,
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

# file_handler의 헬퍼 함수들 import
from rag.etl.step04_chunk.modules.nih.file_handler import parse_chunk_text_to_sentences, get_value_or_no_data

# 문장 분리를 위한 split_sentences import
import sys
from pathlib import Path
common_dir = Path(__file__).resolve().parent.parent.parent.parent / "common"
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


def get_project_root():
    """
    프로젝트 루트 디렉토리를 찾습니다.
    
    Lambda 환경: /tmp 반환
    로컬 환경: 실제 프로젝트 루트 반환
    
    Returns:
        str: 프로젝트 루트 디렉토리 경로
    """
    # Lambda 환경 감지
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp"
    
    current_file = os.path.abspath(__file__)
    # rag/etl/step04_chunk/02_chunker_nih.py
    # 4번 dirname을 하면 프로젝트 루트에 도달
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    return project_root


def get_output_path(base_dir, success=True, file_type="chunk"):
    """
    출력 경로를 생성합니다.
    
    형식: data/processed/nih/{success|fail}/year=YYYY/month=MM/day=DD/stage=chunked/파일명
    
    Args:
        base_dir: 프로젝트 루트 디렉토리
        success: 성공 여부 (True면 success, False면 fail)
        file_type: 파일 타입 ("chunk" 또는 "metadata")
        
    Returns:
        str: 출력 파일 경로
    """
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    
    # 서브 디렉토리: success or fail
    sub_dir = "success" if success else "fail"
    
    # 경로 구성: data/processed/nih/{success|fail}/year=YYYY/month=MM/day=DD/stage=chunked/
    output_dir = os.path.join(
        base_dir,
        "data",
        "processed",
        "nih",
        sub_dir,
        f"year={year}",
        f"month={month:02d}",
        f"day={day:02d}",
        "stage=chunked"
    )
    
    # 파일명 결정
    if file_type == "chunk":
        filename = CHUNK_OUTPUT_FILE if CHUNK_OUTPUT_FILE else "chunk.csv"
    else:  # metadata
        filename = METADATA_OUTPUT_FILE if METADATA_OUTPUT_FILE else "metadata.csv"
    
    output_file = os.path.join(output_dir, filename)
    return output_file


def initialize_csv_files(chunk_output_file, metadata_output_file):
    """
    CSV 파일을 초기화하고 헤더를 작성합니다.
    
    Args:
        chunk_output_file: 청크 CSV 파일 경로
        metadata_output_file: 메타데이터 CSV 파일 경로
        
    Returns:
        tuple: (chunk_writer, metadata_writer, chunk_file, metadata_file)
    """
    # 출력 디렉토리 생성
    os.makedirs(os.path.dirname(chunk_output_file), exist_ok=True)
    
    # 청크 CSV 파일 초기화
    chunk_file = open(chunk_output_file, 'w', newline='', encoding=CSV_ENCODING)
    chunk_fields = ['nctid', 'chunk_id', 'chunk']
    chunk_writer = csv.DictWriter(chunk_file, fieldnames=chunk_fields, extrasaction='ignore')
    chunk_writer.writeheader()
    
    # 메타데이터 CSV 파일 초기화
    metadata_file = open(metadata_output_file, 'w', newline='', encoding=CSV_ENCODING)
    metadata_fields = [
        'nctId', 'officialTitle', 'briefSummary', 'conditions', 'keywords',
        'interventions', 'studyType', 'phases', 'primaryPurpose', 'overallStatus',
        'enrollmentCount', 'startDate', 'completionDate', 'leadSponsor',
        'country', 'armLabel'
    ]
    metadata_writer = csv.DictWriter(metadata_file, fieldnames=metadata_fields, extrasaction='ignore')
    metadata_writer.writeheader()
    
    return chunk_writer, metadata_writer, chunk_file, metadata_file


def write_chunk_batch(chunk_writer, chunk_batch):
    """
    청크 배치를 CSV 파일에 씁니다.
    
    Args:
        chunk_writer: CSV writer 객체
        chunk_batch: 청크 데이터 리스트
    """
    for chunk_data in chunk_batch:
        nct_id = chunk_data.get('nctId', '').strip()
        chunk_text = chunk_data.get('chunk_text', '').strip()

        # 1) core_fields 기반 JSON 객체가 우선: main.py + assets/nih_emb/file_handler.py 포맷과 동일
        core_fields = chunk_data.get('core_fields')
        if core_fields:
            # 필드명 포함 JSON 객체로 직렬화
            chunk_obj = {k: v for k, v in core_fields.items() if v}
            chunk_json = json.dumps(chunk_obj, ensure_ascii=False)
        else:
            # 2) 호환성: core_fields가 없으면 기존처럼 문장 배열(JSON 리스트)로 저장
            chunk_json = parse_chunk_text_to_sentences(chunk_text)
        
        row = {
            'nctid': get_value_or_no_data(nct_id),
            'chunk_id': get_value_or_no_data(chunk_data.get('chunk_id', '')),
            'chunk': chunk_json,
        }
        chunk_writer.writerow(row)


def write_metadata_batch(metadata_writer, seen_studies, new_studies):
    """
    새로운 study 메타데이터를 CSV 파일에 씁니다.
    
    Args:
        metadata_writer: CSV writer 객체
        seen_studies: 이미 본 study ID 집합 (set)
        new_studies: 새로 추가할 study 메타데이터 딕셔너리 {study_id: metadata}
    """
    for study_id, metadata in new_studies.items():
        if study_id and study_id not in seen_studies:
            seen_studies.add(study_id)
            
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
            metadata_writer.writerow(row)


def run_chunking_only(cleaned_data_file, chunk_writer, metadata_writer, success=True):
    """
    청킹만 수행합니다. 클렌징된 데이터를 읽어서 청크로 분할하고 파일에 씁니다.
    
    Args:
        cleaned_data_file (str): 클렌징된 데이터 파일 경로
        chunk_writer: 청크 CSV writer 객체
        metadata_writer: 메타데이터 CSV writer 객체
        success: 성공 여부 (출력 경로 결정용)
        
    Returns:
        tuple: (총 청크 수, 총 study 수, 성공 여부)
    """
    start_time = datetime.now()
    print(f"\n{'=' * 60}")
    print(f"🚀 Chunking 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💾 배치 크기: {BATCH_SIZE}개 청크마다 파일에 저장")
    if IS_LAMBDA:
        print(f"⚙️  실행 환경: AWS Lambda (메모리 최적화 모드)")
        print(f"   - GC 빈도: {GC_BATCH_INTERVAL}배치마다, {GC_STUDY_INTERVAL}개 study마다")
    else:
        print(f"⚙️  실행 환경: 로컬 (성능 최적화 모드)")
        print(f"   - GC 빈도: {GC_BATCH_INTERVAL}배치마다, {GC_STUDY_INTERVAL}개 study마다")
    print(f"💡 환경 변수 USE_LAMBDA_MODE로 모드 설정 가능 (true/false 또는 1/0)")
    print("=" * 60)
    
    # 클렌징된 데이터 읽기
    if not os.path.exists(cleaned_data_file):
        raise FileNotFoundError(f"클렌징된 데이터 파일을 찾을 수 없습니다: {cleaned_data_file}")
    
    print(f"\n📖 클렌징 데이터 파일 읽는 중: {os.path.basename(cleaned_data_file)}")
    
    # 파일 크기 확인
    file_size = os.path.getsize(cleaned_data_file)
    if file_size > 50 * 1024 * 1024:  # 50MB
        print(f"   ⚠️  큰 파일 감지: {file_size / (1024*1024):.1f}MB - 메모리 사용량 주의")
    
    try:
        with open(cleaned_data_file, 'r', encoding='utf-8') as f:
            # 큰 파일의 경우 메모리 효율적으로 처리
            if file_size > 100 * 1024 * 1024:  # 100MB
                print(f"   📦 큰 파일 스트리밍 처리 중...")
            cleaned_data = json.load(f)
    except MemoryError:
        print(f"   ❌ 메모리 부족 오류 발생. 파일이 너무 큽니다: {file_size / (1024*1024):.1f}MB")
        raise
    
    cleaned_studies = cleaned_data.get("cleaned_studies", [])
    print(f"✓ {len(cleaned_studies)}개의 클렌징된 study를 찾았습니다.\n")

    # cleaned_data는 더 이상 필요 없으므로 메모리에서 해제
    del cleaned_data
    import gc
    gc.collect()
    
    global_chunk_counter = 0
    total_chunks = 0
    processed_studies = 0
    failed_studies = 0
    
    chunk_batch = []
    seen_studies = set()  # 메타데이터 중복 제거용
    
    # 각 클렌징된 study를 청크로 분할
    for study_idx, study in enumerate(cleaned_studies, 1):
        study_start_time = datetime.now()

        # 진행률 출력 빈도 줄이기 (성능 최적화: 10개마다 → 50개마다)
        if study_idx % 50 == 0 or study_idx == len(cleaned_studies):
            progress_pct = (study_idx * 100) // len(cleaned_studies) if len(cleaned_studies) > 0 else 0
            print(f"  진행 중: {study_idx}/{len(cleaned_studies)} ({progress_pct}%)", end='\r')

        try:
            cleaned_text = study.get("cleaned_text", "")
            combined_text = study.get("combined_text", "")
            core_fields = study.get("core_fields", {})
            metadata = study.get("metadata", {})
    
            # 필드별 개별 청킹 방식으로 변경
            # 각 필드(value)를 개별적으로 청크로 나누고, 각 청크에 해당 필드명(key)만 포함
            if not core_fields:
                # core_fields가 없으면 기존 방식(combined_text 또는 cleaned_text 전체 청킹)
                text_for_chunking = combined_text if combined_text else cleaned_text
                if not text_for_chunking or not text_for_chunking.strip():
                    continue
                
                text_chunks = create_chunks_with_overlap(
                    text_for_chunking,
                    chunk_size_min=CHUNK_SIZE_MIN,
                    chunk_size_max=CHUNK_SIZE_MAX,
                    overlap_min=OVERLAP_MIN,
                    overlap_max=OVERLAP_MAX
                )
                
                for chunk_text in text_chunks:
                    if not chunk_text or not chunk_text.strip():
                        continue
                    
                    global_chunk_counter += 1
                    chunk_id = f"chi_{global_chunk_counter}"
                    
                    chunk_data = {
                        "chunk_id": chunk_id,
                        "nctId": metadata.get('nctId', ''),
                        "chunk_text": chunk_text.strip(),
                        "metadata": metadata
                    }
                    
                    chunk_batch.append(chunk_data)
                    total_chunks += 1
                    
                    if len(chunk_batch) >= BATCH_SIZE:
                        write_chunk_batch(chunk_writer, chunk_batch)
                        new_studies = {metadata.get('nctId', ''): metadata}
                        write_metadata_batch(metadata_writer, seen_studies, new_studies)
                        chunk_batch = []
                        import gc
                        gc.collect()
                        print(f"\n      💾 {total_chunks}개 청크 저장 완료 (배치 저장)")
            else:
                # 필드별 개별 청킹: 각 필드(value)를 청크로 나누고, 각 청크에 해당 필드명(key)만 포함
                field_order = [
                    'detailedDescription',
                    'armGroups',
                    'primaryOutcomes',
                    'secondaryOutcomes',
                    'eligibilityCriteria'
                ]
                
                for field_name in field_order:
                    field_text = core_fields.get(field_name, '')
                    if not field_text or not field_text.strip():
                        continue
                    
                    # 필드별 특수 처리: 구분자로 먼저 나눈 후 각각 청킹
                    # 필드별 오버랩 설정: 독립적인 항목은 오버랩 미적용
                    USE_OVERLAP_FOR_FIELD = {
                        'detailedDescription': True,      # 오버랩 적용 (문맥 중요)
                        'armGroups': True,                # 오버랩 적용 (문맥 중요)
                        'primaryOutcomes': True,          # 오버랩 적용 (문맥 중요)
                        'secondaryOutcomes': False,        # 오버랩 미적용 (독립적인 항목)
                        'eligibilityCriteria': False,     # 오버랩 미적용 (구조화된 조건)
                    }
                    use_overlap = USE_OVERLAP_FOR_FIELD.get(field_name, True)  # 기본값: 오버랩 적용
                    
                    if field_name == 'secondaryOutcomes':
                        # secondaryOutcomes는 " ||| " 구분자로 먼저 나누기
                        parts = [p.strip() for p in field_text.split(' ||| ') if p.strip()]
                        
                        # 중복 제거: 동일한 part가 여러 번 나타나면 한 번만 청킹
                        seen_parts = set()
                        unique_parts = []
                        for part in parts:
                            if part and part not in seen_parts:
                                seen_parts.add(part)
                                unique_parts.append(part)
                        
                        field_chunks = []
                        for part in unique_parts:
                            # 오버랩 없이 청킹 (독립적인 항목이므로)
                            part_chunks = create_chunks_with_overlap(
                                part,
                                chunk_size_min=CHUNK_SIZE_MIN,
                                chunk_size_max=CHUNK_SIZE_MAX,
                                overlap_min=0,  # 오버랩 미적용
                                overlap_max=0   # 오버랩 미적용
                            )
                            field_chunks.extend(part_chunks)
                    elif field_name == 'eligibilityCriteria':
                        # eligibilityCriteria는 섹션 구분자로 먼저 나누기
                        # "Key Inclusion Criteria:", "Key Exclusion Criteria:", "Inclusion Criteria:", "Exclusion Criteria:" 모두 인식
                        # 성능 최적화: 정규식 컴파일을 한 번만 수행
                        # "Key "는 선택적으로 포함될 수 있음
                        section_pattern = re.compile(r'(?i)(Key\s+)?(Inclusion|Exclusion)\s+Criteria:', re.IGNORECASE)
                        
                        # finditer로 모든 구분자 위치 찾기
                        parts = []
                        last_end = 0
                        matches = list(section_pattern.finditer(field_text))
                        
                        if not matches:
                            # 구분자가 없으면 전체를 하나의 부분으로
                            parts.append(field_text)
                        else:
                            for match in matches:
                                # 구분자 앞의 텍스트
                                prefix = field_text[last_end:match.start()].strip()
                                
                                # 구분자 전체 (Key + Inclusion/Exclusion + Criteria:)
                                section_header = match.group(0)
                                
                                # 다음 구분자까지의 내용 (또는 끝까지)
                                next_match_start = matches[matches.index(match) + 1].start() if matches.index(match) + 1 < len(matches) else len(field_text)
                                content = field_text[match.end():next_match_start].strip()
                                
                                # 의미 없는 내용 필터링: "-", "None", "N/A", 빈 문자열, 매우 짧은 문자열(10자 미만) 등
                                # 단, 구분자만 있어도 의미가 있을 수 있으므로 최소 길이 체크
                                MIN_CONTENT_LENGTH = 10  # 구분자 제외 실제 내용 최소 길이
                                meaningless_patterns = ['-', 'none', 'n/a', 'na', 'null', 'nil', 'tbd', 'tba']
                                
                                # content가 의미 있는지 체크
                                content_is_meaningful = (
                                    len(content) >= MIN_CONTENT_LENGTH and
                                    content.lower() not in meaningless_patterns and
                                    not content.replace('-', '').replace(' ', '').replace('\n', '').replace('\t', '').strip() == ''
                                )
                                
                                # 구분자 앞의 짧은 텍스트(예: "Key")는 섹션 시작에 포함
                                if prefix and len(prefix) <= 20:
                                    # 짧은 prefix는 무시하거나 섹션 시작에 포함
                                    if content_is_meaningful:
                                        parts.append(section_header + ' ' + content)
                                elif prefix:
                                    # 긴 prefix는 별도 섹션으로 처리
                                    parts.append(prefix)
                                    if content_is_meaningful:
                                        parts.append(section_header + ' ' + content)
                                else:
                                    # prefix가 없으면 섹션만
                                    if content_is_meaningful:
                                        parts.append(section_header + ' ' + content)
                                    # content가 의미 없으면 이 섹션은 건너뜀 (구분자만 있고 내용이 없음)
                                
                                last_end = next_match_start
                            
                            # 마지막 구분자 이후의 텍스트가 있으면 추가
                            if last_end < len(field_text):
                                remaining = field_text[last_end:].strip()
                                if remaining and len(remaining) >= MIN_CONTENT_LENGTH:
                                    parts.append(remaining)
                        
                        # 각 부분을 청킹 (최적화: extend 대신 리스트 컴프리헨션)
                        field_chunks = []
                        MIN_PART_LENGTH = 20  # part 최소 길이 (구분자 포함)
                        for part in parts:
                            if part and len(part.strip()) >= MIN_PART_LENGTH:
                                # 오버랩 없이 청킹 (구조화된 조건이므로)
                                part_chunks = create_chunks_with_overlap(
                                    part,
                                    chunk_size_min=CHUNK_SIZE_MIN,
                                    chunk_size_max=CHUNK_SIZE_MAX,
                                    overlap_min=0,  # 오버랩 미적용
                                    overlap_max=0   # 오버랩 미적용
                                )
                                field_chunks.extend(part_chunks)
                    else:
                        # 다른 필드는 오버랩 설정에 따라 청킹
                        overlap_min_val = OVERLAP_MIN if use_overlap else 0
                        overlap_max_val = OVERLAP_MAX if use_overlap else 0
                        field_chunks = create_chunks_with_overlap(
                            field_text,
                            chunk_size_min=CHUNK_SIZE_MIN,
                            chunk_size_max=CHUNK_SIZE_MAX,
                            overlap_min=overlap_min_val,
                            overlap_max=overlap_max_val
                        )
                    
                    # 각 필드 청크에 대해 chunk_data 생성
                    for field_chunk_text in field_chunks:
                        # strip() 한 번만 호출 (성능 최적화)
                        field_chunk_text = field_chunk_text.strip()
                        if not field_chunk_text:
                            continue
                        
                        # JSON 직렬화 후 길이 체크 (MAX_CHUNK_CHARS 제한)
                        # 성능 최적화: JSON 직렬화 대신 텍스트 길이 + 여유분으로 근사치 계산
                        # JSON 구조: {"field_name": "text"} 형태이므로 필드명 길이 + 따옴표 등 고려
                        # 대략: 텍스트 길이 + 필드명 길이 + 20자 여유분
                        MAX_CHUNK_CHARS = 1000
                        estimated_json_len = len(field_chunk_text) + len(field_name) + 20
                        
                        # 정확한 길이 확인 (필요시에만 JSON 직렬화)
                        if estimated_json_len > MAX_CHUNK_CHARS:
                            chunk_fields_temp = {field_name: field_chunk_text}
                            chunk_json_temp = json.dumps(chunk_fields_temp, ensure_ascii=False)
                            
                            if len(chunk_json_temp) > MAX_CHUNK_CHARS:
                                # 문장 단위로 나누면서 JSON 길이 체크 및 오버랩 적용
                                sentences = split_sentences(field_chunk_text)
                                sub_chunks = []  # 서브 청크 리스트
                                current_sub_chunk_sentences = []  # 현재 서브 청크의 문장들
                                
                                def _normalize_sentence_for_join(s: str) -> str:
                                    """문장을 join하기 위해 정규화: 끝의 마침표 제거"""
                                    s = s.strip()
                                    # 문장 끝의 마침표, 느낌표, 물음표 제거 (join 시 다시 추가됨)
                                    s = s.rstrip('.!? ')
                                    return s
                                
                                def _join_sentences(sent_list: list[str]) -> str:
                                    """문장들을 자연스럽게 join (중복 마침표 방지)"""
                                    if not sent_list:
                                        return ""
                                    # 각 문장의 끝 마침표 제거 후 join
                                    normalized = [_normalize_sentence_for_join(s) for s in sent_list if s.strip()]
                                    if not normalized:
                                        return ""
                                    # '. '로 join하고 마지막에 마침표 추가
                                    result = '. '.join(normalized)
                                    # 마지막 문장이 이미 마침표로 끝나지 않으면 추가
                                    if result and not result.rstrip().endswith(('.', '!', '?')):
                                        result += '.'
                                    return result
                                
                                for sentence in sentences:
                                    sentence = sentence.strip()
                                    if not sentence:
                                        continue
                                    
                                    # 문장을 추가했을 때의 JSON 길이 확인
                                    test_sentences = current_sub_chunk_sentences + [sentence]
                                    test_chunk_text = _join_sentences(test_sentences)
                                    test_fields = {field_name: test_chunk_text}
                                    test_json = json.dumps(test_fields, ensure_ascii=False)
                                    
                                    # MAX_CHUNK_CHARS 초과 시 현재까지의 서브 청크 저장
                                    if len(test_json) > MAX_CHUNK_CHARS and current_sub_chunk_sentences:
                                        # 현재 서브 청크 저장
                                        sub_chunk_text = _join_sentences(current_sub_chunk_sentences)
                                        sub_chunks.append(sub_chunk_text)
                                        
                                        # 오버랩 적용: 마지막 몇 문장을 다음 청크에 포함
                                        # 오버랩 크기: 최소 1문장, 최대 3문장 (또는 100자 이하)
                                        overlap_sentences = []
                                        overlap_chars = 0
                                        for s in reversed(current_sub_chunk_sentences):
                                            if overlap_chars + len(s) < 100 and len(overlap_sentences) < 3:
                                                overlap_sentences.insert(0, s)
                                                overlap_chars += len(s)
                                            else:
                                                break
                                        
                                        # 새 서브 청크 시작 (오버랩 문장 + 현재 문장)
                                        current_sub_chunk_sentences = overlap_sentences + [sentence]
                                    else:
                                        # 현재 서브 청크에 문장 추가
                                        current_sub_chunk_sentences.append(sentence)
                                
                                # 마지막 서브 청크 저장
                                if current_sub_chunk_sentences:
                                    sub_chunk_text = _join_sentences(current_sub_chunk_sentences)
                                    sub_chunks.append(sub_chunk_text)
                                
                                # 각 서브 청크를 chunk_data로 생성
                                for sub_chunk_text in sub_chunks:
                                    global_chunk_counter += 1
                                    chunk_id = f"chi_{global_chunk_counter}"
                                    chunk_fields = {field_name: sub_chunk_text}
                                    
                                    chunk_data = {
                                        "chunk_id": chunk_id,
                                        "nctId": metadata.get('nctId', ''),
                                        "chunk_text": sub_chunk_text,
                                        "metadata": metadata,
                                        "core_fields": chunk_fields
                                    }
                                    chunk_batch.append(chunk_data)
                                    total_chunks += 1
                            else:
                                # 예상치가 넘었지만 실제로는 MAX_CHUNK_CHARS 이하인 경우
                                global_chunk_counter += 1
                                chunk_id = f"chi_{global_chunk_counter}"
                                chunk_fields = {field_name: field_chunk_text}
                                
                                chunk_data = {
                                    "chunk_id": chunk_id,
                                    "nctId": metadata.get('nctId', ''),
                                    "chunk_text": field_chunk_text,
                                    "metadata": metadata,
                                    "core_fields": chunk_fields
                                }
                                chunk_batch.append(chunk_data)
                                total_chunks += 1
                        else:
                            # MAX_CHUNK_CHARS 이하면 그대로 저장
                            global_chunk_counter += 1
                            chunk_id = f"chi_{global_chunk_counter}"
                            
                            # 해당 필드명(key)과 필드 청크(value)만 포함
                            chunk_fields = {field_name: field_chunk_text}
                            
                            chunk_data = {
                                "chunk_id": chunk_id,
                                "nctId": metadata.get('nctId', ''),
                                "chunk_text": field_chunk_text,
                                "metadata": metadata,
                                "core_fields": chunk_fields  # 필드명: 필드 청크만 포함
                            }
                            
                            chunk_batch.append(chunk_data)
                            total_chunks += 1
                        
                        # 배치 크기에 도달하면 파일에 쓰기
                        if len(chunk_batch) >= BATCH_SIZE:
                            write_chunk_batch(chunk_writer, chunk_batch)
                            new_studies = {metadata.get('nctId', ''): metadata}
                            write_metadata_batch(metadata_writer, seen_studies, new_studies)
                            chunk_batch = []
                            # 가비지 컬렉션 빈도: Lambda는 더 자주, 로컬은 덜 자주
                            if total_chunks % (BATCH_SIZE * GC_BATCH_INTERVAL) == 0:
                                import gc
                                gc.collect()
                            # 출력 빈도: Lambda는 더 자주, 로컬은 덜 자주
                            output_interval = 5 if IS_LAMBDA else 10
                            if total_chunks % (BATCH_SIZE * output_interval) == 0:
                                print(f"\n      💾 {total_chunks}개 청크 저장 완료 (배치 저장)")

            processed_studies += 1

            # 처리 완료된 study의 청크 데이터는 이미 파일에 저장되었으므로
            # 메모리에서 제거 (study_chunks는 로컬 변수이므로 자동 해제됨)
            # 주기적으로 가비지 컬렉션 실행 (Lambda는 더 자주, 로컬은 덜 자주)
            if processed_studies % GC_STUDY_INTERVAL == 0:
                import gc
                gc.collect()

        except Exception as e:
            print(f"\n      ⚠️  Study {study_idx} 처리 중 오류: {e}")
            failed_studies += 1
            continue
    
    # 남은 청크 배치 쓰기
    if chunk_batch:
        write_chunk_batch(chunk_writer, chunk_batch)
        # 남은 메타데이터 처리
        remaining_studies = {}
        for chunk_data in chunk_batch:
            metadata = chunk_data.get('metadata', {})
            study_id = metadata.get('nctId', '')
            if study_id:
                remaining_studies[study_id] = metadata
        write_metadata_batch(metadata_writer, seen_studies, remaining_studies)
        print(f"\n      💾 남은 {len(chunk_batch)}개 청크 저장 완료")
    
    end_time = datetime.now()
    elapsed_time = end_time - start_time
    
    print(f"\n{'─' * 60}")
    print(f"📊 청킹 처리 요약:")
    print(f"   ✓ 성공: {processed_studies}개 study")
    if failed_studies > 0:
        print(f"   ❌ 실패: {failed_studies}개 study")
    print(f"   📄 총 청크 수: {total_chunks}개")
    print(f"   📋 총 study 수: {len(seen_studies)}개")
    print(f"   ⏱️  소요 시간: {elapsed_time}")
    print(f"{'─' * 60}\n")
    
    return total_chunks, len(seen_studies), failed_studies == 0


def main():
    """
    메인 함수: 청킹만 실행합니다.
    """
    # 시작 시간 기록
    main_start_time = datetime.now()
    print("=" * 60)
    print("NIH 데이터 Chunking 시작")
    print("=" * 60)
    
    # 설정 변수 사용
    cleaned_data = CLEANED_DATA_PATH
    output_format = OUTPUT_FORMAT_OVERRIDE if OUTPUT_FORMAT_OVERRIDE else OUTPUT_FORMAT
    output_chunk = OUTPUT_CHUNK_FILE
    output_metadata = OUTPUT_METADATA_FILE
    
    # 1단계: 라이브러리 초기화
    print("\n[1단계] 라이브러리 초기화 중...")
    init_start = datetime.now()
    init_tokenizer()
    init_end = datetime.now()
    print(f"✓ 라이브러리 초기화 완료 (소요 시간: {init_end - init_start})")
    
    # 2단계: 클렌징된 데이터 파일 경로 처리
    print(f"\n[2단계] 클렌징 데이터 파일 경로 처리 중...")
    base_dir = get_project_root()
    
    if not cleaned_data:
        # 기본 경로: data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=cleaned/에서 최신 파일 찾기
        processed_dir = os.path.join(base_dir, "data", "processed", "nih", "success")
        if os.path.exists(processed_dir):
            # 최신 파일 찾기
            import glob
            pattern = os.path.join(processed_dir, "**", "stage=cleaned", "cleaned_data_*.json")
            files = glob.glob(pattern, recursive=True)
            if files:
                # 최신 파일 선택 (수정 시간 기준)
                cleaned_data_file = max(files, key=os.path.getmtime)
                print(f"   최신 클렌징 파일 자동 선택: {os.path.basename(cleaned_data_file)}")
            else:
                raise FileNotFoundError(f"클렌징된 데이터 파일을 찾을 수 없습니다: {processed_dir}")
        else:
            raise FileNotFoundError(f"처리된 데이터 디렉토리가 없습니다: {processed_dir}")
    else:
        cleaned_data_file = cleaned_data
        if not os.path.isabs(cleaned_data_file):
            if os.path.exists(cleaned_data_file):
                cleaned_data_file = os.path.abspath(cleaned_data_file)
            else:
                cleaned_data_file = os.path.join(base_dir, cleaned_data_file)
    
    print(f"   클렌징 데이터 파일: {cleaned_data_file}")
    
    # 3단계: 출력 파일 경로 생성 및 초기화
    print(f"\n[3단계] 출력 파일 초기화 중...")
    is_success = True
    
    try:
        # 출력 경로 생성
        chunk_output = get_output_path(base_dir, success=is_success, file_type="chunk") if not output_chunk or not os.path.isabs(output_chunk) else output_chunk
        metadata_output = get_output_path(base_dir, success=is_success, file_type="metadata") if not output_metadata or not os.path.isabs(output_metadata) else output_metadata
        
        print(f"   청크 파일: {chunk_output}")
        print(f"   메타데이터 파일: {metadata_output}")
        
        # CSV 파일 초기화 (헤더 작성)
        chunk_writer, metadata_writer, chunk_file, metadata_file = initialize_csv_files(chunk_output, metadata_output)
        print(f"✓ 출력 파일 초기화 완료\n")
        
        # 4단계: 청킹 실행 및 파일에 쓰기
        print(f"[4단계] 청킹 실행 및 파일 저장")
        total_chunks, total_studies, chunk_success = run_chunking_only(
            cleaned_data_file, 
            chunk_writer, 
            metadata_writer,
            success=is_success
        )
        
        # 파일 닫기
        chunk_file.close()
        metadata_file.close()
        
        # 성공 여부에 따라 최종 경로 조정
        if not chunk_success and is_success:
            # 실패한 경우 fail 폴더로 이동
            fail_chunk_output = get_output_path(base_dir, success=False, file_type="chunk")
            fail_metadata_output = get_output_path(base_dir, success=False, file_type="metadata")
            os.makedirs(os.path.dirname(fail_chunk_output), exist_ok=True)
            
            import shutil
            shutil.move(chunk_output, fail_chunk_output)
            shutil.move(metadata_output, fail_metadata_output)
            chunk_output = fail_chunk_output
            metadata_output = fail_metadata_output
            print(f"⚠️  일부 실패로 인해 fail 폴더로 이동")
        
        # 파일 크기 확인
        chunk_size_mb = os.path.getsize(chunk_output) / (1024 * 1024)
        metadata_size_mb = os.path.getsize(metadata_output) / (1024 * 1024)
        
        main_end_time = datetime.now()
        total_elapsed = main_end_time - main_start_time
        
        print(f"\n{'=' * 60}")
        print("완료!")
        print("=" * 60)
        print(f"✓ 총 {total_chunks}개의 청크가 생성되었습니다.")
        print(f"✓ 총 {total_studies}개의 study 메타데이터가 저장되었습니다.")
        print(f"✓ 생성된 파일:")
        print(f"  - {chunk_output} ({chunk_size_mb:.2f} MB)")
        print(f"  - {metadata_output} ({metadata_size_mb:.2f} MB)")
        print(f"⏱️  총 소요 시간: {total_elapsed}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 처리 중 치명적 오류 발생: {e}")
        # 파일이 열려있으면 닫기
        try:
            chunk_file.close()
            metadata_file.close()
        except:
            pass
        
        # 실패한 경우 fail 폴더에 저장 시도
        try:
            fail_chunk_output = get_output_path(base_dir, success=False, file_type="chunk")
            fail_metadata_output = get_output_path(base_dir, success=False, file_type="metadata")
            os.makedirs(os.path.dirname(fail_chunk_output), exist_ok=True)
            
            # 파일이 있으면 이동
            if os.path.exists(chunk_output):
                import shutil
                shutil.move(chunk_output, fail_chunk_output)
                shutil.move(metadata_output, fail_metadata_output)
                print(f"⚠️  fail 폴더로 이동 완료")
        except Exception as save_error:
            print(f"❌ fail 폴더 이동도 실패: {save_error}")
        raise
    
    if output_format != 'csv':
        print("⚠️  JSON 형식 저장은 현재 지원되지 않습니다. CSV 형식을 사용해주세요.")


if __name__ == "__main__":
    main()