"""
Clinical Trials API 데이터 다운로드 도구

이 프로그램은 Clinical Trials API에서 임상시험 데이터를 다운로드하는 도구입니다.
3개의 고정된 질병명(Neoplasms, Autoimmune Diseases, Cardiovascular Diseases)에 대해
2023-01-01부터 오늘까지의 데이터를 병렬 처리로 다운로드합니다.
"""
# 필요한 라이브러리 import
import requests  # 웹 API에서 데이터를 가져오기 위한 라이브러리
import json      # JSON 형식의 데이터를 다루기 위한 라이브러리
import os        # 파일/폴더를 다루기 위한 라이브러리
import time      # Rate limiting을 위한 시간 지연
from datetime import datetime, timedelta  # 날짜 처리
from concurrent.futures import ThreadPoolExecutor, as_completed  # 병렬 처리
from threading import Lock  # 스레드 안전성

# ===== 설정 변수 =====
CONDITIONS = [
    "Neoplasms",
    "Autoimmune Diseases",
    "Cardiovascular Diseases",
]  # 고정된 질병명 목록
COUNTRIES = ["US", "KR", "JP"]  # 고정된 국가 코드 목록
DATE_FROM = "2023-01-01"  # 시작 날짜 (고정)
PAGE_SIZE = 1000  # 한 번에 가져올 데이터 개수 (최대값 권장)
OUTPUT_FOLDER = None  # 저장 폴더명 (None이면 자동 생성)
FILE_PREFIX = None  # 파일명 앞부분 (None이면 자동 생성)

# Rate limiting 설정
MAX_REQUESTS_PER_SECOND = 8  # 안전 마진을 두고 10보다 낮게 설정
MAX_WORKERS = 1  # 동시 스레드 수 (페이지 다운로드용) - 5에서 2로 감소
MAX_COUNTRY_WORKERS = 1  # 국가별 병렬 처리 워커 수 - 3에서 1로 감소 (순차 처리)
REQUEST_DELAY = 1.0 / MAX_REQUESTS_PER_SECOND  # 요청 간 최소 간격 (초)
MAX_RETRIES = 3  # 최대 재시도 횟수
BACKOFF_FACTOR = 2  # Exponential backoff 배수


class RateLimiter:
    """Rate limiting을 위한 클래스 (60초당 50회 제한)"""
    def __init__(self, max_calls=50, time_period=60):
        self.max_calls = max_calls
        self.time_period = time_period
        self.calls = []
        self.lock = Lock()
    
    def wait_if_needed(self):
        """필요시 대기"""
        with self.lock:
            now = time.time()
            # 오래된 호출 기록 제거
            self.calls = [call_time for call_time in self.calls 
                         if now - call_time < self.time_period]
            
            # 최대 호출 수 초과 시 대기
            if len(self.calls) >= self.max_calls:
                sleep_time = self.time_period - (now - self.calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls 
                                 if now - call_time < self.time_period]
            
            self.calls.append(now)


def fetch_page_with_retry(
    api_url, 
    request_params, 
    max_retries=MAX_RETRIES, 
    backoff_factor=BACKOFF_FACTOR
):
    """
    재시도 로직이 포함된 페이지 다운로드 함수
    
    Args:
        api_url: API URL
        request_params: 요청 파라미터
        max_retries: 최대 재시도 횟수
        backoff_factor: 백오프 배수 (exponential backoff)
    
    Returns:
        (success: bool, data: dict, error: str)
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(api_url, params=request_params, timeout=30)
            response.raise_for_status()
            return True, response.json(), None
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"⚠️  재시도 {attempt + 1}/{max_retries} - {wait_time:.1f}초 대기...")
                time.sleep(wait_time)
            else:
                return False, None, str(e)
    return False, None, "Max retries exceeded"


def download_single_page(
    page_num,
    api_url,
    api_params,
    next_page_token,
    output_folder,
    file_prefix,
    rate_limiter,
    s3_prefix=None  # 추가: S3 접두사 (Lambda 환경에서만 사용)
):
    """
    단일 페이지를 다운로드하는 함수 (병렬 처리용)
    
    Returns:
        (success: bool, page_num: int, next_token: str, error: str)
    """
    # Rate limiting 적용
    rate_limiter.wait_if_needed()
    time.sleep(REQUEST_DELAY)  # 추가 안전 마진
    
    request_params = api_params.copy()
    if next_page_token:
        request_params["pageToken"] = next_page_token
    
    success, data, error = fetch_page_with_retry(api_url, request_params)
    
    if not success:
        return False, page_num, None, error
    
    # 파일 저장
    file_path = f"{output_folder}/{file_prefix}_Page_{page_num}.json"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✔ [{file_prefix}] 페이지 {page_num} 저장 완료")
        
        # Lambda 환경에서 즉시 S3에 업로드하고 로컬 파일 삭제
        is_lambda = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
        if is_lambda and s3_prefix:
            try:
                from infra.aws.lambda_functions.trigger_etl.common.s3_utils import (
                    upload_file_to_s3
                )
                
                # S3 키 생성: s3_prefix/{파일명}
                s3_key = f"{s3_prefix}/{file_prefix}_Page_{page_num}.json"
                
                # S3에 업로드
                if upload_file_to_s3(file_path, s3_key):
                    # 업로드 성공 후 로컬 파일 삭제
                    os.remove(file_path)
                    print(f"📤 [{file_prefix}] 페이지 {page_num} S3 업로드 완료 및 로컬 파일 삭제")
                else:
                    print(f"⚠️  [{file_prefix}] 페이지 {page_num} S3 업로드 실패 (로컬 파일 유지)")
            except Exception as e:
                print(f"⚠️  [{file_prefix}] 페이지 {page_num} S3 업로드 중 오류: {e} (로컬 파일 유지)")
        
        return True, page_num, data.get("nextPageToken"), None
    except Exception as e:
        return False, page_num, None, f"File save error: {str(e)}"


def fetch_clinical_trials_for_condition(
    condition,
    country,
    output_folder=None,
    date_from=DATE_FROM,
    date_to=None,
    page_size=PAGE_SIZE,
    file_prefix=None,
    rate_limiter=None,
    s3_prefix=None  # 추가: S3 접두사
):
    """
    특정 질병/조건에 대해 임상시험 데이터를 다운로드하는 함수
    
    Args:
        condition: 질병/조건명 (예: "Neoplasms")
        country: 국가명 (예: "United States")
        output_folder: 저장 폴더명 (None이면 OUTPUT_FOLDER 환경 변수 또는 기본값 사용)
        date_from: 시작 날짜 (YYYY-MM-DD 형식)
        date_to: 종료 날짜 (None이면 오늘까지)
        page_size: 한 페이지에 가져올 데이터 개수
        file_prefix: 파일명 앞부분
        rate_limiter: RateLimiter 인스턴스
    
    Returns:
        (success: bool, total_pages: int, error: str)
    """
    # 종료 날짜가 None이면 오늘 날짜로 설정
    if date_to is None:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    # ===== 1단계: 질병명과 국가명을 파일명/폴더명에 사용할 수 있는 형태로 변환 =====
    
    # 질병명을 간단한 이름으로 변환하는 함수 (파일명/폴더명에 사용)
    # 예: "Cardiovascular Diseases" → "Cardio"
    def get_condition_name(cond):
        # 입력된 질병명을 소문자로 변환하고 앞뒤 공백 제거
        cond_lower = cond.lower().strip()
        
        # 주요 질병명을 짧은 이름으로 변환 (파일명이 너무 길어지지 않도록)
        if "neoplasms" in cond_lower or "cancer" in cond_lower or "tumor" in cond_lower:
            return "neoplasms"
        elif "cardiovascular" in cond_lower or "cardiac" in cond_lower or "heart" in cond_lower:
            return "cardio"
        elif "autoimmune" in cond_lower:
            return "autoimmune"
        else:
            name = cond.replace(" ", "_").replace("Diseases", "").replace("Disease", "").strip("_")
            if len(name) > 30:
                name = name[:30]
            return name or "Clinical_Trial"
    
    def get_country_code_for_filename(country_name):
        country_map = {
            "United States": "US",
            "South Korea": "",
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
        return country_map.get(country_name, country_name.replace(" ", "_"))
    
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
    
    # Lambda 환경 감지
    is_lambda = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    
    # Lambda 환경에서 S3 접두사 생성
    if is_lambda and s3_prefix is None:
        current_date = datetime.now().strftime("%Y%m%d")
        condition_folder_name = f"{condition_name}_{country_code_folder}"
        s3_prefix = f"data/raw/nih/{current_date}/{condition_folder_name}"
    
    # 저장 폴더명이 지정되지 않았으면 환경 변수 또는 기본값 사용
    if output_folder is None:
        # 환경 변수에서 가져오기 (Lambda 핸들러에서 설정됨)
        output_folder = os.environ.get("OUTPUT_FOLDER")
        
        if output_folder is None:
            # 환경 변수도 없으면 기본값 사용
            current_date = datetime.now().strftime("%Y%m%d")
            if is_lambda:
                # Lambda 환경: /tmp 사용
                base_url = "/tmp/data/raw/nih"
            else:
                # 로컬 환경: 프로젝트 루트 기준
                base_url = "data/raw/nih"
            output_folder = os.path.join(base_url, current_date)
    
    # condition별 하위 폴더 생성
    condition_folder = os.path.join(output_folder, f"{condition_name}_{country_code_folder}")
    os.makedirs(condition_folder, exist_ok=True)
    
    # ===== 4단계: 파일명 앞부분 설정 =====
    
    # 파일명 앞부분이 지정되지 않았으면 자동으로 생성
    # 형식: "질병명_국가코드" (예: "Cardio_US")
    if file_prefix is None:
        if country_code_file:
            file_prefix = f"{condition_name}_{country_code_file}"
        else:
            file_prefix = condition_name
    
    # ===== 5단계: API 요청 준비 =====
    
    # Clinical Trials API 주소
    api_url = "https://clinicaltrials.gov/api/v2/studies"
    
    if date_to:
        date_range = f"AREA[LastUpdatePostDate]RANGE[{date_from},{date_to}]"
    else:
        date_range = f"AREA[LastUpdatePostDate]RANGE[{date_from},MAX]"
    
    api_params = {
        "format": "json",              # 응답 형식: JSON
        "markupFormat": "markdown",    # 마크업 형식: 마크다운
        "query.cond": condition,       # 검색할 질병/조건명
        "query.term": date_range,      # 날짜 범위
        "query.locn": country,         # 국가
        "pageSize": page_size          # 한 페이지에 가져올 데이터 개수
    }
    
    # ===== 6단계: 페이지별로 데이터 다운로드 =====
    
    print(f"\n📄 [{file_prefix}] 첫 페이지 다운로드 중...")
    rate_limiter.wait_if_needed()
    time.sleep(REQUEST_DELAY)
    
    success, first_data, error = fetch_page_with_retry(api_url, api_params)
    
    if not success:
        print(f"❌ [{file_prefix}] 첫 페이지 다운로드 실패: {error}")
        return False, 0, error
    
    # 첫 페이지 저장
    file_path = f"{condition_folder}/{file_prefix}_Page_1.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(first_data, f, indent=2, ensure_ascii=False)
    print(f"✔ [{file_prefix}] 페이지 1 저장 완료")
    
    # Lambda 환경에서 즉시 S3에 업로드하고 로컬 파일 삭제
    if is_lambda and s3_prefix:
        try:
            from infra.aws.lambda_functions.trigger_etl.common.s3_utils import (
                upload_file_to_s3
            )
            s3_key = f"{s3_prefix}/{file_prefix}_Page_1.json"
            if upload_file_to_s3(file_path, s3_key):
                os.remove(file_path)
                print(f"📤 [{file_prefix}] 페이지 1 S3 업로드 완료 및 로컬 파일 삭제")
        except Exception as e:
            print(f"⚠️  [{file_prefix}] 페이지 1 S3 업로드 중 오류: {e}")
    
    next_page_token = first_data.get("nextPageToken")
    if not next_page_token:
        print(f"🎉 [{file_prefix}] 단일 페이지만 존재합니다.")
        return True, 1, None
    
    # ===== 7단계: 나머지 페이지 토큰 수집 =====
    
    page_tokens = {}  # page_num -> token 매핑
    current_token = next_page_token
    page_num = 2
    
    print(f"📊 [{file_prefix}] 나머지 페이지 토큰 수집 중...")
    while current_token:
        rate_limiter.wait_if_needed()
        time.sleep(REQUEST_DELAY)
        
        temp_params = api_params.copy()
        temp_params["pageToken"] = current_token
        success, temp_data, error = fetch_page_with_retry(api_url, temp_params)
        
        if success:
            current_token = temp_data.get("nextPageToken")
            if current_token:
                page_tokens[page_num] = current_token
                page_num += 1
        else:
            print(f"⚠️  [{file_prefix}] 페이지 {page_num} 토큰 수집 실패: {error}")
            break
    
    total_pages = len(page_tokens) + 1  # 첫 페이지 포함
    print(f"📊 [{file_prefix}] 총 {total_pages}페이지 확인 완료. 병렬 다운로드 시작...")
    
    # ===== 8단계: 병렬 다운로드 실행 =====
    
    completed_pages = set([1])  # 첫 페이지는 이미 완료
    failed_pages = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {}
        
        for page_num, token in page_tokens.items():
            future = executor.submit(
                download_single_page,
                page_num,
                api_url,
                api_params,
                token,
                condition_folder,  # condition별 폴더 사용
                file_prefix,
                rate_limiter,
                s3_prefix  # 추가
            )
            future_to_page[future] = page_num
        
        # 완료된 작업들을 처리
        for future in as_completed(future_to_page):
            page_num = future_to_page[future]
            try:
                success, page, next_token, error = future.result()
                if success:
                    completed_pages.add(page)
                else:
                    failed_pages.append((page, error))
                    print(f"❌ [{file_prefix}] 페이지 {page} 실패: {error}")
            except Exception as e:
                failed_pages.append((page_num, str(e)))
                print(f"❌ [{file_prefix}] 페이지 {page_num} 예외 발생: {str(e)}")
    
    print(f"✅ [{file_prefix}] 완료: 성공 {len(completed_pages)}페이지, 실패 {len(failed_pages)}페이지")
    if failed_pages:
        print(f"⚠️  [{file_prefix}] 실패한 페이지: {[p[0] for p in failed_pages]}")
    
    return True, len(completed_pages), None


def get_country_name_from_code(country_code):
    """
    국가 코드를 전체 국가명으로 변환하는 함수 (US, KR, JP만 지원)
    
    Args:
        country_code: 국가 코드 ("US", "KR", "JP")
    
    Returns:
        전체 국가명 ("United States", "South Korea", "Japan")
    """
    country_map = {
        "US": "United States",
        "KR": "South Korea",
        "JP": "Japan"
    }
    return country_map.get(country_code.upper(), country_code)


def fetch_all_conditions():
    """
    모든 고정된 condition에 대해 각 국가를 병렬로 처리하는 메인 함수
    """
    start_time = datetime.now()
    print(f"\n{'=' * 60}")
    print(f"🚀 Ingest 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  병렬 처리 모드: {MAX_WORKERS} workers (페이지), {MAX_COUNTRY_WORKERS} workers (국가)")
    print(f"⚙️  Rate limit: {MAX_REQUESTS_PER_SECOND} req/sec")
    print(f"📋 처리할 Condition: {', '.join(CONDITIONS)}")
    print(f"🌍 처리할 국가: {', '.join(COUNTRIES)}")
    print(f"📅 기간: {DATE_FROM} ~ {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'=' * 60}\n")
    
    # Lambda 환경 감지
    is_lambda = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    
    # Rate limiter 인스턴스 생성 (모든 요청 공유)
    rate_limiter = RateLimiter(max_calls=50, time_period=60)
    
    results = {}
    
    # 각 condition에 대해 순차적으로 처리
    for condition in CONDITIONS:
        print(f"\n{'=' * 60}")
        print(f"🔄 Condition 처리 시작: {condition}")
        print(f"{'=' * 60}")
        
        condition_start = datetime.now()
        condition_results = {}
        
        def fetch_for_country(country_code):
            """국가별 다운로드 함수 (병렬 처리용)"""
            country_name = get_country_name_from_code(country_code)
            key = f"{condition}_{country_code}"
            
            print(f"  🌍 [{country_code}] {country_name} 처리 시작...")
            country_start = datetime.now()
            
            # Lambda 환경에서 S3 접두사 생성
            # condition_name과 country_code_folder 변환 로직 (fetch_clinical_trials_for_condition과 동일)
            s3_prefix = None
            if is_lambda:
                # condition_name 변환
                cond_lower = condition.lower().strip()
                if "neoplasms" in cond_lower or "cancer" in cond_lower or "tumor" in cond_lower:
                    condition_name = "neoplasms"
                elif "cardiovascular" in cond_lower or "cardiac" in cond_lower or "heart" in cond_lower:
                    condition_name = "cardio"
                elif "autoimmune" in cond_lower:
                    condition_name = "autoimmune"
                else:
                    name = condition.replace(" ", "_").replace("Diseases", "").replace("Disease", "").strip("_")
                    if len(name) > 30:
                        name = name[:30]
                    condition_name = name or "Clinical_Trial"
                
                # country_code_folder 변환
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
                country_code_folder = country_map.get(country_name, country_name.replace(" ", "_"))
                
                current_date = datetime.now().strftime("%Y%m%d")
                condition_folder_name = f"{condition_name}_{country_code_folder}"
                s3_prefix = f"data/raw/nih/{current_date}/{condition_folder_name}"
            
            success, total_pages, error = fetch_clinical_trials_for_condition(
                condition=condition,
                country=country_name,
                output_folder=OUTPUT_FOLDER,
                date_from=DATE_FROM,
                date_to=None,  # 오늘까지
                page_size=PAGE_SIZE,
                file_prefix=FILE_PREFIX,
                rate_limiter=rate_limiter,
                s3_prefix=s3_prefix  # 추가
            )
            
            country_end = datetime.now()
            country_elapsed = country_end - country_start
            
            result = {
                "condition": condition,
                "country": country_name,
                "country_code": country_code,
                "success": success,
                "total_pages": total_pages,
                "error": error,
                "elapsed_time": country_elapsed
            }
            
            print(f"  ✅ [{country_code}] 완료: {total_pages}페이지, 소요 시간: {country_elapsed}")
            if error:
                print(f"     ⚠️  오류: {error}")
            
            return key, result
        
        # 3개 국가를 병렬로 처리
        with ThreadPoolExecutor(max_workers=MAX_COUNTRY_WORKERS) as executor:
            future_to_country = {
                executor.submit(fetch_for_country, country_code): country_code 
                for country_code in COUNTRIES
            }
            
            for future in as_completed(future_to_country):
                country_code = future_to_country[future]
                try:
                    key, result = future.result()
                    condition_results[key] = result
                except Exception as e:
                    print(f"  ❌ [{country_code}] 예외 발생: {str(e)}")
                    condition_results[f"{condition}_{country_code}"] = {
                        "condition": condition,
                        "country": get_country_name_from_code(country_code),
                        "country_code": country_code,
                        "success": False,
                        "total_pages": 0,
                        "error": str(e),
                        "elapsed_time": timedelta(0)
                    }
        
        condition_end = datetime.now()
        condition_elapsed = condition_end - condition_start
        
        results[condition] = {
            "results": condition_results,
            "elapsed_time": condition_elapsed
        }
        
        print(f"\n⏱️  [{condition}] 전체 소요 시간: {condition_elapsed}")
    
    # 전체 결과 출력
    end_time = datetime.now()
    total_elapsed = end_time - start_time
    
    print(f"\n{'=' * 60}")
    print(f"✅ Ingest 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  총 소요 시간: {total_elapsed}")
    print(f"\n📊 결과 요약:")
    print(f"{'=' * 60}")
    
    total_pages_all = 0
    for condition, condition_data in results.items():
        print(f"\n📋 {condition}:")
        condition_total = 0
        for key, result in condition_data["results"].items():
            status = "✅ 성공" if result["success"] else "❌ 실패"
            print(f"  {status} | {result['country_code']:2s} | {result['total_pages']:4d}페이지 | {result['elapsed_time']}")
            if result["error"]:
                print(f"       오류: {result['error']}")
            condition_total += result["total_pages"]
        print(f"  📊 {condition} 총계: {condition_total}페이지")
        total_pages_all += condition_total
    
    print(f"\n{'=' * 60}")
    print(f"📊 전체 총 페이지 수: {total_pages_all}")
    print(f"{'=' * 60}\n")
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Clinical Trials 데이터 다운로드 시작")
    print(f"질병/조건: {', '.join(CONDITIONS)}")
    print(f"국가: {', '.join(COUNTRIES)}")
    print(f"기간: {DATE_FROM} ~ {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # 모든 condition과 country 조합에 대해 데이터 다운로드
    results = fetch_all_conditions()
    
    # ===== 다운로드 완료 메시지 출력 =====
    print("\n" + "=" * 60)
    print("모든 Condition 및 Country 조합 다운로드 완료!")
    print("=" * 60)


def run(raw_dir: str, limit: int | None = None) -> None:
    """
    pipeline_runner에서 호출하는 진입점.
    
    Args:
        raw_dir: 전체 raw 데이터 루트 디렉토리 (예: 'data/raw')
        limit: 가져올 문서 수 제한 (현재 NIH ingest에서는 사용하지 않음)
    """
    global OUTPUT_FOLDER

    # pipeline_runner의 cfg.raw_dir 하위에 nih/{오늘날짜} 디렉토리를 생성하여 사용
    # 예: raw_dir='data/raw' → 'data/raw/nih/20251215'
    today = datetime.now().strftime("%Y%m%d")
    base_output = os.path.join(raw_dir, "nih", today)
    os.makedirs(base_output, exist_ok=True)
    OUTPUT_FOLDER = base_output

    print("=" * 60)
    print("Clinical Trials 데이터 다운로드 (pipeline_runner 호출)")
    print(f"RAW DIR: {raw_dir}")
    print(f"OUTPUT_FOLDER (NIH): {OUTPUT_FOLDER}")
    if limit is not None:
        print(f"※ NIH ingest는 limit 파라미터를 직접 사용하지 않습니다 (무시).")
    print("=" * 60)

    # 기존 메인 로직 재사용
    fetch_all_conditions()
