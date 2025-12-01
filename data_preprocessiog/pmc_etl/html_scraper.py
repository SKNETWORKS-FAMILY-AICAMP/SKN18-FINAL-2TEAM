# pmc_pipeline/html_scraper.py

from typing import Dict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def get_html_image_map(pmcid: str) -> Dict[str, str]:
    """
    Playwright로 봇 탐지를 우회하여 페이지 HTML을 가져온 뒤,
    BeautifulSoup로 모든 Blob 이미지를 찾아 매핑합니다.
    """
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    image_map = {}  # Key: 확장자 없는 파일명, Value: 실제 URL

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, timeout=60000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass

            html_content = page.content()
            browser.close()

            soup = BeautifulSoup(html_content, "html.parser")
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
        print(f"  [Playwright Error] {pmcid}: {e}")

    return image_map
