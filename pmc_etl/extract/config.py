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
    "Cell & Molecular Mechanisms": [
        # 신호 전달 (Signal Transduction)
        "signal transduction",
        "receptor binding",
        "membrane receptor",
        "kinase cascade",
        # 세포 주기 및 사멸
        "cell cycle regulation",
        "apoptosis",
        "autophagy",
        # 분자 상호작용 및 ECM
        "protein-lipid interaction",
        "protein translocation",
        "extracellular matrix",
        "ecm remodeling",
        "cell adhesion",
        # 유전자 조절
        "transcription factor",
        "epigenetic regulation",

    ],
    "Omics & Systems Biology": [
        # 유전체/후성유전체 (Genomics/Epigenomics)
        "genome sequencing",
        "genetic variation",
        "chromatin accessibility",
        "crispr screening",
        # 단백질체/상호작용체 (Proteomics/Interactomics)
        "protein-protein interaction",
        "ppi network",
        "post-translational modification",
        "ptm mapping",
        # 전사체 (Transcriptomics)
        "rna sequencing",
        "scrnaseq", # single cell rna-seq
        "gene expression profiling",
        "go enrichment", # gene ontology enrichment
        # 시스템 생물학/데이터 분석
        "systems biology modeling",
        "metabolic pathway analysis",
        "flux balance analysis",
        "network topology",
        "big data biology",
    ],
}

MAX_PER_CATEGORY = 200  # 카테고리당 최대 논문 수
