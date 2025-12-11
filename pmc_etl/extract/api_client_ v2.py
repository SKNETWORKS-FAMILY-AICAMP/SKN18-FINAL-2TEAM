# pmc_pipeline/api_client.py

import json
import os
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional, Any, Set

import requests

# -------------------- CONFIG IMPORT -------------------- #
from config import (
    PMC_OAI_ENDPOINT,
    EUTILS_ESEARCH,
    CATEGORY_KEYWORDS,
    DEFAULT_FROM_DATE,
    DEFAULT_UNTIL_DATE,
    MAX_PER_CATEGORY 
)

from utils import build_pubmed_term_for_category, categorize_article
from parsing import extract_article_info


# -------------------- 1. 중복 방지: 제외할 ID 로드 -------------------- #

def load_exclusion_ids(path: str) -> tuple[Set[str], Set[str]]:
    """
    기존 JSON 파일을 읽어서 이미 수집된 PMID와 PMCID 집합(Set)을 반환합니다.
    """
    exclude_pmids = set()
    exclude_pmcids = set()

    if not os.path.exists(path):
        print(f"[INFO] 기존 파일 '{path}'이 없습니다. 제외할 목록 없이 시작합니다.")
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
                
        print(f"[INFO] '{path}'에서 제외할 논문 {count}개를 로드했습니다.")
        print(f"       (PMIDs: {len(exclude_pmids)}, PMCIDs: {len(exclude_pmcids)})")
        return exclude_pmids, exclude_pmcids
        
    except Exception as e:
        print(f"[ERROR] 제외 목록 로드 실패 ({path}): {e}")
        return set(), set()


# -------------------- 2. 검색 및 OAI 클라이언트 -------------------- #

def search_pmc_ids_for_category(category, keywords, max_ids=100, retstart=0):
    """
    config.py의 키워드와 날짜를 사용하여 PubMed(PMC)에서 ID 목록을 검색합니다.
    """
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

    resp = requests.get(EUTILS_ESEARCH, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    id_list = data.get("esearchresult", {}).get("idlist", [])
    pmc_ids = [f"PMC{pmcid}" for pmcid in id_list]
    
    return pmc_ids


def fetch_single_pmc_record(pmcid: str):
    """
    OAI-PMH를 통해 특정 PMCID의 XML 메타데이터를 가져옵니다.
    """
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
        print(f"[Error] Fetch failed for {pmcid}: {e}")
        return None


# -------------------- 3. 새로운 데이터만 수집 (핵심 로직 수정됨) -------------------- #

def save_as_json(data, path):
    """
    수집된 데이터를 JSON 파일로 저장합니다.
    """
    # defaultdict를 일반 dict로 변환
    normal_dict = {k: v for k, v in data.items()}
    
    # 디렉토리가 없다면 생성
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(normal_dict, f, ensure_ascii=False, indent=2)
    # 너무 자주 출력되면 로그가 지저분해지므로, 필요하면 주석 처리 가능
    # print(f"[SAVE] 현재까지 수집된 총 {sum(len(v) for v in data.values())}개 논문 저장 완료.")


def collect_new_articles(
    exclude_pmids: Set[str],
    exclude_pmcids: Set[str],
    target_count_per_category: int = 200,
    batch_size: int = 50,
    save_path: Optional[str] = None  # <--- [수정 1] 저장 경로 인자 추가
):
    """
    config.py의 카테고리 설정을 순회하며, 
    exclude 리스트에 없는 '새로운' 논문만 목표 수량만큼 수집합니다.
    중간중간 데이터를 파일에 저장합니다.
    """
    
    new_collected: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for category, keywords in CATEGORY_KEYWORDS.items():
        print(f"\n[CATEGORY] {category}")
        print(f" -> 목표: 신규 {target_count_per_category}개 수집 시작")
        
        retstart = 0
        max_attempts = 10000
        consecutive_skips = 0
        
        while len(new_collected[category]) < target_count_per_category:
            
            # 1. ID 검색 (배치 단위)
            pmc_ids = search_pmc_ids_for_category(
                category, keywords, max_ids=batch_size, retstart=retstart
            )
            
            if not pmc_ids:
                print("  [INFO] 검색 결과가 더 이상 없습니다. 다음 카테고리로 넘어갑니다.")
                break

            # 다음 배치를 위해 시작 위치 증가
            retstart += len(pmc_ids)

            for pmcid in pmc_ids:
                # 목표 달성 시 루프 탈출
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
                    print(f"  [DUPLICATE] PMID {parsed_pmid}는 이미 존재합니다. Skip.")
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
                
                print(
                    f"  [NEW] {pmcid}: "
                    f"{len(new_collected[category])}/{target_count_per_category} - "
                    f"{article.get('title', 'N/A')[:40]}..."
                )
                
                consecutive_skips = 0

            # -------------------- [수정 2] 배치 종료 후 중간 저장 -------------------- #
            # 한 번의 검색 배치(batch_size 만큼) 처리가 끝날 때마다 파일에 저장합니다.
            if save_path and any(new_collected.values()):
                total_collected = sum(len(v) for v in new_collected.values())
                print(f"  [AUTOSAVE] 현재까지 {total_collected}개 수집됨. 파일 저장 중...")
                save_as_json(new_collected, save_path)
            # ----------------------------------------------------------------------

            if consecutive_skips > 0 and consecutive_skips % 100 == 0:
                print(f"  [INFO] 기존 데이터와 중복되어 {consecutive_skips}개를 건너뛰는 중... (retstart={retstart})")
                
            if retstart > max_attempts:
                print("  [WARN] 검색 범위가 너무 넓어졌습니다. 해당 카테고리 중단.")
                break

        print(f"[DONE] {category}: 총 {len(new_collected[category])}개 신규 수집 완료")

    return new_collected


# -------------------- MAIN 실행 -------------------- #

if __name__ == "__main__":
    # === 사용자 설정 ===
    PREVIOUS_FILE = "/content/drive/MyDrive/skn_final_2team/SKN18-FINAL-2TEAM/pmc_articles_by_category32.json" 
    NEW_FILE = "/content/drive/MyDrive/skn_final_2team/SKN18-FINAL-2TEAM/pmc_articles_batch_2.json"
    TARGET_NEW_COUNT = 400
    
    print(f"=== 추가 수집 시작 ===")
    print(f" - 제외 대상 파일: {PREVIOUS_FILE}")
    print(f" - 저장/업데이트 파일: {NEW_FILE}") # 중간 저장 파일
    print(f" - 목표 수량: 카테고리당 {TARGET_NEW_COUNT}개")

    # 1. 제외할 ID 로드
    ex_pmids, ex_pmcids = load_exclusion_ids(PREVIOUS_FILE)

    # 2. 새로운 데이터 수집 실행 (save_path 인자 전달)
    new_data = collect_new_articles(
        exclude_pmids=ex_pmids,
        exclude_pmcids=ex_pmcids,
        target_count_per_category=TARGET_NEW_COUNT,
        batch_size=50,
        save_path=NEW_FILE  # <--- [수정 3] 여기서 파일 경로를 전달
    )

    # 3. 최종 완료 메시지
    if any(new_data.values()):
        print(f"\n[FINAL] 모든 수집이 완료되었습니다. 최종 파일이 '{NEW_FILE}'에 저장되었습니다.")
    else:
        print("[INFO] 새로 수집된 논문이 없습니다.")