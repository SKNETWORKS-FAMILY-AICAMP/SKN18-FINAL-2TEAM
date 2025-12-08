import re
import pandas as pd


# ==============================
# 🔥 1) 표 감지 함수 추가
# ==============================
def detect_table_blocks(text):
    lines = text.split("\n")
    table_blocks = []
    current_block = []

    def is_table_line(line):
        # 빈 줄 제외
        if not line.strip():
            return False
        # 탭 포함: TSV 형태
        if "\t" in line:
            return True
        # 쉼표가 2개 이상 → CSV 형태
        if line.count(",") >= 2:
            return True
        # 공백 2개 이상으로 구분된 열 구조
        if re.search(r"\S+\s{2,}\S+", line):
            return True
        return False

    for line in lines:
        if is_table_line(line):
            current_block.append(line)
        else:
            if current_block:
                table_blocks.append("\n".join(current_block))
                current_block = []
            table_blocks.append(line)

    if current_block:
        table_blocks.append("\n".join(current_block))

    return table_blocks



# ==============================
# 🔥 2) split_into_sentences 수정 (표 블록 우선 처리)
# ==============================
def split_into_sentences(text):
    blocks = detect_table_blocks(text)   # ← 먼저 표 block으로 1차 분리됨
    sentences = []

    for block in blocks:
        # table block이면 그대로 추가 (문장 split 금지)
        if "\n" in block and ("," in block or "\t" in block):
            sentences.append(block)
            continue

        # 🚨 이하 기존 문장 split 로직 그대로 실행
        protected = block

        protected = re.sub(r'(https?://\S+)', r'<URL>\1</URL>', protected)

        protected = re.sub(r'\b(e\.g\.|i\.e\.|etc\.|Fig\.|Fig\s*\d+\.|No\.|no\.)',
                           r'<ABBR>\1</ABBR>', protected)

        protected = re.sub(r'\bNo\.(\s*\d+)', r'<NO>No_DOT\1</NO>', protected)

        protected = re.sub(r'\b(\d+)\.(\s+)', r'<NUM>\1.</NUM>\2', protected)

        protected = re.sub(r'\b([IVXLCDM]+)\.(\s+)',
                           r'<ROMAN>\1.</ROMAN>\2', protected)

        protected = re.sub(
            r'\(([^)]+?)\)',
            lambda m: '(' + m.group(1).replace('.', '<DOT>') + ')',
            protected
        )

        split_sents = re.split(r'(?<=[.!?])\s+(?=[A-Z<])', protected)

        cleaned = []
        for sent in split_sents:
            sent = sent.replace('No_DOT', 'No.')
            sent = sent.replace('<URL>', '').replace('</URL>', '')
            sent = sent.replace('<ABBR>', '').replace('</ABBR>', '')
            sent = sent.replace('<NUM>', '').replace('</NUM>', '')
            sent = sent.replace('<NO>', '').replace('</NO>', '')
            sent = sent.replace('<ROMAN>', '').replace('</ROMAN>', '')
            sent = sent.replace('<DOT>', '.')
            cleaned.append(sent)

        sentences.extend([s for s in cleaned if s.strip()])

    return sentences



# ==============================
# create_sentence_chunks (기존 그대로)
# ==============================
def create_sentence_chunks(
    sentences, 
    chunk_size=400, 
    chunk_overlap=100, 
    min_chunk_size=300
):
    chunks = []
    current_chunk = ""

    for sentence in sentences:

        # TABLE block은 그대로 하나의 chunk로 밀어 넣음
        if "\n" in sentence and ("," in sentence or "\t" in sentence):
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                current_chunk = ""
            chunks.append(sentence)
            continue

        test_chunk = (current_chunk + " " + sentence).strip()

        if len(test_chunk) < min_chunk_size:
            current_chunk = test_chunk
            continue

        if len(test_chunk) > chunk_size:
            chunks.append(current_chunk.strip())
            if chunk_overlap > 0:
                prev = chunks[-1]
                overlap_text = prev[-chunk_overlap:]
                current_chunk = (overlap_text + " " + sentence).strip()
            else:
                current_chunk = sentence
        else:
            current_chunk = test_chunk

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks



# ==============================
# ===== 메인 실행 코드 (동일)
# ==============================
filename = "cleaned_data_Cell"
df = pd.read_csv(f"{filename}.csv")

df["abstract"] = df["abstract"].fillna("").astype(str)
df["step_content"] = df["step_content"].fillna("").astype(str)
df["guidelines"] = df.get("guidelines", "").fillna("").astype(str)
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

    sentences = split_into_sentences(combined_text)

    chunks = create_sentence_chunks(
        sentences,
        chunk_size=400,
        chunk_overlap=100,
        min_chunk_size=300
    )

    for idx, chunk in enumerate(chunks):
        output_rows.append({
            "protocol_id": f"{protocol_id}",
            "url": row["url"],
            "title": row["title"],
            "chunking_id": f"{filename}_chunk_{protocol_id}_{idx}",
            "text": chunk.replace(" ,", "")
        })

output_df = pd.DataFrame(output_rows)
output_df.to_csv(f"chunked_semantic_text_{filename}.csv", index=False)