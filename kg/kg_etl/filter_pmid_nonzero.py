# filter_pmid_nonzero.py
import pandas as pd
import sys
from pathlib import Path

def main(input_path: str, output_path: str | None = None):
    input_path = Path(input_path)
    if output_path is None:
        # 기본: 원본파일명 + _filtered.csv 로 저장
        output_path = input_path.with_name(input_path.stem + "_filtered.csv")
    else:
        output_path = Path(output_path)

    df = pd.read_csv(input_path)

    # pmid 컬럼 이름이 다를 수 있으면 여기서 수정 ex) 'PMID'
    pmid_col = "pmid"
    if pmid_col not in df.columns:
        raise ValueError(f"'{pmid_col}' 컬럼을 찾을 수 없습니다. 실제 컬럼들: {list(df.columns)}")

    # 문자열로 캐스팅 후 strip
    pmid_str = df[pmid_col].astype(str).str.strip()

    # 조건:
    #  - 빈 문자열("") 제거
    #  - "0" 또는 0 제거
    #  - NaN 제거
    mask_valid = (
        pmid_str.notna() &
        (pmid_str != "") &
        (pmid_str != "0")
    )

    df_filtered = df[mask_valid].copy()

    print(f"원본 행 수: {len(df)}")
    print(f"필터링 후 행 수: {len(df_filtered)}")
    print(f"제거된 행 수: {len(df) - len(df_filtered)}")

    df_filtered.to_csv(output_path, index=False)
    print(f"저장 완료: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python filter_pmid_nonzero.py input.csv [output.csv]")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) >= 3 else None
    main(input_csv, output_csv)
