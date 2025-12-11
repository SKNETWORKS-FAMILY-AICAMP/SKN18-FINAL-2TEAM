# neo4j/pmc_kg_etl/protocol_category_etl.py

import os
import time
import json
from pathlib import Path

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

"""
입력(기본):  neo4j/import/t_protocol_metadata_Cell.csv
      (컬럼: protocol_sid, url, title)

출력(라벨링): neo4j/import/t_protocol_metadata_Cell_labeled.csv
      (컬럼: protocol_sid, url, title, category_parent, category_leaf)

특징:
- 이미 t_protocol_metadata_Cell_labeled.csv 가 존재하면,
  거기 있는 category_parent / category_leaf 를 재사용하고,
  "아직 안 채워진 행"만 LLM으로 분류해서 이어서 수행.
- 중간에 Ctrl+C 등으로 중단되어도, 지금까지 진행된 내용은 CSV에 저장됨.
"""

# ─────────────────────────────────────────────
# 0) 프로젝트 루트(.env) 로드
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]  # SKN18-FINAL-2TEAM
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY 가 .env에서 로드되지 않았어요 😭")

client = OpenAI(api_key=api_key)  # 이 인스턴스 하나만 사용


# ─────────────────────────────────────────────
# 1) 카테고리 트리 정의 (상위 → 하위 리스트)
# ─────────────────────────────────────────────
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

    # 2) 분자·생화학 수준 실험
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

# leaf → parent 매핑, 유효 parent/leaf 집합
LEAF_TO_PARENT: dict[str, str] = {}
for _parent, _leaves in CATEGORY_TREE.items():
    for _leaf in _leaves:
        LEAF_TO_PARENT[_leaf] = _parent

VALID_PARENTS = set(CATEGORY_TREE.keys())
VALID_LEAVES = set(LEAF_TO_PARENT.keys())


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


CATEGORIES_BLOCK = _build_categories_block()

# ─────────────────────────────────────────────
# 2) LLM 시스템 프롬프트
# ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""
You are an expert in wet-lab, biological and computational experiments.

Your task:
Given a protocol title (and optionally URL), classify it into exactly TWO levels
based on the FIXED taxonomy below.

1) category_parent:
   - MUST be exactly one of the following parent labels (string):
     {", ".join(sorted(VALID_PARENTS))}

2) category_leaf:
   - MUST be exactly one of the leaf labels listed under its parent.
   - You are NOT allowed to invent new labels.
   - If the protocol does not clearly fit any specific leaf,
     choose a reasonable "other_..." style leaf under the chosen parent,
     or fall back to:
       parent  = "other_or_not_specified"
       leaf    = "other"

Taxonomy (parent → leaf list):

{CATEGORIES_BLOCK}

Return STRICTLY a JSON object with two keys, for example:
{{
  "category_parent": "cell_based_assays",
  "category_leaf": "cell_culture_and_viability_or_proliferation_assay"
}}

Rules:
- Use concise English for both category_parent and category_leaf.
- Do NOT output explanations or any extra text.
- Do NOT output markdown code fences.
- Output must be valid JSON only.
""".strip()


# ─────────────────────────────────────────────
# 3) 카테고리 보정 함수
# ─────────────────────────────────────────────
def normalize_category(cat_parent: str, cat_leaf: str) -> tuple[str, str]:
    """
    LLM이 준 (cat_parent, cat_leaf)를 우리가 정의한 CATEGORY_TREE에 맞게 보정.
    - leaf가 유효하면 leaf 기준으로 parent를 강제 매핑
    - parent만 유효하면 parent 아래의 'other' 계열 leaf로 보정
    - 둘 다 엉망이면 (other_or_not_specified, other)로 통일
    """
    cat_parent = (cat_parent or "").strip()
    cat_leaf = (cat_leaf or "").strip()

    # 1) leaf가 유효하면 leaf 기준으로 parent 확정
    if cat_leaf in LEAF_TO_PARENT:
        fixed_parent = LEAF_TO_PARENT[cat_leaf]
        fixed_leaf = cat_leaf
        return fixed_parent, fixed_leaf

    # 2) leaf는 이상하지만 parent는 유효한 경우
    if cat_parent in CATEGORY_TREE:
        leaves = CATEGORY_TREE[cat_parent]
        if cat_leaf in leaves:
            return cat_parent, cat_leaf

        # parent 아래 'other' 계열 우선 선택
        other_like = [l for l in leaves if "other" in l]
        if other_like:
            return cat_parent, other_like[0]
        return cat_parent, leaves[-1]

    # 3) 둘 다 엉망일 때 → 기타로 몰아 넣기
    return "other_or_not_specified", "other"


def is_valid_category(cat_parent: str, cat_leaf: str) -> bool:
    """
    이미 저장된 (category_parent, category_leaf)가
    우리가 정의한 CATEGORY_TREE 상에서 유효한 조합인지 확인.
    """
    cat_parent = (cat_parent or "").strip()
    cat_leaf = (cat_leaf or "").strip()

    # 둘 다 비어 있으면 유효하지 않음 → 새로 분류해야 함
    if not cat_parent and not cat_leaf:
        return False

    # leaf가 유효하면 자동으로 parent가 결정되므로 OK
    if cat_leaf in LEAF_TO_PARENT:
        return True

    # parent만 보고 판단
    if cat_parent in CATEGORY_TREE:
        leaves = CATEGORY_TREE[cat_parent]
        if cat_leaf in leaves:
            return True

    return False


# ─────────────────────────────────────────────
# 4) LLM 호출 함수
# ─────────────────────────────────────────────
def classify_protocol(title: str, url: str | None = None) -> tuple[str, str]:
    """
    OpenAI LLM을 호출해서 (category_parent, category_leaf)를 리턴.
    타이틀이 비어 있거나 '<no data>' 인 경우 ("", "") 리턴.
    """
    if not isinstance(title, str) or title.strip() == "" or title.strip() == "<no data>":
        return "", ""

    user_content = f"Protocol title: {title}"
    if isinstance(url, str) and url.strip():
        user_content += f"\nURL: {url}"

    resp = client.chat.completions.create(
        # 실제 사용 가능한 모델로 바꿔서 쓰면 됨 (예: "gpt-4o-mini")
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
        raw_parent = (data.get("category_parent") or "").strip()
        raw_leaf = (data.get("category_leaf") or "").strip()
    except json.JSONDecodeError:
        raw_parent = "other_or_not_specified"
        raw_leaf = "other"

    fixed_parent, fixed_leaf = normalize_category(raw_parent, raw_leaf)
    return fixed_parent, fixed_leaf


# ─────────────────────────────────────────────
# 5) 메인: 재시작 가능한 ETL
# ─────────────────────────────────────────────
def main():
    neo4j_dir = BASE_DIR / "neo4j"
    import_dir = neo4j_dir / "import"

    input_path = import_dir / "t_protocol_metadata_Cell.csv"
    output_path = import_dir / "t_protocol_metadata_Cell_labeled.csv"

    print(f"입력 파일 경로:   {input_path}")
    print(f"출력 파일 경로:   {output_path}")
    print(f"현재 작업 디렉토리: {Path.cwd()}")

    # 1) 기본 입력 CSV 읽기
    base_df = pd.read_csv(input_path)

    # 2) 이미 라벨링된 파일이 있으면 거기서 이어서 하기
    if output_path.exists():
        print("💾 기존 라벨링 파일 발견! (resume 모드)")
        labeled_df = pd.read_csv(output_path)

        # protocol_sid 기준으로 merge (혹시 열 순서/구성이 바뀌었을 가능성 대비)
        if "protocol_sid" in labeled_df.columns and "protocol_sid" in base_df.columns:
            df = base_df.merge(
                labeled_df[["protocol_sid", "category_parent", "category_leaf"]],
                on="protocol_sid",
                how="left",
                suffixes=("", "_old"),
            )
        else:
            # protocol_sid가 없다면 index 기준으로 맞춘다 (덜 안전하지만 fallback)
            print("⚠️ protocol_sid 컬럼이 없어 index 기준으로 병합합니다.")
            df = base_df.copy()
            if "category_parent" in labeled_df.columns:
                df["category_parent"] = labeled_df["category_parent"]
            if "category_leaf" in labeled_df.columns:
                df["category_leaf"] = labeled_df["category_leaf"]
    else:
        print("🆕 라벨링 파일이 없어 새로 시작합니다.")
        df = base_df.copy()
        if "category_parent" not in df.columns:
            df["category_parent"] = ""
        if "category_leaf" not in df.columns:
            df["category_leaf"] = ""

    total_rows = len(df)
    print(f"총 행 개수: {total_rows}")

    try:
        for idx, row in df.iterrows():
            title = row.get("title", "")
            url = row.get("url", "")
            cur_parent = row.get("category_parent", "")
            cur_leaf = row.get("category_leaf", "")

            # 이미 유효한 카테고리면 건너뜀 (resume 포인트)
            if is_valid_category(cur_parent, cur_leaf):
                print(f"[{idx+1}/{total_rows}] 이미 분류됨, 스킵 - title: {str(title)[:60]}...")
                continue

            print(f"[{idx+1}/{total_rows}] 분류 중 - title: {str(title)[:60]}...")

            if isinstance(title, str) and title.strip() not in ("", "<no data>"):
                parent, leaf = classify_protocol(title, url)
                time.sleep(0.02)  # rate limit/과금 고려해서 조정 가능
            else:
                parent, leaf = "", ""

            df.at[idx, "category_parent"] = parent
            df.at[idx, "category_leaf"] = leaf

            # 안전을 위해 N행마다 중간 저장 (예: 20행마다)
            if (idx + 1) % 20 == 0:
                df.to_csv(output_path, index=False)
                print(f"💾 중간 저장 완료 (행 {idx+1}까지 처리)")

    except KeyboardInterrupt:
        print("\n⛔️ 사용자가 중단 (Ctrl+C 감지). 지금까지 진행된 내용 저장합니다...")
    finally:
        # 항상 마지막에 현재까지 결과를 저장
        df.to_csv(output_path, index=False)
        print(f"\n✅ 최종(또는 중간) 저장 완료: {output_path}")


if __name__ == "__main__":
    main()
