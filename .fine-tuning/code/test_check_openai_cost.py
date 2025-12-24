'''
check_openai_cost.py
-------------------------------------
OpenAI API 사용량을 확인하는 코드
gpt-4o-mini에게 이미지를 전달하고 해석을 부탁했을 때 
그 해석과, 사용되는 토큰 수를 확인하는 코드.
'''

import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 확인
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# 이미지 캡션 (하드코딩)
IMAGE_CAPTION = "Schematic illustration of LNP formation process in a microfluidic device at (a) slower and (b) faster mixing. Reprinted from [30] with the permission of the Public Library of Science."


def encode_image(image_path: str) -> str:
    """
    이미지 파일을 base64로 인코딩
    
    Args:
        image_path: 이미지 파일 경로
        
    Returns:
        base64 인코딩된 이미지 문자열
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def check_image_analysis(image_path_or_url: str, prompt: str = "이 이미지를 자세히 분석하고 설명해주세요.") -> dict:
    """
    이미지를 gpt-4o-mini에 전달하고 해석 결과와 토큰 사용량 확인
    
    Args:
        image_path_or_url: 이미지 파일 경로 또는 공개 이미지 URL
        prompt: 이미지에 대한 질문/요청 프롬프트
        
    Returns:
        해석 결과 및 토큰 사용량 정보
    """
    # URL인지 파일 경로인지 확인
    is_url = image_path_or_url.startswith(('http://', 'https://'))
    
    if is_url:
        # URL인 경우 직접 사용 (공개 URL이어야 함)
        image_url = image_path_or_url
        print(f"📷 이미지 URL 분석 시작: {image_url}")
    else:
        # 파일 경로인 경우
        if not os.path.exists(image_path_or_url):
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path_or_url}")
        
        # 이미지 base64 인코딩
        base64_image = encode_image(image_path_or_url)
        
        # 이미지 확장자 확인
        image_ext = Path(image_path_or_url).suffix.lower()
        mime_type = f"image/{image_ext[1:]}" if image_ext else "image/png"
        if image_ext == ".jpg":
            mime_type = "image/jpeg"
        
        # base64 데이터 URL 생성
        image_url = f"data:{mime_type};base64,{base64_image}"
        print(f"📷 이미지 파일 분석 시작: {image_path_or_url}")
    
    # 하드코딩된 캡션을 프롬프트에 포함
    enhanced_prompt = f"""이미지 캡션 정보:
{IMAGE_CAPTION}

위 캡션 정보를 참고하여 {prompt}"""
    
    print(f"📝 캡션: {IMAGE_CAPTION}")
    print(f"💬 프롬프트: {prompt}\n")
    
    try:
        # OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": enhanced_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # 응답 내용 (해석)
        answer = response.choices[0].message.content
        
        # 토큰 사용량
        usage = response.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
        
        # 결과 출력
        print("=" * 60)
        print("🤖 AI 해석 결과")
        print("=" * 60)
        print(answer)
        print()
        print("=" * 60)
        print("📊 토큰 사용량")
        print("=" * 60)
        print(f"입력 토큰 (Prompt): {prompt_tokens:,} tokens")
        print(f"출력 토큰 (Completion): {completion_tokens:,} tokens")
        print(f"총 토큰: {total_tokens:,} tokens")
        print()
        
        return {
            "interpretation": answer,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        }
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    # 기본 이미지 디렉토리 설정
    # .fine-tuning/code/check_openai_cost.py -> .fine-tuning/code -> .fine-tuning
    default_image_dir = Path(__file__).parent.parent / "data" / "raw" / "image"
    
    # 명령줄 인자로 이미지 경로 또는 URL 받기
    if len(sys.argv) > 1:
        image_input = sys.argv[1]
        
        # URL인지 확인
        is_url = image_input.startswith(('http://', 'https://'))
        
        if is_url:
            # URL인 경우 그대로 사용
            image_path_or_url = image_input
        else:
            # 파일 경로인 경우
            # 상대 경로인 경우 기본 이미지 디렉토리에서 찾기
            if not os.path.isabs(image_input) and not os.path.exists(image_input):
                image_path_or_url = str(default_image_dir / image_input)
            else:
                image_path_or_url = image_input
        
        prompt = sys.argv[2] if len(sys.argv) > 2 else "이 이미지를 자세히 분석하고 설명해주세요."
    else:
        # 기본값: 기본 이미지 디렉토리에서 이미지 찾기
        print("사용법: python check_openai_cost.py <이미지_파일명_또는_URL> [프롬프트]")
        print(f"기본 이미지 디렉토리: {default_image_dir}")
        print("\n예시:")
        print("  python check_openai_cost.py image.png")
        print("  python check_openai_cost.py image.jpg \"이 이미지에서 무엇을 볼 수 있나요?\"")
        print("  python check_openai_cost.py https://example.com/image.jpg \"이미지 분석\"")
        print("\n참고:")
        print("  - 이미지 파일 경로 또는 공개 이미지 URL 사용 가능")
        print("  - URL은 공개적으로 접근 가능해야 함")
        print("  - 캡션은 코드에 하드코딩되어 있습니다.")
        sys.exit(1)
    
    # 이미지 분석 및 토큰 사용량 확인 실행 (캡션은 하드코딩된 값 사용)
    result = check_image_analysis(image_path_or_url, prompt)