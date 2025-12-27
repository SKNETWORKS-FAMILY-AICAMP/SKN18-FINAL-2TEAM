# sLLM 파인튜닝 학습 데이터 만들기 

## sLLM 개요
### sLLM 목적
- 실험 결과를 해석하는 sLLM

### 단계별 접근 방법

**Step 1: 파인튜닝 (가장 중요)**
- 실험 결과 해석을 위한 핵심 학습 단계
- Results 문장을 구조화된 사고 단위로 분해하여 학습
- 해석적 판단 제한


**Step 2: 접근 방법 선택**
- ❌ **파인튜닝만으로는 부족**: Step 2에서는 파인튜닝만으로는 한계가 있음
- ✅ **rule + prompt + LLM**: 규칙 기반 로직, 프롬프트 엔지니어링, LLM을 결합한 하이브리드 접근 방식이 효과적

---

## 서론
### 기존 방식의 문제점
Figure 캡션 + Figure 설명 텍스트 + Results 섹션만으로 파인튜닝하면
“그럴듯한 설명을 잘 쓰는 모델”은 되지만 “실험 결과를 정확히 해석하는 sLLM”이 되기 어려움

### 해결책
- 논문 문장이 아니라, 연구자가 머릿속에서 하는 해석 과정을 데이터로 만들기
- 논문의 result에서 뽑아야 할 진짜 학습대상
  - 반드시 필요한 학습 데이터 타입
    - 구조화된 관측 데이터 : (시간, 농도, 그룹, 수치)
    - 비교 기준 명시 : 무엇 대비 변화인가
    - 해석 논리
    - 왜 의미 있는가
    - 어디까지 말할 수 있는가
    - 해석 한계 : sample size, 통계 제한, 추가 실험 필요성
    - 논문 Figure를 학습시키지 말고, “연구자가 Figure를 보고 생각하는 과정”을 학습시켜라!

#### 추천 파인튜닝 데이터셋 포맷 (assistant의 값)
```
{
  "experimental_context": {
    "model": "mouse",
    "assay": "IHC",
    "target": "Hyaluronan",
    "experimental_purpose": "in vivo HA level comparison"
  },
  "observation": {
    "measurement": "HA-positive pixels",
    "direction": "decrease",
    "magnitude": "approximately 5% at 2h vs ~25% in vehicle"
  },
  "comparison": {
    "experimental_group": "L19-WT",
    "control_group": "vehicle-treated mice"
  },
  "temporal_or_dose_dimension": {
    "time": "2 h",
    "dose": "not stated"
  },
  "statistical_claim": {
    "reported": true,
    "confidence": "marginal"
  },
  "interpretation_boundary": {
    "can_conclude": [
      "HA-positive signal is lower in L19-WT-treated mice than in vehicle controls at 2 h"
    ],
    "cannot_conclude": [
      "mechanism of HA degradation",
      "whether degradation is direct or indirect",
      "long-term persistence of the effect",
      "dose–response relationship"
    ]
  }
}

```
- 핵심은 results를 그대로 쓰지 말고, '분해하기'


### 관련 연구 (Related Work)

#### 1. SciBERT / BioBERT 계열: 생명과학 논문 텍스트 이해 모델
**대표 논문:** Beltagy et al., SciBERT (EMNLP 2019), Lee et al., BioBERT (Bioinformatics 2020)

**특징:**
- 대규모 과학 논문을 이용한 BERT 사전학습
- 개체 인식(NER), 관계 추출, 문장 분류 등 텍스트 이해 성능 향상

**한계:**
- 과학 텍스트를 잘 읽는 것에 초점
- 실험 결과 해석이나 추론 단계까지는 다루지 않음
- "무엇까지 말할 수 있는가 / 말하면 안 되는가"에 대한 통제 없음

#### 2. Scientific Information Extraction: 결과 요약·구조화 연구
**대표 논문:** Hou et al., Extracting Scientific Facts (ACL 2019), Jain et al., SciREX (ACL 2020)

**특징:**
- Results/Methods에서 실험 변수, 조건, 결과를 자동 추출
- 테이블, Figure, 캡션을 구조화된 데이터로 변환

**한계:**
- 결과를 사실(fact) 단위로 추출하는 데 초점
- 결과가 왜 의미 있는지, 어디까지 해석 가능한지는 다루지 않음
- 해석은 여전히 연구자(사람)의 몫

#### 3. LLM 기반 과학 요약 및 추론 모델
**대표 논문:** Taylor et al., Galactica (arXiv 2022), Singhal et al., Clinical Knowledge (Nature 2023)

**특징:**
- 대규모 과학 텍스트를 학습한 LLM으로 논문 요약, 질의응답, 과학적 설명 생성
- 과학적 문체와 지식을 "그럴듯하게" 생성

**한계:**
- Figure나 Results를 보고 논문 스타일의 해석을 생성하지만, 실제 실험 조건이나 비교 기준이 불완전해도 "있어 보이는 해석"을 만들어낼 수 있음 (환각 문제)
- 실험 설계의 제약을 명시적으로 통제하지 않음

#### 본 프로젝트의 차별점

기존 연구들은 **과학 텍스트를 잘 읽거나**, **결과를 구조화하거나**, **그럴듯한 요약을 생성**하는 데 초점을 두었습니다.

반면, 본 프로젝트는:
- **"실험 결과를 보고 연구자가 어떤 논리로, 어디까지 해석하는가"**를 학습하는 sLLM을 만드는 것을 목표로 합니다
- Results 문장을 그대로 학습하지 않고, 실험 맥락, 관측 사실, 비교 기준, 해석 가능 범위를 분리하여 구조화합니다
- 해석의 논리적 경계를 명시적으로 모델에 학습시켜, 실험 해석을 보조할 수 있는 모델로 확장합니다



## 본론
### 데이터셋을 뽑아내는 세부 절차
핵심은 Results를 그대로 쓰지 말고, **구조화된 사고 단위로 분해**하는 것

#### 🔧 Step 1. Results 문장을 구조화된 필드로 분해

Results 문장을 서론에서 제시한 6가지 필드로 분해합니다:

1. **experimental_context**: 실험 모델, 분석법, 타겟, 실험 목적
2. **observation**: 측정 대상, 변화 방향, 크기 (배열로 여러 관측값 포함 가능)
3. **comparison**: 실험군 vs 대조군 비교 (배열로 여러 비교 포함 가능)
4. **temporal_or_dose_dimension**: 시간점, 농도/용량
5. **statistical_claim**: 통계적 유의성 (reported, confidence)
6. **interpretation_boundary**: 가능한 결론 vs 불가능한 결론

**Results 문장 예시:**
```
"At 2 h, L19-WT treatment significantly reduced HA-positive pixels 
compared to vehicle-treated mice."
```

**분해 결과 (구조화된 JSON):**
```json
{
  "experimental_context": {
    "model": "mouse",
    "assay": "IHC",
    "target": "Hyaluronan",
    "experimental_purpose": "in vivo HA level comparison"
  },
  "observation": {
    "measurement": "HA-positive pixels",
    "direction": "decrease",
    "magnitude": "approximately 5% at 2h vs ~25% in vehicle"
  },
  "comparison": {
    "experimental_group": "L19-WT",
    "control_group": "vehicle-treated mice"
  },
  "temporal_or_dose_dimension": {
    "time": "2 h",
    "dose": "not stated"
  },
  "statistical_claim": {
    "reported": true,
    "confidence": "significant"
  },
  "interpretation_boundary": {
    "can_conclude": [
      "HA-positive signal is lower in L19-WT-treated mice than in vehicle controls at 2 h"
    ],
    "cannot_conclude": [
      "mechanism of HA degradation",
      "whether degradation is direct or indirect",
      "long-term persistence of the effect",
      "dose–response relationship"
    ]
  }
}
```

👉 이 구조화된 JSON이 연구자가 Figure를 보며 명시적으로 확인한 사실 단위입니다.

#### 🔧 Step 2. 해석의 논리적 경계 명시

⚠️ **중요**: Results 기반 데이터셋에서는 추론 범위를 명확히 제한합니다.

**interpretation_boundary 필드의 역할:**
- `can_conclude`: 데이터가 직접 뒷받침하는 해석만 허용
- `cannot_conclude`: 추론, 가설, 확대 해석은 명시적으로 금지

**이를 학습시키면 모델이:**
- 과장된 결론을 스스로 멈추는 습관을 배웁니다
- "관찰된 사실로부터 어디까지 말해도 되는지"를 명확히 구분합니다
- '무엇이 관찰되었는가'까지만 말하고, '왜 그런가 / 그래서 무엇을 의미하는가'는 말하지 않습니다

**핵심 원칙:**
- ✅ 데이터가 직접 뒷받침하는 해석만 허용
- ✅ 과학적 추론 통제 설계 (Reasoning Boundary Design)
- ❌ 추론, 가설, 확대 해석은 명시적으로 금지
- 신뢰성·재현성·규제 대응

### Results에서 뽑아내는 사고 단위 분해 프롬프트

#### 기본 시스템 프롬프트 (고정)
```
You are a biomedical research assistant.

Your task is NOT to interpret beyond the text.
Your task is to extract the explicit reasoning units that a researcher confirms
when reading a Results section while looking at the corresponding figure.

Rules:
- Do NOT add assumptions.
- Do NOT infer mechanisms.
- Do NOT generalize beyond what is stated.
- If information is missing, explicitly mark it as "not stated".
- Stay strictly within the Results text.
```

**해석:**
- 👉 너는 생의학 연구 보조자이다. 일반 챗봇이 아니라 논문을 읽는 연구자 보조 역할로 역할을 고정
- 👉 텍스트에 쓰여 있지 않은 내용을 해석해서는 안 된다. 암묵적 의미, 추측, 확대 해석 전부 금지
- 👉 네 임무는 연구자가 Results 섹션을 읽고 해당 그림을 보면서 '확인할 수 있는 명시적인 추론 단위'를 추출하는 것이다
  - `explicit` = 명시적으로 확인 가능한 것만
  - `reasoning units` = 관찰, 비교, 방향, 유의성 같은 사실 기반 판단 단위
  - Results + Figure = 데이터로 뒷받침되는 확인 수준
- 👉 규칙: 가정을 넣지 마라, 작용 기전을 추론하지 마라, 범위를 넘어 일반화하지 마라, 정보가 없으면 "not stated"라고 표시해라

#### ✅ 유저 프롬프트 (핵심)
```
Given the following Results sentence(s), decompose them into
explicit reasoning units that reflect what a researcher confirms
from the figure.

Extract the following fields:

1. experimental_context
   - model (e.g., mouse, cell line) or "not stated"
   - assay / measurement method (e.g., IHC, IVIS) or "not stated"
   - target (if applicable) or "not stated"
   - experimental_purpose (if stated) or "not stated"

2. observation (can be an array if multiple observations)
   - what was measured
   - direction of change (increase / decrease / no change / not stated)
   - approximate magnitude or qualitative description

3. comparison (can be an array if multiple comparisons)
   - experimental_group vs control_group
   - treatment vs control
   - group vs group

4. temporal_or_dose_dimension
   - time point(s) or "not stated"
   - dose / concentration (if stated) or "not stated"

5. statistical_claim
   - reported: true/false
   - confidence: significant / not significant / trend / marginal / not stated

6. interpretation_boundary
   - can_conclude: [array of conclusions that can be drawn based ONLY on this result]
   - cannot_conclude: [array of conclusions that cannot be drawn]

Output strictly in JSON.
Do not add explanations outside the JSON.
```

**해석:**
다음에 주어지는 Results 문장을 바탕으로, 연구자가 해당 그림을 보며 확인할 수 있는 명시적인 추론 단위들로 분해하라. 이 프롬프트는 Results 문장을 '연구자가 그림을 보고 확인한 사실 단위'로만 분해하게 하며, 해석의 범위를 JSON 구조로 엄격히 제한하는 지시문이다.

#### ✅ 파인튜닝데이터 입력 예시 (User 메시지)
```
At 2 h, L19-WT treatment significantly reduced HA-positive pixels compared to vehicle-treated mice.
```

#### ✅ 출력 예시 (Assistant 응답 - 구조화된 JSON)
```json
{
  "experimental_context": {
    "model": "mouse",
    "assay": "IHC",
    "target": "Hyaluronan",
    "experimental_purpose": "in vivo HA level comparison"
  },
  "observation": {
    "measurement": "HA-positive pixels",
    "direction": "decrease",
    "magnitude": "approximately 5% at 2h vs ~25% in vehicle"
  },
  "comparison": {
    "experimental_group": "L19-WT",
    "control_group": "vehicle-treated mice"
  },
  "temporal_or_dose_dimension": {
    "time": "2 h",
    "dose": "not stated"
  },
  "statistical_claim": {
    "reported": true,
    "confidence": "significant"
  },
  "interpretation_boundary": {
    "can_conclude": [
      "HA-positive signal is lower in L19-WT-treated mice than in vehicle controls at 2 h"
    ],
    "cannot_conclude": [
      "mechanism of HA degradation",
      "whether degradation is direct or indirect",
      "long-term persistence of the effect",
      "dose–response relationship"
    ]
  }
}
```

👉 이 JSON 하나가 sLLM이 학습해야 할 **최소 사고 단위(minimal reasoning unit)**입니다.

**참고:** 실제 데이터셋에서는 여러 관측값이나 비교가 있을 경우 `observation`과 `comparison`을 배열로 구성할 수 있습니다.


## 결론

### Step 1.5: 파인튜닝 (가장 중요)
- 실험 결과 해석을 위한 핵심 학습 단계
- Results 문장을 구조화된 사고 단위로 분해하여 학습
- 해석적 판단 제한
- **시스템 메시지를 전역으로 설정**하고 구조화된 데이터셋으로 모델을 파인튜닝

### Step 2: 접근 방법 선택
- ❌ **파인튜닝만으로는 부족**: Step 2에서는 파인튜닝만으로는 한계가 있음 (학습 데이터 패턴에만 의존하여 동적 규칙 적용이나 실시간 판단이 어려움)
- ✅ **rule + prompt + LLM**: 규칙 기반 로직, 프롬프트 엔지니어링, LLM을 결합한 하이브리드 접근 방식이 효과적

------------------------------------------------------------

## Phase 파일별 역할

### Phase 0: `phase_0_figure_classification.py`
**목적:** Figure 이미지를 실험 결과 데이터(그래프/표)인지 분류

**입력:**
- `t_figures_with_result_desc_v4.csv`
- 필요 컬럼: `[fig_id, fig_url, fig_caption]`

**처리:**
- GPT Vision API로 이미지 URL 직접 접근
- 실험 결과 데이터 여부 분류 (`is_experiment_result: true/false`)

**출력:**
- 원본 CSV에 `is_experiment_result` 컬럼 추가

---

### Phase 1: `phase_1_result_desc_to_json.py`
**목적:** 중복 문장 제거 + 구조화된 JSON 생성

**입력:**
- `t_figures_with_result_desc_v4.csv` (Phase 0 완료된 파일)
- 필요 컬럼: `[fig_id, is_experiment_result, result_desc]`

**처리:**
- `is_experiment_result=true`인 Figure만 처리
- **중복 문장 제거**: `result_desc`에서 중복 문장 자동 제거
- GPT-4o-mini Text API로 정제된 `result_desc`를 구조화된 JSON으로 변환
- Results 문장을 사고 단위로 분해:
  - `experimental_context` (모델, 분석법)
  - `observation` (측정 대상, 방향, 크기)
  - `comparison` (그룹 비교)
  - `temporal_or_dose_dimension` (시간, 농도)
  - `statistical_claim` (통계적 유의성)
  - `interpretation_boundary` (가능한 결론, 불가능한 결론)

**출력:**
- 원본 CSV에 `structured_json` 컬럼 추가 (중복 제거된 result_desc 기반)
- `structured_results_YYYYMMDDHHMMSS.json` (검증용 JSON 파일)

---

### Phase 2: `phase_2_create_training_dataset.py` ⭐
**목적:** System message 전역 분리 + user/assistant 형식 JSONL 생성

**입력:**
- Phase 1 완료된 CSV (`structured_json` 컬럼 포함)
- `t_figures_with_result_desc_v4.csv`

**처리:**
1. CSV에서 `structured_json` 읽기
2. **자동 전처리 적용**:
   - System message 전역 분리 → 별도 파일로 저장
   - User 메시지: instruction 제거, result_desc만 포함 (Phase 1에서 중복 제거 완료)
   - Assistant 메시지: 빈 필드 제거 (`""`, `[]`, `{}`, `"not stated"` 삭제)

**출력:**
- `training_dataset_preprocessed_YYYYMMDDHHMMSS.jsonl` (user + assistant만)
- `system_message_YYYYMMDDHHMMSS.txt` (전역 시스템 메시지)

---

### Phase 3: `preprocess_training_dataset.py` (레거시)
**목적:** Phase 2에서 생성된 원본 데이터셋을 수동으로 전처리 (이제 Phase 2에서 자동 처리됨)

**⚠️ 주의:** Phase 2에서 `APPLY_PREPROCESSING = True`로 실행하면 이 단계는 **불필요**합니다.

**사용 시나리오:**
- Phase 2를 `APPLY_PREPROCESSING = False`로 실행한 경우
- 기존 `training_dataset_full_*.jsonl` 파일을 전처리하고 싶은 경우

---

## 데이터셋 전처리 (Preprocessing) 가이드

### ⭐ 통합 파이프라인 실행 (권장)

**`run_phase012.py`를 실행하면 Phase 0 → 1 → 2가 순차적으로 자동 실행됩니다!**

```bash
# 통합 파이프라인 실행 (Phase 0 → 1 → 2)
python run_phase012.py

# 또는 개별 Phase 실행
python phase_1_result_desc_to_json.py  # Phase 1: 중복 제거 + 구조화
python phase_2_create_training_dataset.py  # Phase 2: System 분리 + JSONL 생성

# 최종 출력:
#   - training_dataset_preprocessed_*.jsonl (바로 사용 가능!)
#   - system_message_*.txt (전역 시스템 메시지)
```

---

### 왜 전처리가 필요한가?

전처리 없이 생성된 데이터셋(원본 형식)을 OpenAI 파인튜닝에 사용하면 다음 문제들이 발생합니다:

#### 문제 1: System Message 중복
**현상:**
- 모든 대화마다 동일한 system message가 반복됨
- 토큰 낭비 (수천 개 샘플 × 긴 system message)

**해결책: 전역 System Message 분리**
```python
# Before (각 샘플마다 반복)
{"messages": [
  {"role": "system", "content": "You are a biomedical..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}

# After (시스템 메시지는 한 번만, 파일로 분리)
# system_message.txt에 저장
"You are a biomedical..."

# training_dataset.jsonl (시스템 메시지 제거)
{"messages": [
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

**효과:**
- 토큰 비용 절감 (수만 토큰 감소)
- 학습 효율 향상 (중복 데이터 제거)

---

#### 문제 2: User 메시지의 Instruction 중복 및 중복 문장
**현상:**
```json
{
  "role": "user",
  "content": "Given the following Results sentence(s), decompose them into explicit reasoning units...\n\nResults text:\nL19-WT treatment reduced HA-positive pixels at 2h. L19-WT treatment reduced HA-positive pixels at 2h."
}
```
- 매 샘플마다 긴 instruction이 반복됨
- result_desc에 중복 문장이 포함됨
- 모델이 학습하는 패턴: "이 task는 항상 이렇게 긴 지시를 받는구나"

**문제점:**
- **Train-Inference Mismatch**: 실제 사용 시에는 짧은 입력만 줄 텐데, 모델은 긴 instruction을 기대하도록 학습됨
- **성능 저하**: Inference 시 짧은 프롬프트로는 제대로 작동 안 함
- **중복 데이터**: 같은 문장이 반복되어 학습 효율 저하

**해결책: 2단계 정제**
```python
# Phase 1: 중복 문장 제거
"L19-WT treatment reduced HA-positive pixels at 2h. L19-WT treatment reduced HA-positive pixels at 2h."
→ "L19-WT treatment reduced HA-positive pixels at 2h."

# Phase 2: Instruction 제거, 핵심 데이터만 남기기
"Given the following Results sentence(s)...\n\nResults text:\nL19-WT treatment reduced HA-positive pixels at 2h."
→ "L19-WT treatment reduced HA-positive pixels at 2h."
```

**왜 이게 맞는가?**
- Phase 1에서 중복 문장 제거로 데이터 품질 향상
- Phase 2에서 instruction 제거로 실제 사용 패턴에 맞춤
- System message에 이미 task 정의가 있음
- User는 "정제된 입력 데이터"만 제공하면 됨

---

#### 문제 3: Assistant 응답의 빈 필드 반복
**현상:**
```json
{
  "role": "assistant",
  "content": {
    "experimental_context": {
      "model": "mouse",
      "assay": "not stated"
    },
    "observation": {
      "measurement": "HA-positive pixels",
      "direction": "decrease",
      "magnitude": ""
    },
    "statistical_claim": "",
    "interpretation_boundary": {
      "can_conclude": ["..."],
      "cannot_conclude": []
    }
  }
}
```

**문제점:**
- 빈 문자열 `""`, 빈 배열 `[]`이 반복됨
- **SFT(Supervised Fine-Tuning)에서 빈 필드 반복은 진짜 독**
  - 모델이 "정보가 없어도 필드를 만들어야 한다"고 학습
  - 불필요한 토큰 생성 패턴 학습
  - Hallucination 유발 (빈 값을 채우려는 경향)

**해결책: 빈 필드는 아예 제거**
```python
# Before (빈 필드 포함)
{
  "magnitude": "",
  "statistical_claim": "",
  "cannot_conclude": []
}

# After (빈 필드 제거)
{
  # magnitude 필드 자체가 없음
  # statistical_claim 필드 자체가 없음
  # cannot_conclude 필드 자체가 없음
}
```

**규칙:**
- `""` (빈 문자열) → 필드 삭제
- `[]` (빈 배열) → 필드 삭제
- `{}` (빈 객체) → 필드 삭제
- `"not stated"` → 유지 (의미 있는 정보)

**효과:**
- 모델이 "정보가 없으면 필드를 만들지 않는다"를 학습
- 불필요한 토큰 생성 방지
- Hallucination 감소

---

### 전처리 실행 방법

#### ✅ 통합 파이프라인 (권장)

```bash
# run_phase012.py: Phase 0 → 1 → 2 자동 실행
python run_phase012.py

# 출력:
#   - CSV에 is_experiment_result, structured_json 컬럼 추가
#   - training_dataset_preprocessed_*.jsonl (바로 사용 가능!)
#   - system_message_*.txt (전역 시스템 메시지)
```

**장점:**
- 전체 파이프라인 한 번에 실행
- 중복 제거부터 전처리까지 자동 완료
- 실수 방지

#### 개별 Phase 실행

```bash
# Phase 1: 중복 제거 + 구조화
python phase_1_result_desc_to_json.py

# Phase 2: System 분리 + JSONL 생성
python phase_2_create_training_dataset.py
```

### 전처리 결과 검증

전처리 전후 비교:
```bash
# 전처리 전 샘플
{
  "messages": [
    {
      "role": "system",
      "content": "You are a biomedical research assistant..." # 300+ 토큰
    },
    {
      "role": "user",
      "content": "Given the following Results...\n\nResults text:\nL19-WT..." # 100+ 토큰
    },
    {
      "role": "assistant",
      "content": "{\"magnitude\": \"\", \"cannot_conclude\": []...}" # 빈 필드 多
    }
  ]
}

# 전처리 후 샘플
{
  "messages": [
    {
      "role": "user",
      "content": "L19-WT treatment reduced HA-positive pixels at 2h." # 15 토큰
    },
    {
      "role": "assistant",
      "content": "{\"measurement\": \"HA-positive pixels\", \"direction\": \"decrease\"}" # 빈 필드 없음
    }
  ]
}
```

**토큰 절감 예시:**
- 샘플 1개당 평균 400 토큰 → 150 토큰 (62.5% 감소)
- 1000개 샘플 기준: 400K 토큰 → 150K 토큰
- 비용 절감 + 학습 효율 향상

---

### 전처리 핵심 원칙 요약

| 원칙 | 이유 | 효과 |
|------|------|------|
| **System message 전역 분리** | 토큰 중복 제거 | 비용 절감, 학습 효율 향상 |
| **User instruction 제거** | Train-inference 일치 | 실제 사용 시 성능 향상 |
| **빈 필드 완전 제거** | Hallucination 방지 | 불필요한 토큰 생성 방지, 정확도 향상 |

---