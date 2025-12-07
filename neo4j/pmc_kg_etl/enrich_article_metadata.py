"""
enrich_article_metadata_chunked.py

목적: 
  대용량 article.csv를 조금씩 읽어서(Chunk), LLM으로 초록을 분석한 뒤,
  상세 정보를 추가하여 article_enriched.csv에 이어 씁니다.
  
  * 메모리 절약: 전체 파일을 로드하지 않음
  * 이어하기: 중단 시 저장된 곳부터 자동 재개
  * 안전성: 배치 단위 자동 저장

입력: import/article.csv
출력: import/article_enriched.csv
"""

import pandas as pd
import json
import os
from tqdm import tqdm
from openai import OpenAI

# ==============================================================================
# 1. 설정
# ==============================================================================
INPUT_FILE = "C:\\dev\\study\\skn18_fianl-2team\\SKN18-FINAL-2TEAM\\data\\pmc_data\\pmc\\articles.csv"
OUTPUT_FILE = "import/article_enriched.csv"
BATCH_SIZE = 20  # 한 번에 처리할 논문 수 (LLM 속도 고려하여 작게 설정 권장)

client = OpenAI() # API Key는 환경변수(OPENAI_API_KEY)에 설정되어 있다고 가정

# ==============================================================================
# 2. 헬퍼 함수
# ==============================================================================
def get_total_lines(filepath):
    """진행률 표시를 위해 전체 라인 수 계산"""
    if not os.path.exists(filepath): return 0
    print("📊 전체 데이터 크기 확인 중...")
    with open(filepath, "rb") as f:
        return sum(1 for _ in f) - 1 # 헤더 제외

def analyze_abstract(abstract):
    """LLM을 사용하여 초록에서 상세 토픽과 연구 설계를 추출"""
    if not isinstance(abstract, str) or len(abstract) < 30:
        return "", ""

    prompt = f"""
    Analyze the following scientific abstract to extract metadata for a Knowledge Graph.
    
    1. 'detailed_topics': Extract **5 to 10** specific technical keywords.
        - Focus on: Target proteins (e.g., PH20), Genes, Specific diseases, Drugs/Chemicals, Biological mechanisms, or Signaling pathways.
        - AVOID generic terms like "study", "analysis", "result", "method".
    
    2. 'detailed_design': Identify the specific study designs. **Select ALL that apply** from the standard categories below:
        - [Basic Research]: In Vitro, In Vivo, Ex Vivo, In Silico (Simulation), Molecular Docking, Cryo-EM/Crystallography
        - [Clinical Research]: Clinical Trial (Phase I/II/III/IV), Randomized Controlled Trial (RCT), Cohort Study, Case-Control Study, Case Report, Observational Study
        - [Review/Synthesis]: Systematic Review, Meta-Analysis, Narrative Review, Scoping Review
        - [Other]: Bioinformatics Analysis, Protocol, Editorial
    
    Return ONLY a valid JSON object:
    {{
        "topics": ["Term1", "Term2", "...", "Term10"],
        "design": ["In Vitro", "In Vivo"]
    }}
    
    Abstract:
    {abstract[:3000]}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = json.loads(response.choices[0].message.content)
        
        topics_str = ";".join(content.get("topics", []))
        design_str = ";".join(content.get("design", []))
        return topics_str, design_str
    
    except Exception as e:
        # 에러 발생 시 빈 값 반환하고 계속 진행
        return "", ""

# ==============================================================================
# 3. 메인 프로세스
# ==============================================================================
def run_enrichment():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 입력 파일 없음: {INPUT_FILE}")
        return

    # 1. 이어하기 지점 확인
    start_row = 0
    if os.path.exists(OUTPUT_FILE):
        # 이미 생성된 파일이 있다면, 그 라인 수만큼 건너뜀
        start_row = get_total_lines(OUTPUT_FILE)
        if start_row > 0:
            print(f"🔄 이어하기: 기존 {start_row:,}개 데이터 이후부터 시작합니다.")
    else:
        print("🆕 처음부터 시작합니다.")

    # 2. 전체 작업량 계산
    total_rows = get_total_lines(INPUT_FILE)
    
    if start_row >= total_rows:
        print("✅ 이미 모든 데이터 처리가 완료되었습니다.")
        return

    # 3. 배치 처리 시작
    # skiprows: 헤더(0번)는 남기고, 이미 처리한 1~start_row까지 건너뜀
    skip_range = range(1, start_row + 1) if start_row > 0 else None
    
    reader = pd.read_csv(INPUT_FILE, chunksize=BATCH_SIZE, skiprows=skip_range)
    
    print(f"🚀 분석 시작 (Batch Size: {BATCH_SIZE})...")
    
    # tqdm 진행바 설정
    with tqdm(total=total_rows, initial=start_row, unit="paper") as pbar:
        for chunk_df in reader:
            # 배치 내 데이터 처리
            new_topics = []
            new_designs = []
            
            for idx, row in chunk_df.iterrows():
                topics, design = analyze_abstract(row.get('abstract', ''))
                new_topics.append(topics)
                new_designs.append(design)
            
            # 결과 컬럼 추가
            chunk_df['detailed_topics'] = new_topics
            chunk_df['detailed_design'] = new_designs
            
            # 파일 저장 (Append 모드)
            # 처음 시작할 때만 헤더를 쓰고, 이어할 때는 헤더 없이 내용만 추가
            is_header = (start_row == 0)
            chunk_df.to_csv(OUTPUT_FILE, mode='a', header=is_header, index=False)
            
            # 상태 업데이트
            start_row += len(chunk_df) # 다음 배치를 위해 헤더 체크용 변수 업데이트
            pbar.update(len(chunk_df))

    print(f"\n✅ 작업 완료! 저장된 파일: {OUTPUT_FILE}")

if __name__ == "__main__":
    # import 폴더 확인
    if not os.path.exists("import"):
        os.makedirs("import")
        
    run_enrichment()