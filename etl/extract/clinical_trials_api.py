"""
Clinical Trials API 데이터 다운로드 도구

이 프로그램은 Clinical Trials API에서 임상시험 데이터를 다운로드하는 도구입니다.
원하는 질병명, 국가, 날짜 범위를 지정하면 해당 조건에 맞는 데이터를 JSON 파일로 저장합니다.

사용 방법:
    1. 명령줄에서 직접 실행:
       python clinical_trials_api.py --condition "Neoplasms" --country "China" --date_from "2023-01-01" --date_to "2025-12-31"
    
    2. 다른 파이썬 파일에서 모듈로 사용:
       from clinical_trials_api import fetch_clinical_trials
       fetch_clinical_trials("Neoplasms", "China", date_from="2023-01-01", date_to="2025-12-31")
"""
# 필요한 라이브러리 import
import requests  # 웹 API에서 데이터를 가져오기 위한 라이브러리
import json      # JSON 형식의 데이터를 다루기 위한 라이브러리
import os        # 파일/폴더를 다루기 위한 라이브러리
import argparse  # 명령줄 인자를 처리하기 위한 라이브러리


def fetch_clinical_trials(
    condition,
    country,
    output_folder=None,
    date_from="2023-01-01",
    date_to=None,
    page_size=1000,
    file_prefix=None
):
    """
    Clinical Trials API에서 데이터를 다운로드하는 메인 함수입니다.
    
    이 함수는 API에서 데이터를 가져와서 JSON 파일로 저장합니다.
    데이터가 많을 경우 여러 페이지로 나누어서 다운로드합니다.
    
    매개변수:
        condition: 질병/조건명 (예: "Neoplasms", "Cardiovascular Diseases", "Autoimmune Diseases", "Diabetes" 등)
        country: 국가명 (예: "United States", "South Korea", "Japan", "China" 등)
        output_folder: 저장할 폴더명 (지정하지 않으면 자동 생성)
        date_from: 시작 날짜 (형식: "YYYY-MM-DD", 기본값: "2023-01-01")
        date_to: 종료 날짜 (형식: "YYYY-MM-DD", 지정하지 않으면 최신까지)
        page_size: 한 번에 가져올 데이터 개수 (기본값: 1000)
        file_prefix: 파일명 앞부분 (지정하지 않으면 자동 생성)
    
    반환값:
        다운로드된 총 페이지 수
    """
    
    # ===== 1단계: 질병명과 국가명을 파일명/폴더명에 사용할 수 있는 형태로 변환 =====
    
    # 질병명을 간단한 이름으로 변환하는 함수 (파일명/폴더명에 사용)
    # 예: "Cardiovascular Diseases" → "Cardio"
    def get_condition_name(cond):
        # 입력된 질병명을 소문자로 변환하고 앞뒤 공백 제거
        cond_lower = cond.lower().strip()
        
        # 주요 질병명을 짧은 이름으로 변환 (파일명이 너무 길어지지 않도록)
        if "neoplasms" in cond_lower or "cancer" in cond_lower or "tumor" in cond_lower:
            return "neoplasms"  # 암 관련 질병
        elif "cardiovascular" in cond_lower or "cardiac" in cond_lower or "heart" in cond_lower:
            return "cardio"  # 심혈관 질병
        elif "autoimmune" in cond_lower:
            return "autoimmune"  # 자가면역 질병
        else:
            # 알려지지 않은 질병명은 공백을 언더스코어(_)로 변환
            # "Diseases", "Disease" 같은 단어 제거
            name = cond.replace(" ", "_").replace("Diseases", "").replace("Disease", "").strip("_")
            # 파일명이 너무 길면 30자로 제한
            if len(name) > 30:
                name = name[:30]
            # 빈 문자열이면 기본값 사용
            return name or "Clinical_Trial"
    
    # 국가명을 짧은 코드로 변환하는 함수 (파일명에 사용)
    # 예: "United States" → "US"
    def get_country_code_for_filename(country_name):
        # 국가명과 파일명에 사용할 코드를 매핑한 딕셔너리
        country_map = {
            "United States": "US",
            "South Korea": "",  # 한국은 파일명에 국가코드 포함 안 함 (기존 패턴 유지)
            "Korea": "",
            "Japan": "Japan",
            "China": "China",
            "Germany": "Germany",
            "France": "France",
            "United Kingdom": "UK",
            "Canada": "Canada",
            "Mexico": "Mexico",
            "Ireland": "Ireland"
        }
        # 매핑에 있는 국가면 해당 코드 반환, 없으면 공백을 언더스코어로 변환
        return country_map.get(country_name, country_name.replace(" ", "_"))
    
    # 국가명을 짧은 코드로 변환하는 함수 (폴더명에 사용)
    # 폴더명은 파일명보다 길어도 되므로 한국도 "Korea"로 표시
    def get_country_code_for_folder(country_name):
        country_map = {
            "United States": "US",
            "South Korea": "Korea",
            "Korea": "Korea",
            "Japan": "Japan",
            "China": "China",
            "Germany": "Germany",
            "France": "France",
            "United Kingdom": "UK",
            "Canada": "Canada",
            "Mexico": "Mexico",
            "Ireland": "Ireland"
        }
        return country_map.get(country_name, country_name.replace(" ", "_"))
    
    # ===== 2단계: 질병명과 국가코드를 변환 =====
    
    # 입력받은 질병명과 국가명을 파일명/폴더명에 사용할 수 있는 형태로 변환
    condition_name = get_condition_name(condition)  # 예: "Cardiovascular Diseases" → "Cardio"
    country_code_file = get_country_code_for_filename(country)  # 예: "United States" → "US"
    country_code_folder = get_country_code_for_folder(country)  # 예: "United States" → "US"
    
    # ===== 3단계: 저장 폴더 설정 및 생성 =====
    
    # 저장 폴더명이 지정되지 않았으면 자동으로 생성
    # 형식: "질병명_국가코드" (예: "Cardio_US")
    if output_folder is None:
        base_url = "data/nih/raw"
        output_folder = os.path.join(base_url, f"{condition_name}_{country_code_folder}")
    
    # 폴더가 없으면 생성 (이미 있으면 그대로 사용)
    os.makedirs(output_folder, exist_ok=True)
    
    # ===== 4단계: 파일명 앞부분 설정 =====
    
    # 파일명 앞부분이 지정되지 않았으면 자동으로 생성
    # 형식: "질병명_국가코드" (예: "Cardio_US")
    if file_prefix is None:
        if country_code_file:  # 국가코드가 있으면
            file_prefix = f"{condition_name}_{country_code_file}"
        else:  # 국가코드가 없으면 (한국의 경우)
            file_prefix = condition_name
    
    # ===== 5단계: API 요청 준비 =====
    
    # Clinical Trials API 주소
    api_url = "https://clinicaltrials.gov/api/v2/studies"
    
    # 날짜 범위를 API가 이해할 수 있는 형식으로 변환
    # 종료 날짜가 지정되면 해당 날짜까지, 없으면 최신까지
    if date_to:
        date_range = f"AREA[LastUpdatePostDate]RANGE[{date_from},{date_to}]"
    else:
        date_range = f"AREA[LastUpdatePostDate]RANGE[{date_from},MAX]"
    
    # API 요청에 필요한 파라미터 설정
    api_params = {
        "format": "json",              # 응답 형식: JSON
        "markupFormat": "markdown",    # 마크업 형식: 마크다운
        "query.cond": condition,       # 검색할 질병/조건명
        "query.term": date_range,      # 날짜 범위
        "query.locn": country,         # 국가
        "pageSize": page_size          # 한 페이지에 가져올 데이터 개수
    }
    
    # ===== 6단계: 페이지별로 데이터 다운로드 =====
    
    # 현재 페이지 번호 (1부터 시작)
    current_page = 1
    # 다음 페이지로 이동하기 위한 토큰 (첫 페이지는 None)
    next_page_token = None
    
    # 모든 페이지를 다운로드할 때까지 반복
    while True:
        print(f"\n📄 {current_page}페이지 다운로드 중...")
        
        # API 요청 파라미터 복사 (원본을 보존하기 위해)
        request_params = api_params.copy()
        # 다음 페이지가 있으면 토큰을 파라미터에 추가
        if next_page_token:
            request_params["pageToken"] = next_page_token
        
        # API에 요청을 보내서 데이터 가져오기
        response = requests.get(api_url, params=request_params)
        # HTTP 에러가 있으면 프로그램 중단 (예: 404, 500 등)
        response.raise_for_status()
        # 응답을 JSON 형식으로 변환
        data = response.json()
        
        # ===== 7단계: 다운로드한 데이터를 JSON 파일로 저장 =====
        
        # 저장할 파일 경로 생성 (예: "Cardio_US/Cardio_US_Page_1.json")
        file_path = f"{output_folder}/{file_prefix}_Page_{current_page}.json"
        # 파일을 열어서 JSON 데이터 저장
        # indent=2: 보기 좋게 들여쓰기, ensure_ascii=False: 한글 등이 깨지지 않도록
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✔ 저장 완료: {file_path}")
        
        # ===== 8단계: 다음 페이지 확인 =====
        
        # API 응답에서 다음 페이지 토큰 가져오기
        # 토큰이 있으면 다음 페이지가 있다는 의미
        next_page_token = data.get("nextPageToken")
        
        # 다음 페이지가 없으면 (토큰이 None이면) 모든 데이터 다운로드 완료
        if not next_page_token:
            print(f"\n🎉 모든 페이지 다운로드 완료! (총 {current_page}페이지)")
            break  # 반복문 종료
        
        # 다음 페이지로 이동하기 위해 페이지 번호 증가
        current_page += 1
    
    # 다운로드한 총 페이지 수 반환
    return current_page


# ===== 프로그램이 직접 실행될 때 (명령줄에서 실행할 때) =====
if __name__ == "__main__":
    # 명령줄 인자를 처리하기 위한 파서 생성
    # 사용자가 명령줄에서 입력한 옵션들을 파싱(분석)합니다
    parser = argparse.ArgumentParser(
        description="Clinical Trials API에서 데이터를 다운로드합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python clinical_trials_api.py --condition "Neoplasms" --country "China" --date_from "2023-01-01" --date_to "2025-12-31"
  python clinical_trials_api.py --condition "Diabetes" --country "United States" --date_from "2024-01-01"
  python clinical_trials_api.py -c "Cardiovascular Diseases" -l "Japan" -f "2023-01-01" -t "2025-12-31"
        """
    )
    
    # ===== 명령줄에서 받을 수 있는 옵션들 정의 =====
    
    # 질병/조건명 옵션
    parser.add_argument(
        "--condition", "-c",  # --condition 또는 -c로 사용 가능
        type=str,              # 문자열 타입
        required=False,        # 필수 입력 아님 (기본값 사용 가능)
        default="cardiovascular_diseases",   #######여기를 바꿔야 해####### 질병명 변경: "Neoplasms", "Cardiovascular Diseases", "Autoimmune Diseases", "Diabetes" 등
        help="질병/조건명 (예: 'Neoplasms', 'Cardiovascular Diseases', 'Autoimmune Diseases', 'Diabetes' 등)"
    )
    
    # 국가명 옵션
    parser.add_argument(
        "--country", "-l",     # --country 또는 -l로 사용 가능
        type=str,
        required=False,
        default="china",     #######여기를 바꿔야 해####### 국가명 변경: "United States", "South Korea", "Japan", "China", "Mexico" 등
        help="국가명 (예: 'United States', 'South Korea', 'Japan', 'China' 등)"
    )
    
    # 저장 폴더명 옵션
    parser.add_argument(
        "--output_folder", "-o",
        type=str,
        default=None,          # 기본값: None (자동 생성)
        help="저장 폴더명 (지정하지 않으면 자동 생성)"
    )
    
    # 시작 날짜 옵션
    parser.add_argument(
        "--date_from", "-f",
        type=str,
        default="2020-01-01",  #######여기를 바꿔야 해####### 시작 날짜 변경: "2020-01-01", "2023-01-01" 등 (형식: "YYYY-MM-DD")
        help="시작 날짜 (형식: 'YYYY-MM-DD', 기본값: '2023-01-01')"
    )
    
    # 종료 날짜 옵션
    parser.add_argument(
        "--date_to", "-t",
        type=str,
        default="2025-01-01",  #######여기를 바꿔야 해####### 종료 날짜 변경: "2025-12-31", "2024-12-31" 등 (형식: "YYYY-MM-DD")
        help="종료 날짜 (형식: 'YYYY-MM-DD', 지정하지 않으면 최신까지)"
    )
    
    # 페이지 크기 옵션
    parser.add_argument(
        "--page_size", "-p",
        type=int,              # 정수 타입
        default=1000,          # 기본값: 1000
        help="한 번에 가져올 데이터 개수 (기본값: 1000)"
    )
    
    # 파일명 접두사 옵션
    parser.add_argument(
        "--file_prefix",
        type=str,
        default=None,          # 기본값: None (자동 생성)
        help="파일명 앞부분 (지정하지 않으면 자동 생성)"
    )
    
    # ===== 명령줄에서 입력한 인자들을 파싱(분석) =====
    args = parser.parse_args()
    
    # ===== 다운로드할 정보를 화면에 출력 =====
    print("=" * 60)
    print("Clinical Trials 데이터 다운로드 시작")
    print(f"질병/조건: {args.condition}")
    print(f"국가: {args.country}")
    print(f"기간: {args.date_from} ~ {args.date_to if args.date_to else '최신까지'}")
    print("=" * 60)
    
    # ===== 실제 데이터 다운로드 함수 호출 =====
    total_pages = fetch_clinical_trials(
        condition=args.condition,        # 질병/조건명
        country=args.country,            # 국가명
        output_folder=args.output_folder,  # 저장 폴더명
        date_from=args.date_from,        # 시작 날짜
        date_to=args.date_to,            # 종료 날짜
        page_size=args.page_size,        # 페이지 크기
        file_prefix=args.file_prefix     # 파일명 접두사
    )
    
    # ===== 다운로드 완료 메시지 출력 =====
    print("\n" + "=" * 60)
    print(f"다운로드 완료! 총 {total_pages}페이지가 다운로드되었습니다.")
    print("=" * 60)
