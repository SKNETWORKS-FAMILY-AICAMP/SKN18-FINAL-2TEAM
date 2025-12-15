"""
chunk_preprocessing.py
======================
chunked_for_embedding.csv 파일의 chunk 컬럼을 embedding에 적합하도록 전처리합니다.

주요 기능:
1. EDA (Exploratory Data Analysis) - 데이터 탐색적 분석
2. 결측치 분석 (Missing Values Analysis)
3. 전처리 (JSON 파싱, 텍스트 정규화, 문장 합치기)
4. 전처리된 결과 저장

사용 방법:
    python chunk_preprocessing.py          # 전처리 실행
    python chunk_preprocessing.py eda      # EDA 실행
    python chunk_preprocessing.py missing  # 결측치 분석 실행
"""

import os
import sys
import json
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict
from statistics import mean, median, stdev

# ============================================
# 설정 변수 (상단에 변수로 세팅)
# ============================================
INPUT_FILE = os.path.join("data", "nih", "processed", "chunked", "chunked_for_embedding.csv")
OUTPUT_FILE = None  # None이면 기본 경로 사용 (preprocessed_chunked_for_embedding.csv)
MAX_TEXT_LENGTH = None  # 최대 텍스트 길이 (None이면 제한 없음, 숫자면 해당 길이로 자름)
# ============================================


def parse_chunk_json(chunk_str):
    """
    chunk 컬럼의 JSON 배열 문자열을 파싱하여 실제 리스트로 변환합니다.
    
    Args:
        chunk_str (str): JSON 배열 형태의 문자열 (예: '["문장1", "문장2"]')
        
    Returns:
        list: 파싱된 문자열 리스트
    """
    if not chunk_str or not chunk_str.strip():
        return []
    
    try:
        # JSON 파싱 시도
        parsed = json.loads(chunk_str)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, str):
            return [parsed]
        else:
            return []
    except json.JSONDecodeError:
        # JSON 파싱 실패 시, 문자열을 그대로 리스트로 반환
        return [chunk_str]


def normalize_text_for_embedding(text):
    """
    Embedding에 적합하도록 텍스트를 정규화합니다.
    
    Args:
        text (str): 정규화할 텍스트
        
    Returns:
        str: 정규화된 텍스트
    """
    if not text:
        return ""
    
    # 1. 문자열로 변환
    text = str(text)
    
    # 2. 연속된 공백을 하나로 변환
    text = re.sub(r'\s+', ' ', text)
    
    # 3. 앞뒤 공백 제거
    text = text.strip()
    
    # 4. 연속된 마침표 제거 (예: "..." -> ".")
    text = re.sub(r'\.{2,}', '.', text)
    
    # 5. 문장 끝의 연속된 공백과 마침표 정리
    text = re.sub(r'\s+\.', '.', text)
    
    return text


def combine_sentences(sentences):
    """
    여러 문장을 하나의 텍스트로 합칩니다.
    
    Args:
        sentences (list): 문장 리스트
        
    Returns:
        str: 합쳐진 텍스트
    """
    if not sentences:
        return ""
    
    # 빈 문자열 제거
    sentences = [s.strip() for s in sentences if s and s.strip()]
    
    if not sentences:
        return ""
    
    # 문장들을 공백으로 합치기
    combined = " ".join(sentences)
    
    # 정규화
    combined = normalize_text_for_embedding(combined)
    
    return combined


def truncate_text(text, max_length):
    """
    텍스트를 지정된 길이로 자릅니다.
    
    Args:
        text (str): 자를 텍스트
        max_length (int): 최대 길이
        
    Returns:
        str: 잘린 텍스트
    """
    if not max_length or len(text) <= max_length:
        return text
    
    # 단어 단위로 자르기 (마지막 단어가 잘리지 않도록)
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + "..."


def preprocess_chunk_for_embedding(chunk_str, max_length=None):
    """
    chunk 문자열을 embedding에 적합하도록 전처리합니다.
    
    Args:
        chunk_str (str): JSON 배열 형태의 chunk 문자열
        max_length (int, optional): 최대 텍스트 길이
        
    Returns:
        str: 전처리된 텍스트
    """
    # 1. JSON 파싱
    sentences = parse_chunk_json(chunk_str)
    
    # 2. 문장 합치기
    combined_text = combine_sentences(sentences)
    
    # 3. 길이 제한 (선택적)
    if max_length:
        combined_text = truncate_text(combined_text, max_length)
    
    return combined_text


def analyze_missing_values(file_path):
    """
    chunked_for_embedding.csv 파일의 결측치를 분석합니다.
    
    Args:
        file_path (str): 분석할 CSV 파일 경로
        
    Returns:
        dict: 결측치 분석 결과 딕셔너리
    """
    if not os.path.isabs(file_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, file_path)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    # 결측치 통계 수집
    total_rows = 0
    missing_nctid = 0
    missing_chunk_id = 0
    missing_chunk = 0
    empty_chunk = 0
    whitespace_only_chunk = 0
    json_parse_error = 0
    empty_after_parse = 0
    
    missing_rows = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_idx, row in enumerate(reader, 1):
            total_rows += 1
            
            nctid = row.get('nctid', '').strip()
            chunk_id = row.get('chunk_id', '').strip()
            chunk_str = row.get('chunk', '').strip()
            
            row_issues = []
            
            if not nctid:
                missing_nctid += 1
                row_issues.append('missing_nctid')
            
            if not chunk_id:
                missing_chunk_id += 1
                row_issues.append('missing_chunk_id')
            
            if not chunk_str:
                missing_chunk += 1
                row_issues.append('missing_chunk')
            else:
                if len(chunk_str) == 0:
                    empty_chunk += 1
                    row_issues.append('empty_chunk')
                elif not chunk_str.strip():
                    whitespace_only_chunk += 1
                    row_issues.append('whitespace_only_chunk')
                else:
                    try:
                        parsed = json.loads(chunk_str)
                        if isinstance(parsed, list):
                            non_empty_items = [item for item in parsed if item and str(item).strip()]
                            if not non_empty_items:
                                empty_after_parse += 1
                                row_issues.append('empty_after_parse')
                        elif isinstance(parsed, str):
                            if not parsed.strip():
                                empty_after_parse += 1
                                row_issues.append('empty_after_parse')
                        else:
                            empty_after_parse += 1
                            row_issues.append('empty_after_parse')
                    except json.JSONDecodeError:
                        json_parse_error += 1
                        row_issues.append('json_parse_error')
            
            if row_issues and len(missing_rows) < 20:
                missing_rows.append({
                    'row_number': row_idx,
                    'nctid': nctid or '(빈 값)',
                    'chunk_id': chunk_id or '(빈 값)',
                    'chunk_length': len(chunk_str),
                    'issues': row_issues
                })
    
    missing_stats = {
        'total_rows': total_rows,
        'missing_nctid': {
            'count': missing_nctid,
            'percentage': (missing_nctid / total_rows * 100) if total_rows > 0 else 0
        },
        'missing_chunk_id': {
            'count': missing_chunk_id,
            'percentage': (missing_chunk_id / total_rows * 100) if total_rows > 0 else 0
        },
        'missing_chunk': {
            'count': missing_chunk,
            'percentage': (missing_chunk / total_rows * 100) if total_rows > 0 else 0
        },
        'empty_chunk': {
            'count': empty_chunk,
            'percentage': (empty_chunk / total_rows * 100) if total_rows > 0 else 0
        },
        'whitespace_only_chunk': {
            'count': whitespace_only_chunk,
            'percentage': (whitespace_only_chunk / total_rows * 100) if total_rows > 0 else 0
        },
        'json_parse_error': {
            'count': json_parse_error,
            'percentage': (json_parse_error / total_rows * 100) if total_rows > 0 else 0
        },
        'empty_after_parse': {
            'count': empty_after_parse,
            'percentage': (empty_after_parse / total_rows * 100) if total_rows > 0 else 0
        },
        'missing_rows_sample': missing_rows
    }
    
    return missing_stats


def print_missing_values_report(file_path):
    """
    결측치 분석 리포트를 출력합니다.
    
    Args:
        file_path (str): 분석할 파일 경로
    """
    print("\n" + "=" * 80)
    print("🔍 Embedding 데이터 결측치 분석")
    print("=" * 80)
    
    try:
        stats = analyze_missing_values(file_path)
        
        print(f"\n[전체 통계]")
        print(f"  총 행 수: {stats['total_rows']:,}개")
        
        print(f"\n[결측치 통계]")
        print("-" * 80)
        
        nctid_stat = stats['missing_nctid']
        print(f"  nctid 결측치: {nctid_stat['count']:,}개 ({nctid_stat['percentage']:.2f}%)")
        
        chunk_id_stat = stats['missing_chunk_id']
        print(f"  chunk_id 결측치: {chunk_id_stat['count']:,}개 ({chunk_id_stat['percentage']:.2f}%)")
        
        chunk_stat = stats['missing_chunk']
        print(f"  chunk 결측치 (완전히 없음): {chunk_stat['count']:,}개 ({chunk_stat['percentage']:.2f}%)")
        
        empty_stat = stats['empty_chunk']
        print(f"  빈 chunk (빈 문자열): {empty_stat['count']:,}개 ({empty_stat['percentage']:.2f}%)")
        
        whitespace_stat = stats['whitespace_only_chunk']
        print(f"  공백만 있는 chunk: {whitespace_stat['count']:,}개 ({whitespace_stat['percentage']:.2f}%)")
        
        json_error_stat = stats['json_parse_error']
        print(f"  JSON 파싱 오류: {json_error_stat['count']:,}개 ({json_error_stat['percentage']:.2f}%)")
        
        empty_parse_stat = stats['empty_after_parse']
        print(f"  파싱 후 빈 내용: {empty_parse_stat['count']:,}개 ({empty_parse_stat['percentage']:.2f}%)")
        
        total_missing_issues = (
            stats['missing_nctid']['count'] +
            stats['missing_chunk_id']['count'] +
            stats['missing_chunk']['count'] +
            stats['empty_chunk']['count'] +
            stats['whitespace_only_chunk']['count'] +
            stats['empty_after_parse']['count']
        )
        print(f"\n[전체 결측치 요약]")
        print(f"  총 결측치 문제: {total_missing_issues:,}개")
        print(f"  정상 데이터: {stats['total_rows'] - total_missing_issues:,}개")
        print(f"  데이터 품질: {(1 - total_missing_issues / stats['total_rows']) * 100:.2f}%" if stats['total_rows'] > 0 else "N/A")
        
        if stats['missing_rows_sample']:
            print(f"\n[결측치 샘플 (최대 10개)]")
            print("-" * 80)
            for i, row in enumerate(stats['missing_rows_sample'][:10], 1):
                print(f"\n  샘플 {i}:")
                print(f"    행 번호: {row['row_number']}")
                print(f"    nctid: {row['nctid']}")
                print(f"    chunk_id: {row['chunk_id']}")
                print(f"    chunk 길이: {row['chunk_length']}자")
                print(f"    문제: {', '.join(row['issues'])}")
        
    except Exception as e:
        print(f"❌ 결측치 분석 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ 결측치 분석 완료")
    print("=" * 80 + "\n")


def analyze_chunk_file(file_path):
    """
    chunked_for_embedding.csv 파일을 분석합니다.
    
    Args:
        file_path (str): 분석할 CSV 파일 경로
        
    Returns:
        dict: 분석 결과 딕셔너리
    """
    if not os.path.isabs(file_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, file_path)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    rows = []
    nctid_counts = defaultdict(int)
    chunk_lengths = []
    word_counts = []
    empty_chunks = 0
    empty_nctids = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            nctid = row.get('nctid', '').strip()
            chunk_id = row.get('chunk_id', '').strip()
            chunk_str = row.get('chunk', '').strip()
            
            if nctid:
                nctid_counts[nctid] += 1
            else:
                empty_nctids += 1
            
            if not chunk_str:
                empty_chunks += 1
                chunk_lengths.append(0)
                word_counts.append(0)
            else:
                chunk_lengths.append(len(chunk_str))
                words = chunk_str.split()
                word_counts.append(len(words))
            
            rows.append({
                'nctid': nctid,
                'chunk_id': chunk_id,
                'chunk': chunk_str,
                'chunk_length': len(chunk_str),
                'word_count': len(chunk_str.split()) if chunk_str else 0
            })
    
    total_rows = len(rows)
    unique_nctids = len(nctid_counts)
    
    non_empty_lengths = [l for l in chunk_lengths if l > 0]
    non_empty_words = [w for w in word_counts if w > 0]
    
    stats = {
        'total_rows': total_rows,
        'unique_nctids': unique_nctids,
        'empty_nctids': empty_nctids,
        'empty_chunks': empty_chunks,
        'chunk_lengths': {
            'mean': mean(non_empty_lengths) if non_empty_lengths else 0,
            'median': median(non_empty_lengths) if non_empty_lengths else 0,
            'min': min(non_empty_lengths) if non_empty_lengths else 0,
            'max': max(non_empty_lengths) if non_empty_lengths else 0,
            'std': stdev(non_empty_lengths) if len(non_empty_lengths) > 1 else 0
        },
        'word_counts': {
            'mean': mean(non_empty_words) if non_empty_words else 0,
            'median': median(non_empty_words) if non_empty_words else 0,
            'min': min(non_empty_words) if non_empty_words else 0,
            'max': max(non_empty_words) if non_empty_words else 0,
            'std': stdev(non_empty_words) if len(non_empty_words) > 1 else 0
        },
        'nctid_distribution': {
            'mean': mean(nctid_counts.values()) if nctid_counts else 0,
            'median': median(nctid_counts.values()) if nctid_counts else 0,
            'min': min(nctid_counts.values()) if nctid_counts else 0,
            'max': max(nctid_counts.values()) if nctid_counts else 0,
            'total_chunks': sum(nctid_counts.values())
        },
        'sample_data': rows[:5] if rows else []
    }
    
    return stats


def print_eda_report(original_file, preprocessed_file=None):
    """
    EDA 리포트를 출력합니다.
    
    Args:
        original_file (str): 원본 파일 경로
        preprocessed_file (str, optional): 전처리된 파일 경로
    """
    print("\n" + "=" * 80)
    print("📊 Embedding 데이터 탐색적 데이터 분석 (EDA)")
    print("=" * 80)
    
    print("\n[1] 원본 파일 분석")
    print("-" * 80)
    try:
        original_stats = analyze_chunk_file(original_file)
        
        print(f"✓ 총 행 수: {original_stats['total_rows']:,}개")
        print(f"✓ 고유 nctid 수: {original_stats['unique_nctids']:,}개")
        print(f"✓ 빈 nctid: {original_stats['empty_nctids']}개")
        print(f"✓ 빈 chunk: {original_stats['empty_chunks']}개")
        
        print(f"\n[텍스트 길이 통계]")
        cl = original_stats['chunk_lengths']
        print(f"  평균: {cl['mean']:.1f}자")
        print(f"  중앙값: {cl['median']:.1f}자")
        print(f"  최소: {cl['min']:,}자")
        print(f"  최대: {cl['max']:,}자")
        print(f"  표준편차: {cl['std']:.1f}자")
        
        print(f"\n[단어 수 통계]")
        wc = original_stats['word_counts']
        print(f"  평균: {wc['mean']:.1f}단어")
        print(f"  중앙값: {wc['median']:.1f}단어")
        print(f"  최소: {wc['min']:,}단어")
        print(f"  최대: {wc['max']:,}단어")
        print(f"  표준편차: {wc['std']:.1f}단어")
        
        print(f"\n[nctid별 청크 수 분포]")
        nd = original_stats['nctid_distribution']
        print(f"  평균: {nd['mean']:.1f}개 청크/nctid")
        print(f"  중앙값: {nd['median']:.1f}개 청크/nctid")
        print(f"  최소: {nd['min']}개 청크/nctid")
        print(f"  최대: {nd['max']}개 청크/nctid")
        print(f"  총 청크 수: {nd['total_chunks']:,}개")
        
        print(f"\n[샘플 데이터 (상위 3개)]")
        for i, sample in enumerate(original_stats['sample_data'][:3], 1):
            print(f"\n  샘플 {i}:")
            print(f"    nctid: {sample['nctid'] or '(빈 값)'}")
            print(f"    chunk_id: {sample['chunk_id']}")
            print(f"    길이: {sample['chunk_length']:,}자, 단어 수: {sample['word_count']:,}개")
            preview = sample['chunk'][:100] + "..." if len(sample['chunk']) > 100 else sample['chunk']
            print(f"    내용 미리보기: {preview}")
        
    except Exception as e:
        print(f"❌ 원본 파일 분석 중 오류: {e}")
        original_stats = None
    
    if preprocessed_file and os.path.exists(preprocessed_file):
        print("\n\n[2] 전처리된 파일 분석")
        print("-" * 80)
        try:
            preprocessed_stats = analyze_chunk_file(preprocessed_file)
            
            print(f"✓ 총 행 수: {preprocessed_stats['total_rows']:,}개")
            print(f"✓ 고유 nctid 수: {preprocessed_stats['unique_nctids']:,}개")
            print(f"✓ 빈 nctid: {preprocessed_stats['empty_nctids']}개")
            print(f"✓ 빈 chunk: {preprocessed_stats['empty_chunks']}개")
            
            print(f"\n[텍스트 길이 통계]")
            cl = preprocessed_stats['chunk_lengths']
            print(f"  평균: {cl['mean']:.1f}자")
            print(f"  중앙값: {cl['median']:.1f}자")
            print(f"  최소: {cl['min']:,}자")
            print(f"  최대: {cl['max']:,}자")
            print(f"  표준편차: {cl['std']:.1f}자")
            
            print(f"\n[단어 수 통계]")
            wc = preprocessed_stats['word_counts']
            print(f"  평균: {wc['mean']:.1f}단어")
            print(f"  중앙값: {wc['median']:.1f}단어")
            print(f"  최소: {wc['min']:,}단어")
            print(f"  최대: {wc['max']:,}단어")
            print(f"  표준편차: {wc['std']:.1f}단어")
            
            if original_stats:
                print(f"\n[전처리 전후 비교]")
                print(f"  텍스트 길이 변화:")
                print(f"    평균: {original_stats['chunk_lengths']['mean']:.1f} → {cl['mean']:.1f}자 "
                      f"({cl['mean'] - original_stats['chunk_lengths']['mean']:+.1f}자)")
                print(f"    중앙값: {original_stats['chunk_lengths']['median']:.1f} → {cl['median']:.1f}자 "
                      f"({cl['median'] - original_stats['chunk_lengths']['median']:+.1f}자)")
                print(f"    최대: {original_stats['chunk_lengths']['max']:,} → {cl['max']:,}자 "
                      f"({cl['max'] - original_stats['chunk_lengths']['max']:+,}자)")
                
                print(f"\n  단어 수 변화:")
                print(f"    평균: {original_stats['word_counts']['mean']:.1f} → {wc['mean']:.1f}단어 "
                      f"({wc['mean'] - original_stats['word_counts']['mean']:+.1f}단어)")
                print(f"    중앙값: {original_stats['word_counts']['median']:.1f} → {wc['median']:.1f}단어 "
                      f"({wc['median'] - original_stats['word_counts']['median']:+.1f}단어)")
            
        except Exception as e:
            print(f"❌ 전처리된 파일 분석 중 오류: {e}")
    
    print("\n" + "=" * 80)
    print("✅ EDA 완료")
    print("=" * 80 + "\n")


def process_chunked_file(input_file, output_file, max_length=None):
    """
    chunked_for_embedding.csv 파일을 읽어서 전처리하고 새 파일로 저장합니다.
    
    Args:
        input_file (str): 입력 CSV 파일 경로
        output_file (str): 출력 CSV 파일 경로
        max_length (int, optional): 최대 텍스트 길이
        
    Returns:
        str: 저장된 출력 파일 경로
    """
    print("=" * 60)
    print("[Embedding 전처리] 시작")
    print("=" * 60)
    
    if not os.path.isabs(input_file):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        input_file = os.path.join(base_dir, input_file)
    
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_file}")
    
    if output_file is None:
        output_dir = os.path.dirname(input_file)
        output_file = os.path.join(output_dir, "preprocessed_chunked_for_embedding.csv")
    elif not os.path.isabs(output_file):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_file = os.path.join(base_dir, output_file)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"입력 파일: {input_file}")
    print(f"출력 파일: {output_file}")
    if max_length:
        print(f"최대 텍스트 길이: {max_length}자")
    print()
    
    processed_rows = []
    total_rows = 0
    error_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_idx, row in enumerate(reader, 1):
            total_rows += 1
            
            try:
                nctid = row.get('nctid', '')
                chunk_id = row.get('chunk_id', '')
                chunk_str = row.get('chunk', '')
                
                preprocessed_chunk = preprocess_chunk_for_embedding(chunk_str, max_length)
                
                processed_rows.append({
                    'nctid': nctid,
                    'chunk_id': chunk_id,
                    'chunk': preprocessed_chunk
                })
                
                if row_idx % 100 == 0:
                    print(f"  진행 중: {row_idx}개 처리 완료...")
                    
            except Exception as e:
                error_count += 1
                print(f"경고: 행 {row_idx} 처리 중 오류 발생: {e}")
                continue
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['nctid', 'chunk_id', 'chunk']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(processed_rows)
    
    print()
    print("=" * 60)
    print("[Embedding 전처리] 완료")
    print("=" * 60)
    print(f"✓ 총 {total_rows}개 행 처리")
    print(f"✓ 성공: {len(processed_rows)}개")
    if error_count > 0:
        print(f"⚠ 오류: {error_count}개")
    print(f"✓ 전처리된 파일 저장: {output_file}")
    print("=" * 60)
    
    return output_file


def run_eda():
    """EDA를 실행합니다."""
    original_file = INPUT_FILE
    preprocessed_file = None
    
    if OUTPUT_FILE is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        preprocessed_file = os.path.join(
            base_dir, 
            "data", "nih", "processed", "chunked", 
            "preprocessed_chunked_for_embedding.csv"
        )
    else:
        preprocessed_file = OUTPUT_FILE
    
    if not os.path.isabs(preprocessed_file):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        preprocessed_file = os.path.join(base_dir, preprocessed_file)
    
    if not os.path.exists(preprocessed_file):
        preprocessed_file = None
        print("⚠ 전처리된 파일을 찾을 수 없습니다. 원본 파일만 분석합니다.")
    
    print_eda_report(original_file, preprocessed_file)


def run_missing_values_analysis():
    """결측치 분석을 실행합니다."""
    file_path = INPUT_FILE
    print_missing_values_report(file_path)


def main():
    """메인 함수: embedding 전처리를 실행합니다."""
    input_file = INPUT_FILE
    output_file = OUTPUT_FILE
    max_length = MAX_TEXT_LENGTH
    
    result_file = process_chunked_file(input_file, output_file, max_length)
    print(f"\n✓ 전처리 완료: {result_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == 'eda':
            run_eda()
        elif command == 'missing' or command == 'missing_values':
            run_missing_values_analysis()
        else:
            print(f"알 수 없는 명령: {command}")
            print("사용 가능한 명령: 'eda', 'missing'")
    else:
        main()
