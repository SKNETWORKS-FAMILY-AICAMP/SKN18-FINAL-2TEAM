# embed_bge_m3.py
# BGEM3FlagModel로 CSV 텍스트 임베딩 + 결과 검증 스크립트

import os
import time
import argparse
from typing import List

import pandas as pd
from tqdm import tqdm
from FlagEmbedding import BGEM3FlagModel


# ─────────────────────────────────────────
# 1. 임베딩 모델 로드
# ─────────────────────────────────────────
def load_bge_model(model_name: str = "BAAI/bge-m3") -> BGEM3FlagModel:
    print(f"📦 Loading BGEM3FlagModel: {model_name}")
    model = BGEM3FlagModel(
        model_name,
        use_fp16=True,  # 속도 ↑, 약간의 성능 손실 (필요시 False로)
    )
    # BGEM3FlagModel는 dense_vecs를 L2 normalize 해서 반환
    # → dot product = cosine similarity
    return model


# ─────────────────────────────────────────
# 2. 텍스트 임베딩 함수 (배치 단위)
# ─────────────────────────────────────────
def embed_texts(
    model: BGEM3FlagModel,
    text_series: pd.Series,
    embed_batch_size: int = 64,
    max_length: int = 8192,
) -> List[List[float]]:
    """
    한 chunk의 텍스트 Series를 받아서
    BGEM3FlagModel의 dense_vecs(list[list[float]])를 반환.
    """
    texts = (
        text_series
        .astype(str)
        .fillna("")
        .apply(lambda x: x.replace("\n", " ").strip())
        .tolist()
    )

    # BGE 권장 프리픽스: passage (문서/청크)
    processed_texts = [f"passage: {t}" if t else "passage: " for t in texts]

    encoded = model.encode(
        processed_texts,
        batch_size=embed_batch_size,
        max_length=max_length,
    )
    dense_vecs = encoded["dense_vecs"]  # numpy.ndarray (N, d)

    # CSV에 저장하기 위해 list[list[float]]로 변환
    return [vec.tolist() for vec in dense_vecs]


# ─────────────────────────────────────────
# 3. 메인 임베딩 프로세스 (이어하기 + 배치 처리)
# ─────────────────────────────────────────
def process_embeddings(
    input_csv_path: str,
    output_csv_path: str,
    text_col_guess: str = "text",
    batch_size: int = 100,
    embed_batch_size: int = 64,
    max_length: int = 8192,
    model_name: str = "BAAI/bge-m3",
):
    # 0) 모델 로드
    model = load_bge_model(model_name)

    # 1) 이어하기(Resume) 체크
    processed_rows = 0
    if os.path.exists(output_csv_path):
        with open(output_csv_path, "r", encoding="utf-8") as f:
            processed_rows = sum(1 for _ in f) - 1  # 헤더 제외
        if processed_rows < 0:
            processed_rows = 0
        print(f"🔄 기존 작업 파일 감지: {processed_rows}행 완료됨. 이어서 진행합니다.")
    else:
        print("🆕 새로운 임베딩 작업을 시작합니다.")

    # 2) 전체 데이터 행 수 파악
    try:
        total_rows = sum(1 for _ in open(input_csv_path, encoding="utf-8")) - 1
    except FileNotFoundError:
        print(f"❌ 입력 파일을 찾을 수 없습니다: {input_csv_path}")
        return

    if processed_rows >= total_rows:
        print("✅ 이미 모든 데이터의 임베딩이 완료되었습니다!")
        return

    # 3) 배치 단위로 읽기
    skip_rows = range(1, processed_rows + 1) if processed_rows > 0 else None

    chunk_iter = pd.read_csv(
        input_csv_path,
        chunksize=batch_size,
        skiprows=skip_rows,
    )

    print(
        f"🚀 처리 시작 (남은 데이터: {total_rows - processed_rows}행, "
        f"파일: {input_csv_path})"
    )

    with tqdm(total=total_rows, initial=processed_rows, unit="row") as pbar:
        for chunk in chunk_iter:
            if chunk.empty:
                break

            # 텍스트 컬럼 확인
            target_col = text_col_guess
            if target_col not in chunk.columns:
                candidates = [
                    c for c in chunk.columns
                    if "text" in c.lower() or "chunk" in c.lower()
                ]
                if candidates:
                    target_col = candidates[0]
                    print(f"ℹ️ '{target_col}' 컬럼을 텍스트 컬럼으로 사용합니다.")
                else:
                    print(f"❌ 텍스트 컬럼을 찾을 수 없습니다. 컬럼명: {list(chunk.columns)}")
                    return

            # 임베딩 생성
            try:
                embeddings_list = embed_texts(
                    model,
                    chunk[target_col],
                    embed_batch_size=embed_batch_size,
                    max_length=max_length,
                )
                if len(embeddings_list) != len(chunk):
                    print("❌ 임베딩 결과 길이가 chunk 길이와 다릅니다. 이 chunk는 건너뜁니다.")
                    continue
                chunk["embedding"] = embeddings_list
            except Exception as e:
                print(f"❌ 임베딩 생성 중 오류 발생, 이 chunk 건너뜀: {e}")
                time.sleep(1)
                continue

            # CSV 저장 (Append 모드)
            file_exists = (
                os.path.isfile(output_csv_path)
                and os.path.getsize(output_csv_path) > 0
            )

            chunk.to_csv(
                output_csv_path,
                mode="a",
                index=False,
                header=not file_exists,
                encoding="utf-8-sig",
            )

            pbar.update(len(chunk))

    print(f"\n🎉 작업 완료! 결과 파일: {output_csv_path}")


# ─────────────────────────────────────────
# 4. 임베딩 검증 함수
# ─────────────────────────────────────────
def verify_embeddings(
    input_path: str,
    output_path: str,
    id_col_name: str = "chunking_id",
):
    """
    id_col_name을 기준으로 원본과 결과 파일의 정합성을 검증.
    - 원본: input_path
    - 결과: output_path
    """
    print(f"🕵️ 검증 시작...")
    print(f"   - 원본 파일: {input_path}")
    print(f"   - 결과 파일: {output_path}")
    print(f"   - 기준 컬럼: '{id_col_name}'")

    # 1. 파일 존재 확인
    if not os.path.exists(input_path):
        print(f"❌ 원본 파일을 찾을 수 없습니다.")
        return
    if not os.path.exists(output_path):
        print(f"❌ 결과(임베딩) 파일을 찾을 수 없습니다. 아직 작업이 시작되지 않았나요?")
        return

    # 2. 헤더 확인 (컬럼 존재 여부 체크)
    input_header = pd.read_csv(input_path, nrows=0)
    if id_col_name not in input_header.columns:
        print(f"❌ 원본 파일에 '{id_col_name}' 컬럼이 없습니다.")
        print(f"   (현재 컬럼 목록: {list(input_header.columns)})")
        return

    # 3. ID 데이터 로드
    print("⏳ 데이터 로딩 중...")
    try:
        # 원본 ID 셋
        df_input = pd.read_csv(input_path, usecols=[id_col_name])
        input_ids = set(df_input[id_col_name].astype(str))

        # 결과 ID 셋
        df_output = pd.read_csv(output_path, usecols=[id_col_name])
        output_ids_list = df_output[id_col_name].astype(str).tolist()
        output_ids_set = set(output_ids_list)

    except ValueError as e:
        print(f"❌ 컬럼 로드 중 에러 발생: {e}")
        print(f"   결과 파일에 '{id_col_name}' 컬럼이 제대로 생성되었는지 확인하세요.")
        return

    # 4. 비교 분석
    total_input = len(input_ids)
    total_output_rows = len(output_ids_list)
    unique_output = len(output_ids_set)

    missing_ids = input_ids - output_ids_set
    unexpected_ids = output_ids_set - input_ids
    duplicates = total_output_rows - unique_output

    # 5. 결과 리포트
    print("\n" + "=" * 40)
    print("📊 [검증 결과 리포트]")
    print("=" * 40)
    print(f"1. 원본 데이터 수 (Unique ID) : {total_input:,} 개")
    print(f"2. 결과 데이터 수 (Total Rows): {total_output_rows:,} 개")
    print(f"3. 결과 데이터 수 (Unique ID) : {unique_output:,} 개")
    print("-" * 40)

    progress = (unique_output / total_input) * 100 if total_input > 0 else 0
    print(f"📈 진행률: {progress:.2f}%")

    # 중복 확인
    if duplicates > 0:
        print(f"⚠️ 중복된 ID 발견: {duplicates:,} 개 (이어쓰기 과정에서 중복 발생 가능)")
        print(f"   -> drop_duplicates()로 정제가 필요합니다.")
    else:
        print(f"✅ 중복된 ID 없음")

    # 누락 확인
    if len(missing_ids) > 0:
        print(f"❌ 누락된 ID(미완료): {len(missing_ids):,} 개")
        print(f"   (샘플: {list(missing_ids)[:5]} ...)")
        missing_save_path = "missing_ids.csv"
        pd.DataFrame(list(missing_ids), columns=[id_col_name]).to_csv(
            missing_save_path, index=False
        )
        print(f"💾 누락된 ID 목록을 '{missing_save_path}'에 저장했습니다.")
    else:
        print(f"🎉 모든 데이터가 완벽하게 임베딩되었습니다!")

    # 원본에 없는 ID
    if len(unexpected_ids) > 0:
        print(f"❓ 원본에 없는 ID 발견: {len(unexpected_ids):,} 개 (데이터 버전이 다른가요?)")

    print("=" * 40 + "\n")


# ─────────────────────────────────────────
# 5. CLI 진입점
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="BGE M3 임베딩 생성 및 결과 검증 스크립트"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 5-1) embed 서브커맨드
    p_embed = subparsers.add_parser("embed", help="텍스트 CSV에 대해 임베딩 생성")
    p_embed.add_argument("--input", required=True, help="입력 CSV 경로")
    p_embed.add_argument("--output", required=True, help="출력 CSV 경로")
    p_embed.add_argument(
        "--text-col",
        default="text",
        help="텍스트 컬럼 이름 (기본: text, 없으면 자동 추론)",
    )
    p_embed.add_argument("--batch-size", type=int, default=100)
    p_embed.add_argument("--embed-batch-size", type=int, default=64)
    p_embed.add_argument("--max-length", type=int, default=8192)
    p_embed.add_argument(
        "--model-name",
        default="BAAI/bge-m3",
        help="Hugging Face 모델 이름 (기본: BAAI/bge-m3)",
    )

    # 5-2) verify 서브커맨드
    p_verify = subparsers.add_parser("verify", help="임베딩 결과 정합성 검증")
    p_verify.add_argument("--input", required=True, help="원본 CSV 경로")
    p_verify.add_argument("--output", required=True, help="임베딩 CSV 경로")
    p_verify.add_argument(
        "--id-col",
        default="chunking_id",
        help="ID 컬럼 이름 (기본: chunking_id)",
    )

    args = parser.parse_args()

    if args.command == "embed":
        process_embeddings(
            input_csv_path=args.input,
            output_csv_path=args.output,
            text_col_guess=args.text_col,
            batch_size=args.batch_size,
            embed_batch_size=args.embed_batch_size,
            max_length=args.max_length,
            model_name=args.model_name,
        )
    elif args.command == "verify":
        verify_embeddings(
            input_path=args.input,
            output_path=args.output,
            id_col_name=args.id_col,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
