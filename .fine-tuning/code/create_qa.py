'''
.fine-tuning\data\raw\t_figures_with_result_desc_v3__explain.csv 파일에서 
explan_img, result_desc를 바탕으로 "복잡한 추론"을 할 수 있도록 학습시키는 질문(Q)을 생성하고 
.fine-tuning\data\raw\t_figures_with_result_desc_v3__explain.csv 파일에 Q컬럼 생성 및 데이터 추가하고,json으로 데이터셋 만들기
해당 답변은 반드시 result_desc 원문 그대로이고, 질문은 explan_img를 바탕으로 result_desc 원문대로 답변할만한 질문을 생성해야 함. 
최종 대화셋 생성 시: 질문을 영어로 생성하고, 답변은 result_desc 원문 그대로 넣기.
- 1개의row당 1개의 질문 생성. 생성 후 CSV에 각각의 데이터 추가.

.fine-tuning\data\dataset\qa_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl 파일에 저장하기
user: explan_img를 바탕으로 result_desc 원문대로 답변할만한 질문(gpt4O-mini로 생성)
assistant: result_desc 원문 그대로

### 데이터 형식

```json
{
  "messages": [
    {
      "role": "system",
      "content": [
        {
          "type": "text",
          "text": "You are an expert in life science experiments. It is your role to explain and interpret the user's experimental results."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "explan_img(이미지 설명 텍스트) + Q(explan_img를 바탕으로 result_desc 원문대로 답변할만한 질문)
        },
        {
          "type": "image"
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "result_desc 원문 그대로"
        }
      ]
    }
  ]
}
```
'''

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
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
input_csv = script_dir / "data" / "raw" / "t_figures_with_result_desc_v3__explain.csv"
dataset_dir = script_dir / "data" / "dataset"
dataset_dir.mkdir(parents=True, exist_ok=True)

# JSONL 출력 파일 경로
output_jsonl = dataset_dir / f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

# 질문 생성 프롬프트
QUESTION_GENERATION_PROMPT = """You are an expert in life science experiments. Based on the image description provided, generate a complex reasoning question that requires step-by-step analysis to answer.

The question should:
1. Be based on the image description (explan_img)
2. Require complex reasoning and step-by-step thinking to answer
3. Be answerable using the provided result description (result_desc)
4. Be written in English
5. Be challenging and require deep understanding of the experimental results

Image Description:
{explan_img}

Result Description (this is the answer that should be given):
{result_desc}

Generate a complex reasoning question in English that can be answered using the result description above."""


def generate_question(explan_img: str, result_desc: str) -> str:
    """
    explan_img와 result_desc를 바탕으로 복잡한 추론 질문 생성
    
    Args:
        explan_img: 이미지 설명 텍스트 (영어)
        result_desc: 저자 해석 부분 (영어)
        
    Returns:
        생성된 질문 (영어)
    """
    prompt = QUESTION_GENERATION_PROMPT.format(
        explan_img=explan_img,
        result_desc=result_desc
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        question = response.choices[0].message.content.strip()
        return question
        
    except Exception as e:
        print(f"❌ 질문 생성 오류: {e}")
        return None


def create_jsonl_entry(explan_img: str, question: str, result_desc: str, fig_id: str = None, fig_url: str = None) -> dict:
    """
    JSONL 형식의 메시지 엔트리 생성
    
    주석 요구사항 (라인 14-49):
    - user content text: "explan_img(이미지 설명 텍스트) + Q(explan_img를 바탕으로 result_desc 원문대로 답변할만한 질문)"
    - user content에 image 포함
    - assistant: "result_desc 원문 그대로"
    
    Args:
        explan_img: 이미지 설명 텍스트
        question: 생성된 질문 (Q)
        result_desc: 답변 (result_desc 원문 그대로)
        fig_id: 그림 ID (선택사항, 추적용)
        fig_url: 이미지 URL (선택사항)
        
    Returns:
        JSONL 형식의 메시지 딕셔너리
    """
    # user content 구성: explan_img(이미지 설명 텍스트) + Q(질문)
    user_content = [
        {
            "type": "text",
            "text": f"{explan_img}\n\n{question}"
        }
    ]
    
    # 이미지 URL이 있으면 추가 (주석의 "type": "image"는 실제로는 image_url 형식 사용)
    if fig_url and fig_url.strip():
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": fig_url
            }
        })
    
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are an expert in life science experiments. It is your role to explain and interpret the user's experimental results."
                }
            ]
        },
        {
            "role": "user",
            "content": user_content
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": result_desc  # result_desc 원문 그대로
                }
            ]
        }
    ]
    
    entry = {"messages": messages}
    
    # fig_id가 있으면 메타데이터로 추가
    if fig_id:
        entry["fig_id"] = fig_id
    
    return entry


def main():
    """메인 함수"""
    print(f"📂 입력 파일: {input_csv}")
    print(f"📂 출력 JSONL: {output_jsonl}")
    print()
    
    # CSV 파일 읽기
    if not input_csv.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_csv}")
    
    print("📖 CSV 파일 읽는 중...")
    df = pd.read_csv(input_csv)
    print(f"✅ 총 {len(df)}개 행 로드 완료")
    print()
    
    # Q, A 컬럼이 없으면 추가
    if 'Q' not in df.columns:
        df['Q'] = None
    if 'A' not in df.columns:
        df['A'] = None
    
    # 이미 처리된 행 확인
    processed_mask = df['Q'].notna() & (df['Q'] != '')
    processed_count = processed_mask.sum()
    print(f"✅ 이미 처리된 행: {processed_count}개")
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
    
    # JSONL 파일 열기 (append 모드)
    jsonl_file = open(output_jsonl, 'w', encoding='utf-8')
    
    try:
        # 각 행 처리 (처음 50개만)
        for idx, row in df.head(rows_to_process).iterrows():
            fig_id = row['fig_id']
            explan_img = row['explan_img'] if pd.notna(row['explan_img']) else ""
            result_desc = row['result_desc'] if pd.notna(row['result_desc']) else ""
            fig_url = row['fig_url'] if pd.notna(row['fig_url']) else ""
            
            # 이미 처리된 행은 건너뛰기
            if pd.notna(df.loc[idx, 'Q']) and df.loc[idx, 'Q'] != '':
                print(f"[{idx+1}/{rows_to_process}] ⏭️  이미 처리됨: {fig_id}")
                processed += 1
                # CSV 저장 (건너뛰는 경우에도 저장)
                try:
                    df.to_csv(input_csv, index=False)
                except Exception as e:
                    print(f"   ⚠️  CSV 저장 실패: {e}")
                continue
            
            # 필수 데이터 확인
            if not explan_img or explan_img.strip() == "":
                print(f"[{idx+1}/{rows_to_process}] ⏭️  explan_img 없음: {fig_id}")
                skipped += 1
                # CSV 저장 (건너뛰는 경우에도 저장)
                try:
                    df.to_csv(input_csv, index=False)
                except Exception as e:
                    print(f"   ⚠️  CSV 저장 실패: {e}")
                continue
            
            if not result_desc or result_desc.strip() == "":
                print(f"[{idx+1}/{rows_to_process}] ⏭️  result_desc 없음: {fig_id}")
                skipped += 1
                # CSV 저장 (건너뛰는 경우에도 저장)
                try:
                    df.to_csv(input_csv, index=False)
                except Exception as e:
                    print(f"   ⚠️  CSV 저장 실패: {e}")
                continue
            
            # 질문 생성
            print(f"[{idx+1}/{rows_to_process}] 🔄 처리 중: {fig_id}")
            question = generate_question(explan_img, result_desc)
            
            if question:
                # CSV에 Q, A 추가
                df.loc[idx, 'Q'] = question
                df.loc[idx, 'A'] = result_desc  # 원문 그대로
                
                # JSONL 엔트리 생성 및 저장
                jsonl_entry = create_jsonl_entry(explan_img, question, result_desc, fig_id, fig_url)
                jsonl_file.write(json.dumps(jsonl_entry, ensure_ascii=False) + '\n')
                jsonl_file.flush()  # 즉시 디스크에 쓰기
                
                print(f"   ✅ 질문 생성 완료 ({len(question)}자)")
                processed += 1
            else:
                print(f"   ❌ 질문 생성 실패")
                failed += 1
            
            # CSV 저장 (매번 저장 - 메모리 절약)
            try:
                df.to_csv(input_csv, index=False)
                print(f"   💾 CSV 저장 완료")
            except Exception as e:
                print(f"   ⚠️  CSV 저장 실패: {e}")
            
            # API 호출 제한을 위한 짧은 대기
            time.sleep(0.5)
    
    finally:
        jsonl_file.close()
    
    # 최종 CSV 저장
    print(f"\n💾 최종 CSV 저장 중...")
    df.to_csv(input_csv, index=False)
    print("✅ 저장 완료")
    print()
    
    # 결과 출력
    print("=" * 60)
    print("📊 처리 결과")
    print("=" * 60)
    print(f"총 처리 대상: {rows_to_process}개")
    print(f"✅ 성공: {processed}개")
    print(f"⏭️  건너뜀: {skipped}개")
    print(f"❌ 실패: {failed}개")
    print()
    print(f"📁 CSV 파일: {input_csv}")
    print(f"📁 JSONL 파일: {output_jsonl}")


if __name__ == "__main__":
    main()
