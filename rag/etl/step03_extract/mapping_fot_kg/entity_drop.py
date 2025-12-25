import pandas as pd

# 1. 파일 로드
FILE_PATH = '/content/drive/MyDrive/final_project/data/entities_all_dbs.csv'
df = pd.read_csv(FILE_PATH)

print(f"📉 제거 전 데이터 개수: {len(df)}개")

# 2. 중복 제거 (모든 컬럼이 동일한 행 제거)
# 변수명을 df_dedup으로 통일합니다.
df_dedup = df.drop_duplicates()

print(f"📉 중복 제거 후: {len(df_dedup)}개 (삭제된 행: {len(df) - len(df_dedup)}개)")

# 3. 저장
# [중요] 방금 만든 'df_dedup'을 저장해야 합니다.
OUTPUT_PATH = '/content/drive/MyDrive/final_project/data/entity_dedup.csv'
df_dedup.to_csv(OUTPUT_PATH, index=False)

print(f"✅ 중복 제거 완료! 저장된 파일: {OUTPUT_PATH}")