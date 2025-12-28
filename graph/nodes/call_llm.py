"""
각 모델(gpt-4o-mini, gpt-5-nano, SLLM, Local LLM을 호출하는 함수를 제공.
함수 형태로 호출하도록 통합 래퍼 제공.

사용 예:
    from call_llm import gpt4o_mini, sllm
    response = gpt4o_mini("Hello!")
    response = sllm("Hello!")

.env 예시:
    OPENAI_API_KEY=xxxx
    SLLM_BASE_URL=https://podid-7860.proxy.runpod.net/v1  # SLLM 서버 URL
"""

import os
import json
from dotenv import load_dotenv
load_dotenv()

# OpenAI / Gemini 공식 클라이언트
from openai import OpenAI
# import google.generativeai as genai


# -----------------------------------------
# 1) 환경변수 로드
# -----------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in .env")

SLLM_BASE_URL = os.getenv("SLLM_BASE_URL")
if not SLLM_BASE_URL:
    raise ValueError("❌ SLLM_BASE_URL not found in .env")

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
if not RUNPOD_API_KEY:
    raise ValueError("❌ RUNPOD_API_KEY not found in .env")

MODEL_NAME = os.getenv("MODEL_NAME")
if not MODEL_NAME:
    raise ValueError("❌ MODEL_NAME not found in .env")


# -----------------------------------------
# 2) 클라이언트 초기화
# -----------------------------------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------------------
# 3) 공통 response 처리 함수
# -----------------------------------------
def _parse_openai_response(resp):
    """OpenAI response에서 텍스트만 추출."""
    try:
        return resp.choices[0].message.content
    except Exception:
        return str(resp)


# -----------------------------------------
# 4) 모델별 LLM 함수
# -----------------------------------------

def gpt4_1_nano(prompt: str):
    """GPT-4.1-nano 호출"""
    resp = openai_client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return _parse_openai_response(resp)


def gpt4o_mini(prompt: str):
    """GPT-4o-mini 호출"""
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return _parse_openai_response(resp)


def gpt5_nano(prompt: str):
    """GPT-5-nano 호출"""
    resp = openai_client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_openai_response(resp)

# -----------------------------------------
# 5) SLLM 호출 (실험결과해석 모델)
# -----------------------------------------
def sllm(prompt: str, temperature: float = 0.7, max_tokens: int = 1024):
    """
    SLLM 모델 호출 (RunPod 프록시 사용)

    Args:
        prompt: 입력 프롬프트
        temperature: 생성 온도 (기본값: 0.7)
        max_tokens: 최대 토큰 수 (기본값: 1024)

    Returns:
        모델 응답 텍스트

    Raises:
        Exception: Pod가 비활성화되었거나 연결 오류가 발생한 경우
    """
    from openai import OpenAI
    import time

    print(f"\n{'='*60}")
    print(f"[SLLM] 호출 시작")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Base URL: {SLLM_BASE_URL}")
    print(f"  Temperature: {temperature}")
    print(f"  Max Tokens: {max_tokens}")
    print(f"  Prompt Length: {len(prompt)} chars")
    print(f"  Prompt Preview: {prompt[:100]}...")
    print(f"{'='*60}\n")

    sllm_client = OpenAI(
        base_url=SLLM_BASE_URL,
        api_key=RUNPOD_API_KEY,
        timeout=60.0  # 60초 타임아웃
    )

    try:
        start_time = time.time()

        resp = sllm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )

        elapsed = time.time() - start_time
        response_text = _parse_openai_response(resp)

        print(f"\n{'='*60}")
        print(f"[SLLM] 응답 성공")
        print(f"  Elapsed Time: {elapsed:.2f}s")
        print(f"  Response Length: {len(response_text)} chars")
        print(f"  Response Preview: {response_text[:100]}...")
        print(f"{'='*60}\n")

        return response_text

    except Exception as e:
        error_msg = f"[SLLM ERROR] Pod가 비활성화되었거나 연결할 수 없습니다: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg) from e


# -----------------------------------------
# 6) Local LLM (프로토콜 제시 모델)
# -----------------------------------------
# def local_llm(prompt: str):
#     """
#     vLLM 등 로컬 모델 호출
#     — REST API 라고 가정.
#     """
#     import requests
#     url = "http://localhost:8000/generate"
#     data = {"prompt": prompt}

#     try:
#         resp = requests.post(url, json=data)
#         return resp.json().get("text")
#     except Exception as e:
#         return f"[LOCAL LLM ERROR] {e}"



