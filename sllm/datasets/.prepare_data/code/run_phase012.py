"""
통합 실행 스크립트: Phase 0, 1, 2 한 번에 실행
================================================

이 스크립트는 다음 3단계를 순차적으로 실행합니다:
1. Phase 0: Figure 이미지 분류 (실험 결과 데이터 여부)
2. Phase 1: result_desc 중복 제거 + 구조화된 JSON 생성
3. Phase 2: System message 분리 + user/assistant 형식 JSONL 생성

각 Phase의 역할:
    - Phase 0: is_experiment_result 컬럼 추가
    - Phase 1: 중복 문장 제거 + structured_json 컬럼 추가
    - Phase 2: CSV에서 structured_json 읽어서 training dataset (JSONL) 생성

설정:
    - INPUT_CSV_FILENAME: 원본 CSV 파일명
    - PHASE_0_SAMPLE_SIZE: Phase 0에서 처리할 샘플 개수
    - PHASE_1_SAMPLE_SIZE: Phase 1에서 처리할 샘플 개수
    - PHASE_2_SAMPLE_SIZE: Phase 2에서 처리할 샘플 개수
    - LLM_MODEL: 사용할 LLM 모델명 (Phase 0, 1에서 사용)
    - RESUME: 중단된 작업 이어서 실행 여부
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Phase 모듈 import
from phase_0_figure_classification import main as phase_0_main
from phase_1_result_desc_to_json import main as phase_1_main
from phase_2_create_training_dataset import main as phase_2_main

import dotenv
dotenv.load_dotenv()


# ============================================================================
# 🔧 설정 섹션 (여기서 변경)
# ============================================================================

# 원본 CSV 파일명 (data/raw/ 폴더 내 파일명)
INPUT_CSV_FILENAME = "t_figures_with_result_desc_v4.csv"

# Phase 0에서 처리할 샘플 개수 (None = 전체)
PHASE_0_SAMPLE_SIZE = 1000

# Phase 1에서 처리할 샘플 개수 (None = 전체)
PHASE_1_SAMPLE_SIZE = 1000

# Phase 2에서 처리할 샘플 개수 (None = 전체)
PHASE_2_SAMPLE_SIZE = None

# 사용할 LLM 모델 (gpt-4o-mini, gpt-4o 등)
LLM_MODEL = "gpt-4o-mini"

# 중단된 작업 이어서 실행 여부
RESUME = True

# ============================================================================


def get_base_dir() -> Path:
    """기본 디렉토리 경로 반환"""
    return Path(__file__).parent.parent


def get_input_csv_path(filename: str) -> Path:
    """입력 CSV 파일 경로 반환"""
    base_dir = get_base_dir()
    return base_dir / "data" / "raw" / filename


def get_phase_0_output_path(input_filename: str) -> Path:
    """
    Phase 0 출력 파일 경로 반환
    Phase 0는 원본 파일에 is_experiment_result 컬럼을 추가하므로
    입력 파일과 동일한 경로 사용
    """
    return get_input_csv_path(input_filename)


def get_phase_1_output_path(input_filename: str) -> Path:
    """
    Phase 1 출력 파일 경로 반환
    Phase 0 완료 파일을 사용 (파일명 자동 추론)
    """
    # Phase 0는 원본 파일에 컬럼을 추가하므로 같은 파일 사용
    return get_input_csv_path(input_filename)


def validate_input_file(csv_path: Path) -> None:
    """입력 파일 존재 여부 확인"""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"입력 파일을 찾을 수 없습니다: {csv_path}\n"
            f"파일명을 확인하거나 INPUT_CSV_FILENAME 설정을 변경하세요."
        )


def run_phase_0(
    input_csv_filename: str,
    sample_size: Optional[int],
    model: str,
    resume: bool
) -> Path:
    """
    Phase 0 실행: Figure 이미지 분류

    Returns:
        Phase 0 완료된 CSV 파일 경로
    """
    print("\n" + "="*80)
    print("🚀 Phase 0: Figure Classification 시작")
    print("="*80)

    input_csv_path = get_input_csv_path(input_csv_filename)
    validate_input_file(input_csv_path)

    # Phase 0는 원본 파일에 컬럼을 추가하므로 입력과 출력이 같음
    output_csv_path = input_csv_path

    # phase_0_figure_classification.py의 main 함수는 하드코딩된 경로를 사용하므로
    # 직접 클래스를 사용하거나 경로를 수정해야 함
    # 여기서는 phase_0_main을 수정하여 경로를 받도록 해야 하지만,
    # 기존 코드를 최대한 활용하기 위해 임시로 파일을 복사하거나
    # 직접 클래스를 호출하는 방식 사용

    # OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Phase 0 클래스 직접 사용
    from phase_0_figure_classification import FigureClassifier

    classifier = FigureClassifier(
        api_key=api_key,
        model=model
    )

    # 배치 처리 실행
    results_df = classifier.process_batch(
        input_csv=str(input_csv_path),
        output_csv=str(output_csv_path),
        sample_size=sample_size,
        resume=resume
    )

    print(f"\n✅ Phase 0 완료!")
    print(f"📊 결과 파일: {output_csv_path}")
    print(f"   - is_experiment_result 컬럼 추가됨")

    return output_csv_path


def run_phase_1(
    input_csv_path: Path,
    sample_size: Optional[int],
    model: str,
    resume: bool
) -> Path:
    """
    Phase 1 실행: result_desc 중복 제거 + 구조화된 JSON 생성

    Returns:
        Phase 1 완료된 CSV 파일 경로 (structured_json 컬럼 추가)
    """
    print("\n" + "="*80)
    print("🚀 Phase 1: Result Desc to Structured JSON (with Deduplication) 시작")
    print("="*80)

    # Phase 1 클래스 직접 사용
    from phase_1_result_desc_to_json import ResultDescToStructuredConverter
    from datetime import datetime

    # OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # JSON 파일 경로 (검증용)
    base_dir = get_base_dir()
    dataset_dir = base_dir / "data" / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_json_path = dataset_dir / f"structured_results_{timestamp}.json"

    converter = ResultDescToStructuredConverter(
        api_key=api_key,
        model=model
    )

    # 배치 처리 실행 (중복 제거 + 구조화)
    result_df = converter.process_batch(
        input_csv=str(input_csv_path),
        output_csv=str(input_csv_path),  # 같은 파일에 structured_json 컬럼 추가
        output_json=str(output_json_path),  # JSON 검증 파일
        sample_size=sample_size,
        resume=resume
    )

    print(f"\n✅ Phase 1 완료!")
    print(f"📊 CSV 파일: {input_csv_path.name}")
    print(f"   - structured_json 컬럼 추가됨 (중복 제거된 result_desc 기반)")
    print(f"📄 JSON 검증 파일: {output_json_path.name}")

    return input_csv_path


def run_phase_2(
    input_csv_path: Path,
    sample_size: Optional[int]
) -> Path:
    """
    Phase 2 실행: System message 분리 + user/assistant 형식 JSONL 생성

    Returns:
        Phase 2에서 생성된 JSONL 파일 경로
    """
    print("\n" + "="*80)
    print("🚀 Phase 2: Create Training Dataset (System Separation) 시작")
    print("="*80)

    from phase_2_create_training_dataset import TrainingDatasetCreator
    from datetime import datetime

    # 출력 JSONL 파일 경로 (타임스탬프 포함)
    base_dir = get_base_dir()
    dataset_dir = base_dir / "data" / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_jsonl_path = dataset_dir / f"training_dataset_preprocessed_{timestamp}.jsonl"
    system_message_file = dataset_dir / f"system_message_{timestamp}.txt"

    creator = TrainingDatasetCreator()

    # 변환 실행
    creator.convert_to_training_dataset(
        input_csv=str(input_csv_path),
        output_jsonl=str(output_jsonl_path),
        system_message_file=str(system_message_file),
        sample_size=sample_size
    )

    print(f"\n✅ Phase 2 완료!")
    print(f"📦 Training Dataset (JSONL): {output_jsonl_path.name}")
    print(f"📄 System Message: {system_message_file.name}")

    return output_jsonl_path


def main():
    """메인 실행 함수"""
    print("\n" + "="*80)
    print("🎯 통합 파이프라인 실행")
    print("="*80)
    print(f"입력 CSV 파일: {INPUT_CSV_FILENAME}")
    print(f"Phase 0 샘플 수: {PHASE_0_SAMPLE_SIZE if PHASE_0_SAMPLE_SIZE else '전체'}")
    print(f"Phase 1 샘플 수: {PHASE_1_SAMPLE_SIZE if PHASE_1_SAMPLE_SIZE else '전체'}")
    print(f"Phase 2 샘플 수: {PHASE_2_SAMPLE_SIZE if PHASE_2_SAMPLE_SIZE else '전체'}")
    print(f"LLM 모델: {LLM_MODEL}")
    print(f"Resume: {RESUME}")
    print("="*80)

    try:
        # Phase 0 실행
        phase_0_output_csv = run_phase_0(
            input_csv_filename=INPUT_CSV_FILENAME,
            sample_size=PHASE_0_SAMPLE_SIZE,
            model=LLM_MODEL,
            resume=RESUME
        )

        # Phase 1 실행 (중복 제거 + 구조화)
        phase_1_output_csv = run_phase_1(
            input_csv_path=phase_0_output_csv,
            sample_size=PHASE_1_SAMPLE_SIZE,
            model=LLM_MODEL,
            resume=RESUME
        )

        # Phase 2 실행 (System 분리 + Training dataset 생성)
        phase_2_output_jsonl = run_phase_2(
            input_csv_path=phase_1_output_csv,
            sample_size=PHASE_2_SAMPLE_SIZE
        )

        # 최종 요약
        print("\n" + "="*80)
        print("🎉 전체 파이프라인 완료!")
        print("="*80)
        print(f"✅ Phase 0 완료: {phase_0_output_csv}")
        print(f"✅ Phase 1 완료: {phase_1_output_csv.name} (structured_json 추가)")
        print(f"✅ Phase 2 완료: {phase_2_output_jsonl.name} (training dataset)")
        print("="*80)
        print("\n다음 단계:")
        print("1. 데이터셋 품질 검증")
        print("2. Phase 3에서 에러 항목 처리 (필요시)")
        print("3. Colab T4 GPU에서 Gemma-3-1B-IT QLoRA 파인튜닝 실행")
        print("4. 파인튜닝된 모델 평가 및 배포")

    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

