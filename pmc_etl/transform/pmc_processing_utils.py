# pmc_processing_utils.py (최종 수정 버전 - 누락된 함수 정의 추가)

import re
import uuid 
from typing import Any, Dict, Iterable, List

# =========================
#  0. 정규식 패턴 정의 (Reference Markers)
# =========================

# [NEW ADDITION] Figure/Table 참조 패턴 (Fig, Table, SI Appendix 등 키워드 포함)
FIG_TABLE_REF_PATTERN = re.compile(
    r"\(\s*(?:Fig|Figure|Table|Scheme|SI Appendix|Suppl\.)[^()]+?\)", 
    re.IGNORECASE
)

# [기존] 영문/숫자 혼합 참조 삭제 패턴 (참조 제거에 사용)
FIG_REF_PATTERN = re.compile(
    r"\[\s*([A-Za-z0-9]+(?:[\s,\-–\.]\s*[A-Za-z0-9]+)*)\s*\]"
)
FIG_REF_PAREN_PATTERN = re.compile(
    r"\(\s*([A-Za-z0-9]+(?:[\s,\-–\.]\s*[A-Za-z0-9]+)*)\s*\)"
)

# [기존] 숫자만 있는 대괄호/소괄호 패턴 (Bibliography)
REF_SQUARE_PATTERN = re.compile(
    r"\[\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\]"
)
REF_PAREN_PATTERN = re.compile(
    r"\(\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\)"
)
# ... (나머지 인용 관련 패턴 생략: TRAILING_REF_CAPTURE_PATTERN 등) ...
TRAILING_REF_CAPTURE_PATTERN = re.compile(r"(?:^|[;\.\)])\s*(\d+(?:\s*,\s*\d+)*)\s*$")
TRAILING_REF_REMOVE_PATTERN = re.compile(r"([;\.\)])\s*\d+(?:\s*,\s*\d+)*\s*$")
INLINE_REF_CLUSTER_PATTERN = re.compile(r"(?<!\d)(\d{2,}\s*(?:[-–]\s*\d{2,}|\s*,\s*\d{2,})+)(?!\d)")
INLINE_SINGLE_SENT_REF_CAPTURE = re.compile(r"(?<=[\.\?\!])\s*(\d{1,3})\s+(?=[A-Z])")
INLINE_SINGLE_SENT_REF_REMOVE = re.compile(r"([\.\?\!])\s*\d{1,3}(\s+)(?=[A-Z])")
REF_SQUARE_EMPTY_PATTERN = re.compile(r"\[\s*[,;:/\.\-–\s]+\]")
REF_PAREN_EMPTY_PATTERN  = re.compile(r"\(\s*[,;:/\.\-–\s]+\)")

# =========================
#  1. 텍스트 정제 헬퍼 (Single Line 강제)
# =========================

def clean_content(text: Any) -> str:
    """
    CSV 저장용 텍스트 정제 함수.
    """
    if text is None: return ""
    s = str(text)
    s = re.sub(r"[\r\n]+|\\n|//n", " ", s)
    s = s.replace("\t", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+\(", "(", s) 
    s = re.sub(r"\(\s+", "(", s) 
    s = re.sub(r"\s+\)", ")", s) 
    s = re.sub(r"\)\s+", ")", s) 
    return s.strip()

def normalize_title_spacing(text: Any) -> str:
    """
    섹션 제목/경로에서 숫자/구두점 주변 공백을 정리하고,
    맨 앞에 붙은 섹션 번호(예: 4.6., 2.1, 3.)는 통째로 제거한다.
    """
    if text is None: return ""
    s = str(text).strip()
    s = re.sub(r"^,\s*", "", s)
    s = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", s)
    s = re.sub(r"\s+([,;:\.\?\!])", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_reference_spacing(text: Any) -> str:
    """
    참고문헌(raw) 문자열에서 공백만 정리하는 함수.
    """
    if text is None: return ""
    s = str(text).strip()
    s = re.sub(r"\s*([()\[\]])\s*", r"\1", s)
    s = re.sub(r"\s*-\s*", "-", s) 
    s = re.sub(r"\s+([,;:\.\?\!])", r"\1", s)
    s = re.sub(r"\s*–\s*", "–", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _norm_for_class(s: str) -> str:
    """섹션 분류를 위한 정규화 (소문자 + 특수문자 제거)."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def gen_section_id() -> int:
    """
    섹션용 UUID 기반 정수 ID (12자리 정도).
    """
    return uuid.uuid4().int % 10**12


# =========================
#  1-2. 섹션 텍스트에서 레퍼런스 인덱스 추출 + 삭제
# =========================

def extract_figure_table_markers(text: str) -> str:
    """
    [NEW DEFINITION] Figure/Table 참조 표기(예: (Fig. 1), (Table S1))를 추출합니다.
    """
    if not text:
        return ""
    
    # FIG_TABLE_REF_PATTERN을 사용해 괄호와 내용 전체를 추출
    markers = FIG_TABLE_REF_PATTERN.findall(text)
    
    cleaned = [m.strip() for m in markers]
    
    return ";".join(cleaned)


def extract_reference_markers(text: str) -> str:
    """
    섹션/abstract 텍스트에서 레퍼런스 인덱스를 추출. (숫자만)
    """
    if not text:
        return ""

    indices: List[str] = []
    s = text

    # 2) 소괄호 인용 (숫자만)
    for m in REF_PAREN_PATTERN.finditer(s):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # 1) 대괄호 인용 (숫자만)
    for m in REF_SQUARE_PATTERN.finditer(s):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # ... (나머지 숫자 인용 추출 로직 유지) ...
    for m in TRAILING_REF_CAPTURE_PATTERN.finditer(s):
        chunk = m.group(1)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    for m in INLINE_REF_CLUSTER_PATTERN.finditer(s):
        chunk = m.group(1)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    for m in INLINE_SINGLE_SENT_REF_CAPTURE.finditer(s):
        num = m.group(1)
        indices.append(num)

    # 중복 제거 + 순서 유지
    seen = set()
    uniq: List[str] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            uniq.append(idx)

    return ";".join(uniq)


def remove_reference_markers(text: str) -> str:
    """
    본문 텍스트에서 레퍼런스 표기를 아예 제거.
    - [10b] 와 같은 영문/숫자 혼합 Figure 참조도 삭제.
    """
    if not text:
        return ""

    s = text

    # [NEW] 0) Figure/Table 참조 삭제 (FIG_TABLE_REF_PATTERN 사용)
    s = re.sub(FIG_TABLE_REF_PATTERN, "", s) 
    
    # 기존의 일반적인 영문/숫자 혼합 참조 삭제
    s = FIG_REF_PATTERN.sub("", s)
    s = FIG_REF_PAREN_PATTERN.sub("", s)


    # 1) [] / () 레퍼런스 삭제 (숫자만)
    s = REF_SQUARE_PATTERN.sub("", s)
    s = REF_PAREN_PATTERN.sub("", s)

    # 숫자 없이 콤마/공백만 있는 괄호 [,,], ( , , ) 삭제
    s = REF_SQUARE_EMPTY_PATTERN.sub("", s)
    s = REF_PAREN_EMPTY_PATTERN.sub("", s)

    # 완전 빈 괄호 삭제
    s = re.sub(r"\[\s*\]", "", s)
    s = re.sub(r"\(\s*\)", "", s)

    # 2) 문장 끝 ". 46, 47" 꼬리 숫자 삭제
    s = TRAILING_REF_REMOVE_PATTERN.sub(r"\1", s)

    # 3) 문장 안 숫자 클러스터 ", 46, 47" 삭제
    s = INLINE_REF_CLUSTER_PATTERN.sub(" ", s)

    # 4) "CRC. 5 As reported" 같은 단일 숫자 삭제 → ". 5 As" → ". As"
    s = INLINE_SINGLE_SENT_REF_REMOVE.sub(r"\1 ", s)

    # 5) 최후 방어: 괄호 안에 영문/숫자 하나도 없는 경우 통으로 제거
    s = re.sub(r"\[\s*[^0-9A-Za-z]*\]", "", s)
    s = re.sub(r"\(\s*[^0-9A-Za-z]*\)", "", s)

    # ========================================================
    # [잔여 구두점 통합 및 정리]
    # ========================================================
    s = re.sub(r"([\.\?!])\s*([\.\?!])+", r"\1", s)
    s = re.sub(r"([,])\s*([\.\?!])", r"\2", s)
    s = re.sub(r"([\.\?!])\s*([,;:])", r"\1", s)
    s = re.sub(r"([,;:])\s*([,;:])", r"\1", s) 

    # 공백/구두점 정리 (최종)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([\]\)\.,;:])", r"\1", s)

    return s.strip()


# =========================
#  2. Section 카테고리 분류
# =========================

def _classify_section_common(title_norm: str, merged_text: str) -> str:
    # 1) Abstract
    if "abstract" in merged_text:
        return "abstract"

    # 2) Introduction
    if any(k in merged_text for k in ["introduction", "background", "overview"]):
        return "introduction"

    # 3) Results [최우선 순위]
    if any(k in merged_text for k in ["result", "finding"]):
        return "result"

    # 4) Discussion & Conclusion
    if any(k in merged_text for k in [
        "discussion", "conclusion", "concluding", "future direction", "summary"
    ]):
        return "discussion"

    # 5) Method
    if any(k in merged_text for k in [
        "method", "materials and methods", "experimental",
        "experiment", "procedure", "computational details"
    ]):
        return "method"

    return "other"


def _classify_section_for_review(sec: Dict[str, Any]) -> str:
    title = sec.get("title", "")
    path = sec.get("path") or []
    title_norm = _norm_for_class(title)
    top_norm = _norm_for_class(path[0]) if isinstance(path, list) and path else ""
    merged = f"{top_norm} {title_norm}".strip()

    category = _classify_section_common(title_norm, merged)
    if category in ["result", "other"]:
        return "main"
    return category


def _classify_section_for_research(sec: Dict[str, Any]) -> str:
    title = sec.get("title", "")
    path = sec.get("path") or []
    title_norm = _norm_for_class(title)
    top_norm = _norm_for_class(path[0]) if isinstance(path, list) and path else ""
    merged = f"{top_norm} {title_norm}".strip()
    return _classify_section_common(title_norm, merged)


def annotate_section_categories(article: Dict[str, Any]) -> None:
    cat = (article.get("article_category") or "other").lower()
    sections: List[Dict[str, Any]] = article.get("sections") or []

    for sec in sections:
        if cat == "review":
            sec_type = _classify_section_for_review(sec)
        elif cat == "research":
            sec_type = _classify_section_for_research(sec)
        else:
            sec_type = _classify_section_for_research(sec)
        sec["section_category"] = sec_type


# =========================
#  3. JSON Iterator
# =========================

def iter_articles(obj: Any) -> Iterable[Dict[str, Any]]:
    """
    pmc_articles_by_category.json 형태:
    {
      "topic1": [ article_dict, ...],
      "topic2": [ ... ],
      ...
    }
    또는 그냥 [article_dict, ...] 인 경우까지 처리.
    """
    if isinstance(obj, dict):
        for topic, articles in obj.items():
            if not isinstance(articles, list):
                continue
            for art in articles:
                if isinstance(art, dict):
                    art_copy = dict(art)
                    art_copy.setdefault("topic_category", topic)
                    yield art_copy
    elif isinstance(obj, list):
        for art in obj:
            if isinstance(art, dict):
                yield art