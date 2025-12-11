"""
sections.csv를 기반으로

pmid(논문아이디), method(방법), condition(조건),
category_parent(상위 카테고리), category_leaf(하위 카테고리),
materials(재료), equipment(장비)

형태의 실험 테이블을 생성하는 스크립트.
각 논문의 실험 정보를 OpenAI LLM으로 추출한다.
"""

from pathlib import Path
import os
import time
import json
import re

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# 디버그용 플래그 (RAW 응답 보고 싶으면 True)
DEBUG = False

# -----------------------------------
# 경로 및 OpenAI 클라이언트 설정
# -----------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]

# sections.csv 경로 (미누 프로젝트 구조 기준)
SECTIONS_PATH = ROOT_DIR / "data" / "pmc_data" / "pmc" / "sections.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "pmc_data" / "paper_experiments_table.csv"

# .env 로드 (프로젝트 루트에 있는 .env)
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY가 .env에서 로드되지 않았습니다. .env 파일을 확인해주세요.")

client = OpenAI(api_key=api_key)

# -----------------------------------
# 카테고리 후보 (상위 → 하위 리스트)
# -----------------------------------
CATEGORY_TREE: dict[str, list[str]] = {
    # 1) 컴퓨터 기반 연구 (시뮬레이션 + 계산 분석)
    "computational_and_in_silico_studies": [
        "protein_ligand_docking",
        "protein_protein_or_protein_dna_docking",
        "molecular_dynamics_simulation",
        "structure_prediction_or_homology_modeling",
        "quantum_chemistry_or_qm_mm_simulation",
        "systems_biology_or_network_modeling",
        "other_computational_modeling_or_simulation",
    ],

    # 2) 분자·생화학 수준 실험 (assay 단어 적극 사용)
    "molecular_and_biochemical_assays": [
        "biochemical_enzyme_activity_or_kinetics_assay",
        "binding_affinity_assay_itc_spr_fret_etc",
        "spectrophotometric_or_fluorescence_based_assay",
        "protein_purification_and_biophysical_characterization",
        "molecular_biology_assay_pcr_cloning_western_blot",
        "protein_stability_or_thermal_shift_assay",
        "adme_in_vitro_biochemical_assay",
        "other_molecular_or_biochemical_assay",
    ],

    # 3) 세포 기반 assay
    "cell_based_assays": [
        "cell_culture_and_viability_or_proliferation_assay",
        "cell_based_functional_or_signaling_reporter_assay",
        "cytotoxicity_or_apoptosis_assay",
        "cell_migration_or_invasion_assay",
        "high_content_cell_imaging_assay",
        "flow_cytometry_or_facs_based_assay",
        "cellular_adme_or_transport_assay",
        "cell_based_toxicology_assay",
        "other_cell_based_assay",
    ],

    # 4) 조직·오가노이드 / ex vivo 모델
    "tissue_and_organoid_models": [
        "tissue_slice_or_ex_vivo_assay",
        "3d_culture_or_spheroid_assay",
        "organoid_model_assay",
        "ex_vivo_functional_assay",
        "other_tissue_or_organoid_model_assay",
    ],

    # 5) in vivo 동물 / 전임상
    "in_vivo_animal_models": [
        "disease_model_in_vivo_efficacy_study",
        "pk_pd_in_vivo_study",
        "in_vivo_toxicology_or_safety_study",
        "biodistribution_or_in_vivo_imaging_study",
        "behavioral_or_functional_in_vivo_assay",
        "other_in_vivo_preclinical_model",
    ],

    # 6) 오믹스 / high-throughput 분석
    "omics_and_high_throughput_analyses": [
        "ngs_or_genome_sequencing_analysis",
        "transcriptomics_or_bulk_rna_seq_analysis",
        "single_cell_omics_analysis",
        "proteomics_or_phosphoproteomics_analysis",
        "metabolomics_or_lipidomics_analysis",
        "chromatin_or_epigenomics_analysis",
        "multi_omics_integration_or_network_analysis",
        "high_throughput_screening_readout_analysis",
        "microscopy_image_analysis_or_hcs_analysis",
        "electrophysiology_or_signal_processing_analysis",
        "other_omics_or_high_throughput_analysis",
    ],

    # 7) ML/딥러닝/알고리즘
    "ml_and_algorithm_development": [
        "ml_or_dl_prediction_model_for_biology",
        "de_novo_molecule_or_protein_design_model",
        "representation_learning_or_pretraining",
        "generative_modeling_or_diffusion_model",
        "reinforcement_learning_or_optimization",
        "benchmark_or_baseline_comparison",
        "ablation_study_or_hyperparameter_optimization",
        "model_interpretability_or_feature_importance_analysis",
        "production_deployment_or_model_serving_pipeline",
    ],

    # 8) 데이터셋 / 리소스 / 스크리닝
    "data_resources_and_screening": [
        "dataset_construction_or_curation",
        "dataset_statistics_or_descriptive_analysis",
        "data_quality_control_or_preprocessing",
        "knowledgebase_or_database_construction",
        "compound_library_design_or_enumeration",
        "virtual_screening_or_in_silico_screening",
        "high_throughput_experimental_screening",
        "target_prioritization_or_hit_identification",
    ],

    # 9) 임상 / 사람 대상 연구
    "clinical_and_human_studies": [
        "clinical_trial_interventional",
        "clinical_observational_or_cohort_study",
        "case_report_or_case_series",
        "registry_or_real_world_data_analysis",
        "pharmacovigilance_or_safety_signal_detection",
        "diagnostic_or_biomarker_validation_study",
        "health_economics_or_outcomes_research",
        "implementation_or_practice_change_study",
    ],

    # 10) 방법론 / 이론 / 리뷰
    "methodological_and_theoretical_work": [
        "new_experimental_method_or_protocol_development",
        "new_computational_method_or_algorithm",
        "statistical_modeling_or_theoretical_analysis",
        "guideline_or_workflow_or_best_practice",
        "meta_analysis_or_systematic_review",
        "position_paper_or_conceptual_framework",
    ],

    # 11) 기타 / 혼합
    "other_or_not_specified": [
        "mixed_or_multimodal_study_not_easily_classified",
        "insufficient_information_to_classify",
        "other",
    ],
}

# -----------------------------------
# leaf 카테고리 → 상위 카테고리 매핑
# -----------------------------------
LEAF_TO_PARENT_CATEGORY: dict[str, str] = {}
for parent, labels in CATEGORY_TREE.items():
    for leaf in labels:
        LEAF_TO_PARENT_CATEGORY[leaf] = parent

# parent → 기본 leaf (LLM이 parent만 줬을 때 쓸 fallback)
PARENT_DEFAULT_LEAF: dict[str, str] = {
    "computational_and_in_silico_studies": "other_computational_modeling_or_simulation",
    "molecular_and_biochemical_assays": "other_molecular_or_biochemical_assay",
    "cell_based_assays": "other_cell_based_assay",
    "tissue_and_organoid_models": "other_tissue_or_organoid_model_assay",
    "in_vivo_animal_models": "other_in_vivo_preclinical_model",
    "omics_and_high_throughput_analyses": "other_omics_or_high_throughput_analysis",
    "ml_and_algorithm_development": "benchmark_or_baseline_comparison",
    "data_resources_and_screening": "dataset_construction_or_curation",
    "clinical_and_human_studies": "clinical_observational_or_cohort_study",
    "methodological_and_theoretical_work": "new_computational_method_or_algorithm",
    "other_or_not_specified": "other",
}

# -----------------------------------
# 카테고리 문자열 생성 (프롬프트용)
# -----------------------------------
def _build_categories_block() -> str:
    """
    CATEGORY_TREE를 사람이 보기 좋은 문자열 블록으로 변환.
    프롬프트 안에 그대로 넣어줄 문자열을 만든다.
    """
    lines: list[str] = []
    for group, labels in CATEGORY_TREE.items():
        lines.append(f"- {group}:")
        for label in labels:
            lines.append(f"  - {label}")
    return "\n".join(lines)


CATEGORIES = _build_categories_block()

# -----------------------------------
# 1) sections.csv 로드 & 실험 섹션 필터링
# -----------------------------------
def load_sections() -> pd.DataFrame:
    if not SECTIONS_PATH.exists():
        raise FileNotFoundError(f"{SECTIONS_PATH} 가 존재하지 않습니다.")
    df = pd.read_csv(SECTIONS_PATH)
    print(f"[INFO] 전체 섹션 수: {len(df)}")
    return df


def filter_experiment_sections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Methods / Experiments / Results / Main 섹션을
    '실험 관련 섹션'으로 간주해서 필터링.
    """
    sec_cat = df["section_category"].fillna("").str.lower()
    sec_title = df["section_title"].fillna("").str.lower()

    target_cats = ["method", "methods", "result", "results", "main"]

    mask = (
        sec_cat.isin(target_cats)
        | sec_title.str.contains("method")
        | sec_title.str.contains("experiment")
        | sec_title.str.contains("result")
    )

    exp_df = df[mask].copy()
    print(f"[INFO] 실험 관련 섹션 수: {len(exp_df)}")
    print(f"[INFO] 실험 관련 섹션이 있는 논문 수: {exp_df['pmid'].nunique()}")
    return exp_df


def build_paper_texts(exp_df: pd.DataFrame) -> pd.DataFrame:
    """
    같은 pmid에 속한 실험 관련 섹션들의 텍스트를
    한 논문당 하나의 긴 문자열로 합친다.
    """
    exp_df = exp_df.sort_values(["pmid", "path", "section_id"])
    exp_df["section_text"] = exp_df["section_text"].fillna("").astype(str)

    grouped = (
        exp_df.groupby("pmid")["section_text"]
        .apply(lambda xs: "\n\n".join([t for t in xs if t.strip() != ""]))
        .reset_index()
        .rename(columns={"section_text": "experiment_text"})
    )

    print(f"[INFO] 실험 텍스트가 만들어진 논문 수: {len(grouped)}")
    return grouped

# -----------------------------------
# 2) LLM 프롬프트 & 호출 함수
# -----------------------------------
def build_prompt_for_table(text: str) -> str:
    return f"""
너는 생명과학/화학/바이오 논문의 실험 설계를 정리하는 전문가야.

아래 텍스트는 한 논문의 Methods/Experiments/Results 부분에서 뽑은 내용이다.
이 텍스트를 보고, 이 논문에서 수행한 "실험들"을
다음 5개 항목으로 나누어 여러 행(row)으로 정리해줘.

중요 규칙:
- 출력은 반드시 순수한 JSON 배열만 포함해야 한다.
- JSON 배열 앞뒤에 어떤 설명 문장도 붙이지 마.
- ``` 또는 ```json 같은 마크다운 코드 블록을 절대 사용하지 마.
- method, condition, category, materials, equipment 값은 모두 영어로 작성해. 한국어를 절대 사용하지 마.
- 입력 텍스트가 한국어이든 영어이든, 출력은 항상 영어로만 작성해.
- 가능한 한 실험 설정을 최대한 많이 추출하되, 서로 완전히 동일한 설정은 하나로 합쳐라.
- 실험이 명시적으로 잘 안 보이더라도, 문맥을 바탕으로 합리적으로 추론해서 작성해라.
- 정말로 실험/방법에 대한 내용이 전혀 없을 때만 빈 배열 [] 을 반환해라. 애매하면 최소 1개 이상의 실험을 만들어라.

각 행은 하나의 실험 설정을 의미하며 다음 정보를 포함해야 한다:

- method: 어떤 실험 방법/기법/모델을 사용했는지
          (예: "molecular docking", "GNN-based prediction model", "cell viability assay")
- condition: 그 방법을 어떤 조건/설정/데이터 범위에서 사용했는지
             (예: "300 K, 100 ns simulation repeated 3 times",
                  "PDBbind v2019 dataset, train/valid/test = 8:1:1")
- category: 아래 "가능한 category 라벨" 중에서
           **항상 하위 카테고리(leaf) 라벨 하나만** 선택해야 한다.

  중요:
  - 상위 카테고리(group) 이름(예: "in_vivo_animal_models", "cell_based_assays")은 절대 사용하지 마라.
  - 반드시 들여쓰기된 하위 라벨(예: "disease_model_in_vivo_efficacy_study") 중 하나만 선택해라.

가능한 category 라벨 (트리 구조, 예시는 다음과 같음)
- 맨 앞이 '-' 로 시작하는 줄은 상위 카테고리 이름이고,
- 그 아래 '  -' 로 시작하는 줄이 실제로 선택해야 하는 하위 카테고리 이름이다.

{CATEGORIES}

- materials: 주요 재료/시료/시약/데이터셋 등을 영어로 요약
             (예: "HEK293T cells, doxorubicin, PDBbind v2019 dataset")
- equipment: 실험에 핵심적으로 사용된 장비/플랫폼/하드웨어
             (예: "confocal microscope", "HPLC system", "GPU server with 4×A100")

반드시 JSON 배열(JSON array) 형태로만 답해줘.
JSON 배열 외에 어떤 텍스트도 출력하지 마.
각 원소는 다음과 같은 형태의 JSON 객체여야 한다 (예시는 영어로):

[
  {{
    "method": "molecular docking",
    "condition": "Docking performed on 500 protein–ligand complexes from the PDBbind v2019 dataset",
    "category": "protein_ligand_docking",
    "materials": "PDBbind v2019 dataset, protein–ligand complexes",
    "equipment": "docking software, GPU server"
  }},
  {{
    "method": "cell viability assay",
    "condition": "HEK293T cells treated with a concentration gradient of candidate compounds and incubated for 48 h",
    "category": "cell_culture_and_viability_or_proliferation_assay",
    "materials": "HEK293T cells, candidate small-molecule compounds",
    "equipment": "cell culture incubator, plate reader"
  }}
]

아무 실험도 파악하기 어려우면 빈 배열 [] 을 반환해.

--- 텍스트 시작 ---
{text}
--- 텍스트 끝 ---
""".strip()


def _extract_json_array(content: str) -> str:
    """
    LLM이 ```json ... ``` 처럼 코드블록으로 감싸거나,
    앞뒤에 설명 텍스트를 붙여도, JSON 배열 부분만 뽑아서 반환.
    """
    if not isinstance(content, str):
        content = str(content)

    # 1) 코드블록 마크다운 제거
    content = re.sub(r"```json", "", content, flags=re.IGNORECASE)
    content = re.sub(r"```", "", content)
    content = content.strip()

    # 2) 문자열 안에서 첫 '[' 와 마지막 ']' 사이만 취함
    start = content.find("[")
    end = content.rfind("]")

    if start != -1 and end != -1 and start < end:
        content = content[start : end + 1]

    return content.strip()


def call_llm_for_table(text: str) -> list[dict]:
    """
    experiment_text를 LLM에 보내서
    [{method, condition, category_parent, category_leaf, materials, equipment}, ...] 리스트를 받는다.
    """
    if text and len(text) > 8000:
        text = text[:8000]

    prompt = build_prompt_for_table(text)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_content = resp.choices[0].message.content
    if not isinstance(raw_content, str):
        raw_content = str(raw_content)

    if DEBUG:
        print("=== RAW LLM OUTPUT (snippet) ===")
        print(raw_content[:500])
        print("================================")

    # 코드블록/불필요한 텍스트 제거 후 JSON 배열 문자열만 추출
    cleaned_str = _extract_json_array(raw_content)

    try:
        data = json.loads(cleaned_str)
    except Exception as e:
        print("[WARN] JSON 파싱 실패, 원본문자열 일부:", raw_content[:200])
        print("[WARN] 정제된 문자열 일부:", cleaned_str[:200])
        raise e

    if not isinstance(data, list):
        print("[WARN] JSON 최상위가 list가 아님, 강제로 리스트로 감쌈")
        data = [data]

    cleaned: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        method = (item.get("method") or "").strip()
        condition = (item.get("condition") or "").strip()

        leaf_category = (item.get("category") or "").strip()

        # --- parent/leaf 안전 처리 로직 ---
        # 1) 아무것도 없으면 other 계열로
        if not leaf_category:
            parent_category = "other_or_not_specified"
            leaf_category = "other"

        # 2) 정상적인 leaf 라벨인 경우
        elif leaf_category in LEAF_TO_PARENT_CATEGORY:
            parent_category = LEAF_TO_PARENT_CATEGORY[leaf_category]

        # 3) leaf에는 없지만, parent 이름인 경우 (지금 문제 케이스)
        elif leaf_category in CATEGORY_TREE:
            parent_category = leaf_category
            leaf_category = PARENT_DEFAULT_LEAF.get(parent_category, "other")

        # 4) 완전 모르는 값이면 other로
        else:
            parent_category = "other_or_not_specified"
            leaf_category = "other"
        # ----------------------------------

        materials = (item.get("materials") or "").strip()
        equipment = (item.get("equipment") or "").strip()

        # method/condition 둘 다 비어 있으면 버림
        if not method and not condition:
            continue

        cleaned.append(
            {
                "method": method,
                "condition": condition,
                "category_parent": parent_category,
                "category_leaf": leaf_category,
                "materials": materials,
                "equipment": equipment,
            }
        )

    return cleaned


# -----------------------------------
# 3) 메인: 논문별로 호출해서 최종 테이블 생성
# -----------------------------------
def main() -> None:
    sections_df = load_sections()
    exp_sections_df = filter_experiment_sections(sections_df)
    paper_texts_df = build_paper_texts(exp_sections_df)

    rows: list[dict] = []

    for _, row in paper_texts_df.iterrows():
        pmid = row["pmid"]
        text = row["experiment_text"]

        if not isinstance(text, str) or not text.strip():
            print(f"[WARN] pmid {pmid}: experiment_text 비어 있음, 건너뜀")
            continue

        print(f"[INFO] pmid {pmid} -> LLM 호출 중...")

        try:
            exp_list = call_llm_for_table(text)
        except Exception as e:
            print(f"[ERROR] pmid {pmid}: LLM 호출/파싱 실패: {e}")
            continue

        if not exp_list:
            print(f"[INFO] pmid {pmid}: 추출된 실험 없음")
            continue

        for exp in exp_list:
            rows.append(
                {
                    "pmid": pmid,
                    "method": exp["method"],
                    "condition": exp["condition"],
                    "category_parent": exp["category_parent"],
                    "category_leaf": exp["category_leaf"],
                    "materials": exp["materials"],
                    "equipment": exp["equipment"],
                }
            )

        # API 과금/속도 조절용 텀
        time.sleep(0.3)

    if not rows:
        print("[WARN] 추출된 실험 정보가 없습니다.")
        return

    out_df = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"[INFO] 최종 실험 테이블 저장 완료: {OUTPUT_PATH}")
    print(out_df.head())


if __name__ == "__main__":
    main()
