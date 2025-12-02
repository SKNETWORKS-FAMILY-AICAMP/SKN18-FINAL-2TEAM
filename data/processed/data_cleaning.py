import pandas as pd

df = pd.read_csv("api_data_DNA.csv")
# url 중복제거 후 테이블
df = df.drop_duplicates(subset="url", keep="first").reset_index()
df = df.rename(columns={'index': 'protocol_id'})

# title 중복제거 후 테이블
df = df.drop_duplicates(subset="title", keep="first").reset_index()
df = df.drop(columns=['index'])

df = df.replace(r'"+', '"', regex=True)
df = df.replace(r'" ', '', regex=True)

# 띄어쓰기 2칸이상 들여쓰기 제거
df = df.replace(r'\s{2,}', ' ', regex=True)
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

df = df.replace(r"\t", "", regex=True)
df = df.replace(r'\n+', '\n', regex=True)

df = df.replace("<no data>", "")
df = df.replace(r"\\u[0-9a-fA-F]{4}", "", regex=True)

# 따옴표만 있거나 공백만 있는 경우 NaN으로 변환
df = df.replace(r'^\s*["“”\'’]*\s*$', "", regex=True)
df = df.replace("NA", "")

# NaN을 빈 문자열로 변경
df = df.fillna("")

# 공백만 있는 문자열을 빈 문자열로 변경
df = df.applymap(lambda x: "" if isinstance(x, str) and x.strip() == "" else x)
df.to_csv(f"cleaned_data_DNA.csv", index=False)