import re
import pandas as pd

def split_into_sentences(text):
    protected = text

    # URL 보호
    protected = re.sub(r'(https?://\S+)', r'<URL>\1</URL>', protected)

    # 약어 보호
    protected = re.sub(r'\b(e\.g\.|i\.e\.|etc\.|Fig\.|Fig\s*\d+\.|No\.)', 
                       r'<ABBR>\1</ABBR>', protected)

    # 🔥 No. 1 / No. 2. / No. 3) 보호
    protected = re.sub(r'\bNo\.\s*\d+\.?', 
                       lambda m: f"<NO>{m.group(0)}</NO>", 
                       protected)

    # 숫자 목록 보호 (1. 2. 3.)
    protected = re.sub(r'\b(\d+)\.(\s+)', r'<NUM>\1.</NUM>\2', protected)

    # 괄호 안의 마침표 보호 (예: (e.g.)
    protected = re.sub(r'\(([^)]+?)\)', 
                       lambda m: '(' + m.group(1).replace('.', '<DOT>') + ')', 
                       protected)

    # 기존 분리식 (대문자 또는 태그 앞에서만 분리)
    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z<])',
        protected
    )

    # 보호 복원
    cleaned = []
    for sent in sentences:
        sent = sent.replace('<URL>', '').replace('</URL>', '')
        sent = sent.replace('<ABBR>', '').replace('</ABBR>', '')
        sent = sent.replace('<NUM>', '').replace('</NUM>', '')
        sent = sent.replace('<NO>', '').replace('</NO>', '')
        sent = sent.replace('<DOT>', '.')
        cleaned.append(sent)

    return [s for s in cleaned if s.strip()]



def create_sentence_chunks(
    sentences, 
    chunk_size=400, 
    chunk_overlap=100, 
    min_chunk_size=300
):
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # 임시로 sentence 추가해보고 길이 측정
        test_chunk = (current_chunk + " " + sentence).strip()

        # 1) 아직 최소 chunk 길이에 못 미치면 일단 계속 붙임
        if len(test_chunk) < min_chunk_size:
            current_chunk = test_chunk
            continue

        # 2) 최소 길이는 지켰지만 chunk_size를 넘어가면 새 chunk 생성
        if len(test_chunk) > chunk_size:
            chunks.append(current_chunk.strip())

            # === overlap 적용 ===
            if chunk_overlap > 0:
                prev = chunks[-1]
                overlap_text = prev[-chunk_overlap:]
                current_chunk = (overlap_text + " " + sentence).strip()
            else:
                current_chunk = sentence
        else:
            # chunk_size는 넘지 않으므로 그냥 문장 추가
            current_chunk = test_chunk

    # 마지막 chunk 처리
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# ===== 메인 실행코드 =====

filename = "cleaned_data_Cell"
df = pd.read_csv(f"{filename}.csv")

df["abstract"] = df["abstract"].fillna("").astype(str)
df["step_content"] = df["step_content"].fillna("").astype(str)
df["guidelines"] = df.get("guidelines", "").fillna("").astype(str)
# 🔹 url과 title 컬럼 추가 처리
df["url"] = df.get("url", "").fillna("").astype(str)
df["title"] = df.get("title", "").fillna("").astype(str)

output_rows = []

for _, row in df.iterrows():
    protocol_id = str(row["protocol_id"]).strip()

    combined_text = (
        "<abstract>\n" + row["abstract"] + "\n"
        "<step_content>\n" + row["step_content"] + "\n"
        "<guidelines>\n" + row["guidelines"]
    )

    # 1) 문장 단위 split
    sentences = split_into_sentences(combined_text)

    # 2) 문장 기반 chunk + 최소 길이 적용
    chunks = create_sentence_chunks(
        sentences,
        chunk_size=400,
        chunk_overlap=100,
        min_chunk_size=300
    )

    # 3) CSV 저장용 구조
    for idx, chunk in enumerate(chunks):
        output_rows.append({
            "protocol_id": f"{protocol_id}",
            "url": row["url"],
            "title": row["title"],
            "chunking_id": f"{filename}_chunk_{protocol_id}_{idx}",
            "text": chunk.replace(" ,", "")
        })

# ===== CSV 저장 =====
output_df = pd.DataFrame(output_rows)
output_df.to_csv(f"chunked_semantic_text_{filename}.csv", index=False)