"""
SFT Dataset Creation & Quality Audit Pipeline

이 스크립트는 다음 두 단계를 순차적으로 실행합니다:
1. preprocess_to_sft_v3.py: CSV → annotation.json → SFT dataset JSONL
2. dataset_auditor.py: SFT dataset JSONL → Quality audit → Filtered final dataset
"""

import sys
import subprocess
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List

# 현재 스크립트가 있는 디렉토리를 sys.path에 추가 (같은 디렉토리의 모듈 import용)
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# 프로젝트 루트 경로 (상대 경로 계산용)
project_root = script_dir.parent.parent

# 같은 디렉토리의 모듈 import
from preprocess_to_sft_v3 import create_annotation_json, create_sft_dataset
from dataset_auditor import (
    read_jsonl, evaluate_one, write_csv, write_json, write_final_jsonl, 
    FinalEvaluation, SLEEP_BETWEEN
)
from pydantic import ValidationError


def run_preprocessing():
    """Step 1: annotation.json 및 SFT dataset 생성"""
    print("=" * 80)
    print("📝 [Step 1/2] Creating annotation.json and SFT dataset...")
    print("=" * 80)
    
    try:
        annotations, annotation_output = create_annotation_json()
        sft_dataset, sft_output = create_sft_dataset(annotation_output)
        
        print(f"\n✅ Step 1 completed successfully!")
        print(f"   - Annotation JSON: {annotation_output}")
        print(f"   - SFT Dataset JSONL: {sft_output}")
        
        return sft_output
    except Exception as e:
        print(f"\n❌ Step 1 failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def run_audit_via_subprocess(sft_output: str):
    """Step 2: dataset_auditor.py를 subprocess로 실행"""
    print("\n" + "=" * 80)
    print("🔍 [Step 2/2] Running dataset quality audit...")
    print("=" * 80)
    
    # 타임스탬프 생성 (yymmdd_hhmm)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    
    # 출력 파일 경로 설정
    out_csv = f"sllm/datasets/audit_results_{timestamp}.csv"
    out_json = f"sllm/datasets/audit_results_{timestamp}.json"
    out_final_jsonl = f"sllm/datasets/final_sft_dataset_{timestamp}.jsonl"
    
    # dataset_auditor.py 스크립트 경로 (절대 경로로 변환)
    auditor_script = script_dir / "dataset_auditor.py"
    sft_output_abs = Path(sft_output).resolve() if not Path(sft_output).is_absolute() else Path(sft_output)
    out_csv_abs = (project_root / out_csv).resolve()
    out_json_abs = (project_root / out_json).resolve()
    out_final_jsonl_abs = (project_root / out_final_jsonl).resolve()
    
    # subprocess로 실행 (프로젝트 루트를 작업 디렉토리로)
    cmd = [
        sys.executable,
        str(auditor_script),
        "--in_jsonl", str(sft_output_abs),
        "--out_csv", str(out_csv_abs),
        "--out_json", str(out_json_abs),
        "--out_final_jsonl", str(out_final_jsonl_abs)
    ]
    
    print(f"📋 Running: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print(f"\n✅ Step 2 completed successfully!")
        print(f"   - Audit results CSV: {out_csv}")
        print(f"   - Audit results JSON: {out_json}")
        print(f"   - Final filtered dataset: {out_final_jsonl}")
        return out_final_jsonl
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Step 2 failed with exit code {e.returncode}")
        raise
    except Exception as e:
        print(f"\n❌ Step 2 failed: {e}")
        raise


def run_audit_direct(sft_output: str):
    """Step 2: dataset_auditor.py의 함수를 직접 호출 (대안 방법)"""
    print("\n" + "=" * 80)
    print("🔍 [Step 2/2] Running dataset quality audit (direct call)...")
    print("=" * 80)
    
    # 타임스탬프 생성 (yymmdd_hhmm)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    
    # 출력 파일 경로 설정 (절대 경로로 변환)
    sft_output_abs = Path(sft_output).resolve() if not Path(sft_output).is_absolute() else Path(sft_output)
    out_csv = project_root / f"sllm/datasets/audit_results_{timestamp}.csv"
    out_json = project_root / f"sllm/datasets/audit_results_{timestamp}.json"
    out_final_jsonl = project_root / f"sllm/datasets/final_sft_dataset_{timestamp}.jsonl"
    
    print(f"📂 Loading SFT dataset from: {sft_output_abs}")
    raw_samples = read_jsonl(str(sft_output_abs))
    evals: List[FinalEvaluation] = []
    
    print(f"📊 Processing {len(raw_samples)} samples...")
    
    for i, raw in enumerate(raw_samples, start=1):
        try:
            ev = evaluate_one(i, raw)
            evals.append(ev)
            print(f"[{i}/{len(raw_samples)}] {ev.verdict} score={ev.score} hard_fail={ev.hard_fail}")
            time.sleep(SLEEP_BETWEEN)
        except ValidationError as ve:
            print(f"[{i}] Schema validation error: {ve}")
        except Exception as e:
            print(f"[{i}] Error: {e}")
    
    if evals:
        write_csv(str(out_csv), evals)
        write_json(str(out_json), evals)
        write_final_jsonl(str(out_final_jsonl), raw_samples, evals)
        
        pass_count = sum(1 for e in evals if e.verdict == "PASS")
        print(f"\n✅ Step 2 completed successfully!")
        print(f"   - Audit results CSV: {out_csv}")
        print(f"   - Audit results JSON: {out_json}")
        print(f"   - Final filtered dataset: {out_final_jsonl}")
        print(f"   - ✅ Saved {pass_count} PASS samples to {out_final_jsonl}")
        
        return str(out_final_jsonl)
    else:
        print("❌ No valid evaluations produced.")
        raise RuntimeError("No valid evaluations produced")


def main(use_subprocess: bool = True):
    """
    전체 파이프라인 실행
    
    Args:
        use_subprocess: True면 subprocess로 실행, False면 함수 직접 호출
    """
    print("=" * 80)
    print("🚀 Starting SFT Dataset Creation & Quality Audit Pipeline")
    print("=" * 80)
    print()
    
    try:
        # Step 1: 전처리
        sft_output = run_preprocessing()
        
        if not os.path.exists(sft_output):
            raise FileNotFoundError(f"SFT dataset file not found: {sft_output}")
        
        # Step 2: 감사
        if use_subprocess:
            final_output = run_audit_via_subprocess(sft_output)
        else:
            final_output = run_audit_direct(sft_output)
        
        print("\n" + "=" * 80)
        print("🎉 Pipeline completed successfully!")
        print("=" * 80)
        print(f"📁 Final output: {final_output}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ Pipeline failed: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run SFT dataset creation and quality audit pipeline"
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Use direct function calls instead of subprocess (default: use subprocess)"
    )
    
    args = parser.parse_args()
    main(use_subprocess=not args.direct)

