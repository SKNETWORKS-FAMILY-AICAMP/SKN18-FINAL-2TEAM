# Gemma-3 멀티모달 LLM 파인튜닝 프로젝트

## 프로젝트 개요

Gemma-3은 구글에서 개발한 멀티모달 LLM으로, 이미지와 텍스트를 함께 처리할 수 있는 모델입니다. 본 프로젝트는 생명과학 실험 결과 해석을 위한 Gemma-3 파인튜닝 데이터셋을 구축하는 과정을 담고 있습니다.

## 1. 데이터셋 설계 및 생성 방법론

### 1.1 데이터셋 설계 배경

LLaVA 모델 개발 시 사용된 방법론을 착안하여, 이미지와 이미지 캡션 정보를 GPT-4o-mini에 전달하여 해당 이미지에 대한 객관적인 설명을 생성하는 방식을 채택했습니다.

### 1.2 데이터 형식
- 구글 공식 문서의 gemma-3 파인튜닝 예시 데이터 형식을 따름
 
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

### 1.3 데이터 생성 방법

- **실험결과 이미지 설명 텍스트 (`explan_img`)**: 이미지와 캡션을 GPT-4o-mini에 전달하여 생성
  - 프롬프트 해석: "이 실험 결과 이미지를 자세히 설명해 주세요. 이미지에 표시된 실험 결과, 데이터, 그래프 또는 시각적 요소를 구체적으로 설명해 주세요. 답변은 영어로 제공하세요. **없는 내용을 확대 해석하지 말아주세요.**"
  - 실제 프롬프트 ([create_explan_img.py:37](code/create_explan_img.py#L37)):
    ```python
    PROMPT = "Please describe in detail the image of the results of this experiment.
    Please describe in detail the results of the experiment, data, graphs,
    or visual elements shown in the image. Please provide your answers in English.
    Please do not zoom in on what is not there."
    ```
- **질문 생성 (`Q`)**: `explan_img`와 `result_desc`를 바탕으로 GPT-4o-mini로 복잡한 추론 질문 생성
  - 질문 유형: **복잡한 추론** (Complex Reasoning)
  - `explan_img`를 바탕으로 `result_desc` 원문대로 답변할 수 있는 질문 생성
  - 언어: 영어
  - 프롬프트 해석: "생명과학 실험 전문가로서, 제공된 이미지 설명을 바탕으로 단계별 분석이 필요한 복잡한 추론 질문을 생성하세요. 질문은 (1) 이미지 설명을 기반으로 하고, (2) 복잡한 추론과 단계별 사고를 요구하며, (3) 제공된 결과 설명을 사용하여 답변할 수 있어야 하고, (4) 영어로 작성되며, (5) 실험 결과에 대한 깊은 이해를 요구하는 도전적인 질문이어야 합니다."
  - 실제 프롬프트 ([create_qa.py:83-98](code/create_qa.py#L83-L98)):
    ```python
    QUESTION_GENERATION_PROMPT = """You are an expert in life science experiments.
    Based on the image description provided, generate a complex reasoning question
    that requires step-by-step analysis to answer.

    The question should:
    1. Be based on the image description (explan_img)
    2. Require complex reasoning and step-by-step thinking to answer
    3. Be answerable using the provided result description (result_desc)
    4. Be written in English
    5. Be challenging and require deep understanding of the experimental results
    ...
    """
    ```
- **답변 (`A`)**: `result_desc` 원문 그대로 사용
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

## 2. GPT-4o-mini 선정 근거

### 2.1 왜 GPT-4o-mini를 사용했는가?

데이터셋 생성을 위해 GPT-4o가 아닌 **GPT-4o-mini**를 선택한 이유는 다음과 같습니다:

#### 1) 객관적 정보 추출에 적합
- **GPT-4o**: 이미지가 제공하는 정보뿐만 아니라 깊은 해석과 추론까지 수행
  - 장점: 뛰어난 분석 능력
  - 단점: 과잉 해석 가능성, 스타일 variance가 큼
- **GPT-4o-mini**: 이미지에 **객관적으로 존재하는 정보만을 추출**
  - 장점: 일관된 수준, 일관된 스타일, 예측 가능한 출력
  - 장점: 데이터 정제 및 품질 관리 용이

#### 2) 평가자로서의 신뢰성
- 관련 연구에 따르면, GPT-4o-mini는 **평가자로서 치우침 없이 객관적으로 평가**하는 것으로 알려져 있음
- 이미지 설명 생성 시 주관적 해석을 배제하고, 실제 이미지 내용만을 정확하게 추출하는 역할에 적합

#### 3) 이미지 캡션 정보 활용
- 이미지와 함께 **캡션 정보를 전달**함으로써, 이미지에 대해 정확하게 설명하는 것을 확인
- 프롬프트:
  ```
  Please describe in detail the image of the results of this experiment.
  Please describe in detail the results of the experiment, data, graphs,
  or visual elements shown in the image. Please provide your answers in
  English. Please do not zoom in on what is not there.
  ```
- 캡션 정보를 프롬프트에 포함하여 더욱 정확한 이미지 설명 생성

#### 4) 검증 프로세스
- **생성**: GPT-4o-mini 사용
- **검증**: 테스트로 이미지, 캡션 정보, GPT-4o-mini가 추출한 이미지 설명과 질문-답변변을 **GPT (최신 모델)**에 전달하여 검증 완료


### 2.2 비용 분석

#### 실측 데이터 (50개 이미지 기준)
- **50개 이미지**에 대한 설명과 질문 생성 작업
- **비용**: **$0.2** (약 200원)

#### 전체 데이터셋 비용 추정
- QLora 파인튜닝 권장 데이터셋 크기: **최소 3,000개**
- **예상 비용** (3,000개 기준): **$12** (약 12,000원)
- **결론**: 비용 대비 효율적이므로 OpenAI API를 활용한 데이터셋 생성 진행

---

## 3. 현재 진행 상황

### 3.1 완료된 작업
- **50개 이미지**에 대한 파인튜닝 데이터 생성 완료
- 학습 데이터셋의 형태 확정
- JSONL 형태로 데이터셋 생성 완료

### 3.2 다음 단계
- 데이터 전처리 진행
- **다음 주부터 본격적인 파인튜닝 진행 예정**
- 최소 3,000개 이상의 데이터셋 구축 후 QLora 파인튜닝 진행

---

## 4. 이슈 및 해결 방안

### 4.1 이슈: 답변 길이 문제

**문제점**:
- `result_desc`에서 논문 저자의 개별figure 해석 텍스트를 이미지별로 모두 정답 답변으로 사용
- 결과적으로 **질문도 길어지고 답변도 길어지는 문제** 발생
- 보유 모델의 **max token 제한** 및 **데이터 유실 가능성** 우려

### 4.2 이슈: 질문 형태의 정형화

**문제점**:
- 답변이 논문의 정리된 답변이다 보니, 질문도 정리된 형태로 생성됨
- 실제 연구자들의 질문 패턴:
  - "~~수치 나왔는데, 왜 이런 결과가 나오게 되었을까?"
  - "~~에 대해 고려해서 해석해봐"
  - 비정형화된 구어체 질문

**해결 방안**:
- **현재 접근**: "모델을 시험하는 게 아니라, 먼저 **과학적 사고법을 학습시키는 것**"이 목표
- **학습 단계**: 정형화된 질문-답변으로 과학적 추론 능력 학습
- **테스트 단계**: 구어체로 질문하여 실제 사용 환경에서 성능 검증
- **결론**: 학습 데이터는 현재 방식 유지, 평가 시 비정형 질문으로 테스트

---

## 5. 파인튜닝 방법

**방식**: vLLM 및 QLoRA

### 참고 자료

- [Google 공식 문서](https://ai.google.dev/gemma/docs/core/huggingface_vision_finetune_qlora?hl=ko&_gl=1*9d5mm9*_up*MQ..*_ga*MTEwODA0NzY2NC4xNzY2NDY4NDc4*_ga_P1DBVKWT6V*czE3NjY0Njg0NzgkbzEkZzAkdDE3NjY0Njg0NzgkajYwJGwwJGg4NzA1NTMwMDI.)
- [블로그 포스트](https://g3lu.tistory.com/53)

---

## 6. 파일 구조

```
.fine-tuning/
├── README.md                                          # 프로젝트 문서 (본 파일)
├── code/
│   ├── create_explan_img.py                          # 단계 1: 이미지 설명 텍스트 생성
│   ├── create_qa.py                                  # 단계 2: 질문-답변 생성 및 JSONL 데이터셋 생성
│   └── test_check_openai_cost.py                     # 비용 측정 테스트 스크립트
└── data/
    ├── raw/
    │   ├── t_figures_with_result_desc_v3.csv         # 단계 1 입력 파일 (원본)
    │   └── t_figures_with_result_desc_v3__explain.csv # 단계 1 출력 / 단계 2 입력 파일
    └── dataset/
        └── qa_{datetime}.jsonl                       # 단계 2 출력 (JSONL 학습 데이터)
```

---

## 7. 실행 방법

### 단계 1: 이미지 설명 생성

```bash
cd .fine-tuning/code
python create_explan_img.py
```

**결과**: `t_figures_with_result_desc_v3__explain.csv` 파일에 `explan_img` 컬럼 추가

### 단계 2: 질문-답변 데이터셋 생성

```bash
cd .fine-tuning/code
python create_qa.py
```

**결과**:
- CSV 파일에 `Q`, `A` 컬럼 추가
- JSONL 학습 데이터 생성: `.fine-tuning/data/dataset/qa_{datetime}.jsonl`

### 비용 측정 테스트

```bash
cd .fine-tuning/code
python test_check_openai_cost.py <이미지_URL_또는_파일명>
```

---

## 8. 요약

### 핵심 성과
✅ LLaVA 방법론을 착안한 데이터셋 생성 파이프라인 구축
✅ GPT-4o-mini를 활용한 객관적 이미지 설명 생성 방법 확립
✅ GPT-o1을 통한 검증 프로세스 완료
✅ 비용 효율성 확인 (3,000개 기준 $12)
✅ 50개 샘플 데이터로 데이터셋 형태 확정

### 다음 단계
🔜 3,000개 이상 데이터셋 구축
🔜 데이터 전처리 및 품질 검증
🔜 QLora 기반 파인튜닝 진행
🔜 구어체 질문으로 모델 성능 평가

---

**프로젝트 담당**: SKN18-FINAL-2TEAM
**마지막 업데이트**: 2025년 12월
