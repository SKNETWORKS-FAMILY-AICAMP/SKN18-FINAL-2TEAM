# pmc_pipeline/config.py

PMC_OAI_ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
EUTILS_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
XLINK_NS = "{http://www.w3.org/1999/xlink}"

# 날짜 범위 (필요하면 여기만 수정)
DEFAULT_FROM_DATE = "2019/01/01"
DEFAULT_UNTIL_DATE = "2024/12/31"

# 1) 카테고리 & 확장된 키워드 세트
CATEGORY_KEYWORDS = {
    "Protein Structure & Enzyme Engineering": [
        # 구조/안정성
        "protein structure",
        "protein folding",
        "protein stability",
        "thermostability",
        "enzyme stability",
        # 효소학
        "enzyme kinetics",
        "catalytic efficiency",
        "substrate specificity",
        "catalytic mechanism",
        # 공학/돌연변이
        "protein engineering",
        "directed evolution",
        "site-directed mutagenesis",
        "saturation mutagenesis",
    ],
    "Cancer Biology & Oncology": [
        # 암/종양 전반
        "cancer biology",
        "oncology",
        "neoplasm",
        # 신호전달/온코제닉
        "cancer signaling",
        "oncogenic signaling",
        "signal transduction",
        # 미세환경/면역
        "tumor microenvironment",
        "tme",
        "immune checkpoint",
        # 진행/전이
        "angiogenesis",
        "metastasis",
        "tumor invasion",
        "chemoresistance",
    ],
    "AI-based Modeling & Design": [
        # AI/ML 전반
        "ai drug discovery",
        # 계산 설계/스크리닝
        "computational drug design",
        "in silico screening",
        "virtual screening",
        "de novo drug design",
        "de novo protein design",
        "protein language model",
        "structure-based drug design",
    ],
}

MAX_PER_CATEGORY = 20  # 카테고리당 최대 논문 수
