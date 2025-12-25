import json
import os
import time
import logging
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional, Any, Set
import shutil
import importlib
from pathlib import Path
from datetime import datetime
import sys
import requests

# -------------------- CONFIG IMPORT -------------------- #
from rag.etl.common.pmc_config import (
    PMC_OAI_ENDPOINT,
    EUTILS_ESEARCH,
    CATEGORY_KEYWORDS,
    DEFAULT_FROM_DATE,
    DEFAULT_UNTIL_DATE,)

from rag.etl.step01_ingest.pmc_ingest_common.pmc_utils import (
    build_pubmed_term_for_category,
    categorize_article,
)
from rag.etl.step01_ingest.pmc_ingest_common.pmc_parsing import extract_article_info

TARGET_NEW_COUNT = int(os.getenv("PUBMED_TARGET_NEW_COUNT", "10"))
BATCH_SIZE = int(os.getenv("PUBMED_BATCH_SIZE", "50"))


# -------------------- 0. 로깅 설정 -------------------- #
# 로그 포맷: [시간] [레벨] 메시지
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# -------------------- 1. 중복 방지: 제외할 ID 로드 -------------------- #

def load_exclusion_ids(path: str) -> tuple[Set[str], Set[str]]:
    """
    기존 JSON 파일을 읽어서 이미 수집된 PMID와 PMCID 집합(Set)을 반환합니다.
    """
    exclude_pmids = set()
    exclude_pmcids = set()

    if not os.path.exists(path):
        logger.info(f"기존 파일 '{path}'이 없습니다. 제외할 목록 없이 시작합니다.")
        return exclude_pmids, exclude_pmcids

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        count = 0
        for cat, articles in data.items():
            for art in articles:
                if art.get('pmid'):
                    exclude_pmids.add(str(art['pmid']))
                if art.get('pmcid'):
                    exclude_pmcids.add(str(art['pmcid']))
                count += 1
                
        logger.info(f"'{path}'에서 제외할 논문 {count}개를 로드했습니다. (PMIDs: {len(exclude_pmids)}, PMCIDs: {len(exclude_pmcids)})")
        return exclude_pmids, exclude_pmcids
        
    except Exception as e:
        logger.error(f"제외 목록 로드 실패 ({path}): {e}")
        return set(), set()


# -------------------- 2. 검색 및 OAI 클라이언트 -------------------- #

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

    try:
        resp = requests.get(EUTILS_ESEARCH, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        id_list = data.get("esearchresult", {}).get("idlist", [])
        pmc_ids = [f"PMC{pmcid}" for pmcid in id_list]
        return pmc_ids
    except Exception as e:
        logger.error(f"Search API Error (Category: {category}): {e}")
        return []


def fetch_single_pmc_record(pmcid: str):
    numeric_id = pmcid.replace("PMC", "")
    params = {
        "verb": "GetRecord",
        "identifier": f"oai:pubmedcentral.nih.gov:{numeric_id}",
        "metadataPrefix": "pmc",
    }

    try:
        resp = requests.get(PMC_OAI_ENDPOINT, params=params, timeout=60)
        
        if resp.status_code == 400:
            return None
            
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns_oai = {"oai": "http://www.openarchives.org/OAI/2.0/"}

        if root.find(".//oai:error", ns_oai) is not None:
            return None

        return root.find(".//oai:record", ns_oai)
        
    except Exception as e:
        logger.error(f"Fetch failed for {pmcid}: {e}")
        return None


# -------------------- 3. 새로운 데이터만 수집 -------------------- #

def save_as_json(data, path):
    """
    수집된 데이터를 JSON 파일로 저장합니다.
    """
    try:
        normal_dict = {k: v for k, v in data.items()}
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(normal_dict, f, ensure_ascii=False, indent=2)
        
        # 반복 저장 시 로그가 너무 많아질 수 있으므로 debug 레벨로 설정하거나, 필요시 info 유지
        logger.info(f"[AUTOSAVE] 파일 저장 완료: {path}")
    except Exception as e:
        logger.error(f"파일 저장 실패: {e}")


def collect_new_articles(
    exclude_pmids: Set[str],
    exclude_pmcids: Set[str],
    target_count_per_category: int,
    batch_size: int,
    save_path: str
):
    new_collected: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for category, keywords in CATEGORY_KEYWORDS.items():
        logger.info(f"=== [CATEGORY START] {category} (목표: 신규 {target_count_per_category}개) ===")
        
        retstart = 0
        max_attempts = 10000
        consecutive_skips = 0
        
        while len(new_collected[category]) < target_count_per_category:
            
            # 1. ID 검색
            pmc_ids = search_pmc_ids_for_category(
                category, keywords, max_ids=batch_size, retstart=retstart
            )
            
            if not pmc_ids:
                logger.info("검색 결과가 더 이상 없습니다. 다음 카테고리로 이동합니다.")
                break

            retstart += len(pmc_ids)

            for pmcid in pmc_ids:
                if len(new_collected[category]) >= target_count_per_category:
                    break

                if pmcid in exclude_pmcids:
                    consecutive_skips += 1
                    continue
                
                # 상세 정보 가져오기
                record = fetch_single_pmc_record(pmcid)
                if record is None:
                    continue

                article = extract_article_info(record)
                if not article:
                    continue
                
                parsed_pmid = str(article.get('pmid', ''))
                if parsed_pmid and parsed_pmid in exclude_pmids:
                    logger.debug(f"[DUPLICATE] PMID {parsed_pmid} 중복. Skip.")
                    exclude_pmcids.add(pmcid)
                    continue

                matched_cats = categorize_article(article)
                if category not in matched_cats:
                    continue

                # *** 수집 성공 ***
                new_collected[category].append(article)
                
                if parsed_pmid:
                    exclude_pmids.add(parsed_pmid)
                exclude_pmcids.add(pmcid)
                
                # 로그: 진행 상황
                logger.info(
                    f"[NEW] {pmcid} | {len(new_collected[category])}/{target_count_per_category} | "
                    f"{article.get('title', 'N/A')[:40]}..."
                )
                
                consecutive_skips = 0

            # 배치 종료 후 저장
            if save_path and any(new_collected.values()):
                total_collected = sum(len(v) for v in new_collected.values())
                logger.info(f"현재 총 {total_collected}개 수집됨. 자동 저장 수행 중...")
                save_as_json(new_collected, save_path)

            if consecutive_skips > 0 and consecutive_skips % 100 == 0:
                logger.info(f"기존 데이터와 중복되어 {consecutive_skips}개를 건너뛰는 중... (retstart={retstart})")
                
            if retstart > max_attempts:
                logger.warning("검색 범위 초과 (Max Attempts). 해당 카테고리 중단.")
                break

        logger.info(f"[DONE] {category}: 총 {len(new_collected[category])}개 신규 수집 완료")

    return new_collected



def run_incremental(prev_file: str, new_file: str, target_count: int, batch: int) -> None:
    """
    기존 prev/new JSON 파일 경로를 직접 받아서 추가 수집을 수행하는 함수.
    (단독 실행/스크립트용)
    """
    logger.info("=== 추가 수집 프로세스 시작 ===")
    logger.info(f" - 제외 대상(기존) 파일: {prev_file}")
    logger.info(f" - 저장/업데이트 파일 : {new_file}")
    logger.info(f" - 목표 수량(카테고리당): {target_count}개")

    ex_pmids, ex_pmcids = load_exclusion_ids(prev_file)

    new_data = collect_new_articles(
        exclude_pmids=ex_pmids,
        exclude_pmcids=ex_pmcids,
        target_count_per_category=target_count,
        batch_size=batch,
        save_path=new_file,
    )

    if any(new_data.values()):
        logger.info(f"[FINAL] 모든 수집 완료. 최종 파일: '{new_file}'")
    else:
        logger.info("[INFO] 새로 수집된 논문이 없습니다.")


# -------------------- MAIN 실행 (run 명령어 대응) -------------------- #

def run(raw_dir: str, limit: int | None = None) -> None:
    """
    pipeline_runner.run_ingest 에서 호출되는 엔트리포인트.

    Args:
        raw_dir: ETL_RAW_DIR (예: data/raw)
        limit: 카테고리당 수집 목표 개수 (None이면 TARGET_NEW_COUNT 사용)
    """
    logger.info("=== PubMed ingest (pipeline) ===")
    logger.info(f"RAW DIR (arg): {raw_dir}")
    logger.info(f"LIMIT (arg): {limit}")

    base_dir = Path(raw_dir) / "pubmed"
    base_dir.mkdir(parents=True, exist_ok=True)

    prev_file = base_dir / "pubmed_existing.json"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_file = base_dir / f"pubmed_new_{stamp}.json"

    target_count = limit if limit is not None else TARGET_NEW_COUNT
    batch = BATCH_SIZE

    run_incremental(
        prev_file=str(prev_file),
        new_file=str(new_file),
        target_count=target_count,
        batch=batch,
    )


if __name__ == "__main__":
    # Command Line Argument 파싱 설정
    parser = argparse.ArgumentParser(description="PMC Article Collector")
    
    # 인자가 없으면 config.py의 기본값을 사용
    parser.add_argument("--prev", type=str, default=DEFAULT_PREVIOUS_FILE, help="Path to the previous JSON file (for exclusion)")
    parser.add_argument("--new", type=str, default=DEFAULT_NEW_FILE, help="Path to save the new JSON file")
    parser.add_argument("--count", type=int, default=TARGET_NEW_COUNT, help="Target count per category")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size for search API")

    args = parser.parse_args()

    # run 함수 실행
    run_incremental(
        prev_file=args.prev,
        new_file=args.new,
        target_count=args.count,
        batch=args.batch,
    )