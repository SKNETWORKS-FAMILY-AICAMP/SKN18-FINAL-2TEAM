# 수식처리.py
# -*- coding: utf-8 -*-
"""
PMC NXML에서 가져온 수식(<disp-formula>, <inline-formula>, <math>)을
LaTeX 문자열로 변환하는 유틸 모듈.

사용 함수:
    - extract_formula_text(formula_node, display=False)
    - handle_sup_sub(node)

외부 라이브러리:
    - mathml2latex (있으면 MathML → LaTeX에 사용, 없으면 fallback)
"""

from typing import List
import xml.etree.ElementTree as ET

# -----------------------------
# 내부 유틸
# -----------------------------


def _local_name(tag: str) -> str:
    """{namespace}tag 형식에서 tag 이름만 분리."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# MathML → LaTeX용 외부 라이브러리 (있으면 사용)
try:
    from mathml2latex import convert as _mathml2latex_convert  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - import 실패 시
    try:
        from mathml2latex import mathml2latex as _mathml2latex_convert  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        _mathml2latex_convert = None


# -----------------------------
# MathML → LaTeX Fallback
# -----------------------------


def _mathml_to_latex_fallback(elem: ET.Element) -> str:
    """
    mathml2latex 라이브러리가 없을 때 사용하는
    간단한 MathML → LaTeX 변환기.

    자주 쓰이는 태그(mi, mn, mo, mfrac, msup, msub, msubsup, msqrt,
    mroot, mfenced, mrow, mtable, mtr, mtd)를 우선 지원.
    """

    def inner(node: ET.Element) -> str:
        tag = _local_name(node.tag)
        children = list(node)

        if tag in ("math", "mrow"):
            return "".join(inner(ch) for ch in children)

        if tag in ("mi", "mn"):
            txt = (node.text or "").strip()
            return txt

        if tag == "mo":
            txt = (node.text or "").strip()
            mapping = {
                "×": r"\times",
                "⋅": r"\cdot",
                "·": r"\cdot",
                "−": "-",
                "–": "-",
                "+": "+",
                "=": "=",
                "±": r"\pm",
                "∓": r"\mp",
                "∑": r"\sum",
                "∏": r"\prod",
                "∫": r"\int",
                "∞": r"\infty",
                "→": r"\to",
                "⇒": r"\Rightarrow",
                "≥": r"\ge",
                "≤": r"\le",
                "≃": r"\simeq",
                "≈": r"\approx",
                "≠": r"\neq",
            }
            return mapping.get(txt, txt)

        if tag == "msup" and len(children) >= 2:
            base = inner(children[0])
            exp = inner(children[1])
            return f"{base}^{{{exp}}}"

        if tag == "msub" and len(children) >= 2:
            base = inner(children[0])
            sub = inner(children[1])
            return f"{base}_{{{sub}}}"

        if tag == "msubsup" and len(children) >= 3:
            base = inner(children[0])
            sub = inner(children[1])
            exp = inner(children[2])
            return f"{base}_{{{sub}}}^{{{exp}}}"

        if tag == "mfrac" and len(children) >= 2:
            num = inner(children[0])
            den = inner(children[1])
            return rf"\frac{{{num}}}{{{den}}}"

        if tag == "msqrt":
            body = "".join(inner(ch) for ch in children)
            return rf"\sqrt{{{body}}}"

        if tag == "mroot" and len(children) >= 2:
            radicand = inner(children[0])
            degree = inner(children[1])
            return rf"\sqrt[{degree}]{{{radicand}}}"

        if tag == "mfenced":
            open_delim = node.get("open", "(")
            close_delim = node.get("close", ")")
            body = "".join(inner(ch) for ch in children)
            return f"{open_delim}{body}{close_delim}"

        if tag == "mtable":
            rows: List[str] = []
            for row in children:
                if _local_name(row.tag) != "mtr":
                    continue
                cells: List[str] = []
                for cell in list(row):
                    if _local_name(cell.tag) != "mtd":
                        continue
                    cells.append(inner(cell))
                rows.append(" & ".join(cells))
            body = r" \\ ".join(rows)
            return rf"\begin{{matrix}} {body} \end{{matrix}}"

        # 알 수 없는 태그: 자식만 이어 붙임
        if children:
            return "".join(inner(ch) for ch in children)

        # 텍스트가 있으면 사용
        if node.text and node.text.strip():
            return node.text.strip()

        return ""

    return inner(elem)


def mathml_to_latex(math_elem: ET.Element) -> str:
    """
    MathML <math> 요소를 LaTeX 문자열로 변환.
      1) mathml2latex 패키지가 있으면 우선 사용
      2) 없으면 fallback 변환기 사용
    """
    xml_str = ET.tostring(math_elem, encoding="unicode")

    if _mathml2latex_convert is not None:
        try:
            return _mathml2latex_convert(xml_str)
        except Exception:
            # 외부 변환 실패 시 fallback
            pass

    return _mathml_to_latex_fallback(math_elem)


# -----------------------------
# 공개 API
# -----------------------------


def extract_formula_text(formula_node: ET.Element, display: bool = False) -> str:
    """
    <disp-formula>, <inline-formula> 같은 수식 노드에서 수식을 추출해
    LaTeX 문자열로 반환.

    우선순위:
      1) <tex-math> 안의 LaTeX
      2) <math> (MathML) → LaTeX
      3) itertext() 평문
    """
    # 1) tex-math (LaTeX) 우선
    for descendant in formula_node.iter():
        if _local_name(descendant.tag) == "tex-math" and (descendant.text or "").strip():
            tex = descendant.text.strip()
            return f"$$ {tex} $$" if display else f"$ {tex} $"

    # 2) MathML → LaTeX
    for descendant in formula_node.iter():
        if _local_name(descendant.tag) == "math":
            latex = mathml_to_latex(descendant)
            if latex:
                return f"$$ {latex} $$" if display else f"$ {latex} $"

    # 3) 최후 수단: 평문
    parts = [seg.strip() for seg in formula_node.itertext() if seg.strip()]
    return " ".join(parts)


def handle_sup_sub(node: ET.Element) -> str:
    """
    <sup>, <sub> 노드를 ^{...}, _{...} 형태의 LaTeX 스타일 문자열로 변환.
    해당 노드 전체의 텍스트/자식 텍스트를 한 번에 flatten해서 넣는다.
    """
    tag = _local_name(node.tag)
    inner = "".join(seg.strip() for seg in node.itertext() if seg.strip())
    if not inner:
        return ""

    if tag == "sup":
        return f"^{{{inner}}}"
    elif tag == "sub":
        return f"_{{{inner}}}"
    return inner
