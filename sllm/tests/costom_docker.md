# 오류발생으로 도커 이용한 방법은 잠정 중단

# vLLM 서버 Docker 이미지

vLLM을 사용한 OpenAI 호환 API 서버를 RunPod에 배포하기 위한 Docker 이미지입니다.

## 📋 목차

- [빠른 시작](#빠른-시작)
- [이미지 빌드](#이미지-빌드)
- [RunPod 배포](#runpod-배포)
- [환경변수 설정](#환경변수-설정)
- [모델 변경 방법](#모델-변경-방법)
- [사용 예시](#사용-예시)
- [문제 해결](#문제-해결)

## 🚀 빠른 시작

1. **이미지 빌드**
   ```bash
   docker build -f vllm_servingllm.dokerfile -t vllm_servingllm:latest .
   ```

2. **이미지 푸시**
   ```bash
   docker push your-registry/vllm-server:latest
   ```

3. **RunPod에서 Pod 생성**
   - Docker 이미지: `your-registry/vllm-server:latest`
   - 환경변수 설정 (아래 참조)

## 🏗️ 이미지 빌드

### 기본 빌드 (권장 방법)

1. 빌드
```bash
docker build -f vllm_servingllm.dokerfile -t vllm_servingllm:latest .
```

>  **권장**: 이미지 빌드 시 토큰을 넣을 필요가 없습니다. Pod 생성 시 `HF_TOKEN` 환경변수만 설정하면 됩니다.

2. 이미지 허브에 올리기



## ☁️ RunPod 배포

### 1. Pod 생성 페이지 접속

RunPod 대시보드 → **"Deploy"** 또는 **"Create Pod"** 클릭

### 2. Docker 이미지 설정

- **Docker Image**: `enapeace/vllm-server:latest`
- **GPU**: vLLM은 GPU가 필요하므로 적절한 GPU 인스턴스 선택

### 3. 환경변수 설정 및 모델의 port 기재재

**"Environment Variables"** 섹션에서 다음 환경변수들을 추가:

| Key | Value | 설명 |
|-----|-------|------|
| `MODEL_NAME` | `google/gemma-3-1b-it` | 사용할 모델명 |
| `PORT` | `7860` | 서버 포트 (기본값: 7860) |
| `HF_TOKEN` | `hf_xxxxx` | **HuggingFace 토큰 (private/gated 모델인 경우 필수)** |

> 💡 **중요**: `HF_TOKEN`은 **Pod 생성 시 환경변수로 설정**하면 됩니다. 빌드 타임에 토큰을 넣을 필요가 없습니다!

> 💡 **중요**: `HF_TOKEN`은 **Pod 생성 시 환경변수로 설정**하면 됩니다. 빌드 타임에 토큰을 넣을 필요가 없습니다!

### 4. Pod 배포

설정 완료 후 **"Deploy"** 버튼 클릭

## ⚙️ 환경변수 설정

### 필수 환경변수

- **`MODEL_NAME`**: 사용할 모델명
  - 기본값: `google/gemma-3-1b-it`
  - 예시: `google/gemma-3-4b-it`, `meta-llama/Llama-3.2-3B-Instruct`

### 선택 환경변수

| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `PORT` | `7860` | 서버 포트 (여러 Pod 동시 실행 시 각각 다른 포트 설정, 반드시 위에 8888, 7860 작성) |
| `MAX_MODEL_LEN` | `8192` | 최대 모델 길이 |
| `DTYPE` | `auto` | 모델 데이터 타입 (`auto`, `float16`, `bfloat16`) |
| `GPU_MEMORY_UTILIZATION` | `0.9` | GPU 메모리 사용률 (0.0~1.0) |
| `TENSOR_PARALLEL_SIZE` | 없음 | 텐서 병렬 크기 (멀티 GPU 사용 시 설정) |
| `TRUST_REMOTE_CODE` | `true` | 원격 코드 신뢰 여부 (`true`/`false`) |
| `HF_TOKEN` | 없음 | HuggingFace 토큰 (private/gated 모델인 경우) |

## 🔄 모델 변경 방법

**같은 이미지로 여러 모델을 사용할 수 있습니다!**

RunPod Pod 생성 시 `MODEL_NAME` 환경변수만 변경하면 됩니다.

### 예시: Gemma 모델 시리즈

**Pod 1: Gemma-3-1B**
```
MODEL_NAME=google/gemma-3-1b-it
PORT=7801
```

**Pod 2: Gemma-3-4B**
```
MODEL_NAME=google/gemma-3-4b-it
PORT=7804
GPU_MEMORY_UTILIZATION=0.95
```

**Pod 3: Gemma-3-12B**
```
MODEL_NAME=google/gemma-3-12b-it
PORT=7812
GPU_MEMORY_UTILIZATION=0.95
MAX_MODEL_LEN=4096
TENSOR_PARALLEL_SIZE=2  # 멀티 GPU 사용 시
```

## 📝 사용 예시

### API 호출

Pod가 시작되면 OpenAI 호환 API로 사용할 수 있습니다:

```python
import requests

# API 엔드포인트
url = "http://your-pod-ip:7801/v1/chat/completions"

# 요청
response = requests.post(url, json={
    "model": "google/gemma-3-1b-it",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
})

print(response.json())
```


## 🎯 모델 크기별 권장 설정

### 1B 모델 (예: Gemma-3-1B)
```
MODEL_NAME=google/gemma-3-1b-it
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=8192
```
- **필요 GPU 메모리**: ~2GB
- **권장 GPU**: RTX 3060, T4 등

### 4B 모델 (예: Gemma-3-4B)
```
MODEL_NAME=google/gemma-3-4b-it
GPU_MEMORY_UTILIZATION=0.95
MAX_MODEL_LEN=4096
```
- **필요 GPU 메모리**: ~8GB
- **권장 GPU**: RTX 3090, A10 등

### 12B 모델 (예: Gemma-3-12B)
```
MODEL_NAME=google/gemma-3-12b-it
GPU_MEMORY_UTILIZATION=0.95
MAX_MODEL_LEN=2048
TENSOR_PARALLEL_SIZE=2  # 멀티 GPU
```
- **필요 GPU 메모리**: ~24GB (단일 GPU) 또는 멀티 GPU
- **권장 GPU**: A100, H100 등

## 🔍 확인 방법

Pod가 정상적으로 시작되었는지 확인:

1. **로그 확인**
   - RunPod Pod 로그에서 다음 메시지 확인:
     ```
     Starting vLLM server...
     Model: google/gemma-3-1b-it
     Port: 7860
     ```

2. **API 테스트**
   ```bash
   curl http://your-pod-ip:7860/health
   ```

3. **모델 로딩 완료 확인**
   - 로그에서 "Uvicorn running on" 메시지 확인
   - 모델 다운로드 및 로딩에는 시간이 걸릴 수 있습니다

## 🐛 문제 해결

### 문제: 모델 다운로드 실패

**해결책**:
- `HF_TOKEN` 환경변수가 올바르게 설정되었는지 확인
- private/gated 모델인 경우 토큰이 필요합니다

### 문제: GPU 메모리 부족

**해결책**:
- `GPU_MEMORY_UTILIZATION` 값을 낮춤 (예: 0.8)
- `MAX_MODEL_LEN` 값을 줄임 (예: 2048)
- 더 큰 GPU 인스턴스 사용

### 문제: 포트 충돌

**해결책**:
- 여러 Pod를 동시에 실행할 때 각각 다른 `PORT` 설정
- 예: Pod1=7801, Pod2=7804, Pod3=7812

### 문제: 서버가 시작되지 않음

**해결책**:
- Pod 로그에서 오류 메시지 확인
- 환경변수 이름이 정확한지 확인 (대소문자 구분)
- Docker 이미지가 올바르게 빌드되었는지 확인

## 📚 참고 자료

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [RunPod 문서](https://docs.runpod.io/)
- [HuggingFace 모델 허브](https://huggingface.co/models)

## 💡 팁

1. **템플릿 저장**: 자주 사용하는 환경변수 조합을 텍스트로 저장해두면 편리합니다
2. **포트 관리**: 여러 Pod를 동시에 실행할 때 포트를 체계적으로 관리하세요
3. **비용 최적화**: 테스트 후 사용하지 않는 Pod는 중지하여 비용을 절감하세요
4. **모델 캐싱**: 한 번 다운로드한 모델은 캐시에 저장되므로 재시작 시 빠릅니다

