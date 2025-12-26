"""
KG 매핑/관계 구축 파이프라인 진입점.

`mapping_fot_kg` 디렉터리의 스크립트들을 순차적으로 실행한다.

현재 순서:
  1) entity_drop
  2) build_section_mentions_with_entity_id
  3) build_global_masters_meta_only
"""

from __future__ import annotations

import logging
import subprocess
import sys


def _run_module(module: str) -> None:
    """주어진 모듈을 별도 파이썬 프로세스로 실행한다."""
    cmd = [sys.executable, "-m", module]
    log = logging.getLogger("etl.extract.relations")
    log.info("▶ run module: %s", module)
    subprocess.run(cmd, check=True)


def run(entities_dir: str, source: str | None = None) -> None:
    """
    관계(mention/entity 매핑 및 글로벌 마스터) 구축 파이프라인 실행.

    entities_dir 인자는 현재는 로그용으로만 사용하며,
    실제 입출력 경로는 각 하위 스크립트 내부의 설정을 따른다.
    """
    log = logging.getLogger("etl.extract.relations")
    log.info("[EXTRACT:Relations] start: entities_dir=%s, source=%s", entities_dir, source)

    base_mod = "rag.etl.step03_extract.mapping_fot_kg"

    # 1) 섹션 키워드 + 엔티티 마스터 → section_entity_mentions 생성
    _run_module(f"{base_mod}.build_section_mentions_with_entity_id")

    # 2) 논문/임상 엔티티 + mention 통합 global master 생성
    _run_module(f"{base_mod}.build_global_masters_meta_only")

    # 3) 엔티티 마스터 중복 제거
    _run_module(f"{base_mod}.entity_drop")

    log.info("[EXTRACT:Relations] done")
