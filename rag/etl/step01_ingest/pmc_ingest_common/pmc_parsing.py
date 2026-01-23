# pmc_pipeline/parsing.py

import re
import xml.etree.ElementTree as ET
from typing import Tuple, Dict, List, Any, Optional

from rag.etl.common.pmc_config import XLINK_NS
from rag.etl.step01_ingest.pmc_ingest_common.pmc_utils import (
    _local_name,
    _dedup_preserve,
    _append_clean,
    _extract_caption_text,
    gen_fig_id,
    gen_table_id,
    natural_sort_key,
    parse_fig_label,
    normalize_fig_label,
    parse_table_label,
    normalize_table_label,
    categorize_article,
)
from rag.etl.step01_ingest.pmc_ingest_common.pmc_html_scraper import get_html_image_map
from rag.etl.step01_ingest.pmc_ingest_common.pmc_math import extract_formula_text


# -------------------- 본문 + 섹션 추출 -------------------- #

def extract_body_components(
    body_elem: Optional[ET.Element],
) -> Tuple[str, Dict[str, List[str]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    JATS <body>에서
      - 전체 본문 텍스트(body_text)
      - figure/table 캡션 텍스트
      - 섹션/하위섹션 텍스트
      - 수식(equations) 메타
    를 추출한다.
    """
    if body_elem is None:
        return "", {"figures": [], "tables": []}, [], []

    ns = {"jats": "https://jats.nlm.nih.gov/ns/archiving/1.4/"}
    FORMULA_TAGS = {"inline-formula", "disp-formula"}
    FIG_TAGS = {"fig", "fig-group", "figure"}
    TABLE_TAGS = {"table-wrap", "table"}

    # ---------- 캡션만 따로 추출 ----------
    figure_captions: List[str] = []
    table_captions: List[str] = []

    for fig in body_elem.findall(".//jats:fig", ns):
        cap = _extract_caption_text(fig)
        if cap:
            figure_captions.append(cap)

    for tw in body_elem.findall(".//jats:table-wrap", ns):
        cap = _extract_caption_text(tw)
        if cap:
            table_captions.append(cap)

    caption_data = {
        "figures": figure_captions,
        "tables": table_captions,
    }

    # ---------- 수식/텍스트 공통 헬퍼 ----------

    equations: List[Dict[str, Any]] = []
    eq_counter = [1]

    def extract_text_with_equations(
        node: ET.Element,
        current_path: Optional[List[str]] = None,
        skip_child_secs: bool = False,
        collect_fig_ids: Optional[set] = None,
        collect_table_ids: Optional[set] = None,
    ) -> str:
        parts: List[str] = []

        def walk(n: ET.Element):
            tag = _local_name(n.tag)

            if tag in ("sup", "sub"):
            # pmc_math.py의 handle_sup_sub 로직을 직접 구현하거나 가져와서 사용
                inner_text = "".join(n.itertext()).strip()
                if tag == "sup":
                    parts.append(f"^{{{inner_text}}}")
                elif tag == "sub":
                    parts.append(f"_{{{inner_text}}}")

                # tail 텍스트(태그 닫힌 후 나오는 텍스트) 처리
                _append_clean(n.tail, parts)
                return
            
            if tag == "sec" and skip_child_secs:
                _append_clean(n.tail, parts)
                return

            if tag in FIG_TAGS:
                fig_id = n.get("id")
                if collect_fig_ids is not None and fig_id:
                    collect_fig_ids.add(fig_id)
                _append_clean(n.tail, parts)
                return

            if tag in TABLE_TAGS:
                tbl_id = n.get("id")
                if collect_table_ids is not None and tbl_id:
                    collect_table_ids.add(tbl_id)
                _append_clean(n.tail, parts)
                return

            if tag in FORMULA_TAGS:
                try:
                    latex = extract_formula_text(n) or ""
                except Exception:
                    latex = ""

                if latex:
                    eq_id = f"EQ{eq_counter[0]}"
                    eq_counter[0] += 1

                    equations.append(
                        {
                            "id": eq_id,
                            "latex": latex,
                            "display": (tag == "disp-formula"),
                            "path": list(current_path) if current_path else [],
                        }
                    )
                    parts.append(f"[EQ:{eq_id}]")

                _append_clean(n.tail, parts)
                return

            # [수정됨] xref 태그(참고문헌, 그림 참조 등) 처리 로직 추가
            if tag == "xref":
                ref_type = n.get("ref-type")
                # 태그 내부 텍스트 추출 (예: "7", "Fig 1")
                ref_text = "".join(n.itertext()).strip()

                if ref_text:
                    if ref_type == "bibr":
                        # 참고문헌(Bibliographic Reference)인 경우 [7] 처럼 대괄호 처리
                        # 이렇게 해야 "development. 7" -> "development. [7]" 로 구분됨
                        parts.append(f"[{ref_text}]")
                    else:
                        # 그 외(fig, table 등)는 텍스트 흐름을 위해 그대로 둠 (혹은 필요시 처리)
                        parts.append(ref_text)
                
                # xref 태그 뒤에 오는 텍스트(tail) 처리
                _append_clean(n.tail, parts)
                return

            _append_clean(n.text, parts)
            for child in list(n):
                walk(child)
            _append_clean(n.tail, parts)

        walk(node)
        return " ".join(parts)

    # body_text
    body_text = extract_text_with_equations(body_elem, current_path=None, skip_child_secs=False)

    # 섹션별 텍스트 + figure_info

    def extract_section_title(sec_node: ET.Element) -> str:
        title_elem = sec_node.find("jats:title", ns)
        if title_elem is None:
            return ""
        parts = [seg.strip() for seg in title_elem.itertext() if seg and seg.strip()]
        return " ".join(parts) if parts else ""

    sections: List[Dict[str, Any]] = []

    def collect_sections_recursive(
        sec_node: ET.Element,
        level: int,
        parent_titles: List[str],
    ) -> None:
        title_elem = sec_node.find("jats:title", ns)
        title = extract_section_title(sec_node)
        current_path = parent_titles + [title] if title else parent_titles

        fig_ids: set = set()
        table_ids: set = set()
        section_parts: List[str] = []

        for child in list(sec_node):
            if child is title_elem:
                continue
            if _local_name(child.tag) == "sec":
                continue

            txt = extract_text_with_equations(
                child,
                current_path=current_path,
                skip_child_secs=False,
                collect_fig_ids=fig_ids,
                collect_table_ids=table_ids,
            )
            if txt:
                section_parts.append(txt)

        section_text = " ".join(section_parts).strip()

        if title or section_text or fig_ids or table_ids:
            sections.append(
                {
                    "title": title,
                    "text": section_text,
                    "level": level,
                    "path": current_path,
                    "figure_info": {
                        "fig_ids": sorted(fig_ids, key=natural_sort_key),
                        "table_ids": sorted(table_ids, key=natural_sort_key),
                    },
                }
            )

        for child_sec in sec_node.findall("jats:sec", ns):
            collect_sections_recursive(child_sec, level + 1, current_path)

    for top_sec in body_elem.findall("./jats:sec", ns):
        collect_sections_recursive(top_sec, level=1, parent_titles=[])

    return body_text, caption_data, sections, equations


# -------------------- Table Content Parsing -------------------- #

def _extract_cell_text(cell_elem: ET.Element) -> str:
    """
    테이블 셀에서 텍스트를 추출합니다. sup, sub 등 특수 태그 처리 포함.
    """
    parts = []

    def walk(node: ET.Element):
        tag = _local_name(node.tag)

        # sup, sub 처리
        if tag == "sup":
            inner = "".join(node.itertext()).strip()
            parts.append(f"^{{{inner}}}")
            _append_clean(node.tail, parts)
            return
        elif tag == "sub":
            inner = "".join(node.itertext()).strip()
            parts.append(f"_{{{inner}}}")
            _append_clean(node.tail, parts)
            return

        # 텍스트 추가
        _append_clean(node.text, parts)

        # 자식 순회
        for child in list(node):
            walk(child)

        # tail 추가
        _append_clean(node.tail, parts)

    walk(cell_elem)
    return " ".join(parts).strip()


def parse_table_content(table_wrap_elem: ET.Element, ns: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    JATS table-wrap 요소에서 실제 테이블 데이터를 추출합니다.

    Returns:
        dict: {
            "headers": List[List[Dict]],  # 헤더 행들 (text, colspan, rowspan, align 포함)
            "rows": List[List[Dict]]      # 데이터 행들 (text, colspan, rowspan, align 포함)
        }
    """
    # table 요소 찾기 - 자식 요소를 순회하면서 local name으로 찾기
    table_elem = None
    for child in table_wrap_elem:
        if _local_name(child.tag) == "table":
            table_elem = child
            break

    if table_elem is None:
        return None

    headers = []
    rows = []

    # thead 찾기
    thead = None
    for child in table_elem:
        if _local_name(child.tag) == "thead":
            thead = child
            break

    if thead is not None:
        # tr 요소 찾기
        for tr in thead:
            if _local_name(tr.tag) != "tr":
                continue

            header_row = []
            # th, td 요소 찾기
            for cell in tr:
                tag = _local_name(cell.tag)
                if tag not in ["th", "td"]:
                    continue

                cell_text = _extract_cell_text(cell)
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
                align = cell.get("align", "left")
                header_row.append({
                    "text": cell_text,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "align": align
                })
            if header_row:
                headers.append(header_row)

    # tbody 찾기
    tbody = None
    for child in table_elem:
        if _local_name(child.tag) == "tbody":
            tbody = child
            break

    if tbody is not None:
        # tr 요소 찾기
        for tr in tbody:
            if _local_name(tr.tag) != "tr":
                continue

            data_row = []
            # td, th 요소 찾기
            for cell in tr:
                tag = _local_name(cell.tag)
                if tag not in ["td", "th"]:
                    continue

                cell_text = _extract_cell_text(cell)
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
                align = cell.get("align", "left")
                data_row.append({
                    "text": cell_text,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "align": align
                })
            if data_row:
                rows.append(data_row)

    # thead/tbody가 없는 경우, table 바로 아래 tr 처리
    if not headers and not rows:
        for tr in table_elem:
            if _local_name(tr.tag) != "tr":
                continue

            row_data = []
            has_th = False

            for cell in tr:
                tag = _local_name(cell.tag)
                if tag not in ["td", "th"]:
                    continue

                if tag == "th":
                    has_th = True

                cell_text = _extract_cell_text(cell)
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
                align = cell.get("align", "left")
                row_data.append({
                    "text": cell_text,
                    "colspan": colspan,
                    "rowspan": rowspan,
                    "align": align
                })
            if row_data:
                # 첫 번째 행이거나 th 태그가 있으면 헤더로 간주
                if (not headers and len(rows) == 0) or has_th:
                    headers.append(row_data)
                else:
                    rows.append(row_data)

    return {
        "headers": headers,
        "rows": rows
    }


# -------------------- figure / table 메타 + URL -------------------- #

def extract_figures_and_tables(
    article: ET.Element,
    pmcid: Optional[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

    ns = {"jats": "https://jats.nlm.nih.gov/ns/archiving/1.4/"}
    figures: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []

    base_article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else None

    # HTML에서 blob 이미지 매핑
    real_url_map = {}
    if pmcid:
        real_url_map = get_html_image_map(pmcid)

    # ---------- Figures ----------
    for fig in article.findall(".//jats:fig", ns):
        orig_id = fig.get("id")
        label_elem = fig.find("jats:label", ns)
        label_text = "".join(label_elem.itertext()).strip() if label_elem is not None else None
        caption_text = _extract_caption_text(fig)

        parsed_type, parsed_num = parse_fig_label(label_text, caption_text)
        normalized_label = normalize_fig_label(label_text, parsed_type, parsed_num)

        # ---- GA 여부 플래그 ----
        is_ga = False
        lc_caption = (caption_text or "").lower()
        lc_label_raw = (label_text or "").lower()

        # 1) 캡션/라벨에 "graphical abstract" 들어 있으면 GA
        if "graphical abstract" in lc_caption or "graphical abstract" in lc_label_raw:
            is_ga = True

        # 2) orig_id 가 ga1, ga2, ga_01 같은 패턴이면 GA 후보
        if orig_id and re.match(r"^ga[_\-]?\d+$", orig_id.lower()):
            is_ga = True

        page_url = f"{base_article_url}#{orig_id}" if (base_article_url and orig_id) else None

        graphics_meta: List[Dict[str, Any]] = []

        for g in fig.findall(".//jats:graphic", ns):
            href = (
                g.get(XLINK_NS + "href")
                or g.get("xlink:href")
                or g.get("{http://www.w3.org/1999/xlink}href")
            )
            if not href:
                continue

            final_urls = []
            href_basename = href.split("/")[-1].rsplit(".", 1)[0]  # 예: "ga1"

            # 3) 이미지 파일명 자체가 ga1, ga2 등이면 GA 후보
            if re.match(r"^ga\d+$", href_basename.lower()):
                is_ga = True

            if href_basename in real_url_map:
                final_urls.append(real_url_map[href_basename])
            else:
                filename = href
                if not filename.lower().endswith(('.jpg', '.png', '.gif', '.jpeg')):
                    filename += ".jpg"
                backup_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{filename}"
                final_urls.append(backup_url)

            final_urls = _dedup_preserve(final_urls)

            graphics_meta.append({
                "href": href,
                "image_urls": final_urls,
                "mimetype": g.get("mimetype"),
                "mime_subtype": g.get("mime-subtype"),
            })

        # ---- 최종 라벨 결정 ----
        if is_ga:
            # GA는 무조건 "graphical abstract"로 통일
            normalized_label = "graphical abstract"
        elif not normalized_label and orig_id:
            # GA가 아니고, 아직 라벨 없으면 orig_id 기반 fig 번호 추출
            m_id = re.search(r"(\d+)", orig_id)
            if m_id:
                normalized_label = f"fig{m_id.group(1)}"

        # fig_id 생성: pmcid + normalized_label
        fig_id = gen_fig_id(pmcid, normalized_label)

        image_urls = _dedup_preserve([url for gm in graphics_meta for url in (gm.get("image_urls") or [])])
        image_hrefs = _dedup_preserve([gm.get("href") for gm in graphics_meta])

        figures.append({
            "fig_id": fig_id,
            "orig_id": orig_id,
            "label": normalized_label,
            "caption": caption_text,
            "page_url": page_url,
            "graphics": graphics_meta,
            "image_urls": image_urls,
            "image_hrefs": image_hrefs,
        })


    # ---------- Tables ----------
    for tw in article.findall(".//jats:table-wrap", ns):
        tw_id = tw.get("id")
        label_elem = tw.find("jats:label", ns)
        raw_label = "".join(label_elem.itertext()).strip() if label_elem is not None else None
        caption = _extract_caption_text(tw)
        page_url = f"{base_article_url}#{tw_id}" if (base_article_url and tw_id) else None

        tbl_type, tbl_num = parse_table_label(raw_label, caption)
        normalized_label = normalize_table_label(raw_label, tbl_type, tbl_num)

        if not normalized_label and tw_id:
            m_id = re.search(r"(\d+)", tw_id)
            if m_id:
                normalized_label = f"table{m_id.group(1)}"

        href = None
        binary_url = None

        graphic = tw.find(".//jats:graphic", ns)
        if graphic is not None:
            href = (
                graphic.get(XLINK_NS + "href")
                or graphic.get("xlink:href")
                or graphic.get("{http://www.w3.org/1999/xlink}href")
            )

            if href:
                href_basename = href.split("/")[-1].rsplit(".", 1)[0]
                if href_basename in real_url_map:
                    binary_url = real_url_map[href_basename]
                elif pmcid:
                    filename = href
                    if not filename.lower().endswith(('.jpg', '.png')):
                        filename += ".jpg"
                    binary_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{filename}"

        # 테이블 실제 데이터 파싱
        table_content = parse_table_content(tw, ns)

        # table_id 생성: pmcid + normalized_label
        table_id = gen_table_id(pmcid, normalized_label)

        tables.append({
            "id": tw_id,             # XML 원본 id
            "table_id": table_id,    # pmcid + label 조합 문자열 ID
            "orig_id": tw_id,
            "label": normalized_label,
            "caption": caption,
            "page_url": page_url,
            "href": href, # 테이블 이미지로 제공시  이미지 파일명
            "binary_url": binary_url, # 실제 이미지를 다운로드 할 수 있는 완전한 url
            "content": table_content,  # 테이블 실제 내용 추가
        })

    return figures, tables


# -------------------- Article 전체 정보 추출 -------------------- #

def extract_article_info(record) -> Optional[Dict[str, Any]]:
    """
    하나의 <record> 에서 메타데이터 + 본문 구성요소 추출.
    """
    ns_jats = {"jats": "https://jats.nlm.nih.gov/ns/archiving/1.4/"}

    metadata = record.find(".//{http://www.openarchives.org/OAI/2.0/}metadata")
    if metadata is None:
        return None

    article = metadata.find(".//jats:article", ns_jats)
    if article is None:
        article = metadata.find(".//article")
    if article is None:
        return None

    title_elem = article.find(".//jats:article-title", ns_jats)
    title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""

    abstract_elem = article.find(".//jats:abstract", ns_jats)
    abstract = "".join(abstract_elem.itertext()).strip() if abstract_elem is not None else ""

    journal_elem = article.find(".//jats:journal-title", ns_jats)
    journal = "".join(journal_elem.itertext()).strip() if journal_elem is not None else ""

    year = None
    pub_year_elem = article.find(".//jats:pub-date/jats:year", ns_jats)
    if pub_year_elem is not None and pub_year_elem.text:
        year = pub_year_elem.text.strip()

    pmid = None
    pmcid = None
    doi = None

    article_meta = article.find(".//jats:article-meta", ns_jats)
    if article_meta is not None:
        for aid in article_meta.findall("jats:article-id", ns_jats):
            id_type = aid.get("pub-id-type")

            if id_type == "pmid":
                pmid = (aid.text or "").strip() or None
            elif id_type in ("pmcid", "pmc"):
                pmcid = (aid.text or "").strip() or None
            elif id_type == "doi":
                doi = (aid.text or "").strip() or None

    article_type_raw = (article.get("article-type") or "").strip().lower()
    article_category = "other"

    REVIEW_TYPES = {
        "review-article",
        "systematic-review",
        "meta-analysis",
        "mini-review",
        "scoping-review",
        "review",
    }
    RESEARCH_TYPES = {
        "research-article",
        "clinical-trial",
        "clinical-study",
        "original-article",
        "case-report",
    }

    if article_type_raw in REVIEW_TYPES:
        article_category = "review"
    elif article_type_raw in RESEARCH_TYPES:
        article_category = "research"
    else:
        subj_groups = article.findall(".//jats:article-categories/jats:subj-group", ns_jats)
        for sg in subj_groups:
            subj = sg.find(".//jats:subject", ns_jats)
            if subj is not None and subj.text:
                s = subj.text.strip().lower()
                if "review" in s:
                    article_category = "review"
                    break

    body_elem = article.find(".//jats:body", ns_jats)
    body_text, caption_info, sections, equations = extract_body_components(body_elem)

    figures_meta, tables_meta = extract_figures_and_tables(article, pmcid)

    # fig orig_id -> fig_id 매핑
    fig_id_map: Dict[str, str] = {}
    for f in figures_meta:
        orig_id = f.get("orig_id") or f.get("id")
        fid = f.get("fig_id")
        if orig_id and fid is not None:
            fig_id_map[str(orig_id)] = fid

    # 섹션 figure_info에 fig_ids(pmcid+label 조합 문자열 ID) 반영
    for sec in sections:
        finfo = sec.get("figure_info") or {}
        orig_fig_ids = list(finfo.get("fig_ids") or [])
        new_fig_ids: List[str] = []
        for oid in orig_fig_ids:
            mid = fig_id_map.get(str(oid))
            if mid is not None:
                new_fig_ids.append(mid)

        finfo["orig_fig_ids"] = orig_fig_ids
        finfo["fig_ids"] = sorted(new_fig_ids, key=natural_sort_key)
        sec["figure_info"] = finfo

    def build_figure_urls(fig: Dict[str, Any]) -> List[str]:
        urls: List[str] = []
        urls.extend(fig.get("image_urls") or [])
        for g in fig.get("graphics", []):
            urls.extend(g.get("image_urls") or [])
            binary_url = g.get("binary_url")
            if binary_url:
                urls.append(binary_url)
        return _dedup_preserve(urls)

    # figure_captions: fig_id + caption + URL 모음
    figure_captions: List[Dict[str, Any]] = []
    for f in figures_meta:
        urls = build_figure_urls(f)
        figure_captions.append(
            {
                "fig_id": f.get("fig_id"),
                "label": f.get("label"),
                "caption": f.get("caption"),
                "page_url": f.get("page_url"),
                "urls": urls,
            }
        )

    # table_captions: table_id(정수) + XML id + caption + content
    table_captions = [
        {
            "table_id": t.get("table_id"),  # 정수형 UUID 기반 ID
            "id": t.get("id"),             # XML 원본 id
            "label": t.get("label"),
            "caption": t.get("caption"),
            "page_url": t.get("page_url"),
            "href": t.get("href"),
            "binary_url": t.get("binary_url"),
            "content": t.get("content"),  # 테이블 실제 내용
        }
        for t in tables_meta
    ]

    # 참고문헌
    references: List[Dict[str, Any]] = []
    back = article.find(".//jats:back", ns_jats)
    if back is not None:
        ref_list = back.find(".//jats:ref-list", ns_jats)
        if ref_list is not None:
            refs = ref_list.findall(".//jats:ref", ns_jats)
            for ref in refs:
                ref_info: Dict[str, Any] = {}

                # mixed-citation / element-citation 노드 찾기
                citation = ref.find(".//jats:mixed-citation", ns_jats)
                if citation is None:
                    citation = ref.find(".//jats:element-citation", ns_jats)

                # citation 전체 생 텍스트
                raw_text = ""
                if citation is not None:
                    raw_parts = [
                        seg.strip()
                        for seg in citation.itertext()
                        if seg and seg.strip()
                    ]
                    raw_text = " ".join(raw_parts).strip()
                    if raw_text:
                        ref_info["raw"] = raw_text

                if citation is not None:
                    # 1) 저자
                    authors = []
                    person_groups = citation.findall(".//jats:person-group", ns_jats)
                    for pg in person_groups:
                        names = pg.findall(".//jats:name", ns_jats)
                        for name in names:
                            surname = name.find(".//jats:surname", ns_jats)
                            given = name.find(".//jats:given-names", ns_jats)
                            author_name = ""
                            if surname is not None and surname.text:
                                author_name = surname.text
                            if given is not None and given.text:
                                author_name += f" {given.text}"
                            if author_name:
                                authors.append(author_name.strip())
                    if authors:
                        ref_info["authors"] = authors

                    # 2) 제목
                    ref_title = citation.find(".//jats:article-title", ns_jats)
                    if ref_title is not None:
                        title_text = "".join(ref_title.itertext()).strip()
                        if title_text:
                            ref_info["title"] = title_text

                    # 3) 저널/소스
                    source = citation.find(".//jats:source", ns_jats)
                    if source is not None and source.text:
                        ref_info["journal"] = source.text.strip()

                    # 4) 연도
                    ref_year = citation.find(".//jats:year", ns_jats)
                    if ref_year is not None and ref_year.text:
                        ref_info["year"] = ref_year.text.strip()

                    # 5) PMID / DOI
                    pmid_elem = citation.find(
                        './/jats:pub-id[@pub-id-type="pmid"]', ns_jats
                    )
                    if pmid_elem is not None and pmid_elem.text:
                        ref_info["pmid"] = pmid_elem.text.strip()

                    doi_elem = citation.find(
                        './/jats:pub-id[@pub-id-type="doi"]', ns_jats
                    )
                    if doi_elem is not None and doi_elem.text:
                        ref_info["doi"] = doi_elem.text.strip()

                    # 6) 외부 링크들
                    ext_links = citation.findall(".//jats:ext-link", ns_jats)
                    urls: List[str] = []
                    for el in ext_links:
                        href = (
                            el.get(XLINK_NS + "href")
                            or el.get("xlink:href")
                            or el.get("href")
                        )
                        if href:
                            urls.append(href.strip())
                    if urls:
                        seen_u = set()
                        uniq_urls: List[str] = []
                        for u in urls:
                            if u not in seen_u:
                                seen_u.add(u)
                                uniq_urls.append(u)
                        ref_info["urls"] = uniq_urls

                    # 7) title이 비어 있으면 raw_text로 대체
                    if "title" not in ref_info and raw_text:
                        ref_info["title"] = raw_text

                    # 8) 대표 URL 선택 (DOI > 첫 ext-link)
                    primary_url: Optional[str] = None
                    doi_val = ref_info.get("doi")
                    if isinstance(doi_val, str) and doi_val.strip():
                        primary_url = f"https://doi.org/{doi_val.strip()}"
                    else:
                        url_list = ref_info.get("urls") or []
                        if isinstance(url_list, list) and url_list:
                            primary_url = url_list[0]

                    if primary_url:
                        ref_info["url"] = primary_url

                if ref_info:
                    references.append(ref_info)

    return {
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "year": year,
        "pmcid": pmcid,
        "pmid": pmid,
        "doi": doi,
        "article_category": article_category,
        "article_type_raw": article_type_raw,
        "figure_captions": figure_captions,
        "table_captions": table_captions,
        "sections": sections,
        "equations": equations,
        "references": references,
    }