'''
.fine-tuning\data\raw\t_figures_with_result_desc_v3.csv 파일에서 
fig_caption, fig_url을 GPT-4o-mini에 전달하여
실험결과 이미지 설명 텍스트를 생성하고 해당 텍스트를 
.fine-tuning\data\raw\t_figures_with_result_desc_v3__explain.csv파일에에 'explan_img'라는 이름의 새로운 컬럼을 만들고 거기에 삽입하기. 
이미지url이 없는 경우엔 건너뛰기
top 50개 row만 처리하고 중단(test용)
영어로 생성하기

Prompt 해석:  "이 실험 결과 이미지를 자세히 설명해 주세요. 이미지에 표시된 실험 결과, 데이터, 그래프 또는 시각적 요소를 구체적으로 설명해 주세요. 답변은 영어로 제공하세요. 없는 내용을 확대 해석하지 말아주세요."
'''

import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import time

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 확인
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# 파일 경로 설정
script_dir = Path(__file__).parent.parent  # .fine-tuning/code -> .fine-tuning
input_csv = script_dir / "data" / "raw" / "t_figures_with_result_desc_v3.csv"
output_csv = script_dir / "data" / "raw" / "t_figures_with_result_desc_v3__explain.csv"


PROMPT = "Please describe in detail the image of the results of this experiment. Please describe in detail the results of the experiment, data, graphs, or visual elements shown in the image. Please provide your answers in English. Please do not zoom in on what is not there."


def generate_image_explanation(fig_caption: str, fig_url: str) -> str:
    """
    이미지와 캡션을 GPT-4o-mini에 전달하여 이미지 설명 텍스트 생성
    
    Args:
        fig_caption: 이미지 캡션
        fig_url: 이미지 URL
        
    Returns:
        생성된 이미지 설명 텍스트
    """
    # 캡션 정보를 포함한 프롬프트 생성 (영어)
    enhanced_prompt = f"""Image caption information:
{fig_caption}

Please refer to the caption information above and {PROMPT}"""
    
    try:
        # OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": enhanced_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": fig_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # 응답 내용 반환
        explanation = response.choices[0].message.content
        return explanation
        
    except Exception as e:
        print(f"❌ API 호출 오류: {e}")
        return None


def main():
    """메인 함수"""
    print(f"📂 입력 파일: {input_csv}")
    print(f"📂 출력 파일: {output_csv}")
    print()
    
    # CSV 파일 읽기
    if not input_csv.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_csv}")
    
    print("📖 CSV 파일 읽는 중...")
    df = pd.read_csv(input_csv)
    print(f"✅ 총 {len(df)}개 행 로드 완료")
    print()
    
    # 출력 파일이 이미 존재하는 경우 읽기 (중단된 부분부터 계속 처리하기 위해)
    if output_csv.exists():
        print(f"📖 기존 출력 파일 읽는 중: {output_csv}")
        df_output = pd.read_csv(output_csv)
        
        # explan_img 컬럼이 없으면 추가
        if 'explan_img' not in df_output.columns:
            df_output['explan_img'] = None
        
        # 이미 처리된 행 확인 (explan_img가 비어있지 않은 행)
        processed_mask = df_output['explan_img'].notna() & (df_output['explan_img'] != '')
        processed_count = processed_mask.sum()
        print(f"✅ 이미 처리된 행: {processed_count}개")
        
        # df_output을 df에 병합 (explan_img 컬럼만)
        if 'explan_img' in df_output.columns:
            df = df.merge(df_output[['fig_id', 'explan_img']], on='fig_id', how='left')
    else:
        # 출력 파일이 없으면 새로 생성
        df['explan_img'] = None
        print("✅ 새로운 출력 파일 생성")
    
    print()
    
    # 처리할 행 수 제한 (test용: top 50개)
    max_rows = 50
    total_rows = len(df)
    rows_to_process = min(max_rows, total_rows)
    
    print(f"🔢 처리 대상: 처음 {rows_to_process}개 행")
    print()
    
    # 처리 통계
    processed = 0
    skipped = 0
    failed = 0
    
    # 각 행 처리
    for idx, row in df.head(rows_to_process).iterrows():
        fig_id = row['fig_id']
        fig_caption = row['fig_caption'] if pd.notna(row['fig_caption']) else ""
        fig_url = row['fig_url'] if pd.notna(row['fig_url']) else ""
        
        # 이미 처리된 행은 건너뛰기
        if pd.notna(df.loc[idx, 'explan_img']) and df.loc[idx, 'explan_img'] != '':
            print(f"[{idx+1}/{rows_to_process}] ⏭️  이미 처리됨: {fig_id}")
            processed += 1
            continue
        
        # 이미지 URL이 없는 경우 건너뛰기
        if not fig_url or fig_url.strip() == "":
            print(f"[{idx+1}/{rows_to_process}] ⏭️  URL 없음: {fig_id}")
            skipped += 1
            df.loc[idx, 'explan_img'] = ""  # 빈 문자열로 표시
            # 저장
            try:
                df.to_csv(output_csv, index=False)
                print(f"   💾 저장 완료")
            except Exception as e:
                print(f"   ⚠️  저장 실패: {e}")
            continue
        
        # 이미지 설명 생성
        print(f"[{idx+1}/{rows_to_process}] 🔄 처리 중: {fig_id}")
        print(f"   URL: {fig_url[:80]}...")
        
        explanation = generate_image_explanation(fig_caption, fig_url)
        
        if explanation:
            df.loc[idx, 'explan_img'] = explanation
            print(f"   ✅ 생성 완료 ({len(explanation)}자)")
            processed += 1
        else:
            print(f"   ❌ 생성 실패")
            df.loc[idx, 'explan_img'] = ""  # 실패한 경우 빈 문자열
            failed += 1
        
        # 진행 상황 저장 (매번 하나씩 저장)
        try:
            df.to_csv(output_csv, index=False)
            print(f"   💾 저장 완료")
        except Exception as e:
            print(f"   ⚠️  저장 실패: {e}")
        
        # API 호출 제한을 위한 짧은 대기
        time.sleep(0.5)
    
    # 최종 저장
    print(f"\n💾 최종 저장 중...")
    df.to_csv(output_csv, index=False)
    print("✅ 저장 완료")
    print()
    
    # 결과 출력
    print("=" * 60)
    print("📊 처리 결과")
    print("=" * 60)
    print(f"총 처리 대상: {rows_to_process}개")
    print(f"✅ 성공: {processed}개")
    print(f"⏭️  건너뜀 (URL 없음): {skipped}개")
    print(f"❌ 실패: {failed}개")
    print()
    print(f"📁 결과 파일: {output_csv}")


if __name__ == "__main__":
    main()
