from langchain_text_splitters import RecursiveCharacterTextSplitter
import pandas as pd

filename = "cleaned_data_Cell"
df = pd.read_csv(f"{filename}.csv")

# null 전처리
df["abstract"] = df["abstract"].fillna("").astype(str)
df["step_content"] = df["step_content"].fillna("").astype(str)
df["guidelines"] = df.get("guidelines", "").fillna("").astype(str)
# 🔹 url과 title 컬럼 추가 처리
df["url"] = df.get("url", "").fillna("").astype(str)
df["title"] = df.get("title", "").fillna("").astype(str)

output_rows = []

# chunking 및 overlap적용
text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=100)
for _, row in df.iterrows():
    protocol_id = str(row["protocol_id"]).strip()
    text = "" # chunking(enter 단위)통합 결과 => "<abstract> (chunking) <step_content>: (chunking) <guidelines>: (chunking)"
    chunks_abstract = text_splitter.split_text(row["abstract"])
    text += "<abstract>\n"
    # abstract에 대한 chunking 단위별 text삽입
    for a in chunks_abstract:
        text += f"{a}\n"
    chunks_step_content = text_splitter.split_text(row["step_content"])
    text += "<step_content>\n"
    # step_content에 대한 chunking 단위별 text삽입
    for s in chunks_step_content:
        text += f"{s}\n"
    text += "<guidelines>\n"
    chunks_guidelines = text_splitter.split_text(row["guidelines"])
    # guidelines에 대한 chunking 단위별 text삽입
    for g in chunks_guidelines:
        text += f"{g}\n"

# 5) 배열에 저장
    output_rows.append({
        "protocol_id":f"{filename}_{protocol_id}",
        "url": row["url"],
        "title": row["title"],
        "chunking_id":f"{filename}_chunk_{protocol_id}",
        "text":text
    })

# ====== CSV 저장 ======
output_df = pd.DataFrame(output_rows)
output_df.to_csv(f"chunked_text_{filename}.csv", index=False)