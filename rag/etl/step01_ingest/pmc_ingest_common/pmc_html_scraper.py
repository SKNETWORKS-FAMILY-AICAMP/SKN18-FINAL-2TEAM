# pmc_pipeline/html_scraper.py

from typing import Dict

import requests
from bs4 import BeautifulSoup


def get_html_image_map(pmcid: str) -> Dict[str, str]:
    """
    PubMed Central 문서의 HTML을 내려받아 BeautifulSoup로 모든 Blob 이미지를 찾아 매핑합니다.
    사이트에서 과 aggressive 한 스크래핑을 막기 때문에 브라우저 에뮬레이션 대신
    requests 세션을 사용해 최소한의 헤더만 추가합니다.
    """
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    image_map = {}  # Key: 확장자 없는 파일명, Value: 실제 URL

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/115.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=60)
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
