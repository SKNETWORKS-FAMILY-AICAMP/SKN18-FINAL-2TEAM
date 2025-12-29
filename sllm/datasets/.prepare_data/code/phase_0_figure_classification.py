"""
Phase 0: Figure Type Classification
====================================

목적:
    Figure 이미지를 실험 결과 데이터(그래프/표)인지 분류

입력:
    - t_figures_with_result_desc_v3.csv
      필요 컬럼: [fig_id, fig_url, fig_caption]

처리:
    - GPT Vision API로 이미지 URL 직접 접근
    - 실험 결과 데이터 여부 분류 (is_experiment_result: true/false)

출력:
    - t_figures_with_result_desc_v3.csv (원본에 is_experiment_result 컬럼 추가)

설정:
    - SAMPLE_SIZE: 처리할 샘플 개수 (None = 전체)
    - MODEL: 사용할 OpenAI 모델 (기본: gpt-4o-mini)
"""

import os
import pandas as pd
from openai import OpenAI
from typing import Optional
import time
from pathlib import Path
from tqdm import tqdm

import dotenv
dotenv.load_dotenv()


class FigureClassifier:
    """Figure 이미지를 실험 결과 데이터(그래프/표)인지 분류하는 클래스"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini"
    ):
        """
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 (gpt-4o-mini, gpt-4o 등)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        print(f"✅ Using model: {self.model}")

        # 실험 결과 데이터 분류용 프롬프트
        self.system_prompt = """You are a scientific figure classification assistant.

Your task is to determine if a figure shows experimental result data (graphs or tables with quantitative data).

Classification criteria:
- TRUE: Graphs, charts, plots, or tables showing experimental measurements, comparisons, or statistical results
  (bar graphs, line graphs, scatter plots, heatmaps, data tables, etc.)
- FALSE: Everything else (microscopy images, conceptual diagrams, schematics, protocols, illustrations, model structures, etc.)

Rules:
- Focus on whether the figure contains QUANTITATIVE experimental data
- Experimental result graphs and tables are TRUE
- All other types are FALSE

Output ONLY: true or false"""

        self.user_prompt_template = """Based on the figure and its caption, determine if this is experimental result data (graph/table with quantitative data).

Figure Caption: {caption}

Output ONLY: true or false"""

    def classify_figure(
        self,
        image_url: str,
        caption: str
    ) -> bool:
        """
        Figure가 실험 결과 데이터(그래프/표)인지 분류

        Args:
            image_url: Figure 이미지 URL
            caption: Figure 캡션

        Returns:
            True: 실험 결과 데이터 (그래프/표)
            False: 기타 (현미경 이미지, 모식도 등)
        """
        try:
            # 유저 프롬프트 생성
            user_prompt = self.user_prompt_template.format(caption=caption)

            # GPT Vision API 호출 (URL 직접 사용)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                # NOTE: max_tokens=10은 'true' 또는 'false' 정도의 짧은 응답(이미지 분류 목적 상)을 유도하기 위해 설정됨.
                # 즉 장황한 설명 대신 단순한 이진 결과만을 원할 때 작은 값(예: 10~16)을 사용.
                max_tokens=10,
                temperature=0
            )

            # 응답 파싱
            result = response.choices[0].message.content.strip().lower()

            # true/false 변환
            if "true" in result:
                return True
            elif "false" in result:
                return False
            else:
                print(f"Warning: Unexpected response '{result}', defaulting to False")
                return False

        except Exception as e:
            print(f"Error classifying {image_url}: {str(e)}")
            return False

    def process_batch(
        self,
        input_csv: str,
        output_csv: str,
        sample_size: Optional[int] = None,
        resume: bool = True
    ) -> pd.DataFrame:
        """
        CSV 파일의 Figure들을 배치 분류

        Args:
            input_csv: 입력 CSV (t_figures_with_result_desc_v3.csv)
            output_csv: 출력 CSV (같은 파일에 컬럼 추가)
            sample_size: 처리할 샘플 개수 (None = 전체)
            resume: True면 기존 결과에서 이어서 진행

        Returns:
            결과 DataFrame
        """
        # 입력 데이터 로드
        print(f"\n📂 Loading data from: {input_csv}")
        df = pd.read_csv(input_csv)

        # 첫 번째 컬럼이 무명 인덱스인 경우 fig_id로 변환
        if df.columns[0] == 'Unnamed: 0' or df.columns[0] == '':
            df.rename(columns={df.columns[0]: 'fig_id'}, inplace=True)

        print(f"   Total figures: {len(df)}")

        # 필수 컬럼 확인
        required_cols = ['fig_id', 'fig_url', 'fig_caption']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # is_experiment_result 컬럼 추가 (없으면)
        if 'is_experiment_result' not in df.columns:
            df['is_experiment_result'] = None
            print(f"   Added column: is_experiment_result")

        # 샘플 크기 제한
        if sample_size:
            df = df.head(sample_size)
            print(f"   Processing sample: {len(df)} figures")

        # 미처리 데이터 필터링
        if resume:
            unprocessed_df = df[df['is_experiment_result'].isna()]
            processed_count = len(df) - len(unprocessed_df)
            if processed_count > 0:
                print(f"   Resuming: {processed_count} figures already processed")
            df_to_process = unprocessed_df
            print(f"   Remaining: {len(df_to_process)} figures to process")
        else:
            df_to_process = df

        if len(df_to_process) == 0:
            print("✅ All data already processed!")
            return df

        # 각 Figure 처리
        print("\n🔄 Classifying figures...")
        for idx in tqdm(df_to_process.index, desc="Progress"):
            row = df.loc[idx]
            fig_id = row['fig_id']
            fig_url = row['fig_url']
            fig_caption = row.get('fig_caption', '')

            # URL이 없으면 스킵
            if pd.isna(fig_url) or not fig_url:
                print(f"⚠️  Skipping {fig_id}: No URL")
                df.loc[idx, 'is_experiment_result'] = False
                continue

            # 분류 실행
            is_experiment_result = self.classify_figure(fig_url, fig_caption)

            # 결과 저장 (원본 DataFrame에)
            df.loc[idx, 'is_experiment_result'] = is_experiment_result

            # 매 건마다 저장 (데이터 손실 방지)
            df.to_csv(output_csv, index=False)

            # API Rate limit 방지
            time.sleep(0.3)

        print(f"\n✅ Processing complete!")

        # 통계 출력
        self._print_statistics(df)

        return df

    def _print_statistics(self, df: pd.DataFrame):
        """결과 통계 출력"""
        print("\n" + "="*60)
        print("📊 STATISTICS")
        print("="*60)

        total = len(df[df['is_experiment_result'].notna()])
        experiment_true = len(df[df['is_experiment_result'] == True])
        experiment_false = len(df[df['is_experiment_result'] == False])

        if total > 0:
            print(f"Total classified: {total}")
            print(f"  - Experimental result data (TRUE):  {experiment_true} ({experiment_true/total*100:.1f}%)")
            print(f"  - Other (FALSE):                    {experiment_false} ({experiment_false/total*100:.1f}%)")
        else:
            print("No classifications yet.")
        print("="*60)


# ============================================================================
# 실행 스크립트
# ============================================================================
def main(
    sample_size: Optional[int] = 50,
    model: str = "gpt-4o-mini",
    resume: bool = True
):
    """
    메인 실행 함수

    Args:
        sample_size: 처리할 샘플 개수 (None = 전체, 기본값: 50)
        model: 사용할 OpenAI 모델 (기본값: gpt-4o-mini)
        resume: 중단된 작업 이어서 실행 여부 (기본값: True)
    """
    # OpenAI API 키 확인
    API_KEY = os.getenv("OPENAI_API_KEY")
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # 경로 설정
    BASE_DIR = Path(__file__).parent.parent
    INPUT_CSV = BASE_DIR / "data" / "raw" / "t_figures_with_result_desc_v3__graph.csv"
    OUTPUT_CSV = INPUT_CSV  # 같은 파일에 컬럼 추가

    # 입력 파일 존재 확인
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    # 처리기 초기화
    print("\n" + "="*60)
    print("🚀 Phase 0: Figure Classification")
    print("="*60)
    print(f"File:   {INPUT_CSV.name}")
    print(f"Model:  {model}")
    print(f"Sample: {sample_size if sample_size else 'ALL'}")
    print(f"Resume: {resume}")
    print("="*60)

    classifier = FigureClassifier(
        api_key=API_KEY,
        model=model
    )

    # 배치 처리 실행
    results_df = classifier.process_batch(
        input_csv=str(INPUT_CSV),
        output_csv=str(OUTPUT_CSV),
        sample_size=sample_size,
        resume=resume
    )

    print(f"\n💾 Results saved to: {OUTPUT_CSV}")
    print(f"\n✅ Done! Classified {len(results_df[results_df['is_experiment_result'].notna()])} figures")
    print("\n다음 단계: Phase 1에서 is_experiment_result=true인 Figure에 대해 설명 생성")


# ============================================================================
# 스크립트 실행 시
# ============================================================================
if __name__ == "__main__":
    # ========================================
    # 🔧 여기서 설정 변경
    # ========================================

    SAMPLE_SIZE = 10        # 처리할 샘플 개수 (None = 전체)
    MODEL = "gpt-4o-mini"   # 사용할 모델 (gpt-4o-mini, gpt-4o 등)
    RESUME = True           # 중단된 작업 이어서 실행 여부

    # ========================================

    main(
        sample_size=SAMPLE_SIZE,
        model=MODEL,
        resume=RESUME
    )
