import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
ENT_DIR = ROOT_DIR / "data" / "entities"

# 1. 파일 로드
FILE_PATH = ENT_DIR / "ts_global_entity_master.csv"
df = pd.read_csv(FILE_PATH)

print(f"?? 제거 전 데이터 개수: {len(df)}개")

# 2. 중복 제거 (모든 컬럼이 동일한 행 제거)
df_dedup = df.drop_duplicates()

print(f"?? 중복 제거 후: {len(df_dedup)}개 (삭제된 행: {len(df) - len(df_dedup)}개)")

# 3. 저장
OUTPUT_PATH = ENT_DIR / "ts_global_entity_master_dedup.csv"
df_dedup.to_csv(OUTPUT_PATH, index=False)

print(f"? 중복 제거 완료! 저장된 파일: {OUTPUT_PATH}")
