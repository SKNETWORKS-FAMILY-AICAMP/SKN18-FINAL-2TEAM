"""
JSONL 파일의 input과 output을 문자열화된 JSON으로 변환
LLaMA-Factory 형식에 맞춤
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


def convert_jsonl_to_string_json(input_jsonl_path: str, output_json_path: str = None) -> Tuple[list, Path]:
    """
    JSONL 파일을 읽어서 input/output을 문자열화된 JSON으로 변환
    
    Args:
        input_jsonl_path: 입력 JSONL 파일 경로
        output_json_path: 출력 JSON 파일 경로 (None이면 자동 생성)
    
    Returns:
        (converted_data, output_path)
    """
    from pathlib import Path
    
    # 프로젝트 루트 기준으로 경로 변환
    script_dir = Path(__file__).parent  # sllm/training/
    project_root = script_dir.parent.parent  # 프로젝트 루트
    
    # 입력 파일 경로
    if os.path.isabs(input_jsonl_path):
        input_path = Path(input_jsonl_path)
    else:
        input_path = project_root / input_jsonl_path.replace("\\", "/")
    
    # 출력 파일 경로
    if output_json_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_json_path = f"sllm/datasets/the_final_{timestamp}.json"
    
    if os.path.isabs(output_json_path):
        output_path = Path(output_json_path)
    else:
        output_path = project_root / output_json_path
    
    print(f"📂 입력 파일: {input_path}")
    print(f"📂 출력 파일: {output_path}")
    
    # 입력 파일 존재 확인
    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일이 존재하지 않습니다: {input_path}")
    
    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # JSONL 파일 읽어서 변환
    data = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                data.append(obj)
            except json.JSONDecodeError as e:
                print(f"⚠️ {line_num}번째 줄 JSON 파싱 오류: {e}")
                continue
    
    print(f"✅ {len(data)}개 항목 읽기 완료")
    
    # input과 output을 JSON 문자열로 변환
    converted_data = []
    for idx, item in enumerate(data, start=1):
        converted_item = {
            "instruction": item.get("instruction", ""),
            "input": json.dumps(item.get("input", {}), ensure_ascii=False) if isinstance(item.get("input"), (dict, list)) else str(item.get("input", "")),
            "output": json.dumps(item.get("output", {}), ensure_ascii=False) if isinstance(item.get("output"), (dict, list)) else str(item.get("output", ""))
        }
        converted_data.append(converted_item)
        
        if idx % 500 == 0:
            print(f"   처리 중: {idx}/{len(data)}")
    
    print(f"✅ 변환 완료: {len(converted_data)}개 항목")
    
    # JSON 배열로 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)
    
    file_size = output_path.stat().st_size
    print(f"✅ 저장 완료: {output_path}")
    print(f"   파일 크기: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"   총 항목 수: {len(converted_data):,}개")
    
    # 샘플 출력 (첫 번째 항목 확인)
    if converted_data:
        print(f"\n📋 샘플 (첫 번째 항목):")
        print(f"   instruction: {converted_data[0]['instruction'][:50]}...")
        print(f"   input (타입): {type(converted_data[0]['input']).__name__}")
        print(f"   input (길이): {len(converted_data[0]['input'])} 문자")
        print(f"   output (타입): {type(converted_data[0]['output']).__name__}")
        print(f"   output (길이): {len(converted_data[0]['output'])} 문자")
    
    return converted_data, output_path


if __name__ == "__main__":
    # 명령줄 실행용
    import argparse
    
    parser = argparse.ArgumentParser(description="JSONL을 문자열화된 JSON으로 변환")
    parser.add_argument("--input", required=True, help="입력 JSONL 파일 경로")
    parser.add_argument("--output", help="출력 JSON 파일 경로 (기본값: 자동 생성)")
    args = parser.parse_args()
    
    convert_jsonl_to_string_json(args.input, args.output)

