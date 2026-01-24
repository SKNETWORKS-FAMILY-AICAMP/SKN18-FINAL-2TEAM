# pmc_pipeline/html_scraper.py

from typing import Dict
import time
import random

try:
    from curl_cffi import requests
except ImportError:
    # curl_cffi가 없으면 일반 requests 사용 (설치 권장)
    import requests

from bs4 import BeautifulSoup

# 세션 재사용 (연결 유지, 쿠키 공유)
_session = None
_last_request_time = 0
_request_delay = 2.0  # 요청 간 딜레이 (초)
_session_initialized = False  # 세션 초기화 여부


def _get_session():
    """세션 객체를 가져오거나 생성합니다."""
    global _session, _session_initialized

    if _session is None:
        # curl_cffi가 있는 경우 Chrome으로 위장
        if hasattr(requests, "Session") and "impersonate" in requests.Session.__init__.__code__.co_varnames:
             _session = requests.Session(impersonate="chrome")
        else:
             _session = requests.Session()

    # 첫 요청 전에 메인 페이지 방문 (자연스러운 접근)
    if not _session_initialized:
        try:
            # 메인 페이지 먼저 방문
            _session.get("https://pmc.ncbi.nlm.nih.gov/", timeout=30)
            time.sleep(1.5)  # 자연스러운 대기
            _session_initialized = True
        except:
            pass  # 실패해도 계속 진행

    return _session


def get_html_image_map(pmcid: str) -> Dict[str, str]:
    """
    PubMed Central 문서의 HTML을 내려받아 BeautifulSoup로 모든 Blob 이미지를 찾아 매핑합니다.
    사이트에서 과도한 스크래핑을 막기 때문에 세션 재사용과 요청 간 딜레이를 적용합니다.

    Args:
        pmcid: PubMed Central ID (예: "PMC11764125")

    Returns:
        Dict[str, str]: {파일명: blob URL} 매핑
    """
    global _last_request_time

    # Rate Limiting: 마지막 요청 이후 최소 대기 시간 확보 (랜덤화)
    elapsed = time.time() - _last_request_time
    min_delay = _request_delay
    max_delay = _request_delay + 2.0  # 2-4초 랜덤

    if elapsed < min_delay:
        wait_time = random.uniform(min_delay - elapsed, max_delay)
        time.sleep(wait_time)
    else:
        # 충분히 시간이 지났어도 약간의 랜덤 딜레이 추가
        time.sleep(random.uniform(0.5, 1.5))

    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    image_map = {}  # Key: 확장자 없는 파일명, Value: 실제 URL
    session = _get_session()

    try:
        # curl_cffi를 쓰면 헤더를 자동으로 관리해주지만, 명시적으로 넣어도 됨
        # (impersonate="chrome" 상태에서는 기본 헤더가 이미 설정됨)
        resp = session.get(url, timeout=60)
        _last_request_time = time.time()  # 요청 시간 기록
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        imgs = soup.find_all("img")

        for img in imgs:
            src = img.get("src") or img.get("data-src")
            if not src:
                continue

            if "/blobs/" in src and "cdn.ncbi" in src:
                filename = src.split("/")[-1]
                basename = filename.rsplit(".", 1)[0]
                image_map[basename] = src

    except Exception as e:
        print(f"  [PMC HTML Fetch Error] {pmcid}: {e}")

    return image_map
