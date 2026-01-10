"""
image_processor.py
--------------------

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
# Stage 1: Vision API로 이미지에서 마크다운 형태로 모든 사실 추출 (Two-Pass)
# ============================================
def stage1_extract_from_image(image_url: str) -> str | None:
    """
    Stage 1: 마크다운 형태로 그래프의 모든 사실 추출 (Two-Pass)

    Pass 0: 그래프 타입 판별 (bar_chart, line_chart 등)
    Pass 1: 타입별 특화 프롬프트로 상세 추출

    수치가 명확하게 안보이는 경우 '대략' '약' 이런 식으로 수치를 뽑아내도 됨

    Args:
        image_url: 이미지 URL (S3 URL 또는 HTTP/HTTPS URL)

    Returns:
        추출된 마크다운 텍스트 또는 None
    """
    # Pass 0: 그래프 타입 판별 (짧은 프롬프트)
    logger.info("[Stage 1 - Pass 0] 그래프 타입 판별 중...")

    figure_type_raw = analyze_image_with_vision(
        image_url,
        FIGURE_TYPE_DETECTION_PROMPT,
        return_as_text=True
    )

    if not figure_type_raw:
        logger.warning("[Stage 1 - Pass 0] 타입 판별 실패, 'unknown'으로 폴백")
        figure_type = "unknown"
    else:
        # 타입 정규화 (응답에서 타입명만 추출)
        figure_type = figure_type_raw.strip().lower()

        # 여러 줄인 경우 첫 줄만 사용
        if '\n' in figure_type:
            figure_type = figure_type.split('\n')[0].strip()

        # 알려진 타입 목록
        known_types = list(FIGURE_TYPE_PROMPTS.keys())

        # 타입이 알려진 타입에 속하는지 확인
        if figure_type not in known_types:
            # 부분 매칭 시도 (예: "bar chart" → "bar_chart")
            for known_type in known_types:
                if known_type.replace('_', ' ') in figure_type or known_type in figure_type:
                    figure_type = known_type
                    break
            else:
                # 매칭 실패 시 unknown으로 폴백
                logger.warning(f"[Stage 1 - Pass 0] 알 수 없는 타입: {figure_type}, 'unknown'으로 폴백")
                figure_type = "unknown"

    logger.info(f"[Stage 1 - Pass 0] 판별된 그래프 타입: {figure_type}")

    # Pass 1: 타입별 특화 프롬프트로 상세 추출
    logger.info(f"[Stage 1 - Pass 1] {figure_type} 전용 프롬프트로 상세 추출 중...")

    specialized_prompt = FIGURE_TYPE_PROMPTS.get(figure_type, MIXED_FALLBACK_PROMPT)

    markdown_result = analyze_image_with_vision(
        image_url,
        specialized_prompt,
        return_as_text=True
    )

    if not markdown_result:
        logger.warning("[Stage 1 - Pass 1] 상세 추출 실패")
        return None

    # 타입 정보를 마크다운 헤더에 추가 (Stage 2에서 활용 가능)
    markdown_with_type = f"<!-- Figure Type: {figure_type} -->\n\n{markdown_result}"

    logger.info(f"[Stage 1] Two-Pass 추출 완료 (타입: {figure_type}, 길이: {len(markdown_result)} chars)")

    return markdown_with_type


# ============================================
# Stage 2: 마크다운에서 JSON으로 변환
# ============================================
def stage2_convert_markdown_to_json(stage1_markdown: str) -> Dict[str, Any] | None:
    """
    Stage 2: 마크다운 → JSON 변환
    Stage 1에서 추출된 마크다운을 구조화된 JSON으로 변환

    Args:
        stage1_markdown: Stage 1에서 추출된 마크다운 텍스트

    Returns:
        변환된 JSON 딕셔너리 또는 None
    """
    try:
        from graph.nodes.call_llm import sllm

        # Stage 2 User 프롬프트 생성
        user_prompt = f"""The following is experimental result data in markdown format extracted from Stage 1.

    {stage1_markdown}

    Please convert the above markdown to JSON. Follow Stage 2 rules."""

        # sllm 호출 (system_prompt 포함)
        # max_tokens를 2000으로 축소 (sllm 컨텍스트 윈도우 4096 고려)
        result_text = sllm(
            prompt=user_prompt,
            system_prompt=STAGE2_PROMPT,
            temperature=0.1,
            max_tokens=2000
        )

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
            converted_json = json.loads(result_text)
            logger.info(f"Stage 2 변환 완료: {len(result_text)} chars")

            # Stage 2 변환된 JSON 로그 출력
            logger.info(f"Stage 2 변환된 JSON 데이터:\n{json.dumps(converted_json, ensure_ascii=False, indent=2)}")

            return converted_json
        except json.JSONDecodeError as e:
            logger.error(f"Stage 2 JSON 파싱 실패: {e}")
            logger.debug(f"Stage 2 원본 응답 텍스트:\n{result_text}")
            # 파싱 실패 시 None 반환
            logger.warning("Stage 2 실패, 마크다운을 JSON으로 변환할 수 없습니다.")
            return None

    except Exception as e:
        logger.error(f"Stage 2 변환 실패: {e}", exc_info=True)
        return None


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
def analyze_image_with_vision(image_url: str, prompt_template: str, return_as_text: bool = False) -> str | Dict[str, Any] | None:
    """
    chandra 모델(vLLM 서빙)을 사용하여 이미지에서 실험 결과 추출

    Args:
        image_url: 이미지 URL (S3 URL 또는 HTTP/HTTPS URL)
        prompt_template: 프롬프트 템플릿 (STAGE1_PROMPT)
        return_as_text: True면 텍스트 그대로 반환, False면 JSON 파싱 시도

    Returns:
        return_as_text=True: 추출된 텍스트(마크다운) 또는 None
        return_as_text=False: 추출된 JSON 딕셔너리 또는 None
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
            # max_completion_tokens=8192  # chandra OCR: 복잡한 이미지와 구조화된 JSON 출력을 위해 충분한 토큰 할당
        )

        # 응답이 잘렸는지 확인
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            logger.warning("⚠️ chandra 모델 응답이 max_completion_tokens 제한으로 잘렸습니다. 일부 데이터가 누락되었을 수 있습니다.")

        result_text = response.choices[0].message.content.strip()

        # return_as_text=True인 경우 텍스트 그대로 반환 (마크다운 등)
        if return_as_text:
            logger.info(f"Stage 1 추출 성공 (텍스트): {len(result_text)} chars")
            logger.info(f"[Stage 1] 추출된 마크다운 데이터:\n{result_text}")
            return result_text

        # return_as_text=False인 경우 JSON 파싱 시도 (하위 호환성)
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
# Pass 0: 그래프 타입 판별용 프롬프트 (매우 짧음)
# ============================================
FIGURE_TYPE_DETECTION_PROMPT = """Identify the figure type from this biomedical image.

    Choose EXACTLY ONE type from:
    - bar_chart
    - line_chart
    - scatter_plot
    - box_plot
    - heatmap
    - microscopy
    - western_blot
    - table
    - mixed (multiple graph types in one figure)
    - unknown

    Return ONLY the type name, nothing else."""


# ============================================
# Pass 1: 타입별 전문 추출 프롬프트
# ============================================

# Bar Chart 전용 프롬프트
BAR_CHART_PROMPT = """You are analyzing a BAR CHART from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Experimental method: [method if visible]
    - Measured target: [target/marker]
    - Sample: [sample type if visible]

    ## Axis Information
    - X-axis: [x-axis label]
    - Y-axis: [y-axis label] (unit: [unit])
    - Y-axis range: [min] ~ [max]

    ## Bar Data (left to right, in order)

    For each bar:
    - Bar [N]: [group name]
    - Height: approximately [value] [unit]
    - Color: [color]
    - Error bar: [present/absent]

    ## Statistical Significance

    Record all significance markers (brackets, asterisks, lines, etc.):
    - [Bar N] vs [Bar M]: [*, **, ***, ns, p=value, etc.]

    RULES:
    - Number bars sequentially from left to right: 1, 2, 3...
    - If group name is unclear, label as "Bar N" only
    - Estimate height based on Y-axis scale, use "approximately"
    - Record all significance markers completely (brackets, lines, asterisks, etc.)
    - Clearly specify which bars the brackets are above and which bars the asterisks are above

    Return English markdown only."""


# Line Chart 전용 프롬프트
LINE_CHART_PROMPT = """You are analyzing a LINE CHART from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Experimental method: [method]
    - Measured target: [target/marker]

    ## Axis Information
    - X-axis: [x-axis label] (unit: [unit])
    - Y-axis: [y-axis label] (unit: [unit])

    ## Line Data

    For each line:
    - Line [N]: [legend label]
    - Color/style: [color/style]
    - Start value (X=[x_start]): approximately [y_value]
    - Intermediate observed values: X=[x] → Y≈[y], ...
    - End value (X=[x_end]): approximately [y_value]
    - Overall trend: [increasing/decreasing/stable/variable]
    - Error bar/shading: [present/absent]

    ## Statistical Significance
    [Only if significance markers between lines exist at specific X points]

    RULES:
    - Estimate all values based on scale markings, use "approximately"
    - Record major inflection points or notable features
    - Describe trends only as overall patterns

    Return English markdown only."""


# Scatter Plot 전용 프롬프트
SCATTER_PLOT_PROMPT = """You are analyzing a SCATTER PLOT from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Measurement content: [what is being measured]

    ## Axis Information
    - X-axis: [x-axis label] (unit: [unit], range: [min]~[max])
    - Y-axis: [y-axis label] (unit: [unit], range: [min]~[max])

    ## Point Distribution

    - Total number of points: approximately [N]
    - Distribution by group (if distinguished by color/shape):
    - Group A ([color/shape]): approximately [N] points, mainly distributed in [X range] × [Y range] area
    - Group B: ...

    ## Visual Patterns
    - Correlation: [positive/negative/none/non-linear]
    - Dense regions: [near X, Y coordinates]
    - Outliers: [present/absent, location]
    - Regression line/trend line: [present/absent, equation or slope]

    RULES:
    - Focus on distribution patterns rather than exact point counts
    - No statistical interpretation, only visual patterns

    Return English markdown only."""


# Box Plot 전용 프롬프트
BOX_PLOT_PROMPT = """You are analyzing a BOX PLOT from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Axis Information
    - X-axis: [groups]
    - Y-axis: [y-axis label] (unit: [unit])

    ## Box Data (left to right)

    For each box:
    - Box [N]: [group name]
    - Median: approximately [value]
    - Box range (IQR): approximately [Q1] ~ [Q3]
    - Whisker range: approximately [min] ~ [max]
    - Outliers: [count, location]

    ## Statistical Significance
    [Only if brackets are clear]

    RULES:
    - Estimate each line position of the box based on Y-axis scale
    - Use "approximately"

    Return English markdown only."""


# Microscopy 전용 프롬프트
MICROSCOPY_PROMPT = """You are analyzing MICROSCOPY/IHC/IF images from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Staining/markers: [staining method, markers]
    - Tissue/sample: [tissue type]
    - Magnification: [magnification if visible]
    - Scale bar: [length]

    ## Observations by Panel

    For each panel/image:
    ### Panel [A/B/C or condition name]
    - Condition: [treatment, time point]
    - Channel: [DAPI, GFP, etc. if multi-channel]
    - Observations:
    - Staining intensity: [strong/moderate/weak/absent]
    - Distribution: [uniform/non-uniform, region]
    - Cell density: [high/moderate/low]
    - Morphological features: [color, shape, size]
    - Quantitative indicators: [if overlay numbers exist]

    RULES:
    - Record only color, intensity, and distribution
    - No functional/interpretive meaning
    - Specify color for each channel

    Return English markdown only."""


# Heatmap 전용 프롬프트
HEATMAP_PROMPT = """You are analyzing a HEATMAP from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Data type: [gene expression, protein levels, etc.]

    ## Axis Information
    - X-axis (columns): [list labels or count]
    - Y-axis (rows): [list labels or count]
    - Color scale: [minimum value] (color) ~ [maximum value] (color)

    ## Main Patterns
    - High expression/value regions: [location, color]
    - Low expression/value regions: [location, color]
    - Clustering: [dendrogram present/absent, major clusters]
    - Notable patterns: [diagonal, blocks, etc.]

    RULES:
    - Focus on overall patterns rather than individual cell values
    - If labels are too numerous, record only the count

    Return English markdown only."""


# Western Blot 전용 프롬프트
WESTERN_BLOT_PROMPT = """You are analyzing a WESTERN BLOT from a biomedical experiment.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Target proteins: [protein names]
    - Sample/condition: [treatment groups]

    ## Band Information

    For each target:
    ### [Protein name] ([expected molecular weight] kDa)
    - Lane composition: [Lane 1: Condition A, Lane 2: Condition B, ...]
    - Band observations:
    - Lane 1: Band [strong/moderate/weak/absent], position [kDa]
    - Lane 2: ...
    - Loading control (if present): [β-actin, GAPDH, etc.]

    ## Quantitative Data (if present)
    - Graph type: [bar chart, etc.]
    - Values: [if relative values are shown]

    RULES:
    - Evaluate band intensity visually only
    - Record position with reference to molecular weight markers

    Return English markdown only."""


# Table 전용 프롬프트
TABLE_PROMPT = """You are analyzing a TABLE from a biomedical paper.

    Extract ALL data in English markdown format.

    STRUCTURE:
    # Table Title (if visible)

    ## Table Structure
    - Number of rows: [N]
    - Number of columns: [M] 

    ## Content
    [Copy entire content in markdown table format]

    | Col1 | Col2 | Col3 | ... |
    |------|------|------|-----|
    | ... | ... | ... | ... |

    ## Footnotes/Notes
    [Table footer notes or abbreviation explanations]

    RULES:
    - Transcribe all cell contents accurately
    - Keep numbers as-is, keep text as-is
    - Empty cells as blank

    Return English markdown only."""


# Mixed/Unknown 폴백 프롬프트
MIXED_FALLBACK_PROMPT = """You are analyzing a complex or mixed-type figure.

    Extract ALL observable facts in English markdown format.

    STRUCTURE:
    # Figure Title (if visible)

    ## Overall Context
    - Experimental method: [method]
    - Measured target: [target]

    ## Components
    [Describe each panel or subgraph independently]

    ### Component 1: [bar chart, microscopy image, etc.]
    [Description appropriate for that type]

    ### Component 2: [...]
    [...]

    RULES:
    - Describe complex structures completely without omission
    - Mention panel relationships if explicitly indicated

    Return English markdown only."""


# ============================================
# 타입별 프롬프트 매핑
# ============================================
FIGURE_TYPE_PROMPTS = {
    "bar_chart": BAR_CHART_PROMPT,
    "line_chart": LINE_CHART_PROMPT,
    "scatter_plot": SCATTER_PLOT_PROMPT,
    "box_plot": BOX_PLOT_PROMPT,
    "heatmap": HEATMAP_PROMPT,
    "microscopy": MICROSCOPY_PROMPT,
    "western_blot": WESTERN_BLOT_PROMPT,
    "table": TABLE_PROMPT,
    "mixed": MIXED_FALLBACK_PROMPT,
    "unknown": MIXED_FALLBACK_PROMPT,
}


# ============================================
# Stage 2: 마크다운 → JSON 변환
# ============================================
STAGE2_PROMPT = """You are a biomedical data structuring assistant.

    INPUT:
    - You will receive markdown text produced by STAGE 1 (image → markdown description)
    - The markdown contains all observable facts from a biomedical figure/graph
    - Your task is to convert this markdown into structured JSON

    GOAL:
    - Convert the markdown description into a well-structured JSON format
    - Preserve ALL information from the markdown
    - Organize data into logical sections (context, panels, data, statistics)
    - Keep estimated values with their qualifiers (approximately, roughly, etc.)

    OUTPUT JSON STRUCTURE:
    ```json
    {
    "figure_context": {
        "title": "string (if available)",
        "assay_or_method": "string",
        "target_or_marker": "string",
        "sample_or_model": "string"
    },
    "panels": [
        {
        "panel_id": "A | B | main | etc.",
        "panel_label": "string (time point or condition)",
        "axes": {
            "x_label": "string",
            "y_label": "string",
            "x_unit": "string (if applicable)",
            "y_unit": "string (if applicable)"
        },
        "groups": [
            {
            "name": "string (group name from legend or x-axis)",
            "value": "string (observed value, may include approximately/roughly)",
            "value_numeric": number | null (numeric value if parseable, null if approximate),
            "error_bar": "present | absent | unknown"
            }
        ],
        "statistical_comparisons": [
            {
            "group1": "string",
            "group2": "string",
            "significance": "* | ** | *** | ns | p=value",
            "note": "string (additional context if any)"
            }
        ],
        "observations": "string (any additional visual observations)"
        }
    ]
    }
    ```

    CONVERSION RULES:
    1. **Preserve all information** - don't omit anything from the markdown
    2. **Keep approximations** - if markdown says "approximately 50%", store value as "approximately 50%" and value_numeric as 50 or null
    3. **Structure comparisons** - extract statistical significance markers and group pairs
    4. **Maintain original text** - keep descriptions and labels as-is
    5. **Handle missing data** - use null or omit fields if information is not available

    IMPORTANT:
    - Output JSON only (no markdown code blocks, no explanations)
    - Be faithful to the input markdown
    - If the markdown structure is different from the template, adapt the JSON structure accordingly
    - Preserve all qualitative descriptions and observations

    Return JSON only."""


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
QUERY_TEMPLATE_WITH_IMAGE = """Question: {question}

    Attached experimental image analysis results:
    {experiment_json}

    Please answer the question by referring to the above experimental results."""


# ============================================
# Image Processor Node
# ============================================
def image_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:

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
    # Stage 2, 3 비활성화 - Stage 1 마크다운만 state에 저장
    ##########################################################################

    # Stage 1의 마크다운 결과를 state에 저장 (generate_answer에서 사용)
    state["image_analysis_markdown"] = stage1_result
    logger.info(f"[IMAGE_PROCESSING NODE] Stage 1 마크다운만 state에 저장 완료 - 길이: {len(stage1_result)} chars")
    logger.info("[IMAGE_PROCESSING NODE] Stage 2, 3은 비활성화됨 (마크다운만 사용)")

    # 원본 질문 보존 (generate_answer에서 image_analysis_markdown과 함께 사용)
    logger.info("[IMAGE_PROCESSING NODE] 종료")

    return state

