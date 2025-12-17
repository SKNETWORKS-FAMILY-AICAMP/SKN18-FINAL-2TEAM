# common_experiment_categories.py
"""
공통 실험 카테고리 정의 모듈

- CATEGORY_TREE: parent → leaf 리스트
- LEAF_TO_PARENT: leaf → parent 매핑
- VALID_PARENTS, VALID_LEAVES: 유효 카테고리 집합
- PARENT_DEFAULT_LEAF: parent별 fallback leaf (대개 "other_*")
- CATEGORIES_BLOCK: 프롬프트에 넣을 트리 문자열
- normalize_category, is_valid_category: LLM 출력 보정/검증용
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ─────────────────────────────────────
# 1) CATEGORY_TREE (최종 버전)
# ─────────────────────────────────────

CATEGORY_TREE: Dict[str, List[str]] = {
    # A) 분자생물학
    "molecular_biology_methods": [
        "pcr",
        "qpcr_or_rtqpcr",
        "rt_pcr",
        "cloning_or_assembly",
        "site_directed_mutagenesis",
        "plasmid_preparation",
        "nucleic_acid_extraction",
        "gel_electrophoresis_dna_or_rna",
        "western_blot",
        "northern_or_southern_blot",
        "crispr_genome_editing",
        "other_molecular_biology",
    ],

    # B) 단백질 발현 / 정제 / 생화학 분석
    "protein_expression_and_biochemical_assays": [
        "protein_expression_bacterial",
        "protein_expression_mammalian_or_insect",
        "protein_purification_affinity",
        "protein_purification_chromatography_other",
        "dialysis_or_buffer_exchange",
        "sds_page",
        "native_page",
        "bca_or_bradford_assay",
        "elisa",
        "enzyme_activity_assay",
        "enzyme_kinetics_assay",
        "binding_assay_itc",
        "binding_assay_spr_or_bli",
        "dose_response_biochemical_assay",
        "other_biochemical_assay",
    ],

    # C) 단백질 안정성 / 생물물리
    "protein_stability_and_biophysical_methods": [
        "thermal_shift_assay_dsf",
        "thermal_stability_melting_curve_other",
        "circular_dichroism_cd",
        "differential_scanning_calorimetry_dsc",
        "sec_mals",
        "dynamic_light_scattering_dls",
        "spectroscopy_uv_vis_or_fluorescence",
        "mass_spectrometry_lcms",
        "other_biophysical_method",
    ],

    # D) 세포 기반 assay
    "cell_based_assays": [
        "cell_culture",
        "transfection_or_transduction",
        "cell_viability_mtt_or_mts",
        "cell_viability_wst_or_cck8",
        "cell_toxicity_ldh",
        "apoptosis_or_caspase_assay",
        "dose_response_viability_assay",
        "dose_response_cytotoxicity_assay",
        "drug_response_assay",
        "proliferation_assay_brdu_or_edu",
        "reporter_gene_assay",
        "flow_cytometry",
        "immunofluorescence_staining",
        "migration_assay_wound_healing",
        "invasion_assay_transwell",
        "high_content_imaging",
        "other_cell_based_assay",
    ],

    # E) 조직 / ex vivo / organoid / 혈액 기반
    "tissue_and_ex_vivo_assays": [
        "pbmc_isolation",
        "density_gradient_cell_isolation",
        "whole_blood_processing",
        "immune_cell_isolation",
        "tissue_slice_or_explant_assay",
        "organoid_or_spheroid_assay",
        "ihc_or_histology",
        "ex_vivo_functional_assay",
        "other_ex_vivo_assay",
    ],

    # F) in vivo (마우스 등) 모델
    "in_vivo_models": [
        "mouse_disease_model_efficacy",
        "xenograft_or_syngeneic_tumor_model",
        "in_vivo_dose_response_assay",
        "pharmacokinetics_pk",
        "pharmacodynamics_pd",
        "toxicity_study_in_vivo",
        "biodistribution_or_in_vivo_imaging",
        "behavioral_assay",
        "other_in_vivo_study",
    ],

    # G) 계산 / in silico
    "computational_methods": [
        "molecular_docking",
        "molecular_dynamics_simulation",
        "free_energy_or_binding_energy_calculation",
        "homology_modeling_or_structure_prediction",
        "virtual_screening",
        "qm_or_qmmm_simulation",
        "ml_prediction_model_for_biology",
        "generative_model_protein_or_ligand",
        "other_computational_method",
    ],

    # H) 완전 기타/불명시 fallback 용
    "other_or_not_specified": [
        "other",
    ],
}

# ─────────────────────────────────────
# 2) 매핑/헬퍼
# ─────────────────────────────────────

LEAF_TO_PARENT: Dict[str, str] = {}
for parent, leaves in CATEGORY_TREE.items():
    for leaf in leaves:
        LEAF_TO_PARENT[leaf] = parent

VALID_PARENTS = set(CATEGORY_TREE.keys())
VALID_LEAVES = set(LEAF_TO_PARENT.keys())

PARENT_DEFAULT_LEAF: Dict[str, str] = {}
for parent, leaves in CATEGORY_TREE.items():
    # parent 아래 "other" 포함 leaf가 있으면 그것을 기본값으로
    other_like = [l for l in leaves if "other" in l]
    if other_like:
        PARENT_DEFAULT_LEAF[parent] = other_like[0]
    else:
        PARENT_DEFAULT_LEAF[parent] = leaves[-1]


def _build_categories_block() -> str:
    """
    CATEGORY_TREE를 프롬프트에 넣기 좋은 트리 문자열로 변환.
    """
    lines: list[str] = []
    for group, labels in CATEGORY_TREE.items():
        lines.append(f"- {group}:")
        for label in labels:
            lines.append(f"  - {label}")
    return "\n".join(lines)


CATEGORIES_BLOCK: str = _build_categories_block()


# ─────────────────────────────────────
# 3) 카테고리 보정 / 검증 함수
# ─────────────────────────────────────

def normalize_category(cat_parent: str, cat_leaf: str) -> Tuple[str, str]:
    """
    LLM이 준 (cat_parent, cat_leaf)를 CATEGORY_TREE 기준으로 보정.

    규칙:
    1) leaf가 유효하면 leaf 기준으로 parent 강제 매핑
    2) leaf는 이상하지만 parent는 유효하면:
       - parent 아래 'other' 계열 leaf 우선 선택
       - 없으면 마지막 leaf 선택
    3) 둘 다 엉망이면 (other_or_not_specified, other)로 통일
    """
    cat_parent = (cat_parent or "").strip()
    cat_leaf = (cat_leaf or "").strip()

    # 1) leaf 기준
    if cat_leaf in LEAF_TO_PARENT:
        fixed_parent = LEAF_TO_PARENT[cat_leaf]
        fixed_leaf = cat_leaf
        return fixed_parent, fixed_leaf

    # 2) parent만 유효한 경우
    if cat_parent in CATEGORY_TREE:
        leaves = CATEGORY_TREE[cat_parent]
        if cat_leaf in leaves:
            return cat_parent, cat_leaf

        other_like = [l for l in leaves if "other" in l]
        if other_like:
            return cat_parent, other_like[0]
        return cat_parent, leaves[-1]

    # 3) 완전 엉뚱 → 기타
    return "other_or_not_specified", "other"


def is_valid_category(cat_parent: str, cat_leaf: str) -> bool:
    """
    (cat_parent, cat_leaf)가 CATEGORY_TREE 상에서 유효한 조합인지 확인.
    """
    cat_parent = (cat_parent or "").strip()
    cat_leaf = (cat_leaf or "").strip()

    # 둘 다 비어 있으면 무효
    if not cat_parent and not cat_leaf:
        return False

    # leaf가 유효하면 OK
    if cat_leaf in LEAF_TO_PARENT:
        return True

    # parent만 보고 판단
    if cat_parent in CATEGORY_TREE:
        leaves = CATEGORY_TREE[cat_parent]
        if cat_leaf in leaves:
            return True

    return False
