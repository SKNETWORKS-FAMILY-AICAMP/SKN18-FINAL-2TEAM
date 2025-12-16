"""
call_llm.py
--------------------
각 모델(gpt-4o-mini, gpt-5-nano, SLLM, Local LLM - Gemini는 비활성화)을
함수 형태로 호출하도록 통합 래퍼 제공.

사용 예:
    from call_llm import gpt4o_mini
    response = gpt4o_mini("Hello!")

.env 예시:
    OPENAI_API_KEY=xxxx
    GEMINI_API_KEY=xxxx
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
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in .env")

# if not GEMINI_API_KEY:
#     raise ValueError("❌ GEMINI_API_KEY not found in .env")


# -----------------------------------------
# 2) 클라이언트 초기화
# -----------------------------------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# genai.configure(api_key=GEMINI_API_KEY)
# gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash")


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


# def gemini_llm(prompt: str):
#     """Google Gemini Flash 호출"""
#     resp = gemini_model.generate_content(prompt)
#     return resp.text


# -----------------------------------------
# 5) SLLM 호출 (너희 실험결과해석 모델)
# -----------------------------------------
def sllm(prompt: str):
    """
    내부 구축한 작은 SLLM 호출
    — REST API 서버를 만들었다고 가정.
    """
    import requests
    url = "http://localhost:8001/sllm"   # 네 서버 엔드포인트로 변경
    data = {"prompt": prompt}

    try:
        resp = requests.post(url, json=data, timeout=10)
        return resp.json().get("response")
    except Exception as e:
        return f"[SLLM ERROR] {e}"


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



