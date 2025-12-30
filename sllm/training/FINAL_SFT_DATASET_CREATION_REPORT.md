# 최종 파인튜닝 데이터셋 생성 보고서
## Final SFT Dataset Creation Report

**작성일**: 2025-01-30  
**최종 업데이트**: 2025-01-30
**목적**: 바이오메디컬 소규모 언어 모델(Small Language Model) 파인튜닝을 위한 고품질 데이터셋 생성 파이프라인

---

## 목차 (Table of Contents)

1. [개요](#1-개요)
2. [전체 파이프라인 구조](#2-전체-파이프라인-구조)
3. [1단계: Annotation JSON 생성](#3-1단계-annotation-json-생성)
4. [2단계: SFT Dataset JSONL 변환](#4-2단계-sft-dataset-jsonl-변환)
5. [3단계: 데이터셋 품질 감사](#5-3단계-데이터셋-품질-감사)
6. [데이터 구조 상세](#6-데이터-구조-상세)
7. [품질 감사 기준](#7-품질-감사-기준)
8. [결과물 및 통계](#8-결과물-및-통계)
9. [실행 방법](#9-실행-방법)

---

## 1. 개요

본 보고서는 바이오메디컬 연구 결과(Results section) 텍스트로부터 파인튜닝용 고품질 데이터셋을 생성하는 전체 파이프라인을 설명합니다.

### 1.1 목표
- **입력**: 연구 논문의 Results section 텍스트 (CSV 형식)
- **출력**: 파인튜닝용 고품질 SFT (Supervised Fine-Tuning) 데이터셋 (JSONL 형식)
- **핵심 원칙**: 
  - 실험적 관찰 사실만 추출
  - 메커니즘/인과관계 추론 금지
  - 해석 경계 명확화
  - 엄격한 품질 검증

### 1.2 파이프라인 단계
1. **Annotation JSON 생성**: Results 텍스트에서 구조화된 데이터 추출
2. **SFT Dataset JSONL 변환**: 학습용 형식으로 변환
3. **품질 감사 및 필터링**: 자동화된 품질 검증을 통한 최종 데이터셋 생성

---

## 2. 전체 파이프라인 구조

```
CSV (Results Section Text)
    ↓
[Step 1] preprocess_to_sft_v3.py
    ├─→ Annotation JSON (구조화된 데이터)
    └─→ SFT Dataset JSONL (초기 학습 데이터)
    ↓
[Step 2] dataset_auditor.py
    ├─→ 하드 실패 체크 (규칙 기반)
    ├─→ LLM Judge 평가 (5가지 항목)
    └─→ 최종 필터링
    ↓
Final SFT Dataset JSONL (파인튜닝용 고품질 데이터셋)
```

### 2.1 입력 데이터
- **형식**: CSV 파일
- **필수 컬럼**: 
  - `section_id`: 섹션 고유 식별자
  - `section_text`: Results section 텍스트 내용
- **위치**: `sllm/datasets/section_category_result.csv`

### 2.2 중간 산출물
1. **Annotation JSON** (`annotation_v3_*.json`)
   - OpenAI GPT-4o를 사용한 구조화된 데이터 추출 결과
   - 각 샘플당 `sid`, `section_id`, `observations`, `question`, `conclusion`, `interpretation_boundary` 포함

2. **초기 SFT Dataset JSONL** (`sft_dataset_v3_*.jsonl`)
   - 학습용 형식으로 변환된 데이터
   - `instruction`, `input`, `output` 구조

### 2.3 최종 산출물
1. **Audit Results CSV** (`audit_results_*.csv`)
   - 모든 샘플의 평가 결과 (PASS/FAIL, 점수, 이슈 등)

2. **Audit Results JSON** (`audit_results_*.json`)
   - 상세 평가 결과 (JSON 형식)

3. **Final SFT Dataset JSONL** (`final_sft_dataset_*.jsonl`)
   - **PASS된 샘플만 포함**하는 최종 파인튜닝용 데이터셋

---

## 3. 1단계: Annotation JSON 생성

### 3.1 프로세스 개요

`preprocess_to_sft_v3.py`의 `create_annotation_json()` 함수가 수행합니다.

1. CSV 파일에서 Results section 텍스트 읽기
2. 각 텍스트에 대해 OpenAI GPT-4o API 호출
3. 구조화된 JSON 데이터 추출
4. 실시간 저장 (1건씩 즉시 저장)

### 3.2 시스템 프롬프트 핵심 원칙

```
- 실험적으로 관찰된 사실만 추출
- 메커니즘, 인과관계, 추론적 설명 금지
- 배경 정보, 방법론, 리뷰 내용 제거
- 유효한 관찰이 없으면 "NO_VALID_RESULTS" 반환
```

### 3.3 추출 데이터 구조

각 샘플은 다음 필드를 포함합니다:

```json
{
  "sid": 1,                    // 자동 증가 ID (1부터 시작)
  "section_id": "xxx",         // 원본 CSV의 section_id
  "observations": [             // 실험적 관찰 사실 리스트
    "관찰1",
    "관찰2",
    ...
  ],
  "question": "비교 질문?",    // 중립적 비교 질문 (반드시 ?로 끝남)
  "conclusion": {               // 해석 및 결론
    "interpretation": [         // 효과 수준 요약만
      "효과 설명1",
      ...
    ],
    "interpretation_limits": [  // 해석 한계
      "한계 설명1",
      ...
    ],
    "cautions": [               // 주의사항
      "주의사항1",
      ...
    ],
    "suggested_next_steps": [  // 제안된 다음 단계
      "다음 단계1",
      ...
    ]
  },
  "interpretation_boundary": { // 해석 경계
    "can_conclude": [          // 가능한 해석
      "가능한 해석1",
      ...
    ],
    "cannot_conclude": [       // 금지된 해석
      "메커니즘 설명",
      "인과관계 추론",
      ...
    ]
  }
}
```

### 3.4 주요 특징

- **실시간 저장**: 각 샘플 처리 후 즉시 파일에 저장 (중단 시 재개 가능)
- **중복 방지**: 이미 처리된 `section_id`는 자동 건너뛰기
- **에러 처리**: JSON 파싱 실패 시 해당 샘플만 스킵하고 계속 진행

### 3.5 출력 파일

- **경로**: `sllm/datasets/annotation_v3_YYMMDDHHMMSS.json`
- **형식**: JSON 배열
- **예시 파일명**: `annotation_v3_250130124321.json`

---

## 4. 2단계: SFT Dataset JSONL 변환

### 4.1 프로세스 개요

`preprocess_to_sft_v3.py`의 `create_sft_dataset()` 함수가 수행합니다.

Annotation JSON을 학습용 형식(JSONL)으로 변환합니다.

### 4.2 변환 로직

각 annotation 항목을 다음과 같이 변환:

```python
# Input: annotation.json의 한 항목
{
  "sid": 1,
  "section_id": "xxx",
  "observations": [...],
  "question": "...",
  "conclusion": {...},
  "interpretation_boundary": {...}
}

# Output: SFT dataset JSONL의 한 줄
{
  "instruction": "You are a biomedical research assistant...",
  "input": {
    "observations": [...],           // conclusion 제외
    "question": "...",
    "interpretation_boundary": {...}
  },
  "output": {                        // conclusion만 포함
    "interpretation": [...],
    "interpretation_limits": [...],
    "cautions": [...],
    "suggested_next_steps": [...]
  }
}
```

### 4.3 Instruction 텍스트

```
You are a biomedical research assistant.
Interpret the experimental results strictly based on the provided observations.
Do not infer mechanisms or conclusions beyond the data.
Clearly state interpretation limits.
```

### 4.4 데이터 분리 원칙

- **Input**: 모델이 받을 정보
  - `observations`: 실험적 관찰 사실
  - `question`: 답변해야 할 질문
  - `interpretation_boundary`: 해석 경계 제약

- **Output**: 모델이 생성해야 할 답변
  - `conclusion` 전체 (interpretation, limits, cautions, next_steps)

### 4.5 출력 파일

- **경로**: `sllm/datasets/sft_dataset_v3_YYMMDDHHMMSS.jsonl`
- **형식**: JSONL (한 줄에 하나의 JSON 객체)
- **예시 파일명**: `sft_dataset_v3_250130124321.jsonl`

---

## 5. 3단계: 데이터셋 품질 감사

### 5.1 프로세스 개요

`dataset_auditor.py`가 수행하는 2단계 평가 시스템:

1. **하드 실패 체크** (Hard Fail Checks): 규칙 기반 자동 실패 판정
2. **LLM Judge 평가**: 5가지 항목으로 세밀한 품질 평가

### 5.2 하드 실패 체크 (Hard Fail Checks)

다음 조건 중 **하나라도 해당되면 즉시 FAIL** 처리됩니다.

#### 5.2.1 관찰 데이터 비어있음 (`observations_empty`)
- **조건**: `input.observations` 리스트가 비어있거나 모든 항목이 공백
- **이유**: 관찰 데이터가 없으면 해석 불가능

#### 5.2.2 해석 경계 위반 (`cannot_conclude_violation`)
- **조건**: `interpretation_boundary.cannot_conclude`에 "mechanism", "causal", "explanation" 등이 포함되어 있는데, 출력에서 금지된 패턴 발견
- **금지 패턴**:
  - `mechanism` (메커니즘)
  - `cause/causal/causality` (인과관계)
  - `catalyze/catalytic` (촉매)
  - `explain/explains` (설명)
  - `therefore`, `thus`, `due to` (따라서, ~때문에)
  - `indicates mechanism`, `suggests mechanism` (메커니즘을 시사)
- **이유**: 명시적으로 금지된 해석 범위를 벗어남

#### 5.2.3 질문-관찰 데이터 불일치 (`question_misaligned_with_observations`)
- **조건**: 
  - 질문에서 추출한 키워드(5자 이상)가 6개 이상
  - 그 중 70% 이상이 관찰 데이터에 전혀 등장하지 않음
- **제외 키워드**: `compare`, `between`, `effects`, `effect`, `difference`
- **이유**: 관찰 데이터로 답할 수 없는 질문

### 5.3 LLM Judge 평가 (5가지 항목)

LLM Judge는 각 샘플을 **0-100점 척도**로 평가하며, 다음 5가지 항목으로 세분화합니다.

#### 5.3.1 Integrity (무결성) - 0~30점
- **평가 기준**: 관찰 데이터의 품질
- **포함 사항**:
  - 관찰 데이터가 비어있지 않음
  - 결과(result-like) 데이터인지 확인
  - 배경 정보나 방법론이 아닌 실제 관찰 결과인지
  - 해석적 내용이 아닌 객관적 관찰인지

#### 5.3.2 Alignment (정렬) - 0~20점
- **평가 기준**: 질문과 관찰 데이터의 일치도
- **포함 사항**:
  - 질문이 관찰 데이터만으로 답변 가능한지
  - 질문이 관찰 데이터의 범위를 벗어나지 않는지

#### 5.3.3 Faithfulness (충실성) - 0~25점
- **평가 기준**: 출력이 관찰 데이터에 근거하는지
- **포함 사항**:
  - 출력의 모든 주장이 관찰 데이터로 뒷받침되는지
  - 관찰 데이터에 없는 새로운 엔티티나 범위를 도입하지 않는지

#### 5.3.4 Boundary (경계 준수) - 0~15점
- **평가 기준**: 해석 경계 제약 준수
- **포함 사항**:
  - `cannot_conclude`에 명시된 제약을 위반하지 않는지
  - `can_conclude` 범위 내에서만 해석하는지

#### 5.3.5 Atomicity (원자성) - 0~10점
- **평가 기준**: 단일 작업 집중도
- **포함 사항**:
  - 하나의 명확한 작업에 집중하는지
  - 관련 없는 여러 도메인을 섞지 않는지

### 5.4 최종 판정 로직

#### 5.4.1 하드 실패 처리
- 하드 실패가 발생하면:
  - **최종 verdict**: 무조건 `FAIL`
  - **최종 score**: LLM Judge 점수와 관계없이 **최대 49점**으로 제한

#### 5.4.2 점수 기반 판정
- **PASS 조건**:
  - 하드 실패가 없음
  - LLM Judge의 `final_score`가 **70점 이상**
  - LLM Judge의 `verdict`가 `PASS`
- **FAIL 조건**:
  - 하드 실패 발생
  - 또는 `final_score`가 70점 미만
  - 또는 LLM Judge의 `verdict`가 `FAIL`

#### 5.4.3 추천 조치 (Recommended Action)
LLM Judge가 다음 중 하나를 추천합니다:
- **KEEP AS-IS**: 그대로 사용 가능
- **USE AFTER REVISION**: 수정 후 사용 가능
- **REMOVE FROM TRAINING SET**: 학습 데이터셋에서 제거

### 5.5 출력 파일

1. **Audit Results CSV** (`audit_results_*.csv`)
   - 모든 샘플의 평가 결과
   - 컬럼: `idx`, `verdict`, `score`, `breakdown_*`, `hard_fail`, `hard_fail_reasons`, `key_issues`, `recommended_action`
   - `hard_fail_reasons`와 `key_issues`는 파이프(`|`)로 구분

2. **Audit Results JSON** (`audit_results_*.json`)
   - 상세 평가 결과 (JSON 배열 형식)

3. **Final SFT Dataset JSONL** (`final_sft_dataset_*.jsonl`)
   - **PASS된 샘플만 포함**
   - 실제 파인튜닝에 사용할 최종 데이터셋
   - 원본 SFT dataset JSONL과 동일한 구조

---

## 6. 데이터 구조 상세

### 6.1 Annotation JSON 구조

```json
{
  "sid": 1,
  "section_id": "section_001",
  "observations": [
    "Treatment A showed 45% reduction in cell viability.",
    "Control group maintained 95% viability.",
    "Statistical significance: p < 0.001"
  ],
  "question": "What is the difference in cell viability between Treatment A and Control?",
  "conclusion": {
    "interpretation": [
      "Treatment A resulted in a 45% reduction in cell viability compared to control.",
      "Control group maintained high viability (95%)."
    ],
    "interpretation_limits": [
      "Results are limited to the specific cell line tested.",
      "Only one time point was measured."
    ],
    "cautions": [
      "Results may not generalize to other cell types.",
      "Mechanism of action was not investigated."
    ],
    "suggested_next_steps": [
      "Test at multiple time points.",
      "Evaluate in different cell lines.",
      "Assess dose-response relationship."
    ]
  },
  "interpretation_boundary": {
    "can_conclude": [
      "Treatment A reduced cell viability compared to control.",
      "The reduction was statistically significant."
    ],
    "cannot_conclude": [
      "The mechanism by which Treatment A reduces viability.",
      "Causal relationship between treatment and effect.",
      "Generalizability to other experimental conditions."
    ]
  }
}
```

### 6.2 SFT Dataset JSONL 구조

```json
{
  "instruction": "You are a biomedical research assistant.\nInterpret the experimental results strictly based on the provided observations.\nDo not infer mechanisms or conclusions beyond the data.\nClearly state interpretation limits.",
  "input": {
    "observations": [
      "Treatment A showed 45% reduction in cell viability.",
      "Control group maintained 95% viability.",
      "Statistical significance: p < 0.001"
    ],
    "question": "What is the difference in cell viability between Treatment A and Control?",
    "interpretation_boundary": {
      "can_conclude": [
        "Treatment A reduced cell viability compared to control.",
        "The reduction was statistically significant."
      ],
      "cannot_conclude": [
        "The mechanism by which Treatment A reduces viability.",
        "Causal relationship between treatment and effect.",
        "Generalizability to other experimental conditions."
      ]
    }
  },
  "output": {
    "interpretation": [
      "Treatment A resulted in a 45% reduction in cell viability compared to control.",
      "Control group maintained high viability (95%)."
    ],
    "interpretation_limits": [
      "Results are limited to the specific cell line tested.",
      "Only one time point was measured."
    ],
    "cautions": [
      "Results may not generalize to other cell types.",
      "Mechanism of action was not investigated."
    ],
    "suggested_next_steps": [
      "Test at multiple time points.",
      "Evaluate in different cell lines.",
      "Assess dose-response relationship."
    ]
  }
}
```

### 6.3 평가 결과 구조 (CSV/JSON)

```json
{
  "idx": 1,
  "verdict": "PASS",
  "score": 85,
  "breakdown_integrity": 28,
  "breakdown_alignment": 18,
  "breakdown_faithfulness": 23,
  "breakdown_boundary": 10,
  "breakdown_atomicity": 6,
  "hard_fail": false,
  "hard_fail_reasons": [],
  "key_issues": [
    "Minor: Some observations could be more specific."
  ],
  "recommended_action": "KEEP AS-IS"
}
```

---

## 7. 품질 감사 기준

### 7.1 평가 원칙

1. **보수적 접근**: 불확실할 때는 FAIL 선호
2. **데이터 수정 금지**: 평가만 수행하고 데이터를 수정하지 않음
3. **엄격한 기준**: 바이오메디컬 도메인의 특성상 오해석 방지에 중점
4. **명확한 근거**: 모든 판정에 명확한 이유 제공

### 7.2 통과 기준 요약

✅ **PASS 조건**:
- 하드 실패 없음
- LLM Judge 점수 70점 이상
- 5가지 평가 항목 모두 적절한 점수 획득

❌ **FAIL 주요 원인**:
1. 관찰 데이터 부재
2. 해석 경계 위반 (금지된 메커니즘/인과관계 언급)
3. 질문-관찰 데이터 불일치
4. 관찰 데이터로 뒷받침되지 않는 출력
5. 여러 작업 혼재

### 7.3 LLM Judge 비활성화 모드

`USE_LLM_JUDGE=0`으로 설정하면 LLM Judge 없이 순수 규칙 기반 평가만 수행합니다.

- **하드 실패 있음**: 35점
- **하드 실패 없음**: 
  - 기본 점수: 78점
  - 소프트 과도 추론 패널티: `SOFT_OVERREACH_WORDS` 포함 시 단어당 -3점
  - 소프트 과도 추론 단어: `likely`, `potential`, `may`, `could`, `suggest`, `imply`

---

## 8. 결과물 및 통계

### 8.1 출력 파일 요약

| 파일명 패턴 | 설명 | 형식 |
|------------|------|------|
| `annotation_v3_*.json` | 구조화된 추출 데이터 | JSON 배열 |
| `sft_dataset_v3_*.jsonl` | 초기 학습 데이터셋 | JSONL |
| `audit_results_*.csv` | 평가 결과 (모든 샘플) | CSV |
| `audit_results_*.json` | 평가 결과 (상세) | JSON |
| `final_sft_dataset_*.jsonl` | **최종 파인튜닝용 데이터셋** | JSONL |

### 8.2 통계 정보

평가 완료 후 다음 정보가 출력됩니다:

```
=== Summary ===
verdict
PASS    120
FAIL     30

Top FAIL reasons:
[상위 15개 FAIL 샘플의 상세 정보]
```

### 8.3 품질 지표

- **통과율**: PASS 샘플 수 / 전체 샘플 수
- **평균 점수**: 전체 샘플의 평균 점수
- **하드 실패율**: 하드 실패 발생 샘플 수 / 전체 샘플 수
- **항목별 평균 점수**: Integrity, Alignment, Faithfulness, Boundary, Atomicity

---

## 9. 실행 방법

### 9.1 전체 파이프라인 실행

```bash
# 방법 1: run_pipeline.py 사용 (권장)
cd sllm/training
python run_pipeline.py

# 방법 2: subprocess 대신 직접 함수 호출
python run_pipeline.py --direct
```

### 9.2 단계별 실행

#### Step 1: Annotation JSON 및 SFT Dataset 생성

```bash
cd sllm/training
python preprocess_to_sft_v3.py
```

**설정 변수** (`preprocess_to_sft_v3.py` 상단):
- `PROCESS_ROWS`: 처리할 데이터 row 개수 (기본값: 1500)
- `CSV_PATH`: 입력 CSV 파일 경로

#### Step 2: 데이터셋 품질 감사

```bash
cd sllm/training
python dataset_auditor.py \
  --in_jsonl sllm/datasets/sft_dataset_v3_250130124321.jsonl \
  --out_csv sllm/datasets/audit_results_250130_1243.csv \
  --out_json sllm/datasets/audit_results_250130_1243.json \
  --out_final_jsonl sllm/datasets/final_sft_dataset_250130_1243.jsonl
```

### 9.3 환경 변수 설정

`.env` 파일에 다음 변수 설정:

```env
# OpenAI API (필수)
OPENAI_API_KEY=your_api_key_here

# LLM API 설정 (선택)
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_TIMEOUT_SEC=60
LLM_RETRY=2

# 감사 설정 (선택)
USE_LLM_JUDGE=1  # 1=사용, 0=비사용 (규칙 기반만)
SLEEP_BETWEEN=0.2  # 샘플 간 대기 시간 (초)
```

### 9.4 주의사항

1. **API 비용**: GPT-4o 사용 시 비용 발생 (Step 1: annotation 생성, Step 2: LLM Judge)
2. **실행 시간**: 샘플 수에 비례하여 시간 소요
3. **중단 및 재개**: 
   - Step 1: 이미 처리된 `section_id`는 자동 건너뛰기
   - Step 2: 중단 시 처음부터 다시 실행 필요
4. **디스크 공간**: 중간 파일들이 저장되므로 충분한 공간 확보

---

## 10. 결론

본 파이프라인은 바이오메디컬 연구 결과로부터 고품질 파인튜닝 데이터셋을 생성하기 위한 체계적인 접근 방식을 제공합니다.

### 10.1 핵심 특징

1. **구조화된 추출**: GPT-4o를 활용한 정확한 데이터 추출
2. **엄격한 품질 관리**: 2단계 평가 시스템 (하드 실패 체크 + LLM Judge)
3. **해석 경계 명확화**: 메커니즘/인과관계 추론 방지
4. **자동화된 필터링**: PASS된 샘플만 최종 데이터셋에 포함

### 10.2 활용 방안

- 소규모 언어 모델 파인튜닝
- 바이오메디컬 도메인 특화 모델 개발
- 실험 결과 해석 보조 시스템 구축

---

 


