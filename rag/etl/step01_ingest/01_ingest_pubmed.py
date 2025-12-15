"""
테스트용 PubMed ingest 스텁.
"""

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


import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional, Any

import requests

from config import PMC_OAI_ENDPOINT, EUTILS_ESEARCH, CATEGORY_KEYWORDS, MAX_PER_CATEGORY, DEFAULT_FROM_DATE, DEFAULT_UNTIL_DATE

from utils import build_pubmed_term_for_category, categorize_article
from parsing import extract_article_info


# -------------------- ESearch (카테고리별 PMC id 검색) -------------------- #

def search_pmc_ids_for_category(category, keywords, max_ids=100, retstart=0):
    term = build_pubmed_term_for_category(
        keywords,
        from_date=DEFAULT_FROM_DATE,
        until_date=DEFAULT_UNTIL_DATE,
    )
    term += ' AND "open access"[filter]'
    params = {
        "db": "pmc",
        "term": term,
        "retmode": "json",
        "retmax": max_ids,
        "retstart": retstart,
    }

    print(f"[ESearch] Category={category}, term={term}")
    resp = requests.get(EUTILS_ESEARCH, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    id_list = data.get("esearchresult", {}).get("idlist", [])
    pmc_ids = [f"PMC{pmcid}" for pmcid in id_list]

    print(f"[ESearch] {category}: {len(pmc_ids)} PMCID(s) found")
    return pmc_ids


# -------------------- OAI-PMH 클라이언트 -------------------- #

def build_pmc_oai_params(resumption_token: Optional[str] = None) -> Dict[str, str]:
    if resumption_token:
        return {
            "verb": "ListRecords",
            "resumptionToken": resumption_token,
        }
    else:
        return {
            "verb": "ListRecords",
            "set": "pmc-openaccess",
            "metadataPrefix": "pmc",
            "from": DEFAULT_FROM_DATE,
            "until": DEFAULT_UNTIL_DATE,
        }


def fetch_pmc_records():
    """
    2019-01-01 ~ 2024-12-31 기간의 pmc-openaccess 레코드를
    resumptionToken으로 나눠서 순차적으로 yield.
    """
    resumption_token = None

    while True:
        params = build_pmc_oai_params(resumption_token=resumption_token)
        print(f"[PMC OAI] Requesting with params: {params}")
        resp = requests.get(PMC_OAI_ENDPOINT, params=params, timeout=60)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)

        ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}

        for record in root.findall(".//oai:record", ns):
            yield record

        rt_elem = root.find(".//oai:resumptionToken", ns)
        if rt_elem is not None and rt_elem.text:
            resumption_token = rt_elem.text
            print(f"[PMC OAI] Next resumptionToken: {resumption_token}")
        else:
            print("[PMC OAI] No more resumptionToken. Finished.")
            break


def fetch_single_pmc_record(pmcid: str):
    numeric_id = pmcid.replace("PMC", "")
    params = {
        "verb": "GetRecord",
        "identifier": f"oai:pubmedcentral.nih.gov:{numeric_id}",
        "metadataPrefix": "pmc",
    }

    print(f"[OAI GetRecord] Requesting {pmcid} with params={params}")
    resp = requests.get(PMC_OAI_ENDPOINT, params=params, timeout=60)

    if resp.status_code == 400:
        print(f"[OAI GetRecord] Article {pmcid} not available in full text format (400)")
        return None

    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns_oai = {"oai": "http://www.openarchives.org/OAI/2.0/"}

    error_elem = root.find(".//oai:error", ns_oai)
    if error_elem is not None:
        error_code = error_elem.get("code", "unknown")
        error_msg = error_elem.text or ""
        print(f"[OAI GetRecord] Error for {pmcid}: {error_code} - {error_msg}")
        return None

    record = root.find(".//oai:record", ns_oai)
    if record is None:
        print(f"[OAI GetRecord] No record element for {pmcid}")
        return None

    return record


# -------------------- 카테고리별 수집 + 저장 -------------------- #

def collect_articles_per_category(
    max_per_category: int = MAX_PER_CATEGORY,
    batch_size: int = 50,
):
    collected: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for category, keywords in CATEGORY_KEYWORDS.items():
        print(f"\n[CATEGORY] {category}")

        retstart = 0
        max_attempts = 500

        while len(collected[category]) < max_per_category and retstart < max_attempts:
            pmc_ids = search_pmc_ids_for_category(
                category,
                keywords,
                max_ids=batch_size,
                retstart=retstart,
            )

            if not pmc_ids:
                print("  [INFO] No more articles found. Stopping search.")
                break

            retstart += len(pmc_ids)

            for pmcid in pmc_ids:
                if len(collected[category]) >= max_per_category:
                    break

                record = fetch_single_pmc_record(pmcid)
                if record is None:
                    continue

                article = extract_article_info(record)
                if not article:
                    continue

                matched_cats = categorize_article(article)
                if category not in matched_cats:
                    continue

                collected[category].append(article)
                print(
                    f"  [COLLECTED] {pmcid}: "
                    f"{len(collected[category])}/{max_per_category} - "
                    f"{article.get('title', 'N/A')[:80]}"
                )

        print(f"[DONE] {category}: collected {len(collected[category])} articles")

    return collected


def save_as_json(data, path="pmc_articles_by_category.json"):
    normal_dict = {k: v for k, v in data.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normal_dict, f, ensure_ascii=False, indent=2)
    print(f"[SAVE] Saved JSON to {path}")





def run(raw_dir: str, limit: int | None = None) -> None:
    """원격 데이터 대신 경로와 제한값만 출력한다."""
    print(f"[INGEST:PubMed] raw_dir={raw_dir}, limit={limit}")
