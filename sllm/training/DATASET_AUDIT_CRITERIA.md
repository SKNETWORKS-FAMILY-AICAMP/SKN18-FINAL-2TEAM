# 데이터셋 품질 감사 기준 (Dataset Quality Audit Criteria)

## 개요

이 문서는 `dataset_auditor.py`에서 사용하는 데이터셋 필터링 기준을 정리한 보고서입니다. 바이오메디컬 LLM 파인튜닝을 위한 데이터셋 샘플의 품질을 평가하고, 부적합한 샘플을 제거하는 기준을 명시합니다.

---

## 1. 평가 구조

데이터셋 샘플은 **2단계 평가 시스템**을 거칩니다:

1. **하드 실패 체크 (Hard Fail Checks)**: 자동으로 실패시키는 규칙 기반 검사
2. **LLM Judge 평가**: 5가지 항목으로 세밀한 품질 평가

최종적으로 **PASS/FAIL** 판정을 받으며, **PASS된 샘플만** 최종 학습 데이터셋에 포함됩니다.

---

## 2. 하드 실패 체크 (Hard Fail Checks)

다음 조건 중 **하나라도 해당되면 즉시 FAIL** 처리됩니다.

### 2.1. 관찰 데이터 비어있음 (`observations_empty`)
- **조건**: `input.observations` 리스트가 비어있거나 모든 항목이 공백만 포함
- **이유**: 관찰 데이터가 없으면 해석이 불가능

### 2.2. 해석 경계 위반 (`cannot_conclude_violation`)
- **조건**: `interpretation_boundary.cannot_conclude`에 "mechanism", "causal", "explanation" 등이 포함되어 있는데, 출력에서 금지된 패턴이 발견됨
- **금지 패턴**:
  - `mechanism` (메커니즘)
  - `cause/causal/causality` (인과관계)
  - `catalyze/catalytic` (촉매)
  - `explain/explains` (설명)
  - `therefore`, `thus`, `due to` (따라서, 따라서, ~때문에)
  - `indicates mechanism`, `suggests mechanism` (메커니즘을 시사)
- **이유**: 명시적으로 금지된 해석 범위를 벗어남

### 2.3. 질문-관찰 데이터 불일치 (`question_misaligned_with_observations`)
- **조건**: 
  - 질문에서 추출한 키워드(5자 이상)가 6개 이상
  - 그 중 70% 이상이 관찰 데이터에 전혀 등장하지 않음
- **제외 키워드**: `compare`, `between`, `effects`, `effect`, `difference` (일반적인 질문 단어)
- **이유**: 관찰 데이터로 답할 수 없는 질문

---

## 3. LLM Judge 평가 (5가지 항목)

LLM Judge는 각 샘플을 **0-100점 척도**로 평가하며, 다음 5가지 항목으로 세분화합니다:

### 3.1. Integrity (무결성) - 0~30점
- **평가 기준**: 관찰 데이터의 품질
- **포함 사항**:
  - 관찰 데이터가 비어있지 않음
  - 결과(result-like) 데이터인지 확인
  - 배경 정보나 방법론이 아닌 실제 관찰 결과인지
  - 해석적 내용이 아닌 객관적 관찰인지

### 3.2. Alignment (정렬) - 0~20점
- **평가 기준**: 질문과 관찰 데이터의 일치도
- **포함 사항**:
  - 질문이 관찰 데이터만으로 답변 가능한지
  - 질문이 관찰 데이터의 범위를 벗어나지 않는지

### 3.3. Faithfulness (충실성) - 0~25점
- **평가 기준**: 출력이 관찰 데이터에 근거하는지
- **포함 사항**:
  - 출력의 모든 주장이 관찰 데이터로 뒷받침되는지
  - 관찰 데이터에 없는 새로운 엔티티나 범위를 도입하지 않는지

### 3.4. Boundary (경계 준수) - 0~15점
- **평가 기준**: 해석 경계 제약 준수
- **포함 사항**:
  - `cannot_conclude`에 명시된 제약을 위반하지 않는지
  - `can_conclude` 범위 내에서만 해석하는지

### 3.5. Atomicity (원자성) - 0~10점
- **평가 기준**: 단일 작업 집중도
- **포함 사항**:
  - 하나의 명확한 작업에 집중하는지
  - 관련 없는 여러 도메인을 섞지 않는지

---

## 4. 최종 판정 로직

### 4.1. 하드 실패 처리
- 하드 실패가 발생하면:
  - **최종 verdict**: 무조건 `FAIL`
  - **최종 score**: LLM Judge 점수와 관계없이 **최대 49점**으로 제한

### 4.2. 점수 기반 판정
- **PASS 조건**:
  - 하드 실패가 없음
  - LLM Judge의 `final_score`가 **70점 이상**
  - LLM Judge의 `verdict`가 `PASS`
- **FAIL 조건**:
  - 하드 실패 발생
  - 또는 `final_score`가 70점 미만
  - 또는 LLM Judge의 `verdict`가 `FAIL`

### 4.3. 추천 조치 (Recommended Action)
LLM Judge가 다음 중 하나를 추천합니다:
- **KEEP AS-IS**: 그대로 사용 가능
- **USE AFTER REVISION**: 수정 후 사용 가능
- **REMOVE FROM TRAINING SET**: 학습 데이터셋에서 제거

---

## 5. LLM Judge 비활성화 모드

`USE_LLM_JUDGE=0`으로 설정하면 LLM Judge 없이 순수 규칙 기반 평가만 수행합니다.

### 5.1. 점수 계산
- **하드 실패 있음**: 35점
- **하드 실패 없음**: 
  - 기본 점수: 78점
  - 소프트 과도 추론 패널티: `SOFT_OVERREACH_WORDS` 포함 시 단어당 -3점
  - 최종 점수: `max(0, min(100, 78 - soft_penalty))`

### 5.2. 소프트 과도 추론 단어
- `likely`, `potential`, `may`, `could`, `suggest`, `imply`
- 이 단어들이 출력에 포함되면 패널티 적용

### 5.3. 판정
- **PASS**: 하드 실패 없음 AND 점수 ≥ 70
- **FAIL**: 하드 실패 있음 OR 점수 < 70

---

## 6. 데이터 구조

### 6.1. 입력 데이터 구조
```json
{
  "instruction": "지시사항",
  "input": {
    "observations": ["관찰1", "관찰2", ...],
    "question": "질문",
    "interpretation_boundary": {
      "can_conclude": ["가능한 해석1", ...],
      "cannot_conclude": ["금지된 해석1", ...]
    }
  },
  "output": {
    "interpretation": ["해석1", ...],
    "interpretation_limits": ["한계1", ...],
    "cautions": ["주의사항1", ...],
    "suggested_next_steps": ["다음 단계1", ...]
  }
}
```

### 6.2. 평가 결과 구조
```json
{
  "idx": 1,
  "verdict": "PASS" | "FAIL",
  "score": 0-100,
  "breakdown_integrity": 0-30,
  "breakdown_alignment": 0-20,
  "breakdown_faithfulness": 0-25,
  "breakdown_boundary": 0-15,
  "breakdown_atomicity": 0-10,
  "hard_fail": true | false,
  "hard_fail_reasons": ["reason1", ...],
  "key_issues": ["issue1", ...],
  "recommended_action": "KEEP AS-IS" | "USE AFTER REVISION" | "REMOVE FROM TRAINING SET"
}
```

---

## 7. 출력 파일

### 7.1. CSV 파일 (`audit_results_*.csv`)
- 모든 샘플의 평가 결과를 CSV 형식으로 저장
- `hard_fail_reasons`와 `key_issues`는 파이프(`|`)로 구분

### 7.2. JSON 파일 (`audit_results_*.json`)
- 모든 샘플의 평가 결과를 JSON 형식으로 저장
- 상세 분석용

### 7.3. 최종 JSONL 파일 (`final_sft_dataset_*.jsonl`)
- **PASS된 샘플만** 포함
- 실제 파인튜닝에 사용할 최종 데이터셋

---

## 8. 평가 원칙

1. **보수적 접근**: 불확실할 때는 FAIL 선호
2. **데이터 수정 금지**: 평가만 수행하고 데이터를 수정하지 않음
3. **엄격한 기준**: 바이오메디컬 도메인의 특성상 오해석 방지에 중점
4. **명확한 근거**: 모든 판정에 명확한 이유 제공

---

## 9. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_API_BASE` | `https://api.openai.com/v1` | LLM API 엔드포인트 |
| `OPENAI_API_KEY` | (필수) | API 키 |
| `LLM_MODEL` | `gpt-4o` | 사용할 모델 |
| `LLM_TIMEOUT_SEC` | `60` | 타임아웃 (초) |
| `LLM_RETRY` | `2` | 재시도 횟수 |
| `SLEEP_BETWEEN` | `0.2` | 샘플 간 대기 시간 (초) |
| `USE_LLM_JUDGE` | `1` | LLM Judge 사용 여부 (1=사용, 0=비사용) |

---

## 10. 요약

### 통과 기준
- ✅ 하드 실패 없음
- ✅ LLM Judge 점수 70점 이상
- ✅ 5가지 평가 항목 모두 적절한 점수 획득

### 실패 주요 원인
1. 관찰 데이터 부재
2. 해석 경계 위반 (금지된 메커니즘/인과관계 언급)
3. 질문-관찰 데이터 불일치
4. 관찰 데이터로 뒷받침되지 않는 출력
5. 여러 작업 혼재

---

**작성일**: 2025-01-23  
**버전**: 1.0

