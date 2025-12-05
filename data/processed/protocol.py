import requests
from bs4 import BeautifulSoup

# 토큰 설정 (발급받은 CLIENT_ACCESS_TOKEN) # https://www.protocols.io 로그인 => https://www.protocols.io/developers 하단에 client access token복사
CLIENT_ACCESS_TOKEN = "de16b3557405a8ae5643170bbb110d58cc14a1ba4f6e3029f26985ef73d9cb0b481cc2ad44714a30b67671eb460fd1d4bc413fa5904e63706d2a08313627d7b4"

# 공통 헤더 구성
headers = {
    "Authorization": f"Bearer {CLIENT_ACCESS_TOKEN}",
    "Accept": "application/json",
}

# 공개 프로토콜 목록 조회 (public protocols)
def get_public_protocols(page_size=10, page_id=1, search_key=None):
    url = "https://www.protocols.io/api/v3/protocols"
    params = {
        "filter": "public",
        "page_size": page_size,
        "page_id": page_id,
    }
    if search_key:
        params["key"] = search_key

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()

    return resp.json()

# 특정 프로토콜 상세 조회 (ID 또는 URI 사용 가능)
def get_protocol(protocol_id_or_uri):
    # API 문서상 protocols 조회는 v4 엔드포인트도 존재 (문서 참고) :contentReference[oaicite:2]{index=2}
    url = f"https://www.protocols.io/api/v4/protocols/{protocol_id_or_uri}"
    params = {
        "include": "steps,components,files,annotations,changelog",  # << 추가
        "content_format": "html",  # ← HTML 형식으로 요청
        "last_version": 1
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

# 제곱수 및 지수 처리
def html_to_text_with_superscript(html_content):
    if not html_content:
        return "<no data>"
    soup = BeautifulSoup(html_content, "html.parser")

    # <sup> 변환
    for sup in soup.find_all("sup"):
        sup.replace_with("^" + sup.get_text())

    # vertical-align: super 변환
    for span in soup.find_all("span", style=True):
        if "vertical-align: super" in span["style"]:
            span.replace_with("^" + span.get_text())

    return soup.get_text()