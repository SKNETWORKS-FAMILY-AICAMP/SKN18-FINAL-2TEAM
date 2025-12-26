import csv
from pathlib import Path
from typing import Set, Dict, Any, Generator, List

def load_existing_chunk_ids(out_path: Path) -> Set[str]:
    """
    [공용 메타데이터 로드 함수]
    이미 생성된 CSV 파일에서 chunk_id를 모두 읽어서 반환합니다.
    """
    if not out_path.exists():
        return set()

    existing_ids: Set[str] = set()
    try:
        with out_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "chunk_id" not in reader.fieldnames:
                return set()
            for row in reader:
                cid = row.get("chunk_id")
                if cid:
                    existing_ids.add(str(cid))
    except Exception:
        return set()
    return existing_ids


def iter_chunk_csv_rows(csv_path: Path, required_cols: List[str]) -> Generator[Dict[str, Any], None, None]:
    """
    [임베딩 데이터 노드 함수]
    chunk CSV 파일을 row-by-row로 읽는 제너레이터입니다.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Chunk CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as inf:
        reader = csv.DictReader(inf)
        # 헤더 검증
        missing = [c for c in required_cols if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Chunk CSV에 필요한 컬럼이 없습니다: {missing}")

        for r in reader:
            yield r