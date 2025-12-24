# Gemma-3 멀티모달 LLM 파인튜닝 가이드

## 1. 데이터셋 만들기

**목표**: 다음 형식대로 데이터 추출

### 데이터 형식
- 구글 공식홈페이지의 gemma-3 파인튜닝 예시 데이터 형식
 
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
          "text": "explan_img(이미지 설명 텍스트) + Q(explan_img를 바탕으로 result_desc 원문대로 답변할만한 질문)"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "이미지 URL"
          }
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

### 데이터 생성 방법

- **실험결과 이미지 설명 텍스트**: 이미지와 캡션을 GPT-4o-mini에 전달하여 생성 (`explan_img`)
- **질문 생성**: `explan_img`와 `result_desc`를 바탕으로 GPT-4o-mini로 복잡한 추론 질문 생성
  - 질문 유형: **복잡한 추론**
  - `explan_img`를 바탕으로 `result_desc` 원문대로 답변할 수 있는 질문 생성
  - 언어: 영어
- **답변**: `result_desc` 원문 그대로 사용
- **출력**: 위 JSON 형식에 맞춰 JSONL 파일로 출력

### 데이터셋 생성 파이프라인

```
이미지 + 캡션 → 설명 텍스트 생성 및 csv파일에 새로운 컬럼'explan_img'에 삽입 (비어있는 row부터 계속 생성)
         ↓
explan_img + result_desc → 복잡한 추론 Q 생성 (GPT-4o-mini 사용, 영어로 생성)
         ↓
답변(A) = result_desc 원문 그대로 사용
         ↓
CSV에 Q, A 컬럼 추가 및 데이터 적재
         ↓
JSONL 학습 데이터로 저장 (qa_{datetime}.jsonl)
```

### 세부 단계

#### 단계 1: 이미지 설명 텍스트 생성 (`explan_img`)

**입력 파일**: `t_figures_with_result_desc_v3.csv`

**처리 과정**:
1. CSV 파일에서 `fig_caption`, `fig_url` 추출
2. GPT-4o-mini에 이미지 URL과 캡션 전달
3. 실험결과 이미지 설명 텍스트 생성
4. `explan_img` 컬럼에 삽입 (비어있는 row부터 계속 생성)

**주요 사항**:
- 이미지 URL이 없는 경우 건너뛰기
- 이미지 설명(`explan_img`): **영어로 생성**
- 중단된 부분부터 계속 생성 가능하도록 추적 가능하도록 설정
- 참고: vLLM RunPod 비용이 더 나으면 RunPod로 실행 예정

**출력**: `t_figures_with_result_desc_v3__explain.csv` (기존 파일에 `explan_img` 컬럼 추가)

#### 단계 2: 복잡한 추론 질문-답변 생성 및 JSON 데이터셋 만들기

**입력 파일**: `t_figures_with_result_desc_v3__explain.csv`

**입력 데이터**:
- `explan_img`: 이미지 설명 텍스트 (영어)
- `result_desc`: 저자 해석 부분 (영어)

**처리 과정**:
1. `explan_img`와 `result_desc`를 바탕으로 "복잡한 추론" 질문(Q) 생성 (GPT-4o-mini 사용)
2. 질문은 `explan_img`를 바탕으로 `result_desc` 원문대로 답변할 수 있는 질문으로 생성
3. 답변(A)은 `result_desc` 원문 그대로 사용
4. CSV 파일에 Q, A 컬럼 생성 및 데이터 추가 (1개의 row당 1개의 질문 생성)
5. JSONL 형식으로 데이터셋 생성

**주요 사항**:
- 질문 생성: GPT-4o-mini 사용
- 1개의 row당 1개의 질문 생성
- 생성 후 `t_figures_with_result_desc_v3__explain.csv`에 Q, A 컬럼 추가 및 데이터 적재
- 중단한 부분부터 계속 생성할 수 있도록 추적 가능하도록 설정 (이미 처리된 행은 건너뛰기)

**언어 설정**:
- **질문(Q)**: 영어로 생성
- **답변(A)**: `result_desc` 원문 그대로 사용

**데이터 형식**:
- User content: `explan_img`(이미지 설명 텍스트) + Q(질문)을 함께 포함
- Assistant content: `result_desc` 원문 그대로

**출력**:
- CSV 파일: `t_figures_with_result_desc_v3__explain.csv` (Q, A 컬럼 추가)
- JSONL 파일: `.fine-tuning/data/dataset/qa_{datetime}.jsonl`

---

## 2. 데이터셋 생성에 사용할 GPT 모델

### 핵심 원칙: "일관된 사고 틀을 가진 teacher"

### GPT-4o-mini 사용 권장

**장점:**
- 항상 비슷한 수준
- 항상 같은 스타일
- 항상 같은 실수 유형
- → **데이터 정제 가능**

### GPT-4o 사용 시 주의사항

**단점:**
- 어떤 샘플은 너무 뛰어남
- 어떤 샘플은 과잉 해석
- 스타일 variance 큼
- → **데이터셋 전체 품질 불안정**

### ⚠️ 예외 사항 (중요)

**GPT-4o를 "부분적으로" 사용 가능한 경우:**

**역할**: 정답 검증기 또는 리뷰어

**사용 예시:**

1. GPT-4o-mini가 생성한 해석을 GPT-4o에게 검증 요청:
   ```
   Is there any inference in this explanation
   that is not supported by the caption?
   ```

2. 또는:
   ```
   List any statements that may over-interpret the figure.
   ```

**결론**: 
- **생성은 mini, 검증은 4o**
- 이 구조가 최적입니다.

---

## 3. 파인튜닝 방법

**방식**: vLLM 및 QLoRA

### 참고 자료

- [Google 공식 문서](https://ai.google.dev/gemma/docs/core/huggingface_vision_finetune_qlora?hl=ko&_gl=1*9d5mm9*_up*MQ..*_ga*MTEwODA0NzY2NC4xNzY2NDY4NDc4*_ga_P1DBVKWT6V*czE3NjY0Njg0NzgkbzEkZzAkdDE3NjY0Njg0NzgkajYwJGwwJGg4NzA1NTMwMDI.)
- [블로그 포스트](https://g3lu.tistory.com/53)

---

## 파일 구조

```
.fine-tuning/
├── README.md                          # 이 파일
├── code/
│   ├── create_explan_img.py          # 단계 1: 이미지 설명 텍스트 생성
│   └── create_qa.py                  # 단계 2: 질문-답변 생성 및 JSONL 데이터셋 생성
└── data/
    ├── raw/
    │   ├── t_figures_with_result_desc_v3.csv              # 단계 1 입력 파일
    │   └── t_figures_with_result_desc_v3__explain.csv    # 단계 1 출력 파일 (단계 2 입력 파일)
    └── dataset/
        └── qa_{datetime}.jsonl        # 단계 2 출력 파일 (JSONL 학습 데이터)
```
