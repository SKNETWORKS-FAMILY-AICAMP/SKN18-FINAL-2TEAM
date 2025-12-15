# 메모리 시스템 개선사항 (2025-12-13)

## 📌 요약
대화 메모리 전달 방식을 **케이스별 분리 → 스마트 통합**으로 개선하여 State 경량화 및 컨텍스트 정확도 향상

---

## 🔧 주요 변경사항

### 1. 메모리 전달 방식 개선
**Before (비효율적)**
```python
# 모든 케이스 타입 히스토리를 각각 전달 (무거움)
state["simulation_q_history"] = [...]  # 최대 3개
state["inference_q_history"] = [...]   # 최대 3개
state["bio_q_history"] = [...]         # 최대 3개
state["protocal_q_history"] = [...]    # 최대 3개
```

**After (효율적)** ✅
```python
# 현재 질문과 관련된 히스토리만 전달
state["relevant_history"] = [...]      # 최대 5개
state["history_source"] = "CURRENT_TYPE" | "FOLLOW_UP_TYPE"
```

### 2. 스마트 꼬리질문 처리
```python
# Classifier에서 자동 판단
state["is_follow_up"] = True/False           # 꼬리질문 여부
state["reference_case_type"] = "BIO_Q"       # 참조하는 케이스 타입
```

**동작 방식**
- 일반 질문: 현재 질문 타입의 과거 대화 전달
- 꼬리질문: 참조하는 질문 타입의 과거 대화 전달

### 3. memory_slot 개선
```python
# topic → 요약으로 변경
state["memory_slot"] = {
    "last_case": "BIO_Q",           # 직전 케이스 타입
    "last_summary": "단백질 폴딩..."  # 직전 답변 요약
}
```

---

## 📊 개선 효과

| 항목 | Before | After | 개선율 |
|------|--------|-------|--------|
| State 메모리 필드 | 4개 (각 3개) | 1개 (5개) | **~58% 절감** |
| 전달 대화 수 | 최대 12개 | 최대 5개 | **관련 대화만 전달** |
| 컨텍스트 정확도 | 낮음 (무관한 대화 포함) | 높음 (관련 대화만) | **정확도 향상** |

---

## 🎯 사용 예시

### Case 1: 일반 질문
```
Q: "단백질 폴딩이 뭐야?" (BIO_Q로 분류)
→ BIO_Q 관련 과거 대화 5개 전달
```

### Case 2: 꼬리질문 (핵심 개선!)
```
Q1: "AlphaFold3 어떻게 써?" (SIMULATION_Q)
A1: [시뮬레이션 안내]

Q2: "그 결과를 어떻게 해석해?" 
→ is_follow_up: True
→ reference_case_type: "SIMULATION_Q"
→ SIMULATION_Q 관련 과거 대화 5개 전달 ✅
   (INFERENCE_Q 대화가 아닌 원래 맥락 전달!)
```

---

## 📁 수정된 파일

1. **`graph/state.py`**
   - `is_follow_up`, `reference_case_type`, `relevant_history` 필드 추가

2. **`graph/nodes/classifier.py`**
   - 꼬리질문 자동 감지 및 참조 케이스 타입 추출

3. **`graph/nodes/memory.py`**
   - 케이스별 히스토리 제거 → `relevant_history` 통합
   - `memory_slot`에서 `topic` → `last_summary`로 변경

4. **`graph/nodes/generate_answer.py`**
   - 모든 케이스 타입(BIO_Q, SIMULATION_Q, PROTOCOL_Q, INFERENCE_Q)에서 `relevant_history` 활용

