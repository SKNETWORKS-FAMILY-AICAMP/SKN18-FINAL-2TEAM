"""
enrich_article_metadata_chunked.py

목적: 
  대용량 article.csv를 조금씩 읽어서(Chunk), LLM으로 초록을 분석한 뒤,
  상세 정보를 추가하여 article_enriched.csv에 이어 씁니다.
  
  * 메모리 절약: 전체 파일을 로드하지 않음
  * 이어하기: 중단 시 저장된 곳부터 자동 재개
  * 안전성: 배치 단위 자동 저장

입력: articles.csv
출력:
  - import/article_enriched.csv        (요약 + detailed_topics/design 문자열 컬럼 포함)
  - import/article_topics.csv         (정규화: pmid, topic 한 줄씩)
  - import/article_designs.csv        (정규화: pmid, design 한 줄씩)
"""

import pandas as pd
import json
import os
from pathlib import Path
from tqdm import tqdm
from openai import OpenAI

# ======================================================================
# 1. 설정
# ======================================================================
# pmid 필터링이 끝난 PMC 기사 파일(articles.csv)을 사용하고,
# 같은 디렉터리 안에 article_enriched.csv / article_topics.csv / article_designs.csv 를 생성한다.
ROOT_DIR = Path(__file__).resolve().parents[2]
END_DIR = ROOT_DIR / "data" / "entities" / "pubmed"
FILTERED_DIR = ROOT_DIR / "data" / "pubmed" / "pmc_csv" / "filtered"


INPUT_FILE = FILTERED_DIR / "articles.csv"
OUTPUT_FILE = END_DIR / "ts_article_enriched.csv"
# TOPIC_FILE = END_DIR / "tsarticle_topics.csv"
# DESIGN_FILE = END_DIR / "ts_article_designs.csv"

BATCH_SIZE = 20  # 한 번에 처리할 논문 수 (LLM 속도 고려하여 작게 설정 권장)

client = OpenAI()  # OPENAI_API_KEY는 환경변수에 있다고 가정


# ======================================================================
# 2. 헬퍼 함수
# ======================================================================
def get_total_lines(filepath: str) -> int:
    """진행률 표시를 위해 전체 라인 수 계산"""
    if not os.path.exists(filepath):
        return 0
    print("📊 전체 데이터 크기 확인 중...")
    with open(filepath, "rb") as f:
        return sum(1 for _ in f) - 1  # 헤더 제외


def analyze_abstract(abstract: str):
    """
    LLM을 사용하여 초록에서:
      - summary (2~3문장 요약)
      - topics  (5~10개 키워드, 리스트)
      - design  (연구 설계 카테고리, 리스트)
    를 추출.
    """
    if not isinstance(abstract, str) or len(abstract) < 30:
        return "", [], []

    prompt = f"""
You are an expert biomedical curator. Analyze the following scientific abstract
and return structured metadata as JSON.

1. "summary": Write a concise summary (2–3 sentences, max 80–120 words) that captures
   the main goal, methods, and key findings.

2. "topics": Extract 5–10 biomedical target/domain entities and normalize them to
   standard concept names used in UMLS or PrimeKG-style biomedical knowledge graphs.

   - Focus on:
     • Target proteins or genes (e.g., "PDCD1 (PD-1)", "EGFR")
     • Specific diseases (e.g., "Non-Small Cell Lung Carcinoma")
     • Drugs or chemicals (e.g., "Pembrolizumab", "Doxorubicin")
     • Biological mechanisms or signaling pathways (e.g., "JAK-STAT signaling pathway")

   - For each topic, DO:
     • Choose a canonical, KG-friendly label (UMLS/MeSH/PrimeKG style), not a vague description.
     • Prefer official gene symbols, standard disease names, or drug names.
     • If multiple synonyms exist, pick ONE representative canonical name.

   - AVOID:
     • Generic words like "study", "analysis", "result", "method", "effect".
     • Very broad terms like "cancer", "inflammation" unless that is clearly the main concept.

   - Output each topic as a single normalized concept name string (1–6 words) in English.


3. "design": Identify ALL applicable study designs from the list below.
   Return only the exact labels, do not invent new ones.

   [Basic Research]
   - "In Vitro"
   - "In Vivo"
   - "Ex Vivo"
   - "In Silico (Simulation)"
   - "Molecular Docking"
   - "Cryo-EM/Crystallography"

   [Clinical Research]
   - "Clinical Trial Phase I"
   - "Clinical Trial Phase II"
   - "Clinical Trial Phase III"
   - "Clinical Trial Phase IV"
   - "Randomized Controlled Trial (RCT)"
   - "Cohort Study"
   - "Case-Control Study"
   - "Case Report"
   - "Observational Study"

   [Review/Synthesis]
   - "Systematic Review"
   - "Meta-Analysis"
   - "Narrative Review"
   - "Scoping Review"

   [Other]
   - "Bioinformatics Analysis"
   - "Protocol"
   - "Editorial"
   - "Other"

Return ONLY a valid JSON object with this exact schema:

{{
  "summary": "One paragraph summary...",
  "topics": ["Term1", "Term2", "..."],
  "design": ["In Vitro", "Cohort Study"]
}}

If something is unclear or does not fit, use "Other" in the design list.

Abstract:
{abstract[:3000]}
    """.strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)

        summary = (data.get("summary") or "").strip()

        topics = data.get("topics") or []
        if not isinstance(topics, list):
            topics = []
        # 문자열 리스트만 남김
        topics = [str(t).strip() for t in topics if str(t).strip()]

        design = data.get("design") or []
        if not isinstance(design, list):
            design = []
        design = [str(d).strip() for d in design if str(d).strip()]

        return summary, topics, design

    except Exception as e:
        # 에러 발생 시 빈 값 반환하고 계속 진행
        print(f"[WARN] analyze_abstract error: {e}")
        return "", [], []


# ======================================================================
# 3. 메인 프로세스
# ======================================================================
def run_enrichment():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 입력 파일 없음: {INPUT_FILE}")
        return

    # 1. 이어하기 지점 확인 (OUTPUT_FILE 기준)
    start_row = 0
    if os.path.exists(OUTPUT_FILE):
        start_row = get_total_lines(OUTPUT_FILE)
        if start_row > 0:
            print(f"🔄 이어하기: 기존 {start_row:,}개 데이터 이후부터 시작합니다.")
    else:
        print("🆕 처음부터 시작합니다.")

    # 2. 전체 작업량 계산
    total_rows = get_total_lines(INPUT_FILE)
    if total_rows == 0:
        print("❌ INPUT_FILE이 비어있거나 읽을 수 없습니다.")
        return

    if start_row >= total_rows:
        print("✅ 이미 모든 데이터 처리가 완료되었습니다.")
        return

    # 3. 배치 처리 시작
    # skiprows: 헤더(0번)는 남기고, 이미 처리한 1~start_row까지 건너뜀
    skip_range = range(1, start_row + 1) if start_row > 0 else None
    reader = pd.read_csv(INPUT_FILE, chunksize=BATCH_SIZE, skiprows=skip_range)

    print(f"🚀 분석 시작 (Batch Size: {BATCH_SIZE})...")

    # # topics/design 정규화 테이블 헤더 여부
    # topic_header = not os.path.exists(TOPIC_FILE)
    # design_header = not os.path.exists(DESIGN_FILE)

    # tqdm 진행바
    with tqdm(total=total_rows, initial=start_row, unit="paper") as pbar:
        for chunk_df in reader:
            # 배치 내 데이터 처리
            summaries = []
            topics_str_list = []
            design_str_list = []

            topics_rows = []   # pmid, topic
            designs_rows = []  # pmid, design

            for idx, row in chunk_df.iterrows():
                abstract = row.get("abstract", "")
                pmid = row.get("pmid", "")

                summary, topics, design = analyze_abstract(abstract)

                # 문자열 컬럼용
                topics_str = ";".join(topics)
                design_str = ";".join(design)

                summaries.append(summary)
                topics_str_list.append(topics_str)
                design_str_list.append(design_str)

                # 정규화 테이블용
                for t in topics:
                    topics_rows.append({"pmid": pmid, "topic": t})
                for d in design:
                    designs_rows.append({"pmid": pmid, "design": d})

            # 결과 컬럼 추가
            chunk_df["abstract_summary"] = summaries
            chunk_df["detailed_topics"] = topics_str_list
            chunk_df["detailed_design"] = design_str_list

            # 메인 enriched CSV 저장 (Append)
            is_header = (start_row == 0)
            chunk_df.to_csv(
                OUTPUT_FILE, mode="a", header=is_header, index=False
            )

            # # topics 정규화 테이블 저장
            # if topics_rows:
            #     tdf = pd.DataFrame(topics_rows)
            #     tdf.to_csv(
            #         TOPIC_FILE,
            #         mode="a",
            #         header=topic_header,
            #         index=False,
            #     )
            #     topic_header = False

            # # design 정규화 테이블 저장
            # if designs_rows:
            #     ddf = pd.DataFrame(designs_rows)
            #     ddf.to_csv(
            #         DESIGN_FILE,
            #         mode="a",
            #         header=design_header,
            #         index=False,
            #     )
            #     design_header = False

            # 상태 업데이트
            start_row += len(chunk_df)
            pbar.update(len(chunk_df))

    print(f"\n✅ 작업 완료!")
    print(f"  - 메인: {OUTPUT_FILE}")
    # print(f"  - 토픽 정규화: {TOPIC_FILE}")
    # print(f"  - 설계 정규화: {DESIGN_FILE}")


if __name__ == "__main__":
    # import 폴더 확인
    if not os.path.exists("import"):
        os.makedirs("import")

    run_enrichment()
