# pmc_pipeline/config.py

PMC_OAI_ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
EUTILS_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
XLINK_NS = "{http://www.w3.org/1999/xlink}"

# 날짜 범위 (2019~2024)
DEFAULT_FROM_DATE = "2019/01/01"
DEFAULT_UNTIL_DATE = "2024/12/31"

# 1) 카테고리 & 확장된 키워드 세트 (최종 통합본)
CATEGORY_KEYWORDS = {
    # ==========================================
    # [1. mRNA 및 LNP 특화 (NEW! Focus Area)]
    # ==========================================
    "mRNA Therapeutics & LNP Delivery": [
        # mRNA 설계 및 구조
        "mrna therapeutics", "mrna vaccine", "ivt mrna",
        "codon optimization", "nucleoside modification", "n1-methylpseudouridine",
        "5' cap structure", "poly(a) tail", "utr engineering",
        "self-amplifying rna", "sarna", "circular rna", "circrna",
        # LNP 및 전달체 기술
        "lipid nanoparticle", "lnp", "solid lipid nanoparticle",
        "ionizable lipid", "cationic lipid", # LNP 핵심 성분
        "peg-lipid", "lipid composition", "lipidoid",
        "encapsulation efficiency", "endosomal escape", # 효능 핵심 지표
        "microfluidic mixing", "microfluidic assembly", # 제조 공정
        "mrna delivery", "extrahepatic delivery", # 간 외 전달 (최신 트렌드)
    ],

    # ==========================================
    # [2. 단백질 공학 및 기초 물성]
    # ==========================================
    "Protein Structure & Enzyme Engineering": [
        "protein structure", "protein folding", "protein stability",
        "thermostability", "enzyme stability",
        "enzyme kinetics", "catalytic efficiency", "substrate specificity",
        "catalytic mechanism",
        "protein engineering", "directed evolution",
        "site-directed mutagenesis", "saturation mutagenesis",
    ],
    "Physicochemical Properties & Residue Analysis": [
        "amino acid property", "physicochemical property",
        "hydrophobicity", "hydropathy", "isoelectric point", "pka value",
        "solvent accessibility", "sasa",
        "residue interaction", "salt bridge", "disulfide bond", "pi-pi stacking",
        "mutation effect prediction", "sequence-function relationship",
        "protein electrostatics",
    ],
    "AI-based Modeling & Design": [
        "ai drug discovery",
        "computational drug design", "in silico screening", "virtual screening",
        "de novo drug design", "de novo protein design",
        "protein language model", "structure-based drug design",
        "molecular dynamics simulation",
    ],
    "Synthetic Biology & Metabolic Engineering": [
        "synthetic biology", "metabolic engineering",
        "cell factory", "strain engineering",
        "genetic circuit", "gene cluster",
        "biosynthesis pathway", "biocatalysis",
        "industrial enzyme production", "fermentation optimization",
    ],

    # ==========================================
    # [3. 바이오 의약품 및 모달리티]
    # ==========================================
    "Antibody Engineering & Therapeutics": [
        "monoclonal antibody", "mab", "antibody engineering",
        "bispecific antibody", "multispecific antibody",
        "antibody-drug conjugate", "adc",
        "nanobody", "vhh", "single-domain antibody",
        "phage display", "affinity maturation", "humanization",
        "fc engineering", "adcc", "cdc",
    ],
    "Fusion Proteins & Linker Design": [
        "fusion protein", "chimeric protein", "recombinant fusion",
        "linker design", "flexible linker", "rigid linker", "helical linker",
        "fc-fusion", "albumin fusion",
        "bifunctional protein", "bifunctional enzyme",
        "protein tagging", "epitope tag",
        "fusion partner", "solubility tag",
    ],
    "Cytokines & Immunomodulation": [
        "cytokine therapy", "interleukin", "interferon", "chemokine",
        "cytokine storm", "cytokine release syndrome",
        "immunomodulation", "immune signaling",
        "jak-stat signaling", "tnf inhibitor",
        "pro-inflammatory cytokine", "anti-inflammatory cytokine",
        "fusion protein", 
    ],
    
    # ==========================================
    # [4. PH20, 제형 및 일반 전달 기술]
    # ==========================================
    "Glycobiology & Carbohydrate Enzymes": [
        "glycobiology", "glycosylation", "glycan analysis",
        "cazyme", "carbohydrate-active enzymes", "glycosyl hydrolase",
        "hyaluronidase", "hyaluronan", "hyaluronic acid",
        "extracellular matrix degradation", "glycoprotein structure",
    ],
    "Drug Delivery & Biopharmaceutics": [ # (LNP 제외 일반 DDS)
        "drug delivery system", "dds", "nanomedicine",
        "nanoparticle formulation", "liposome",
        "subcutaneous delivery", "subcutaneous injection",
        "pharmacokinetics", "bioavailability", "drug absorption",
        "biologics formulation", "protein aggregation",
    ],

    # ==========================================
    # [5. 유전자 교정 및 최신 질환 트렌드]
    # ==========================================
    "Gene Editing & Viral Vectors": [ # (mRNA/LNP와 구분하여 AAV/CRISPR 중심)
        "gene therapy", "viral vector",
        "aav vector", "adeno-associated virus", "lentivirus",
        "gene editing", "crispr-cas9", "prime editing", "base editing",
        "gene knock-in", "gene knockout", "ex vivo gene therapy",
    ],
    "Metabolic Disease & Obesity": [
        "obesity", "type 2 diabetes", "metabolic syndrome",
        "glp-1", "glucagon-like peptide-1", "incretin mimetic",
        "insulin resistance", "adipose tissue biology",
        "nash", "nafld",
        "energy homeostasis",
    ],
    "Neurodegenerative Diseases": [
        "alzheimer's disease", "parkinson's disease",
        "neurodegeneration", "amyloid beta", "tau protein",
        "blood-brain barrier", "bbb penetration",
        "neuroinflammation", "microglia", "synaptic plasticity",
    ],

    # ==========================================
    # [6. 기초 생물학 및 오믹스]
    # ==========================================
    "Omics & Systems Biology": [
        "genome sequencing", "genetic variation", "chromatin accessibility", "crispr screening",
        "protein-protein interaction", "ppi network",
        "post-translational modification", "ptm mapping",
        "rna sequencing", "scrnaseq", "gene expression profiling", "go enrichment",
        "systems biology modeling", "metabolic pathway analysis",
        "flux balance analysis", "network topology", "big data biology",
    ],
    "Cancer Biology & Oncology": [
        "cancer biology", "oncology", "neoplasm",
        "cancer signaling", "oncogenic signaling", "signal transduction",
        "tumor microenvironment", "tme", "immune checkpoint",
        "angiogenesis", "metastasis", "tumor invasion", "chemoresistance",
    ],
    "Cell & Molecular Mechanisms": [
        "signal transduction", "receptor binding", "membrane receptor", "kinase cascade",
        "cell cycle regulation", "apoptosis", "autophagy",
        "protein-lipid interaction", "protein translocation",
        "extracellular matrix", "ecm remodeling", "cell adhesion",
        "transcription factor", "epigenetic regulation",
    ],
    "Stem Cells & Organoids": [
        "stem cell biology", "pluripotent stem cells", "induced pluripotent stem cells", "ipsc",
        "mesenchymal stem cells", "stem cell differentiation",
        "organoid", "organoid culture", "patient-derived organoids",
        "spheroid", "3d cell culture", "organ-on-a-chip",
        "tissue engineering", "regenerative medicine", "scaffold design", "bioprinting",
    ],
}

MAX_PER_CATEGORY = 500