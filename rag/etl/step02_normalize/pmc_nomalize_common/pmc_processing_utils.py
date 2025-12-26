# pmc_processing_utils.py (수정됨)

import re
import uuid 
from typing import Any, Dict, Iterable, List

# =========================
#  0. 정규식 패턴 정의 (Reference Markers)
# =========================

FIG_TABLE_REF_PATTERN = re.compile(
    r"\(\s*(?:Fig|Figure|Table|Scheme|SI Appendix|Suppl\.)[^()]+?\)", 
    re.IGNORECASE
)
FIG_REF_PATTERN = re.compile(
    r"\[\s*([A-Za-z0-9]+(?:[\s,\-–\.]\s*[A-Za-z0-9]+)*)\s*\]"
)
FIG_REF_PAREN_PATTERN = re.compile(
    r"\(\s*([A-Za-z0-9]+(?:[\s,\-–\.]\s*[A-Za-z0-9]+)*)\s*\)"
)
REF_SQUARE_PATTERN = re.compile(
    r"\[\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\]"
)
REF_PAREN_PATTERN = re.compile(
    r"\(\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\)"
)
TRAILING_REF_CAPTURE_PATTERN = re.compile(r"(?:^|[;\.\)])\s*(\d+(?:\s*,\s*\d+)*)\s*$")
TRAILING_REF_REMOVE_PATTERN = re.compile(r"([;\.\)])\s*\d+(?:\s*,\s*\d+)*\s*$")
INLINE_REF_CLUSTER_PATTERN = re.compile(r"(?<!\d)(\d{2,}\s*(?:[-–]\s*\d{2,}|\s*,\s*\d{2,})+)(?!\d)")
INLINE_SINGLE_SENT_REF_CAPTURE = re.compile(r"(?<=[\.\?\!])\s*(\d{1,3})\s+(?=[A-Z])")
INLINE_SINGLE_SENT_REF_REMOVE = re.compile(r"([\.\?\!])\s*\d{1,3}(\s+)(?=[A-Z])")
REF_SQUARE_EMPTY_PATTERN = re.compile(r"\[\s*[,;:/\.\-–\s]+\]")
REF_PAREN_EMPTY_PATTERN  = re.compile(r"\(\s*[,;:/\.\-–\s]+\)")

# =========================
#  1. 텍스트 정제 헬퍼 (LaTeX 보정 및 정규화)
# =========================

def normalize_latex_spacing(text: str) -> str:
    """
    [NEW] LaTeX 수식 변환 과정에서 발생한 공백 및 텍스트 붙음 문제를 보정합니다.
    예: 2^ ^{ΔΔCt} -> 2^{ΔΔCt}, 10 ^{5} -> 10^{5}, M)an -> M) an
    """
    if not text:
        return ""
    
    s = text

    # 1. [Case A] 중복된 Caret 제거 (2^ ^{...} -> 2^{...})
    # 설명: 글자(\S) 뒤에 '^'가 있고, 공백(\s*) 뒤에 또 '^{'가 나오는 패턴
    # \s* 로 변경하여 공백이 없거나(2^^{) 여러 개여도(2^  ^{) 모두 잡도록 함
    s = re.sub(r"(\S)\^\s*\^\{", r"\1^{", s)
    
    # 2. [Case B] 숫자/문자 뒤 불필요한 공백 제거 (2 ^{...} -> 2^{...})
    # 설명: Caret이 하나만 있는데, 앞에 공백이 있는 경우 붙여줌
    s = re.sub(r"(\w)\s+\^\{", r"\1^{", s)
    
    # 3. [Case C] 괄호 뒤 텍스트 붙음 방지 (M)an -> M) an)
    # 영어 대소문자([a-zA-Z])가 2글자 이상 이어질 때만 띄어쓰기 (단위 등 오탐 방지)
    s = re.sub(r"\)([a-zA-Z]{2,})", r") \1", s)

    return s

def clean_content(text: Any) -> str:
    """
    CSV 저장용 텍스트 정제 함수.
    기본 공백 정리 + normalize_latex_spacing 적용
    """
    if text is None: return ""
    s = str(text)
    
    # 1. 줄바꿈 및 탭 정리
    s = re.sub(r"[\r\n]+|\\n|//n", " ", s)
    s = s.replace("\t", " ")
    
    # 2. 괄호 주변 공백 정리 (소괄호 안쪽 공백 제거)
    s = re.sub(r"\s+\(", "(", s) 
    s = re.sub(r"\(\s+", "(", s) 
    s = re.sub(r"\s+\)", ")", s) 
    s = re.sub(r"\)\s+", ")", s) 
    
    # 3. [적용] LaTeX 및 텍스트 붙음 보정
    s = normalize_latex_spacing(s)

    # 4. 다중 공백 정리
    s = re.sub(r"\s+", " ", s)
    
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

    for m in REF_PAREN_PATTERN.finditer(s):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    for m in REF_SQUARE_PATTERN.finditer(s):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

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
    """
    if not text:
        return ""

    s = text

    s = re.sub(FIG_TABLE_REF_PATTERN, "", s) 
    s = FIG_REF_PATTERN.sub("", s)
    s = FIG_REF_PAREN_PATTERN.sub("", s)

    s = REF_SQUARE_PATTERN.sub("", s)
    s = REF_PAREN_PATTERN.sub("", s)
    s = REF_SQUARE_EMPTY_PATTERN.sub("", s)
    s = REF_PAREN_EMPTY_PATTERN.sub("", s)
    s = re.sub(r"\[\s*\]", "", s)
    s = re.sub(r"\(\s*\)", "", s)

    s = TRAILING_REF_REMOVE_PATTERN.sub(r"\1", s)
    s = INLINE_REF_CLUSTER_PATTERN.sub(" ", s)
    s = INLINE_SINGLE_SENT_REF_REMOVE.sub(r"\1 ", s)

    s = re.sub(r"\[\s*[^0-9A-Za-z]*\]", "", s)
    s = re.sub(r"\(\s*[^0-9A-Za-z]*\)", "", s)

    s = re.sub(r"([\.\?!])\s*([\.\?!])+", r"\1", s)
    s = re.sub(r"([,])\s*([\.\?!])", r"\2", s)
    s = re.sub(r"([\.\?!])\s*([,;:])", r"\1", s)
    s = re.sub(r"([,;:])\s*([,;:])", r"\1", s) 

    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([\]\)\.,;:])", r"\1", s)

    return s.strip()


# =========================
#  2. Section 카테고리 분류
# =========================

def _classify_section_common(title_norm: str, merged_text: str) -> str:
    if "abstract" in merged_text:
        return "abstract"
    if any(k in merged_text for k in ["introduction", "background", "overview"]):
        return "introduction"
    if any(k in merged_text for k in ["result", "finding"]):
        return "result"
    if any(k in merged_text for k in [
        "discussion", "conclusion", "concluding", "future direction", "summary"
    ]):
        return "discussion"
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