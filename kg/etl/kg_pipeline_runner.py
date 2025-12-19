"""
kg/etl/kg_pipeline_runner.py

Bio/Med R&D Agentic Platform - Knowledge Graph ETL 오케스트레이터

단계:
  1) from_rag_docs
     - rag/etl/02_normalize 결과(정규화 문서) 기반으로
       Publication / Trial / Protocol / Experiment 같은 "베이스 노드" 생성

  2) from_rag_entities
     - rag/etl/03_extract 결과(엔터티/관계 JSON) 기반으로
       Protein / Disease / Drug / Trial 관계 upsert

  3) from_sim_results
     - sim_tools(AlphaFold3 / RFdiffusion / ProteinMPNN) 결과를
       (SimulationResult) 노드 및 (Protein)-[HAS_SIM_RESULT]->(Experiment) 관계로 연결

  4) maintenance
     - constraints 적용, 그래프 메트릭(centrality 등) 계산/갱신

사용 예:
  python -m kg.etl.kg_pipeline_runner --source pubmed
  python -m kg.etl.kg_pipeline_runner --source all --skip-sim
  python -m kg.etl.kg_pipeline_runner --run maintenance
"""

import argparse
import logging
import os
from dataclasses import dataclass
from importlib import import_module
from typing import Literal


SourceType = Literal["pubmed", "nih", "protocols", "all"]
RunStageType = Literal["all", "docs", "entities", "sim", "maintenance"]


@dataclass
class KGPipelineConfig:
    """
    KG ETL에서 참조하는 디렉터리 설정.

    - rag_processed_dir : rag/etl/02_normalize 결과 (정규화 문서)
    - rag_entities_dir  : rag/etl/03_extract 결과 (엔터티/관계)
    - sim_results_dir   : sim_tools 결과 파일 위치
    """

    rag_processed_dir: str = os.getenv("RAG_PROCESSED_DIR", "data/processed")
    rag_entities_dir: str = os.getenv("RAG_ENTITIES_DIR", "data/entities")
    sim_results_dir: str = os.getenv("SIM_RESULTS_DIR", "data/sim_results")


def setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
    )


# ─────────────────────────────────────────────
# 1) RAG 정규화 문서 → 베이스 노드 (Paper/Trial/Protocol/Experiment)
# ─────────────────────────────────────────────


def run_from_rag_docs(cfg: KGPipelineConfig, source: SourceType) -> None:
    """
    01_from_rag_docs 단계 실행.

    기대하는 모듈 & run 시그니처:

      kg.etl.01_from_rag_docs.01_load_normalized_docs.run(
          processed_dir: str,
          source: str | None,
      ) -> list[dict]

      kg.etl.01_from_rag_docs.02_build_base_nodes.run(
          docs: list[dict],
      ) -> None

    실제 구현에서는 docs 구조를 자유롭게 정의하면 됨.
    """
    logger = logging.getLogger("kg.from_rag_docs")

    logger.info("▶ [KG] from_rag_docs start (source=%s)", source)

    src_filter: str | None = None if source == "all" else source

    load_mod = import_module("kg.etl.01_from_rag_docs.01_load_normalized_docs")
    build_mod = import_module("kg.etl.01_from_rag_docs.02_build_base_nodes")

    docs = load_mod.run(
        processed_dir=cfg.rag_processed_dir,
        source=src_filter,
    )
    logger.info("  - loaded %s docs from normalized data", len(docs) if docs is not None else "N")

    build_mod.run(docs=docs)

    logger.info("✔ [KG] from_rag_docs done")


# ─────────────────────────────────────────────
# 2) RAG 엔터티/관계 → Protein/Disease/Trial 그래프 upsert
# ─────────────────────────────────────────────


def run_from_rag_entities(cfg: KGPipelineConfig, source: SourceType) -> None:
    """
    02_from_rag_entities 단계 실행.

    기대하는 모듈 & run 시그니처:

      kg.etl.02_from_rag_entities.01_load_entities.run(
          entities_dir: str,
          source: str | None,
      ) -> dict | list[dict]

      kg.etl.02_from_rag_entities.02_upsert_entities_relations.run(
          entities: dict | list[dict],
      ) -> None
    """
    logger = logging.getLogger("kg.from_rag_entities")

    logger.info("▶ [KG] from_rag_entities start (source=%s)", source)

    src_filter: str | None = None if source == "all" else source

    load_mod = import_module("kg.etl.02_from_rag_entities.01_load_entities")
    upsert_mod = import_module("kg.etl.02_from_rag_entities.02_upsert_entities_relations")

    entities = load_mod.run(
        entities_dir=cfg.rag_entities_dir,
        source=src_filter,
    )
    logger.info("  - loaded entities (type=%s)", type(entities).__name__)

    upsert_mod.run(entities=entities)

    logger.info("✔ [KG] from_rag_entities done")


# ─────────────────────────────────────────────
# 3) Simulation 결과 → KG 반영
# ─────────────────────────────────────────────


def run_from_sim_results(cfg: KGPipelineConfig) -> None:
    """
    03_from_sim_results 단계 실행.

    기대하는 모듈 & run 시그니처:

      kg.etl.03_from_sim_results.01_load_sim_results.run(
          sim_results_dir: str,
      ) -> list[dict]

      kg.etl.03_from_sim_results.02_link_protein_experiment.run(
          sim_results: list[dict],
      ) -> None
    """
    logger = logging.getLogger("kg.from_sim_results")

    logger.info("▶ [KG] from_sim_results start")

    load_mod = import_module("kg.etl.03_from_sim_results.01_load_sim_results")
    link_mod = import_module("kg.etl.03_from_sim_results.02_link_protein_experiment")

    sim_results = load_mod.run(sim_results_dir=cfg.sim_results_dir)
    logger.info("  - loaded %s sim_results", len(sim_results) if sim_results is not None else "N")

    link_mod.run(sim_results=sim_results)

    logger.info("✔ [KG] from_sim_results done")


# ─────────────────────────────────────────────
# 4) Maintenance (constraints + graph metrics)
# ─────────────────────────────────────────────


def run_maintenance(run_metrics: bool = True) -> None:
    """
    04_maintenance 단계 실행.

    기대하는 모듈 & run 시그니처:

      kg.etl.04_maintenance.01_apply_constraints.run() -> None

      kg.etl.04_maintenance.02_recompute_graph_metrics.run() -> None
    """
    logger = logging.getLogger("kg.maintenance")

    logger.info("▶ [KG] maintenance start")

    # constraints (반드시 실행 권장)
    try:
        constraints_mod = import_module("kg.etl.04_maintenance.01_apply_constraints")
        constraints_mod.run()
        logger.info("  - constraints applied")
    except ModuleNotFoundError:
        logger.info("⏭  01_apply_constraints 모듈 없음 → 스킵")

    # 그래프 메트릭 (선택)
    if run_metrics:
        try:
            metrics_mod = import_module("kg.etl.04_maintenance.02_recompute_graph_metrics")
            metrics_mod.run()
            logger.info("  - graph metrics recomputed")
        except ModuleNotFoundError:
            logger.info("⏭  02_recompute_graph_metrics 모듈 없음 → 스킵")

    logger.info("✔ [KG] maintenance done")


# ─────────────────────────────────────────────
# CLI & main
# ─────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KG ETL Pipeline Runner (RAG → KG, Sim → KG)"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["pubmed", "nih", "protocols", "all"],
        default="all",
        help="RAG 기반 문서/엔터티의 소스 필터 (기본: all)",
    )
    parser.add_argument(
        "--run",
        type=str,
        choices=["all", "docs", "entities", "sim", "maintenance"],
        default="all",
        help="어떤 스테이지를 실행할지 선택 (기본: all)",
    )
    parser.add_argument(
        "--no-metrics",
        action="store_true",
        help="maintenance 실행 시 graph metrics 계산은 건너뛴다.",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    logger = logging.getLogger("kg.pipeline")

    args = parse_args()
    cfg = KGPipelineConfig()

    logger.info("=== KG ETL PIPELINE START ===")
    logger.info("Config: %s", cfg)
    logger.info("Source: %s, Run stage=%s", args.source, args.run)

    # stage 선택 실행
    if args.run in ("all", "docs"):
        run_from_rag_docs(cfg=cfg, source=args.source)

    if args.run in ("all", "entities"):
        run_from_rag_entities(cfg=cfg, source=args.source)

    if args.run in ("all", "sim"):
        run_from_sim_results(cfg=cfg)

    if args.run in ("all", "maintenance"):
        run_maintenance(run_metrics=(not args.no_metrics))

    logger.info("=== KG ETL PIPELINE DONE ===")


if __name__ == "__main__":
    main()
