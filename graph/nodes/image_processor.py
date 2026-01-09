"""
image_processor.py
--------------------
이미지 업로드 및 분석 노드
- S3에 이미지 업로드
- Vision API로 실험 결과 JSON 추출
- 질의에 JSON 정보 덧붙이기
"""

from typing import Dict, Any, List, Optional
import json
import base64
import os
import uuid
from pathlib import Path
from datetime import datetime
import httpx
from graph.llm_config import get_model_name
from graph.logger_config import get_logger

logger = get_logger(__name__)

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
# chandra 모델 클라이언트 생성
# ============================================
def _get_chandra_client():
    """chandra 모델용 OpenAI 클라이언트 생성 (vLLM 서빙)"""
    from openai import OpenAI
    return OpenAI(
        base_url="https://j8pr82uxpeizpc-8000.proxy.runpod.net/v1",
        api_key="EMPTY",
        http_client=httpx.Client(timeout=300.0),
    )


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
        logger.warning("boto3 없음, S3 업로드 건너뜀")
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
        
        logger.info(f"S3 업로드 성공: {s3_url}")
        return s3_url
        
    except Exception as e:
        logger.error(f"S3 업로드 실패: {e}", exc_info=True)
        return None


# ============================================
# Stage 1: Vision API로 이미지에서 원시 JSON 추출
# ============================================
def stage1_extract_from_image(image_url: str) -> Dict[str, Any] | None:
    """
    Stage 1: Ultra-Conservative Extraction
    Vision API를 사용하여 이미지에서 사실만 추출 (OCR + 구조 인식)
    
    Args:
        image_url: 이미지 URL (S3 URL 또는 HTTP/HTTPS URL)
    
    Returns:
        추출된 원시 JSON 딕셔너리 또는 None
    """
    return analyze_image_with_vision(image_url, STAGE1_PROMPT)


# ============================================
# Stage 2: JSON 정제 및 검증
# ============================================
def stage2_refine_json(stage1_json: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Stage 2: Rule-Based JSON Refinement
    Stage 1 JSON을 검증하고 정제 (규칙 검사 + 논리 검증)
    
    Args:
        stage1_json: Stage 1에서 추출된 원시 JSON
    
    Returns:
        정제된 JSON 딕셔너리 또는 None
    """
    try:
        client = _get_openai_client()
        
        # Stage 1 JSON을 문자열로 변환
        stage1_json_str = json.dumps(stage1_json, ensure_ascii=False, indent=2)
        
        # Stage 2 프롬프트 생성
        prompt = f"""다음은 Stage 1에서 추출된 원시 JSON 데이터입니다.

{stage1_json_str}

위 JSON을 검증하고 정제해주세요. Stage 2 규칙을 따르세요."""
        
        # LLM 호출 (이미지 없이, JSON만 입력)
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {
                    "role": "system",
                    "content": STAGE2_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_completion_tokens=4000
        )
        
        # 응답이 잘렸는지 확인
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            logger.warning("⚠️ Stage 2 응답이 max_completion_tokens 제한으로 잘렸습니다.")
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 추출 (마크다운 코드 블록 제거)
        if result_text.startswith('```'):
            lines = result_text.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            result_text = '\n'.join(lines).strip()
        
        # JSON 파싱
        try:
            refined_json = json.loads(result_text)
            logger.info(f"Stage 2 정제 완료: {len(result_text)} chars")
            
            # Stage 2 정제된 JSON 로그 출력
            logger.info(f"Stage 2 정제된 JSON 데이터:\n{json.dumps(refined_json, ensure_ascii=False, indent=2)}")
            
            return refined_json
        except json.JSONDecodeError as e:
            logger.error(f"Stage 2 JSON 파싱 실패: {e}")
            logger.debug(f"Stage 2 원본 응답 텍스트:\n{result_text}")
            # 파싱 실패 시 Stage 1 JSON 반환
            logger.warning("Stage 2 실패, Stage 1 JSON을 그대로 사용합니다.")
            return stage1_json
            
    except Exception as e:
        logger.error(f"Stage 2 정제 실패: {e}", exc_info=True)
        # 실패 시 Stage 1 JSON 반환
        logger.warning("Stage 2 실패, Stage 1 JSON을 그대로 사용합니다.")
        return stage1_json


# ============================================
# Stage 3: TOON 변환 (성능 테스트용, 선택적)
# ============================================
def stage3_convert_to_toon(stage2_json: Dict[str, Any]) -> Optional[str]:
    """
    Stage 3: TOON 포맷 변환 (성능 테스트용)
    Stage 2 정제된 JSON을 TOON 포맷으로 변환
    
    Args:
        stage2_json: Stage 2에서 정제된 JSON
    
    Returns:
        TOON 포맷 문자열 또는 None (실패 시)
    """
    try:
        # toon_format 라이브러리 import 시도
        try:
            from toon_format import encode
        except ImportError:
            logger.warning("⚠️ toon_format 라이브러리가 설치되지 않았습니다. TOON 변환을 건너뜁니다.")
            logger.info("설치 방법: pip install git+https://github.com/toon-format/toon-python.git")
            return None
        
        # TOON 변환
        toon_str = encode(stage2_json)
        
        # 토큰 절약 효과 계산 (근사치)
        json_str = json.dumps(stage2_json, ensure_ascii=False, indent=2)
        json_size = len(json_str)
        toon_size = len(toon_str)
        
        if json_size > 0:
            savings_percent = (1 - toon_size / json_size) * 100
            logger.info(f"Stage 3 TOON 변환 완료: {toon_size} chars (JSON: {json_size} chars, {savings_percent:.1f}% 절약)")
        else:
            logger.info(f"Stage 3 TOON 변환 완료: {toon_size} chars")
        
        return toon_str
        
    except Exception as e:
        logger.error(f"Stage 3 TOON 변환 실패: {e}", exc_info=True)
        logger.warning("TOON 변환 실패, JSON 형식으로 계속 진행합니다.")
        return None


# ============================================
# Vision API로 이미지 분석 (내부 함수)
# ============================================
def analyze_image_with_vision(image_url: str, prompt_template: str) -> Dict[str, Any] | None:
    """
    chandra 모델(vLLM 서빙)을 사용하여 이미지에서 실험 결과 추출
    
    Args:
        image_url: 이미지 URL (S3 URL 또는 HTTP/HTTPS URL)
        prompt_template: 프롬프트 템플릿 (STAGE1_PROMPT)
    
    Returns:
        추출된 JSON 딕셔너리 또는 None
    """
    try:
        from openai import InternalServerError, APIConnectionError, APIError
        
        client = _get_chandra_client()
        
        # 이미지 URL 처리 (S3 URL 또는 HTTP/HTTPS URL)
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_url}
        }
        
        # chandra 모델 API 호출
        response = client.chat.completions.create(
            model="chandra",
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
            max_completion_tokens=8192  # chandra OCR: 복잡한 이미지와 구조화된 JSON 출력을 위해 충분한 토큰 할당
        )
        
        # 응답이 잘렸는지 확인
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            logger.warning("⚠️ chandra 모델 응답이 max_completion_tokens 제한으로 잘렸습니다. 일부 데이터가 누락되었을 수 있습니다.")
        
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
            logger.info(f"Stage 1 추출 성공: {len(result_text)} chars")
            
            # Stage 1 원시 JSON 로그 출력
            logger.info(f"[Stage 1] 추출된 원시 JSON 데이터:\n{json.dumps(result_json, ensure_ascii=False, indent=2)}")
            
            return result_json
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.debug(f"원본 응답 텍스트 전체:\n{result_text}")
            # JSON 파싱 실패 시 원본 텍스트를 observation에 저장
            return {
                "analysis_error": True,
                "raw_text": result_text
            }
            
    except InternalServerError as e:
        # 502 Bad Gateway 등 서버 에러
        error_msg = str(e)
        if "502" in error_msg or "Bad gateway" in error_msg:
            logger.error("⚠️ chandra 모델 서버가 응답하지 않습니다 (502 Bad Gateway). RunPod 서버 상태를 확인해주세요.")
        else:
            logger.error(f"⚠️ chandra 모델 서버 에러 (InternalServerError): {e}")
        return None
    except APIConnectionError as e:
        logger.error(f"⚠️ chandra 모델 서버 연결 실패 (APIConnectionError): {e}")
        return None
    except APIError as e:
        logger.error(f"⚠️ chandra 모델 API 에러: {e}")
        return None
    except Exception as e:
        logger.error(f"⚠️ chandra 모델 API 호출 실패: {e}", exc_info=True)
        return None


# ============================================
# Stage 1: Ultra-Conservative Extraction (chandra OCR)
# ============================================
STAGE1_PROMPT = """You are an OCR transcription assistant for biomedical figures.

Your task is to EXTRACT ONLY VISIBLE TEXT AND STRUCTURE from the image.
This is a PURE OCR TASK - extract text exactly as it appears, without any interpretation.

CRITICAL RULES:
1. Extract ONLY text that is explicitly visible and readable in the image
2. DO NOT interpret, analyze, or infer anything
3. DO NOT estimate values from graphs, bars, or curves
4. DO NOT assign meaning to symbols or annotations
5. If text is unclear or ambiguous, DO NOT include it

EXTRACT THE FOLLOWING (if visible):
- Figure title and caption text (exact text only)
- Panel labels (e.g., "A", "B", "0.5h", "1h")
- Axis labels (x-axis, y-axis labels)
- Axis tick labels (numbers/text on axes)
- Legend text (exact labels only)
- Group names (exactly as written)
- Printed dose/condition text
- Statistical annotation symbols (e.g., "*", "**", "ns") - text only, no interpretation
- Table cell text (if tables are present)

DO NOT EXTRACT:
- Values estimated from graph positions
- Inferred relationships between groups
- Biological interpretations
- Comparisons or trends
- Anything that requires guessing

OUTPUT FORMAT:
Output a JSON object with this structure (use only fields that apply):

{
  "figure_context": {
    "title": "exact title text if visible",
    "caption": "exact caption text if visible",
    "assay_or_method": "text if explicitly stated",
    "target_or_marker": "text if explicitly stated",
    "dose_or_condition": "text if explicitly stated"
  },
  "panels": [
    {
      "panel_id": "A or 1 or identifier",
      "panel_label": "exact label text",
      "panel_type": "bar_plot" | "line_plot" | "scatter" | "table" | "image_only" | "other",
      "axes": {
        "x_label": "exact x-axis label",
        "y_label": "exact y-axis label",
        "x_ticks": ["tick1", "tick2", ...],
        "y_ticks": ["tick1", "tick2", ...],
        "units": { "x": "unit if visible", "y": "unit if visible" }
      },
      "legend_labels": ["label1", "label2", ...],
      "conditions": {
        "time_point": "text if explicitly stated",
        "dose": "text if explicitly stated"
      },
      "raw_annotations": [
        {
          "text": "exact symbol text (e.g., '*', 'ns')",
          "location": "brief location description"
        }
      ]
    }
  ]
}

IMPORTANT:
- Output JSON only, no markdown, no explanations
- Use empty arrays [] if no data is available
- Omit fields entirely if no data exists
- Extract text exactly as it appears - no modifications
- If uncertain about any text, omit it

Return JSON only."""


# ============================================
# Stage 2: Rule-Based JSON Refinement
# ============================================
STAGE2_PROMPT = """You are a biomedical figure JSON validator and refiner.

INPUT:
- You will receive a JSON object produced by STAGE 1 (chandra OCR: image → raw JSON).
- Stage 1 used chandra OCR model to extract visible text and structure from the image.
- You do NOT have access to the image.
- Therefore, you MUST NOT invent or add new factual content.

GOAL:
- Produce a FACT-SAFE, SELF-DESCRIBING JSON that:
  (1) contains ONLY information supported by the input JSON,
  (2) removes any risky/ambiguous/inferred content,
  (3) normalizes minor formatting inconsistencies (whitespace, empty strings, structure),
  (4) optionally adds a "validation" section describing issues found.

CRITICAL: Stage 2 is primarily about DELETION and CLEANUP, NOT enhancement.
"Refinement" means removing wrong things and normalizing structure, NOT adding new content.

================================================
ABSOLUTE HARD RULES
================================================

1) DO NOT add new facts.
   - You may only copy, delete, or normalize what already exists in the input.
   - You may not create new group names, time points, doses, labels, or comparisons.

2) DO NOT infer comparisons or trends.
   - No "increase/decrease".
   - No "control vs treatment".
   - No biological interpretation.

3) DO NOT manufacture statistical comparison pairs.
   - If the input contains entities for significance, you must treat them as suspicious.
   - Without the image, you cannot verify bracket endpoints.

4) Prefer DELETION over GUESSING.
   - If something is questionable, remove it.
   - Empty arrays are acceptable.
   - Primary action: DELETE invalid/risky content.
   - Secondary action: NORMALIZE formatting (whitespace, empty strings, structure).
   - Tertiary action (rare): MINIMAL structural cleanup (e.g., renaming keys for consistency, but NO new data).

5) OCR error correction (MINIMAL, only obvious fixes):
   - You may fix obvious OCR errors ONLY if you are 100% certain (e.g., "0" vs "O" in context, "1" vs "l").
   - DO NOT correct scientific terms or abbreviations unless it's clearly a typo.
   - When in doubt, keep the original OCR text.
   - If you correct anything, add a note in validation.issues explaining the correction.

================================================
SIGNIFICANCE / ANNOTATIONS POLICY (STAGE 2)
================================================

Because you cannot see the image:

A) If annotations are in "raw_annotations" (recommended STAGE 1 format):
   - Keep them as raw symbols only.
   - DO NOT convert them into compared entity pairs.
   - Optionally, you may rename/standardize "raw_annotations" entries.

B) If the input contains any annotation objects with "entities": [A, B]
   - You MUST NOT trust these entity pairings.
   - Remove the "entities" field OR remove the entire annotation.
   - Default action: remove the entire annotation unless it is purely textual
     and does not imply comparisons.

C) If the input contains p-values or significance markers without entity mapping:
   - Keep only the literal text and (optional) a coarse location string if present.

================================================
OUTPUT REQUIREMENTS
================================================

- Output JSON ONLY.
- No markdown.
- No explanation.
- The output must be "self-describing" with labels/units.
- Preserve panel structure if present.

================================================
CANONICAL OUTPUT SHAPE (USE WHAT APPLIES)
================================================

{
  "figure_context": { ... },
  "panels": [ ... ],
  "validation": {
    "issues": [
      {
        "severity": "error" | "warning" | "info",
        "path": string,
        "message": string
      }
    ],
    "actions_taken": [
      {
        "action": "removed" | "normalized" | "kept",
        "path": string,
        "details": string
      }
    ]
  }
}

================================================
REFINEMENT CHECKLIST (APPLY IN ORDER)
================================================

Step 1) Validate type/shape:
  - Ensure top-level keys are objects/arrays as expected.
  - Remove unknown keys that look like derived analysis (e.g., "interpretation", "conclusion").

Step 2) Clean figure_context:
  - Trim whitespace.
  - Remove empty-string fields (""), omit them entirely.
  - Keep only fields that contain non-empty strings.
  - Fix obvious OCR errors ONLY if 100% certain (e.g., "Figure 1" vs "Figure I", but preserve scientific terms as-is).
  
  TERMINOLOGY CONSISTENCY CHECK (CRITICAL):
  - Compare "figure_context.target_or_marker" with panel "axes.y_label" values.
  - If they use different terminology (e.g., "Hyaluronan" vs "HA positive pixels (%)"):
      → DO NOT auto-correct or change either value (you cannot see the image).
      → ADD a validation warning (severity: "info") explaining the terminology difference.
      → Example warning:
        {
          "severity": "info",
          "path": "figure_context.target_or_marker",
          "message": "Target label derived from title text; axis label uses '[y_label_text]'. Terminology differs."
        }
  - Same check applies to:
      - "target_or_marker" vs "y_label"
      - "assay_or_method" vs panel labels or conditions
      - Any other context fields that might overlap with panel-level labels

Step 3) Clean panels:
  - Ensure each panel has:
    - panel_id (string)
    - panel_label (string) if present
    - panel_type (string) if present
  - Normalize axes:
    - Remove empty x_label/y_label if empty strings
    - Keep x_ticks/y_ticks only if they are non-empty arrays of strings
    - Keep units only if non-empty strings exist
  - Normalize conditions:
    - Remove empty strings
    - Keep only non-empty fields

Step 4) Handle annotations:
  - If "raw_annotations" exists:
      - keep as-is, but remove entries with empty text
      - normalize text to exact visible markers (e.g., "*", "**", "***", "ns", "p=...")
  - If "annotations" contains "entities":
      - REMOVE the entire annotations array (default safest)
      - Add a validation warning explaining why
  - If "annotations" exists without entities and only contains text:
      - you may keep it, but ensure it does not imply comparisons

Step 5) Remove anything that implies numeric datapoints beyond printed text:
  - If any field looks like measured values from bars/curves (e.g., "mean", "value": "12.3" not from ticks),
    remove it unless it is explicitly labeled as an axis tick or table cell in input.

Step 6) Terminology consistency validation:
  - Check for terminology mismatches between figure_context and panels.
  - If "target_or_marker" exists and panels have "axes.y_label":
      - Compare the terminology (exact match, partial match, or completely different).
      - If different, add validation warning but DO NOT change either value.
      - Warning should explain which source each term comes from (title vs axis).
  - Apply similar checks for other context fields that might overlap with panel data.
  
Step 7) Produce validation report:
  - Add issues for:
      - Any content you removed
      - Any terminology inconsistencies found
      - Any suspicious patterns detected
  - Include JSON pointer-like paths (e.g., "panels[0].annotations", "figure_context.target_or_marker").
  - Use appropriate severity levels:
      - "error": Invalid/structure-breaking issues
      - "warning": Risky or ambiguous content
      - "info": Terminology inconsistencies, minor inconsistencies

FINAL REMINDER:
You cannot see the image.
So you must be conservative.
When in doubt, delete.

Remember:
- Stage 2 is 80% DELETION, 15% NORMALIZATION, 5% minimal structural cleanup.
- You are NOT enriching the data.
- You are making it SAFER by removing risky parts.

Return JSON only.
"""


# ============================================
# Legacy prompt (사용 안함, 원래 의도가 담김 전체 프롬프트, 한 번에 불가능 해서 2단계로 분리)
# ============================================
IMAGE_ANALYSIS_PROMPT = """You are a biomedical figure transcription assistant.

Your task is to TRANSCRIBE ONLY UNAMBIGUOUS, DIRECTLY OBSERVABLE FACTS
from the provided image into JSON.

This is a STRICT TRANSCRIPTION task.
NOT interpretation. NOT summarization. NOT analysis.
Silence is correct. Guessing is incorrect.

Figures may include IHC, IF, WB, ELISA, qPCR, flow, bar/line plots, tables, etc.
Each figure is different.

You MUST adapt the JSON structure to THIS IMAGE.
Do NOT force a fixed schema.

================================================
ABSOLUTE HARD RULES (NON-NEGOTIABLE)
================================================

1) USE ONLY information that is explicitly visible and readable in the image:
   - titles and captions
   - panel labels
   - axis labels and tick labels
   - legend labels
   - group names
   - units
   - printed dose/time text
   - clearly readable annotation text

2) DO NOT interpret or infer ANYTHING.
   - Do NOT describe increase, decrease, trend, effect, or comparison.
   - Do NOT explain biological meaning.
   - Do NOT assume control vs treatment logic.
   - Do NOT assume comparisons based on position, color, or convention.

3) DO NOT estimate or derive numeric values.
   - Bar heights, curve positions, and error bars are NOT data.
   - Record ONLY numbers printed as text in the image
     (axis ticks, table cells, explicit labels).

4) AMBIGUITY OVERRIDES COMPLETENESS (MOST IMPORTANT RULE):
   If ANY element requires guessing, reconstruction, alignment inference,
   or domain knowledge:
   → DO NOT RECORD IT.
   - Do NOT output null.
   - Do NOT approximate.
   - Do NOT "best guess".
   - OMIT the element entirely.
   EMPTY ARRAYS ARE ALWAYS CORRECT.

================================================
STATISTICAL SIGNIFICANCE — EXTREME RESTRICTION
================================================

Statistical annotations (*, **, ***, ns, p-values) are HIGH RISK.

You may record a significance annotation ONLY IF **ALL** conditions below are met:

A) The annotation text (*, **, ***, ns, p=...) is clearly readable.

B) The bracket has EXACTLY TWO endpoints.

C) Each endpoint can be mapped to ONE AND ONLY ONE x-axis label
   by direct, obvious vertical alignment (no diagonal, no grouping).

D) The bracket spans EXACTLY TWO bars (not more, not nested).

E) The mapping does NOT rely on:
   - x-axis order
   - proximity
   - assumed control groups
   - scientific convention or expectation

F) You are 100% CERTAIN of the compared entities.

If **ANY** condition fails:
→ DISCARD THE ENTIRE SIGNIFICANCE ANNOTATION.

CRITICAL PROHIBITIONS:
- NEVER default to Vehicle, Control, or the leftmost group.
- NEVER reconstruct or normalize comparisons.
- NEVER split multi-group brackets into pairs.
- NEVER guess the compared entities.

An empty "annotations" array is ALWAYS a valid and correct output.

================================================
OUTPUT FORMAT RULES
================================================

- Output JSON ONLY.
- No markdown.
- No explanation.
- No comments.
- No trailing text.

The JSON must be SELF-DESCRIBING.
Include labels and units that explain what each field represents.

================================================
ALLOWED JSON TOOLBOX (USE ONLY WHAT APPLIES)
================================================

{
  "figure_context": {
    "title": string,
    "caption": string,
    "assay_or_method": string,
    "target_or_marker": string,
    "dose_or_condition": string,
    "sample_or_model": string
  },
  "panels": [
    {
      "panel_id": string,
      "panel_label": string,
      "panel_type": "bar_plot" | "line_plot" | "scatter" | "table" | "image_only" | "other",
      "axes": {
        "x_label": string,
        "y_label": string,
        "x_ticks": string[],
        "y_ticks": string[],
        "units": { "x": string, "y": string }
      },
      "legend": [
        { "label": string, "style": string }
      ],
      "conditions": {
        "time_point": string,
        "dose": string,
        "treatment": string
      },
      "annotations": [
        {
          "annotation_type": "significance" | "p_value" | "note" | "n_value",
          "text": string,
          "entities": [string, string]
        }
      ],
      "data_table": [
        {
          "row_label": string,
          "col_label": string,
          "value": string,
          "unit": string
        }
      ]
    }
  ]
}

================================================
MANDATORY EXTRACTION PROCEDURE
================================================

Step 1) Transcribe visible figure-level text (title, caption, dose).

Step 2) Identify panels ONLY if they are visually separable
        (e.g., labeled "0.5h", "1h", "2h", "4h").

Step 3) For each panel:
        - Identify panel_type from visible structure.
        - Transcribe axis labels, tick labels, and units ONLY if fully legible.
        - Transcribe group names EXACTLY as written.
        - Transcribe explicit conditions printed near the panel.

Step 4) Statistical annotations:
        - Apply the EXTREME RESTRICTION rules above.
        - If uncertain, DISCARD without hesitation.

Step 5) Tables:
        - Transcribe ONLY cells that are clearly readable.

FINAL REMINDER:
If you are unsure whether something is correct,
LEAVE IT OUT.
Silence is correct. Guessing is incorrect.

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
    logger.info("[IMAGE_PROCESSING NODE] 시작")
    
    # 디버깅: state 키 확인
    logger.debug(f"State keys: {list(state.keys())}")
    
    attached_images = state.get("attached_images", [])
    question = state.get("question", "")
    user_id = state.get("user_id", "")
    
    # 디버깅: attached_images 값 확인
    logger.debug(f"attached_images 타입: {type(attached_images)}, 값: {attached_images}, 길이: {len(attached_images) if attached_images else 0}")
    
    # 이미지가 없으면 스킵
    if not attached_images:
        logger.info("첨부된 이미지 없음, 스킵")
        return state
    
    logger.info(f"{len(attached_images)}개 이미지 처리 시작")
    
    # 2단계 처리 (Stage 1 + Stage 2)
    
    # 첫 번째 이미지만 분석 (여러 이미지가 있어도 첫 번째만)
    first_image = attached_images[0]
    
    # 1. 이미지 S3 업로드 후 URL 가져오기
    image_url = None
    
    # file 필드 확인 (base64 문자열 또는 File 객체)
    image_file = first_image.get('file')
    if image_file:
        # base64 문자열이든 File 객체든 모두 S3에 업로드
        if HAS_BOTO3:
            logger.info("이미지를 S3에 업로드 중...")
            image_url = upload_image_to_s3(first_image, user_id)
        else:
            logger.warning("boto3 없음, S3 업로드 불가")
    
    # file 필드가 없거나 S3 업로드 실패 시 url 필드 확인
    if not image_url:
        existing_url = first_image.get('url')
        if existing_url and existing_url.startswith('http'):
            # 이미 HTTP URL인 경우 그대로 사용
            image_url = existing_url
            logger.info(f"기존 URL 사용: {image_url}")
    
    if not image_url:
        logger.warning("이미지 URL을 얻을 수 없음 (S3 업로드 실패 또는 URL 없음), 스킵")
        return state
    
    # 업로드된 이미지 URL을 state에 저장 (DB 저장용)
    if "uploaded_image_urls" not in state:
        state["uploaded_image_urls"] = []
    state["uploaded_image_urls"].append(image_url)
    logger.info(f"업로드된 이미지 URL을 state에 저장: {image_url}")
    
    
    ##########################################################################
    # 2. Stage 1: Vision API로 이미지에서 원시 JSON 추출
    ##########################################################################

    logger.info(f"[Stage 1] Vision API 호출 중... (이미지 URL: {image_url[:100]}...)")
    stage1_result = stage1_extract_from_image(image_url)
    
    if not stage1_result:
        logger.warning("[Stage 1] 이미지 추출 실패, 원본 질문 유지")
        # 이미지 URL은 저장했으므로 state 반환
        return state
      
      
    ##########################################################################
    # 3. Stage 2: JSON 정제 및 검증
    ##########################################################################
    
    logger.info("[Stage 2] JSON 정제 및 검증 시작...")
    stage2_result = stage2_refine_json(stage1_result)
    
    if not stage2_result:
        logger.warning("[Stage 2] 정제 실패, Stage 1 결과 사용")
        stage2_result = stage1_result
    
    # 최종 분석 결과를 state에 저장 (JSON 형식)
    state["image_analysis_result"] = stage2_result
    logger.info(f"Stage 2 정제 완료 - Stage 2 결과 키: {list(stage2_result.keys())}")
    
    
    ##########################################################################
    # 4. Stage 3: TOON 변환 (성능 테스트용, 선택적)
    ##########################################################################
    
    # 환경 변수로 TOON 변환 활성화/비활성화 제어 (기본값: True)
    enable_toon_conversion = os.getenv('ENABLE_TOON_CONVERSION', 'true').lower() in ('true', '1', 'yes')
    
    if enable_toon_conversion:
        logger.info("[Stage 3] TOON 포맷 변환 시작...")
        toon_result = stage3_convert_to_toon(stage2_result)
        
        if toon_result:
            # TOON 변환 성공 시 별도 필드에 저장
            state["image_analysis_result_toon"] = toon_result
            logger.info("image_analysis_result_toon이 state에 저장되었습니다 (성능 테스트용)")
        else:
            logger.warning("[Stage 3] TOON 변환 실패 또는 비활성화, JSON 형식으로 계속 진행")
    else:
        logger.info("[Stage 3] TOON 변환 비활성화됨 (ENABLE_TOON_CONVERSION=false)")
    
    # 원본 질문 보존 (generate_answer에서 image_analysis_result와 함께 사용)
    # 질의 보강은 generate_answer 노드에서 처리하도록 변경
    logger.info(f"image_analysis_result가 state에 저장되었습니다 (generate_answer에서 사용)")
    
    logger.info("[IMAGE_PROCESSING NODE] 종료")
    
    return state

