# RunPod vLLM 서빙 가이드

## 📋 빠른 배포 방법 (Start Command 사용)

Docker 이미지 없이 RunPod에서 바로 vLLM 서버를 시작하는 방법입니다.

---

## 🚀 1. Pod 생성 설정

### Container Image
```
runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

### GPU 선택
- **추천**: RTX 4090
- **대안**: RTX A6000, A100

### Expose HTTP Ports
```
8888, 7801, 7804, 7812, 7808
```

### Container Disk
```
50GB 이상
```

---

## 🔑 2. Environment Variables 설정

| Name | Value | 설명 |
|------|-------|------|
| `HF_TOKEN` | `hf_xxxxxxxxxxxxx` | HuggingFace 인증 토큰 |

**HuggingFace 토큰 발급 방법**:
1. [HuggingFace Token 페이지](https://huggingface.co/settings/tokens) 접속
2. "New token" 클릭
3. Type: "Read" 선택
4. 토큰 복사

---

## 💻 3. 모델별 Start Command

### Gemma 3 1B (추천 - 가볍고 빠름)

```bash
bash -c 'pip install vllm==0.13.0 --break-system-packages && huggingface-cli login --token $HF_TOKEN && python -m vllm.entrypoints.openai.api_server --model google/gemma-3-1b-it --host 0.0.0.0 --port 7801 --dtype auto --max-model-len 8192 --trust-remote-code'
```

### Gemma 3 4B

```bash
bash -c 'pip install vllm==0.13.0 --break-system-packages && huggingface-cli login --token $HF_TOKEN && python -m vllm.entrypoints.openai.api_server --model google/gemma-3-4b-it --host 0.0.0.0 --port 7804 --dtype auto --max-model-len 8192 --trust-remote-code'
```

### Gemma 3 12B(아직 실행확인 안해봄)

```bash
bash -c 'pip install vllm==0.13.0 --break-system-packages && huggingface-cli login --token $HF_TOKEN && python -m vllm.entrypoints.openai.api_server --model google/gemma-3-12b-it --host 0.0.0.0 --port 7812 --dtype auto --max-model-len 8192 --trust-remote-code'
```

### Qwen3-VL-8B-Instruct(확인필요_vllm 0.13버전이지원하고있는지)

```bash
bash -c 'pip install vllm==0.13.0 --break-system-packages && huggingface-cli login --token $HF_TOKEN && python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-VL-8B-Instruct --host 0.0.0.0 --port 7808 --dtype auto --max-model-len 8192 --trust-remote-code'
```

### 파인튜닝한 커스텀 모델

```bash
bash -c 'pip install vllm==0.13.0 --break-system-packages && huggingface-cli login --token $HF_TOKEN && python -m vllm.entrypoints.openai.api_server --model your-username/your-finetuned-model --host 0.0.0.0 --port 7815 --dtype auto --max-model-len 8192 --trust-remote-code'
```

---

## 🌐 4. API 엔드포인트 URL

### URL 형식

```
https://[POD_ID]-7860.proxy.runpod.net/v1
```

**예시**:
```
https://m8jnilwfg85kr8-7860.proxy.runpod.net/v1
```

### URL 구성 요소

| 부분 | 설명 | 예시 |
|------|------|------|
| `[POD_ID]` | Pod 고유 ID | `m8jnilwfg85kr8` |
| `7860` | vLLM 서버 포트 | `7860` |
| `proxy.runpod.net` | RunPod 프록시 도메인 | 고정 |
| `/v1` | OpenAI API v1 엔드포인트 | 고정 |

### Pod ID 확인 방법

**RunPod 대시보드**:
1. Pod 카드 → **Connect** 탭
2. HTTP Services → Port 7860
3. URL 복사

---

## 📖 5. API 사용 예제

### Python (OpenAI 라이브러리)

```python
from openai import OpenAI

# API 클라이언트 초기화
client = OpenAI(
    base_url="https://m8jnilwfg85kr8-7860.proxy.runpod.net/v1",
    api_key="EMPTY"  # vLLM은 API 키 불필요
)

# 채팅 완성 요청
response = client.chat.completions.create(
    model="google/gemma-3-1b-it",
    messages=[
        {"role": "user", "content": "안녕하세요!"}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
```

### LangChain 통합

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://m8jnilwfg85kr8-7860.proxy.runpod.net/v1",
    api_key="EMPTY",
    model="google/gemma-3-1b-it",
    temperature=0.7
)

response = llm.invoke("파이썬으로 피보나치 수열을 구현해주세요.")
print(response.content)
```

### cURL (터미널)

```bash
curl https://m8jnilwfg85kr8-7860.proxy.runpod.net/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-3-1b-it",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

---

## 🔧 6. 배포 과정

### 단계별 진행

```
1. RunPod Pod 생성
   ├─ Container Image 입력
   ├─ GPU 선택 (RTX 4090)
   ├─ Expose HTTP Ports: 7860, 8888
   ├─ Environment Variables: HF_TOKEN
   └─ Start Command 입력 (모델별 선택)
   
2. Deploy 클릭
   
3. Pod Running 대기 (1-2분)
   
4. vLLM 설치 & 서버 시작 (2-3분)
   ├─ pip install vllm
   ├─ HuggingFace 로그인
   ├─ 모델 다운로드
   └─ vLLM 서버 시작
   
5. Connect 탭에서 URL 확인
   └─ Port 7860 → Ready 상태 확인
   
6. API 사용 시작! ✅
```

### 예상 소요 시간

- **Pod 생성**: 1-2분
- **vLLM 설치**: 1분
- **모델 다운로드**: 1-2분 (Gemma 3 1B 기준)
- **서버 시작**: 30초
- **총 소요 시간**: 약 3-5분

---

## 📊 7. 모델별 사양 비교

| 모델 | 크기 | VRAM | 속도 | 용도 |
|------|------|------|------|------|
| **Gemma 3 1B** | 1B | ~3GB | 매우 빠름 | 개발/테스트, 간단한 대화 |
| **Gemma 2 2B** | 2B | ~5GB | 빠름 | 일반 대화, 요약 |
| **Gemma 2 9B** | 9B | ~20GB | 보통 | 복잡한 추론, 코딩 |
| **Qwen 3 7B** | 7B | ~16GB | 보통 | 다국어, 코딩 |

---

## ❓ FAQ

### Q1. `/v1` 경로는 왜 필요한가요?

**A**: vLLM은 OpenAI API 호환 서버로, OpenAI API v1 스펙을 따릅니다.

**OpenAI API 엔드포인트 구조**:
```
https://api.openai.com/v1/chat/completions
                      ↑
                     v1 경로
```

**vLLM도 동일한 구조**:
```
https://[pod-id]-7860.proxy.runpod.net/v1/chat/completions
                                       ↑
                                      v1 경로
```

**base_url에 `/v1` 포함 이유**:
- OpenAI 클라이언트가 자동으로 `/chat/completions` 등을 추가
- `base_url` + `/chat/completions` = 전체 URL
- 예: `https://podid-7860.proxy.runpod.net/v1` + `/chat/completions`

**만약 `/v1`을 빼면**:
```python
base_url="https://podid-7860.proxy.runpod.net"  # /v1 없음
# 결과: https://podid-7860.proxy.runpod.net/chat/completions
# → 404 에러! (올바른 경로: /v1/chat/completions)
```

### Q2. Pod를 Stop했다가 Start하면 URL이 바뀌나요?

**A**: **Stop → Start는 URL 유지**, **Terminate → 새 Deploy는 URL 변경**

```
Stop → Start:
  Pod ID: abc123 → abc123 (동일) ✅
  URL: https://abc123-7860.proxy.runpod.net/v1 (동일) ✅

Terminate → New Deploy:
  Pod ID: abc123 → xyz789 (변경) ❌
  URL: https://xyz789-7860.proxy.runpod.net/v1 (변경) ❌
```

### Q3. 여러 모델을 동시에 서빙할 수 있나요?

**A**: 아니요, 하나의 Pod는 하나의 모델만 서빙합니다.

**여러 모델 서빙 방법**:
1. **여러 Pod 생성** (각각 다른 모델)
2. **다른 포트 사용** (같은 Pod에서 불가능)

**예시**:
```
Pod 1: Gemma 3 1B → https://pod1-7860.proxy.runpod.net/v1
Pod 2: Llama 3.1 8B → https://pod2-7860.proxy.runpod.net/v1
```

### Q4. API 키는 왜 "EMPTY"인가요?

**A**: vLLM 서버는 기본적으로 인증이 없습니다.

**보안 강화 방법**:
- RunPod URL은 추측하기 어려움 (Pod ID가 랜덤)
- 필요시 Nginx 프록시로 API 키 추가 가능
- 개발/팀 내부 사용에는 충분히 안전

### Q5. Pod 비용은 어떻게 되나요?

**A**: GPU 종류와 사용 시간에 따라 과금됩니다.

**예상 비용** (RTX 4090 기준):
- 시간당: ~$0.50
- 일일 (24시간): ~$12
- 월간 (24/7): ~$360

**절약 팁**:
- 사용하지 않을 때 **Stop** (과금 중지)
- 개발 시간만 Running 상태 유지
- Spot Instance 사용 (더 저렴, 불안정)

---

## 🛠️ 문제 해결

### 문제 1: Port 7860이 "Not Ready"

**증상**: Connect 탭에서 Port 7860이 Ready 안 됨

**해결**:
1. 3-5분 더 대기 (모델 다운로드 중)
2. **Logs** 탭에서 진행 상황 확인
3. 에러 있으면 Pod 재시작

### 문제 2: 404 에러

**증상**: URL 접속 시 404 Not Found

**원인**:
- vLLM 서버가 아직 시작 안 됨
- 잘못된 URL

**해결**:
1. Connect 탭에서 정확한 URL 확인
2. `/v1` 경로 포함했는지 확인
3. Logs에서 "Uvicorn running" 메시지 확인

### 문제 3: CUDA Out of Memory

**증상**: Logs에 "CUDA out of memory" 에러

**원인**: 선택한 GPU 메모리가 모델에 비해 작음

**해결**:
1. 더 큰 GPU 선택 (A100)
2. 더 작은 모델 사용 (Gemma 3 1B)
3. `--max-model-len` 줄이기

---

## 📚 참고 자료

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [RunPod 공식 문서](https://docs.runpod.io/)
- [OpenAI API 문서](https://platform.openai.com/docs/api-reference)
- [HuggingFace Models](https://huggingface.co/models)

---
