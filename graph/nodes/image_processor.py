"""
image_processor.py
--------------------
이미지 업로드 및 분석 노드
- S3에 이미지 업로드
- Vision API로 실험 결과 JSON 추출
- 질의에 JSON 정보 덧붙이기
"""

from typing import Dict, Any, List
import json
import base64
import os
import uuid
from pathlib import Path
from datetime import datetime
from graph.llm_config import get_model_name

# boto3 import (선택적)
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    boto3 = None
    HAS_BOTO3 = False

# OpenAI Vision API 사용
from graph.nodes.call_llm import _get_openai_client


# ============================================
# S3 업로드 함수
# ============================================
def get_s3_bucket() -> str:
    """S3 버킷 이름 가져오기"""
    return os.getenv('S3_BUCKET_NAME', 'skn18-file-uploads')


def get_s3_client():
    """S3 클라이언트 생성"""
    if not HAS_BOTO3:
        return None
    region = os.getenv('AWS_REGION', 'ap-northeast-2')
    return boto3.client('s3', region_name=region)


def upload_image_to_s3(image_data: Dict[str, Any], user_id: str) -> str | None:
    """
    이미지를 S3에 업로드
    
    Args:
        image_data: 이미지 데이터 딕셔너리
            - file: File 객체 (base64 또는 File)
            - name: 파일명
            - type: MIME 타입
        user_id: 사용자 ID
    
    Returns:
        S3 URL 또는 None (실패 시)
    """
    if not HAS_BOTO3:
        print("[ImageProcessor] boto3 없음, S3 업로드 건너뜀")
        return None
    
    try:
        s3_client = get_s3_client()
        if not s3_client:
            return None
        
        bucket = get_s3_bucket()
        
        # 날짜 형식: YYYYMMDD
        date_str = datetime.now().strftime('%Y%m%d')
        file_uuid = str(uuid.uuid4())
        
        # 파일명 안전하게 처리
        original_filename = image_data.get('name', 'image.png')
        safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in ('_', '-', '.'))
        file_ext = Path(safe_filename).suffix or '.png'
        
        # S3 키 생성: chat/images/u/{user_id}/dt={date}/{uuid}{ext}
        s3_key = f'chat/images/u/{user_id}/dt={date_str}/{file_uuid}{file_ext}'
        
        # 이미지 데이터 처리
        image_file = image_data.get('file')
        if isinstance(image_file, str):
            # base64 문자열인 경우
            if image_file.startswith('data:image'):
                # data:image/png;base64,xxxx 형식
                header, encoded = image_file.split(',', 1)
                image_bytes = base64.b64decode(encoded)
            else:
                # 순수 base64
                image_bytes = base64.b64decode(image_file)
        else:
            # File 객체인 경우
            image_file.seek(0)
            image_bytes = image_file.read()
        
        # Content-Type 결정
        content_type = image_data.get('type', 'image/png')
        
        # S3에 업로드
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type
        )
        
        # S3 URL 생성
        region = os.getenv('AWS_REGION', 'ap-northeast-2')
        s3_url = f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'
        
        print(f"[ImageProcessor] S3 업로드 성공: {s3_url}")
        return s3_url
        
    except Exception as e:
        print(f"[ImageProcessor] S3 업로드 실패: {e}")
        return None


# ============================================
# Vision API로 이미지 분석
# ============================================
def analyze_image_with_vision(image_url: str, prompt_template: str) -> Dict[str, Any] | None:
    """
    Vision API를 사용하여 이미지에서 실험 결과 추출
    
    Args:
        image_url: 이미지 URL (S3 URL 또는 HTTP/HTTPS URL)
        prompt_template: 프롬프트 템플릿 (PROMPTING_FOR_INFERENCE_Q.md 내용)
    
    Returns:
        추출된 JSON 딕셔너리 또는 None
    """
    try:
        client = _get_openai_client()
        
        # 이미지 URL 처리 (S3 URL 또는 HTTP/HTTPS URL)
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_url}
        }
        
        # Vision API 호출
        response = client.chat.completions.create(
            model="gpt-4o",  # Vision 지원 모델
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_template},
                        image_content
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 추출 (마크다운 코드 블록 제거)
        if result_text.startswith('```'):
            lines = result_text.split('\n')
            # 첫 줄과 마지막 줄 제거
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            result_text = '\n'.join(lines).strip()
        
        # JSON 파싱
        try:
            result_json = json.loads(result_text)
            print(f"[ImageProcessor] 이미지 분석 성공: {len(result_text)} chars")
            
            # 추출된 JSON 전체 로그 출력
            print(f"\n{'='*60}")
            print(f"[ImageProcessor] 추출된 이미지 JSON 데이터 (사실만 추출, 의견 없음)")
            print(f"{'='*60}")
            # print(json.dumps(result_json, ensure_ascii=False, indent=2))
            print(json.dumps(result_json, ensure_ascii=False, indent=2))
            print(f"{'='*60}\n")
            
            return result_json
        except json.JSONDecodeError as e:
            print(f"\n{'='*60}")
            print(f"[ImageProcessor] JSON 파싱 실패")
            print(f"에러: {e}")
            print(f"{'='*60}")
            print(f"[ImageProcessor] 원본 응답 텍스트 전체:")
            print(f"{'='*60}")
            print(result_text)
            print(f"{'='*60}\n")
            # JSON 파싱 실패 시 원본 텍스트를 observation에 저장
            return {
                "analysis_error": True,
                "raw_text": result_text
            }
            
    except Exception as e:
        print(f"[ImageProcessor] Vision API 호출 실패: {e}")
        return None


# ============================================
# Vision API 프롬프트 템플릿 (이미지 분석용)
# ============================================
IMAGE_ANALYSIS_PROMPT = """You are a biomedical figure transcription assistant.

Your task is to EXTRACT ONLY UNAMBIGUOUS, DIRECTLY OBSERVABLE FACTS from the provided image.
This is a strict transcription task with aggressive filtering of uncertainty.

========================
HARD RULES (CRITICAL)
========================
1) Use ONLY information that is explicitly visible and unambiguous in the image
   (titles, axis labels, tick labels, group names, dose text, panel labels, and clearly readable significance markers).
2) Do NOT infer, interpret, summarize, or reconstruct comparisons.
3) Do NOT estimate numeric values from bar heights or error bars.
4) If ANY element is ambiguous, partially occluded, low-resolution, overlapping, or requires guessing:
   → DO NOT RECORD IT AT ALL.
   → Do NOT set it to null. Omit the entry entirely.
5) Significance markers (*, **, ***, ns) MUST be recorded ONLY IF:
   - The marker is clearly visible, AND
   - The bracket endpoints clearly and unambiguously map to two specific group labels.
   Otherwise, DISCARD the marker.
6) Do NOT assume comparisons based on x-axis order or visual proximity.
7) Output JSON ONLY. No markdown, no explanation, no comments.

========================
WHAT QUALIFIES AS A RECORDABLE FACT
========================
- Exact text strings that are clearly readable in the image.
- Axis labels and tick labels that are fully legible.
- Panel/time labels that are explicitly printed.
- Group names exactly as printed.
- A significance bracket ONLY when:
  - Both endpoints visually align with specific group labels, AND
  - The marker text (*, ns, etc.) is readable.

========================
WHAT MUST BE DISCARDED
========================
- Any inferred comparison (e.g., “adjacent bars”).
- Any assumed reference group (e.g., vehicle control).
- Any qualitative interpretation (increase, decrease, reduction, effect).
- Any summary across groups or time points.
- Any significance marker whose bracket endpoints are not perfectly clear.

========================
OUTPUT JSON SCHEMA (MUST MATCH EXACTLY)
========================
{
  "assay": string | null,
  "target": string | null,
  "dose": string | null,
  "y_axis_label": string | null,
  "y_axis_ticks": string[] | null,
  "time_points": string[],
  "groups": string[],
  "panels": [
    {
      "time": string,
      "significance": [
        {
          "pair": [string, string],
          "marker": string
        }
      ]
    }
  ]
}

========================
EXTRACTION PROCEDURE (FOLLOW STRICTLY)
========================
Step A) Read and copy assay, target, and dose ONLY if clearly printed.
Step B) Read all panel time labels exactly as shown.
Step C) Read all group labels exactly as printed on the x-axis.
Step D) Read y-axis label and tick labels if fully legible.
Step E) For each panel:
        - Scan for significance brackets.
        - If a bracket’s left and right endpoints clearly align with two specific group labels:
            → record exactly ONE entry with {pair, marker}.
        - If endpoints are unclear or span multiple groups:
            → DISCARD the bracket entirely.

Return JSON only.
"""


# ============================================
# 질의 보강 템플릿
# ============================================
QUERY_TEMPLATE_WITH_IMAGE = """질문: {question}

첨부된 실험 이미지 분석 결과:
{experiment_json}

위 실험 결과를 참고하여 질문에 답변해주세요."""


# ============================================
# Image Processor Node
# ============================================
def image_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    이미지 처리 노드
    - 이미지가 없으면 스킵
    - 이미지가 있으면 S3 업로드 → Vision API 분석 → 질의 보강
    
    Input:
        - state["attached_images"]: 첨부된 이미지 리스트
        - state["question"]: 사용자 질문
        - state["user_id"]: 사용자 ID
    
    Output:
        - state["image_analysis_result"]: 이미지 분석 결과 (JSON)
        - state["question"]: 보강된 질문 (이미지 분석 결과 포함)
    """
    print(f"\n{'='*60}")
    print(f"[IMAGE_PROCESSING NODE] 시작")
    print(f"{'='*60}\n")
    
    # 디버깅: state 키 확인
    print(f"[ImageProcessor] State keys: {list(state.keys())}")
    
    attached_images = state.get("attached_images", [])
    question = state.get("question", "")
    user_id = state.get("user_id", "")
    
    # 디버깅: attached_images 값 확인
    print(f"[ImageProcessor] attached_images 타입: {type(attached_images)}, 값: {attached_images}")
    print(f"[ImageProcessor] attached_images 길이: {len(attached_images) if attached_images else 0}")
    
    # 이미지가 없으면 스킵
    if not attached_images:
        print("[ImageProcessor] 첨부된 이미지 없음, 스킵")
        return state
    
    print(f"[ImageProcessor] {len(attached_images)}개 이미지 처리 시작")
    
    # 프롬프트 템플릿 사용 (파일 대신 상수로 정의된 프롬프트 사용)
    prompt_template = IMAGE_ANALYSIS_PROMPT
    print(f"[ImageProcessor] 프롬프트 템플릿 사용: {len(prompt_template)} chars")
    
    # 첫 번째 이미지만 분석 (여러 이미지가 있어도 첫 번째만)
    first_image = attached_images[0]
    
    # 1. 이미지 S3 업로드 후 URL 가져오기
    image_url = None
    
    # file 필드 확인 (base64 문자열 또는 File 객체)
    image_file = first_image.get('file')
    if image_file:
        # base64 문자열이든 File 객체든 모두 S3에 업로드
        if HAS_BOTO3:
            print("[ImageProcessor] 이미지를 S3에 업로드 중...")
            image_url = upload_image_to_s3(first_image, user_id)
        else:
            print("[ImageProcessor] boto3 없음, S3 업로드 불가")
    
    # file 필드가 없거나 S3 업로드 실패 시 url 필드 확인
    if not image_url:
        existing_url = first_image.get('url')
        if existing_url and existing_url.startswith('http'):
            # 이미 HTTP URL인 경우 그대로 사용
            image_url = existing_url
            print(f"[ImageProcessor] 기존 URL 사용: {image_url}")
    
    if not image_url:
        print("[ImageProcessor] 이미지 URL을 얻을 수 없음 (S3 업로드 실패 또는 URL 없음), 스킵")
        return state
    
    # 업로드된 이미지 URL을 state에 저장 (DB 저장용)
    if "uploaded_image_urls" not in state:
        state["uploaded_image_urls"] = []
    state["uploaded_image_urls"].append(image_url)
    print(f"[ImageProcessor] 업로드된 이미지 URL을 state에 저장: {image_url}")
    
    # 2. Vision API로 이미지 분석 (S3 URL 사용)
    print(f"[ImageProcessor] Vision API 호출 중... (이미지 URL: {image_url[:100]}...)")
    analysis_result = analyze_image_with_vision(image_url, prompt_template)
    
    if not analysis_result:
        print("[ImageProcessor] 이미지 분석 실패, 원본 질문 유지")
        # 이미지 URL은 저장했으므로 state 반환
        return state
    
    # 분석 결과를 state에 저장 (질의 보강 전에 저장)
    state["image_analysis_result"] = analysis_result
    
    # 3. 질의 보강
    try:
        experiment_json_str = json.dumps(analysis_result, ensure_ascii=False, indent=2)
        enhanced_question = QUERY_TEMPLATE_WITH_IMAGE.format(
            question=question,
            experiment_json=experiment_json_str
        )
        
        # State 업데이트
        state["question"] = enhanced_question
        
        print(f"[ImageProcessor] 질의 보강 완료")
        print(f"[ImageProcessor] 분석 결과 키: {list(analysis_result.keys())}")
        print(f"[ImageProcessor] 추출된 JSON이 state['image_analysis_result']에 저장됨")
        
    except Exception as e:
        print(f"[ImageProcessor] 질의 보강 실패: {e}, 원본 질문 유지")
    
    print(f"\n[IMAGE_PROCESSING NODE] 종료")
    print(f"{'='*60}\n")
    
    return state

