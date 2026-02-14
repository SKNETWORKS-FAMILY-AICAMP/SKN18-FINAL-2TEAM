import logging
import sys
from pathlib import Path
from typing import Optional

# 직접 실행 시 프로젝트 루트를 path에 추가 (rag 모듈 인식)
_SCRIPT_DIR = Path(__file__).resolve().parent


def _find_project_root() -> Path:
    """data/raw/pubmed 이 존재하는 디렉터리를 프로젝트 루트로 사용 (python -m 등 경로 이슈 방지)."""
    def has_pubmed_data(d: Path) -> bool:
        return (d / "data" / "raw" / "pubmed").exists()

    # 1) __file__ 기준으로 상위 디렉터리에서 data/raw/pubmed 찾기
    candidate = _SCRIPT_DIR
    for _ in range(10):
        if has_pubmed_data(candidate):
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    # 2) 실행 시 cwd(또는 cwd 상위)에서 찾기 — 프로젝트 루트에서 python -m 실행 시 대부분 여기서 찾음
    cwd = Path.cwd()
    for _ in range(10):
        if has_pubmed_data(cwd):
            return cwd
        parent = cwd.parent
        if parent == cwd:
            break
        cwd = parent

    # 3) fallback: step02_normalize -> etl -> rag -> 루트
    return _SCRIPT_DIR.parents[3]


_PROJECT_ROOT = _find_project_root()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rag.etl.step02_normalize.pmc_nomalize_common.pmc_json_to_csv_main import (
    json_to_csv,
)
from rag.etl.step02_normalize.pmc_nomalize_common.preprocess_split_v2 import (
    split_sections,
)

logger = logging.getLogger(__name__)


def _pick_latest_json(raw_pubmed_dir: Path) -> Optional[Path]:
    """raw/pubmed 디렉터리에서 가장 최근 JSON 파일 하나 선택."""
    if not raw_pubmed_dir.exists():
        logger.warning("[NORMALIZE:PubMed] raw pubmed dir not found: %s", raw_pubmed_dir)
        return None

    json_files = sorted(raw_pubmed_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not json_files:
        logger.warning("[NORMALIZE:PubMed] no JSON files under %s", raw_pubmed_dir)
        return None

    latest = json_files[-1]
    logger.info("[NORMALIZE:PubMed] picked latest JSON: %s", latest)
    return latest


def run(raw_dir: str, processed_dir: str, csv_out_dir: Optional[str] = None) -> None:
    """pipeline_runner 에서 호출되는 엔트리포인트.

    Args:
        raw_dir: data/raw 루트 경로
        processed_dir: data/processed 루트 경로
        csv_out_dir: (선택) JSON→CSV 결과를 쓸 디렉터리
                    - 절대경로면 그대로 사용
                    - 상대경로면 processed_dir 기준으로 조합
                    - None 이면 processed_dir/pubmed/pmc_csv 사용

    1) raw/pubmed 아래 최신 JSON → CSV 세트 생성
    2) sections.csv → sections_meta.csv, sections_for_chunk.csv 분리
    """
    raw_base = Path(raw_dir)
    proc_base = Path(processed_dir)
    # 상대 경로면 프로젝트 루트 기준으로 해석 (어디서 실행해도 동일하게 동작)
    if not raw_base.is_absolute():
        raw_base = _PROJECT_ROOT / raw_base
    if not proc_base.is_absolute():
        proc_base = _PROJECT_ROOT / proc_base

    logger.info(
        "[NORMALIZE:PubMed] run() called with raw_dir=%s, processed_dir=%s, csv_out_dir=%s",
        raw_base,
        proc_base,
        csv_out_dir,
    )

    # 0. CSV 출력 디렉터리 결정
    if csv_out_dir is None:
        out_base = proc_base / "pubmed" / "pmc_csv"
    else:
        csv_out_path = Path(csv_out_dir)
        if csv_out_path.is_absolute():
            out_base = csv_out_path
        else:
            out_base = proc_base / csv_out_path
    out_base.mkdir(parents=True, exist_ok=True)

    # 1. 입력 JSON 선택 (data/raw/pubmed/*.json 중 최신 1개)
    raw_pubmed_dir = raw_base / "pubmed"
    input_json = _pick_latest_json(raw_pubmed_dir)
    if input_json is None:
        logger.info("[NORMALIZE:PubMed] skip: no input JSON")
        return

    # 2. JSON → CSV (articles/sections/equations/figures/tables/references)
    csv_out_dir_path = out_base
    logger.info(
        "[NORMALIZE:PubMed] step1 json_to_csv: input=%s, out_dir=%s",
        input_json,
        csv_out_dir_path,
    )
    json_to_csv(str(input_json), str(csv_out_dir_path))

    # 3. sections.csv → meta / chunk용으로 분리
    sections_csv = csv_out_dir_path / "sections.csv"
    meta_out = csv_out_dir_path / "sections_meta.csv"
    chunk_out = csv_out_dir_path / "sections_for_chunk.csv"

    logger.info(
        "[NORMALIZE:PubMed] step2 split_sections: input=%s, meta_out=%s, chunk_out=%s",
        sections_csv,
        meta_out,
        chunk_out,
    )

    ok = split_sections(
        input_csv=str(sections_csv),
        meta_out=str(meta_out),
        chunk_prep_out=str(chunk_out),
    )

    if ok:
        logger.info("[NORMALIZE:PubMed] DONE (json_to_csv + split_sections)")
    else:
        logger.error("[NORMALIZE:PubMed] ERROR in split_sections")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    run(
        raw_dir="data/raw",
        processed_dir="data/processed",
    )
