import pandas as pd
import re
import os
from pathlib import Path
from tqdm import tqdm

# ==========================================
# 설정
# ==========================================
# 기본 파일 경로: 프로젝트 루트 기준
#  - normalization 파이프라인(00_pmc_normalization_pipeline)에서 호출될 때는
#    DATA_DIR 이 pmc_csv/filtered 로 override 되므로,
#    여기 값은 단독 실행 시 기본값 역할만 한다.
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed" / "pubmed" / "pmc_csv" / "filtered"

REF_FILE = "references.csv"
ARTICLE_FILE = "articles.csv"
# 기능 ㅣ 저널 논문 제목 정규화 -> article_enriched.csv 와 references.csv 의 제목 비교 용이하게
# ==========================================
# 정규화 함수 (핵심 로직)
# ==========================================
def normalize_text(text):
    """
    제목 정규화:
    1. 문자열이 아니면 빈 문자열 반환
    2. 소문자로 변환
    3. 알파벳(a-z)과 숫자(0-9)를 제외한 모든 문자(공백, 특수문자) 제거
    예: "COVID-19: A Review." -> "covid19areview"
    """
    if pd.isna(text) or text == "":
        return ""
    
    text = str(text).lower()
    # 정규표현식: 알파벳과 숫자가 아닌 것은 모두 제거
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def process_csv(filename, title_col, new_col):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"⚠️ 파일이 없습니다: {filename}")
        return

    print(f"loading {filename}...")
    df = pd.read_csv(filepath)
    
    # 정규화 적용
    print(f"Processing titles in {filename}...")
    tqdm.pandas() # 진행바 활성화
    df[new_col] = df[title_col].progress_apply(normalize_text)
    
    # 결과 저장 (덮어쓰기 혹은 새 파일)
    output_path = os.path.join(DATA_DIR, filename) # 원본 덮어쓰기
    df.to_csv(output_path, index=False)
    print(f"✅ 저장 완료: {output_path} (컬럼 추가됨: {new_col})\n")

# ==========================================
# 실행
# ==========================================
if __name__ == "__main__":
    # 1. References 파일 처리 (참고문헌 제목 정규화)
    process_csv(REF_FILE, title_col='ref_title', new_col='ref_title_norm')

    # 2. Article 파일 처리 (타겟 논문 제목 정규화)
    # 주의: 타겟 논문 쪽에도 정규화된 제목이 있어야 비교가 가능합니다!
    process_csv(ARTICLE_FILE, title_col='title', new_col='title_norm')
