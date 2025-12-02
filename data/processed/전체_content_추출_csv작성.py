from protocol import get_protocol, get_public_protocols, html_to_text_with_superscript
import pandas as pd

search_keyword = "mouse"
page_id = 1

url, title, abstract, step_content, reference_result, guidelines_result, materials_result = [], [], [], [], [], [], []

while True:
    public_list = get_public_protocols(page_size=200, page_id=page_id, search_key=search_keyword)
    protocols = public_list.get("items", [])
    print(f"page id: {page_id}")
    print("=" * 50)

    if not protocols:
        # 데이터프레임 생성 및 CSV 저장
        df = pd.DataFrame({
            "url": url,
            "title": title,
            "abstract": abstract,
            "step_content": step_content,
            "reference": reference_result,
            "guidelines": guidelines_result,
            "materials": materials_result
        })
        print(df)
        df.to_csv(f"api_data_{search_keyword}.csv", index=False)
        break

    for i, proto_item in enumerate(protocols):
        print("=" * 50)
        print(f"진행 상황: {i + 1} / {len(protocols)}")
        protocol_id = proto_item["id"]
        protocol_url = proto_item["url"]
        url.append(protocol_url)
        print(f"url: {protocol_url}")

        detail = get_protocol(protocol_id)
        proto = detail.get("payload", {})

        # Title
        title_text = proto.get('title') or "<no data>"
        title.append(title_text)
        print(f"title: {title_text}")

        # Abstract
        abstract_html = proto.get("description") or ""
        abstract_str = html_to_text_with_superscript(abstract_html)
        if not abstract_str.strip():
            abstract_str = "<no data>"
        abstract.append(abstract_str)
        print(f"abstract: {abstract_str}")

        # Steps
        steps_list = proto.get("steps") or []
        step_str = ""
        for s in steps_list:
            step_html = s.get("step") or ""
            step_str += html_to_text_with_superscript(step_html)
        if not step_str.strip():
            step_str = "<no data>"
        step_content.append(step_str)
        print(f"step_content: {step_str}")

        # References
        reference_html = proto.get("protocol_references") or ""
        reference_str = html_to_text_with_superscript(reference_html)
        if not reference_str.strip():
            reference_str = "<no data>"
        reference_result.append(reference_str)
        print(f"reference: {reference_str}")

        # Guidelines
        guidelines_html = proto.get("guidelines") or ""
        guidelines_str = html_to_text_with_superscript(guidelines_html)
        if not guidelines_str.strip():
            guidelines_str = "<no data>"
        guidelines_result.append(guidelines_str)
        print(f"guidelines: {guidelines_str}")

        # Materials
        materials_html = proto.get("materials_text") or ""
        materials_str = html_to_text_with_superscript(materials_html)
        if not materials_str.strip():
            materials_str = "<no data>"
        materials_result.append(materials_str)
        print(f"materials: {materials_str}")

    page_id += 1
