# pmc_pipeline/utils.py

import uuid
import re
from typing import List, Optional, Tuple, Dict, Any

from rag.etl.common.pmc_config import (
    DEFAULT_FROM_DATE,
    DEFAULT_UNTIL_DATE,
    CATEGORY_KEYWORDS,
)

try:
    from rag.etl.step01_ingest.pmc_ingest_common.pmc_math import extract_formula_text, handle_sup_sub
except ImportError:
    from rag.etl.step01_ingest.pmc_ingest_common.pmc_math import extract_formula_text, handle_sup_sub


def _local_name(tag: Optional[str]) -> str:
    if not tag:
        return ""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _dedup_preserve(items: List[Optional[str]]) -> List[str]:
    """Remove empty values while preserving the first occurrence order."""
    seen = set()
    deduped: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _append_clean(text: Optional[str], bucket: List[str]) -> None:
    if not text:
        return
    stripped = text.strip()
    if stripped:
        bucket.append(stripped)


def _extract_caption_text(node) -> Optional[str]:
    """fig/table 안의 caption/title/label 텍스트를 하나의 문자열로 정리."""
    for candidate in ("caption", "title", "label"):
        for descendant in node.iter():
            if _local_name(descendant.tag) == candidate:
                parts = [seg.strip() for seg in descendant.itertext() if seg.strip()]
                if parts:
                    return " ".join(parts)
    parts = [seg.strip() for seg in node.itertext() if seg.strip()]
    return " ".join(parts) if parts else None


def gen_random_fig_id() -> int:
    """figure용 UUID 기반 숫자 ID (12자리 정수)."""
    return uuid.uuid4().int % 10**12


def gen_random_table_id() -> int:
    """table용 UUID 기반 숫자 ID (12자리 정수)."""
    return uuid.uuid4().int % 10**12



# -------------------- Figure 라벨 처리 -------------------- #

def parse_fig_label(label: Optional[str], caption: Optional[str]) -> Tuple[str, Optional[int]]:
    """
    Figure/Fig/Scheme 라벨 파싱.
    - Figure 1, Fig. 2
    - Figure (1), Fig. (2)
    - Scheme 1, Scheme-2, Scheme (3)
    - 숫자만 있는 케이스도 figure로 처리.
    - 앞에 0이 두 개 이상 붙고 실제 숫자 값이 10 이상인 경우
      (예: 0045, 0065)만 graphical abstract로 처리.
    - 0001, 0002 등은 Figure 1, 2로 처리.
    """
    def _is_special_ga_number(num_str: str) -> bool:
        """
        0045, 0065 같은 케이스만 골라내기 위한 헬퍼.
        조건:
        1) 전체가 숫자이고, 앞에 0이 하나 이상 있다.
        2) leading zero가 2개 이상.
        3) leading zero 제거 후 값이 10 이상.
        """
        if not re.match(r"^0+\d+$", num_str):
            return False

        core = num_str.lstrip("0")
        if not core:
            return False  # 전부 0인 이상한 케이스 방지

        leading_zeros = len(num_str) - len(core)
        if leading_zeros < 2:
            return False

        try:
            value = int(core)
        except ValueError:
            return False

        # 값이 한 자릿수(1~9)면 일반 Figure로 취급 (0001 등)
        if value < 10:
            return False

        return True

    raw_label = (label or "").strip()
    source = raw_label if raw_label else (caption or "").strip()
    source = source.lower().strip()

    if not source:
        return "other", None

    # 텍스트에 'graphical abstract'가 있으면 무조건 그래픽컬 초록
    if "graphical abstract" in source:
        return "graphical_abstract", None

    # 1) Fig/Figure 패턴
    m_fig = re.search(r"\bfig(?:ure)?\.?\s*[-:.]?\s*\(?\s*(\d+)\s*\)?", source)
    if m_fig:
        num_str = m_fig.group(1)      # 예: "0065", "0045", "10", "1"
        if _is_special_ga_number(num_str):
            return "graphical_abstract", None

        # 일반 figure: leading zero 제거 후 정수로
        core = num_str.lstrip("0") or "0"
        return "figure", int(core)

    # 2) 숫자만 있는 라벨 (예: "1", "0045", "0001")
    m_num = re.match(r"^(\d+)\.?$", source)
    if m_num:
        num_str = m_num.group(1)
        if _is_special_ga_number(num_str):
            return "graphical_abstract", None

        core = num_str.lstrip("0") or "0"
        return "figure", int(core)

    # 3) Scheme
    m_scheme = re.search(r"\bscheme\.?\s*[-:.]?\s*\(?\s*(\d+)\s*\)?", source)
    if m_scheme:
        num_str = m_scheme.group(1)
        core = num_str.lstrip("0") or "0"
        return "scheme", int(core)

    return "other", None



def normalize_fig_label(
    raw_label: Optional[str],
    fig_label_text: str,
    fig_label_number: Optional[int],
) -> Optional[str]:
    if fig_label_text == "graphical_abstract":
        return "graphical abstract"
    if fig_label_number is not None:
        if fig_label_text == "scheme":
            return f"scheme{fig_label_number}"
        return f"fig{fig_label_number}"
    if raw_label:
        return raw_label.lower()
    return None


# -------------------- Table 라벨 처리 -------------------- #

def parse_table_label(label: Optional[str], caption: Optional[str]) -> Tuple[str, Optional[int]]:
    """
    Table label/caption에서 table 번호 파싱.
    - "Table 1", "Tab. 2", "Table-3", "Table (4)" 등 → ("table", 1/2/3/4)
    """
    raw_label = (label or "").strip()
    source = raw_label if raw_label else (caption or "").strip()
    source = source.lower()

    if not source:
        return "other", None

    # Table 1, Tab. 2, Table-3, Table (4)
    m_tbl = re.search(r"\btab(?:le)?\.?\s*[-:.]?\s*\(?\s*(\d+)\s*\)?", source)
    if m_tbl:
        return "table", int(m_tbl.group(1))

    # 숫자만 있는 경우도 테이블 번호로 간주
    m_num = re.match(r"^(\d+)\.?$", source.strip())
    if m_num:
        return "table", int(m_num.group(1))

    return "other", None


def normalize_table_label(
    raw_label: Optional[str],
    label_type: str,
    label_number: Optional[int],
) -> Optional[str]:
    """
    table label canonical form:
    - ("table", 1) → "table1"
    - 아니면 raw_label 소문자 그대로.
    """
    if label_number is not None and label_type == "table":
        return f"table{label_number}"
    if raw_label:
        return raw_label.lower()
    return None


def build_image_urls(
    pmcid: Optional[str],
    href: Optional[str],
    binary_url: Optional[str] = None,
) -> List[str]:
    """
    Construct absolute image URLs that mirror the current PMC UI.
    Uses both CDN and pmc host PDF paths, then falls back to legacy binary_url.
    """ 
    candidates: List[Optional[str]] = []
    if pmcid and href:
        candidates.append(f"https://cdn.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/{href}")
        candidates.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/{href}")
    if binary_url:
        candidates.append(binary_url)
    return _dedup_preserve(candidates)


# -------------------- 카테고리 분류/검색 유틸 -------------------- #

def text_matches_keywords(target_text: str, keywords) -> bool:
    text = target_text.lower()
    for kw in keywords:
        if kw.lower() in text:
            return True
    return False


def categorize_article(article: Dict[str, Any]) -> list:
    text = f"{article['title']} {article['abstract']} ".lower()
    matched = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if text_matches_keywords(text, keywords):
            matched.append(category)
    return matched


def build_pubmed_term_for_category(
    keywords,
    from_date: str = DEFAULT_FROM_DATE,
    until_date: str = DEFAULT_UNTIL_DATE,
) -> str:
    kw_terms = [f'"{kw}"[Title/Abstract]' for kw in keywords]
    kw_part = " OR ".join(kw_terms)
    date_part = f'("{from_date}"[PDAT] : "{until_date}"[PDAT])'
    term = f"({kw_part}) AND {date_part}"
    return term
