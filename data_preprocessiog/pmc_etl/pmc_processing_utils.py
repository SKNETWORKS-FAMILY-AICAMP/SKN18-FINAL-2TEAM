# pmc_processing_utils.py

import re
import uuid 
from typing import Any, Dict, Iterable, List

# =========================
#  1. 텍스트 정제 헬퍼 (Single Line 강제)
# =========================

def clean_content(text: Any) -> str:
    """
    CSV 저장용 텍스트 정제 함수.
    - None 처리
    - 모든 줄바꿈 문자를 공백으로 치환하여 한 줄로 만듦
    - 불필요한 공백 제거
    """
    if text is None:
        return ""
    s = str(text)

    # 1. 줄바꿈 및 이스케이프 문자 공백 치환
    s = re.sub(r"[\r\n]+|\\n|//n", " ", s)

    # 2. 탭 제거
    s = s.replace("\t", " ")

    # 3. 중복 공백 제거
    s = re.sub(r"\s+", " ", s)

    return s.strip()

def normalize_title_spacing(text: Any) -> str:
    """
    섹션 제목/경로에서 숫자/구두점 주변 공백을 정리하고,
    맨 앞에 붙은 섹션 번호(예: 4.6., 2.1, 3.)는 통째로 제거한다.

    예)
      ",4.6. Isolation of Mouse Hepatic Cells"
        -> "Isolation of Mouse Hepatic Cells"
      "2.1. Introduction"
        -> "Introduction"
      "3 Results"
        -> "Results"
      "3D Reconstruction of Protein"
        -> "3D Reconstruction of Protein"  (앞에 번호가 아니라서 유지)
    """
    if text is None:
        return ""

    s = str(text).strip()

    # 0) 맨 앞에 콤마만 있으면 제거: ",4.6. Isolation" -> "4.6. Isolation"
    s = re.sub(r"^,\s*", "", s)

    # 1) 맨 앞 섹션 번호 블록 제거
    #    - "4.6. " / "4.6 " / "4." / "4 " 등
    #    - ^  숫자(.숫자)*  .(optional)  + 공백
    s = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", s)

    # 2) 구두점 앞 공백 제거: "Results ," -> "Results,"
    s = re.sub(r"\s+([,;:\.\?\!])", r"\1", s)

    # 3) 여러 공백을 하나로
    s = re.sub(r"\s+", " ", s)

    return s.strip()



def normalize_reference_spacing(text: Any) -> str:
    """
    참고문헌(raw) 문자열에서 공백만 정리하는 함수.
    - 쉼표/세미콜론/콜론/마침표 앞 공백 제거
    - en dash(–) 주변 공백 제거: "283 – 328" -> "283–328"
    - 연속 공백은 하나로 축소
    """
    if text is None:
        return ""

    s = str(text).strip()

    # 1) 구두점 앞 공백 제거: "Feldman , D. ;" -> "Feldman, D.;"
    s = re.sub(r"\s+([,;:\.\?\!])", r"\1", s)

    # 2) en dash 주변 공백 제거: "283 – 328" -> "283–328"
    s = re.sub(r"\s*–\s*", "–", s)

    # 3) 여러 공백을 하나로
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
    - fig_id / table_id와 비슷한 방식으로 전역적으로 유니크하게 사용 가능
    """
    return uuid.uuid4().int % 10**12


# =========================
#  1-2. 섹션 텍스트에서 레퍼런스 인덱스 추출 + 삭제
# =========================

# [1], [1, 2, 3], [1–3], (1,2), (1-3) 등 패턴
REF_SQUARE_PATTERN = re.compile(
    r"\[\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\]"
)
REF_PAREN_PATTERN = re.compile(
    r"\(\s*(\d+(\s*[-–]\s*\d+)?)(\s*,\s*(\d+(\s*[-–]\s*\d+)?))*\s*\)"
)
# 숫자 없이 콤마/세미콜론/대시/공백/점만 들어 있는 괄호 (예: [,,], [ , , ], (,,))
REF_SQUARE_EMPTY_PATTERN = re.compile(r"\[\s*[,;:/\.\-–\s]+\]")
REF_PAREN_EMPTY_PATTERN  = re.compile(r"\(\s*[,;:/\.\-–\s]+\)")

# 문장 끝에 괄호 없이 나열된 인용 번호: ". 46, 47" / "; 12, 13" / ") 3, 4"
TRAILING_REF_CAPTURE_PATTERN = re.compile(
    r"(?:^|[;\.\)])\s*(\d+(?:\s*,\s*\d+)*)\s*$"
)
TRAILING_REF_REMOVE_PATTERN = re.compile(
    r"([;\.\)])\s*\d+(?:\s*,\s*\d+)*\s*$"
)

# 문장 안에 콤마/대시로 이어진 숫자 클러스터
# 예: ", 46, 47", "; 23–25", ", 12, 13, 15"
INLINE_REF_CLUSTER_PATTERN = re.compile(
    r"(?<!\d)"  # 앞에 다른 숫자 없음
    r"(\d{2,}\s*(?:[-–]\s*\d{2,}|\s*,\s*\d{2,})+)"  # 2자리 이상 숫자 + (콤마/대시 + 2자리 이상 숫자)+
    r"(?!\d)"   # 뒤에도 숫자 없음
)

# "문장 끝 + 숫자 하나 + 다음 문장 시작" 패턴
# 예: "CRC. 5 As reported" → 5를 ref로 인식
INLINE_SINGLE_SENT_REF_CAPTURE = re.compile(
    r"(?<=[\.\?\!])\s*(\d{1,3})\s+(?=[A-Z])"
)
INLINE_SINGLE_SENT_REF_REMOVE = re.compile(
    r"([\.\?\!])\s*\d{1,3}(\s+)(?=[A-Z])"
)



def extract_reference_markers(text: str) -> str:
    """
    섹션/abstract 텍스트에서 레퍼런스 인덱스를 추출.
    - [1], [1,2,3], [1–3], (1), (1,2,3)
    - 문장 끝 ". 46, 47"
    - 문장 안 숫자 클러스터 ", 46, 47"
    - 문장 사이 숫자 하나 "CRC. 5 As reported"
    => 숫자만 모아서 "1;2;3" 형태로 반환 (중복 제거).
    """
    if not text:
        return ""

    indices: List[str] = []

    # 1) 대괄호 인용
    for m in REF_SQUARE_PATTERN.finditer(text):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # 2) 소괄호 인용
    for m in REF_PAREN_PATTERN.finditer(text):
        chunk = m.group(0)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # 3) 문장 끝 ". 46, 47" 같은 꼬리 숫자
    m = TRAILING_REF_CAPTURE_PATTERN.search(text)
    if m:
        chunk = m.group(1)  # "46, 47"
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # 4) 문장 안 숫자 클러스터 ", 46, 47", "; 23–25" 등
    for m in INLINE_REF_CLUSTER_PATTERN.finditer(text):
        chunk = m.group(1)
        for num in re.findall(r"\d+", chunk):
            indices.append(num)

    # 5) "CRC. 5 As reported" 같은 단일 숫자
    for m in INLINE_SINGLE_SENT_REF_CAPTURE.finditer(text):
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
    예:
      ".... proteins [1, 2, 3]."   → ".... proteins."
      ".... (1,2,3)"               → "...."
      ".... 00 kDa [,,]. Dex"      → ".... 00 kDa. Dex"
      ".... Enrichr. 46, 47"       → ".... Enrichr."
      ".... CRC. 5 As reported"    → ".... CRC. As reported"
    """
    if not text:
        return ""

    s = text

    # 1) [] / () 레퍼런스 삭제
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

    # 공백/구두점 정리
    s = re.sub(r"\s+", " ", s)                    # 여러 공백 → 하나
    s = re.sub(r"\s+([\]\)\.,;:])", r"\1", s)     # 구두점/괄호 앞 공백 제거

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
