# filter_section_id_zero_prefix.py
import pandas as pd
import sys
from pathlib import Path

def main(input_path: str, output_path: str | None = None):
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "_filtered.csv")
    else:
        output_path = Path(output_path)

    df = pd.read_csv(input_path)

    section_col = "section_id"  # 컬럼 이름 다르면 여기만 바꿔줘
    if section_col not in df.columns:
        raise ValueError(
            f"'{section_col}' 컬럼을 찾을 수 없습니다. 실제 컬럼들: {list(df.columns)}"
        )

    # 문자열로 변환 후 앞뒤 공백 제거
    sec_str = df[section_col].astype(str).str.strip()

    # 제거 조건: "0_" 로 시작하는 값 (예: 0_sec0, 0_fig, 0_foo)
    bad_mask = sec_str.str.startswith("0_")

    # 반대로, 이 조건이 아닌 행만 남기기
    df_filtered = df[~bad_mask].copy()

    print(f"원본 행 수: {len(df)}")
    print(f"제거된 행 수: {bad_mask.sum()}")
    print(f"필터링 후 행 수: {len(df_filtered)}")

    df_filtered.to_csv(output_path, index=False)
    print(f"저장 완료: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python filter_section_id_zero_prefix.py input.csv [output.csv]")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) >= 3 else None
    main(input_csv, output_csv)
