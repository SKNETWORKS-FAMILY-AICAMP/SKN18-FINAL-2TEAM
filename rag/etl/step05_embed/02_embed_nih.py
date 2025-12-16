"""
NIH chunk → embedding 스텝.

입력:
  - data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=chunked/chunk.csv

출력:
  - data/processed/nih/success/year=YYYY/month=MM/day=DD/stage=embed/{timestamp}_nih_embeddings.csv
    (컬럼: nctid, chunk_id, text, embedding_model, embedding_dim, embedding)
    (embedding은 JSON 문자열로 저장)

동시에 embeddings_dir에도 동일 파일을 미러링하여 이후 upsert 단계가 경로를 참조할 수 있도록 한다.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from rag.etl.common.nih_config import CHUNK_OUTPUT_FILE

load_dotenv()

logger = logging.getLogger("etl.embed.nih")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되어야 NIH 임베딩을 생성할 수 있습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

EMBEDDING_MODEL = os.getenv("NIH_EMBED_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536
CHUNK_FILENAME = os.getenv("NIH_EMBED_CHUNK_FILENAME", CHUNK_OUTPUT_FILE or "chunk.csv")
OUTPUT_FILENAME_SUFFIX = os.getenv("NIH_EMBED_OUTPUT", "nih_embeddings.csv")
MANIFEST_FILENAME = "manifest.json"
MAX_EMBED_RETRIES = int(os.getenv("NIH_EMBED_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("NIH_EMBED_RETRY_BASE_DELAY", "1.5"))
CHUNK_FILE_OVERRIDE = os.getenv("NIH_EMBED_CHUNK_FILE")


def _project_root() -> Path:
    """프로젝트 루트를 반환한다 (Lambda 환경은 /tmp)."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp")
    return Path(__file__).resolve().parents[3]


def _is_lambda() -> bool:
    """Lambda 환경인지 확인한다."""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _check_disk_space(path: Path, required_mb: float = 100.0) -> bool:
    """디스크 공간이 충분한지 확인한다 (Lambda /tmp 제한: 512MB)."""
    if not _is_lambda():
        return True  # 로컬 환경에서는 체크하지 않음
    
    try:
        import shutil
        stat = shutil.disk_usage(path)
        free_mb = stat.free / (1024 * 1024)
        
        if free_mb < required_mb:
            logger.warning(
                "[EMBED][NIH] 디스크 공간 부족: %.2f MB 사용 가능 (필요: %.2f MB)",
                free_mb,
                required_mb,
            )
            return False
        return True
    except Exception as e:
        logger.warning("[EMBED][NIH] 디스크 공간 체크 실패: %s", e)
        return True  # 체크 실패 시 계속 진행


def _default_success_root() -> Path:
    base = _project_root() / "data" / "processed" / "nih"
    return base / "success"


def _resolve_success_root(chunks_dir: str | None) -> Path:
    if chunks_dir:
        base = Path(chunks_dir)
        if base.name != "success" and (base / "success").exists():
            base = base / "success"
        return base
    return _default_success_root()


def _strip_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """BOM 등이 포함된 컬럼명을 정리한다."""
    df = df.copy()
    df.columns = [col.replace("\ufeff", "").strip() for col in df.columns]
    return df


def _list_chunk_files(success_root: Path) -> list[Path]:
    """사용 가능한 chunk.csv 파일 목록을 반환한다."""
    if CHUNK_FILE_OVERRIDE:
        path = Path(CHUNK_FILE_OVERRIDE)
        if not path.exists():
            raise FileNotFoundError(f"NIH_EMBED_CHUNK_FILE 경로를 찾을 수 없습니다: {path}")
        return [path]

    if not success_root.exists():
        return []

    pattern = f"**/stage=chunked/{CHUNK_FILENAME}"
    return sorted(success_root.glob(pattern))


def _pick_latest_chunk_file(success_root: Path) -> Path | None:
    """가장 최근에 수정된 chunk 파일을 선택한다."""
    chunk_files = _list_chunk_files(success_root)
    if not chunk_files:
        return None
    return max(chunk_files, key=lambda p: p.stat().st_mtime)


def _key_to_readable(key: str) -> str:
    """camelCase 또는 snake_case를 읽기 쉬운 형태로 변환한다.
    
    예:
        eligibilityCriteria -> "Eligibility Criteria"
        primaryOutcomes -> "Primary Outcomes"
        armGroups -> "Arm Groups"
    """
    # camelCase -> "Camel Case" (소문자 다음 대문자 사이에 공백 추가)
    key = re.sub(r'([a-z])([A-Z])', r'\1 \2', key)
    # snake_case -> "Snake Case"
    key = key.replace('_', ' ')
    # 첫 글자 대문자, 나머지 단어도 첫 글자 대문자
    return key.title()


def _flatten_text(value: Any, parent_key: str = "") -> list[str]:
    """list/dict 구조를 문자열 리스트로 평탄화한다.
    키 값을 유지하여 의미적 모호성을 방지한다.
    
    Args:
        value: 평탄화할 값 (dict, list, str 등)
        parent_key: 부모 키 (재귀 호출 시 사용)
    
    Returns:
        키를 포함한 텍스트 리스트
    """
    if value is None:
        return []
    
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # 부모 키가 있으면 키를 포함하여 반환
        if parent_key:
            readable_key = _key_to_readable(parent_key)
            return [f"{readable_key}: {text}"]
        return [text]
    
    if isinstance(value, (int, float, bool)):
        text = str(value)
        if parent_key:
            readable_key = _key_to_readable(parent_key)
            return [f"{readable_key}: {text}"]
        return [text]
    
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_text(item, parent_key))
        return items
    
    if isinstance(value, dict):
        items: list[str] = []
        for k, v in value.items():
            # dict의 경우, 각 키에 대해 재귀 호출
            items.extend(_flatten_text(v, k))
        return items
    
    text = str(value).strip()
    if text:
        if parent_key:
            readable_key = _key_to_readable(parent_key)
            return [f"{readable_key}: {text}"]
        return [text]
    return []


def _chunk_to_text(chunk_raw: str) -> str:
    """chunk 컬럼 문자열을 실제 텍스트로 변환.
    
    키 값을 유지하여 의미적 모호성을 방지한다.
    예: {"eligibilityCriteria": "Age >= 18"} 
        -> "Eligibility Criteria: Age >= 18"
    """
    chunk_raw = (chunk_raw or "").strip()
    if not chunk_raw:
        return ""

    try:
        parsed = json.loads(chunk_raw)
    except json.JSONDecodeError:
        # JSON이 아니면 그대로 반환
        return chunk_raw

    # 키를 포함한 텍스트로 변환
    sentences = _flatten_text(parsed)
    return "\n".join(sentences)


def _embed_text(text: str) -> list[float]:
    """OpenAI 임베딩을 생성한다 (간단한 retry 포함)."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_EMBED_RETRIES + 1):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:  # pragma: no cover - 네트워크 예외
            last_error = exc
            sleep_for = RETRY_BASE_DELAY * attempt
            logger.warning(
                "[EMBED][NIH] 임베딩 요청 실패 (attempt=%s/%s): %s",
                attempt,
                MAX_EMBED_RETRIES,
                exc,
            )
            time.sleep(sleep_for)

    assert last_error is not None
    raise last_error


def _target_embed_dir(chunk_file: Path) -> Path:
    """chunk 파일 경로와 동일한 날짜 디렉터리 하위의 stage=embed 경로를 생성.
    
    Lambda 환경에서는 /tmp 하위에 생성한다.
    """
    if _is_lambda():
        # Lambda 환경: /tmp/nih_embeddings에 저장
        embed_dir = Path("/tmp") / "nih_embeddings"
        embed_dir.mkdir(parents=True, exist_ok=True)
        return embed_dir
    
    # 로컬 환경: 기존 로직 유지
    day_dir = chunk_file.parent.parent  # .../day=DD
    embed_dir = day_dir / "stage=embed"
    embed_dir.mkdir(parents=True, exist_ok=True)
    return embed_dir


def _write_manifest(manifest_path: Path, data: dict[str, Any]) -> None:
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _mirror_to_embeddings_dir(src: Path, embeddings_dir: str) -> Path | None:
    """embeddings_dir 아래로 결과 파일을 복사한다."""
    if not embeddings_dir:
        return None
    dest_dir = Path(embeddings_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest


def _process_single_row(
    idx: int,
    row: pd.Series,
    total_rows: int,
    csv_rows: list[dict[str, Any]],
    batch_size: int,
    output_path: Path,
    is_first_batch: bool,
    success: int,
    skipped: int,
    errors: list[dict[str, Any]],
) -> tuple[bool, int, int, list[dict[str, Any]]]:
    """단일 행을 처리하고 필요시 배치 저장한다.
    
    Returns:
        (is_first_batch, success, skipped, errors) 업데이트된 값들
    """
    # 진행 상황 출력 (10개마다 또는 첫 번째)
    if (idx + 1) % 10 == 0 or idx == 0:
        print(f"[EMBED][NIH]   처리 중: {idx + 1}/{total_rows} 행 (성공: {success}, 건너뜀: {skipped}, 오류: {len(errors)})", flush=True)
    
    nctid = str(row.get("nctid", "")).strip()
    chunk_id = str(row.get("chunk_id", "")).strip()
    chunk_raw = str(row.get("chunk", "")).strip()

    if not chunk_id or not chunk_raw:
        skipped += 1
        return is_first_batch, success, skipped, errors

    text = _chunk_to_text(chunk_raw)
    if not text:
        skipped += 1
        return is_first_batch, success, skipped, errors

    try:
        # 임베딩 생성 (시간이 오래 걸릴 수 있음)
        embedding = _embed_text(text)
    except Exception as exc:  # pragma: no cover - 외부 API 예외
        errors.append({"row": int(idx), "chunk_id": chunk_id, "error": str(exc)})
        logger.error("[EMBED][NIH] row=%s chunk_id=%s 실패: %s", idx, chunk_id, exc)
        print(f"[EMBED][NIH]   ⚠️  오류 발생 (행 {idx + 1}): {exc}", flush=True)
        return is_first_batch, success, skipped, errors

    # CSV 행 데이터 생성 (embedding은 JSON 문자열로 변환)
    csv_rows.append({
        "nctid": nctid,
        "chunk_id": chunk_id,
        "text": text,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
        "embedding": json.dumps(embedding, ensure_ascii=False),  # JSON 문자열로 저장
    })
    success += 1

    # 배치 크기에 도달하면 파일에 저장
    if len(csv_rows) >= batch_size:
        print(f"[EMBED][NIH]   💾 배치 저장 중: {len(csv_rows)}개 행을 파일에 저장...", flush=True)
        batch_df = pd.DataFrame(csv_rows)
        # 첫 배치면 헤더 포함, 이후는 헤더 없이 append
        batch_df.to_csv(
            output_path,
            mode="w" if is_first_batch else "a",
            index=False,
            header=is_first_batch,
            encoding="utf-8-sig" if is_first_batch else "utf-8",  # BOM은 첫 배치만
            quoting=csv.QUOTE_ALL,
        )
        csv_rows.clear()  # 배치 비우기
        is_first_batch = False
        print(f"[EMBED][NIH]   ✓ 배치 저장 완료: 총 {success}/{total_rows} 행 처리됨", flush=True)
        logger.info(
            "[EMBED][NIH] progress: %s/%s (skipped=%s, errors=%s) - 파일 저장 완료",
            success,
            total_rows,
            skipped,
            len(errors),
        )
    
    return is_first_batch, success, skipped, errors


def process_chunk_file(chunk_path: Path, embeddings_dir: str) -> tuple[Path, dict[str, Any]]:
    """단일 chunk.csv 파일을 임베딩한다.
    
    Lambda 환경에서는 메모리 효율성을 위해 청크 단위로 읽는다.
    """
    print(f"[EMBED][NIH] 📖 입력 파일 읽기 시작: {chunk_path}")
    logger.info("[EMBED][NIH] input=%s", chunk_path)
    
    # Lambda 환경 체크 및 디스크 공간 확인
    is_lambda = _is_lambda()
    if is_lambda:
        file_size_mb = chunk_path.stat().st_size / (1024 * 1024)
        print(f"[EMBED][NIH] ⚠️  Lambda 환경 감지: 입력 파일 크기 {file_size_mb:.2f} MB")
        
        # 디스크 공간 확인 (입력 파일 크기의 2배 + 여유 50MB)
        required_mb = file_size_mb * 2 + 50
        if not _check_disk_space(chunk_path.parent, required_mb):
            raise RuntimeError(
                f"디스크 공간 부족: /tmp에 최소 {required_mb:.2f} MB 필요 "
                f"(Lambda /tmp 제한: 512MB)"
            )
    
    # 메모리 효율적인 청크 단위 읽기 (Lambda 환경 또는 큰 파일)
    CHUNK_READ_SIZE = int(os.getenv("NIH_EMBED_CHUNK_READ_SIZE", "1000" if is_lambda else "0"))
    
    if CHUNK_READ_SIZE > 0:
        print(f"[EMBED][NIH] ⏳ CSV 파일 청크 단위로 읽기 중... (청크 크기: {CHUNK_READ_SIZE}행)")
        # 청크 단위로 처리하기 위해 파일을 두 번 읽어야 함 (첫 번째는 행 수 확인)
        total_rows = sum(1 for _ in open(chunk_path, 'r', encoding='utf-8-sig')) - 1  # 헤더 제외
        print(f"[EMBED][NIH] ✓ 파일 정보 확인 완료: 총 {total_rows}개 행 (청크 단위 처리)")
    else:
        print(f"[EMBED][NIH] ⏳ CSV 파일 전체 로딩 중...")
        df = pd.read_csv(chunk_path, dtype=str, encoding="utf-8-sig")
        df = _strip_column_names(df).fillna("")
        total_rows = len(df)
        print(f"[EMBED][NIH] ✓ CSV 파일 로딩 완료: {total_rows}개 행")

    print(f"[EMBED][NIH] 📁 출력 디렉토리 준비 중...")
    embed_dir = _target_embed_dir(chunk_path)
    timestamp_suffix = datetime.now().strftime("%H%M%S")
    output_path = embed_dir / f"{timestamp_suffix}_{OUTPUT_FILENAME_SUFFIX}"
    print(f"[EMBED][NIH] ✓ 출력 파일 경로: {output_path}")

    success = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    start_ts = datetime.now(timezone.utc).isoformat()

    # 배치 단위로 저장하여 중간에 끊겨도 데이터 보존
    # Lambda 환경에서는 메모리 절약을 위해 배치 크기 조정
    BATCH_SIZE = int(os.getenv("NIH_EMBED_BATCH_SIZE", "25" if not is_lambda else "10"))
    csv_rows = []
    is_first_batch = True  # 첫 배치인지 확인 (헤더 작성용)

    print(f"[EMBED][NIH] 🚀 임베딩 시작: 총 {total_rows}개 행 처리 예정 (배치 크기: {BATCH_SIZE})")
    print(f"[EMBED][NIH] 📊 진행 상황:")

    # 컬럼명 확인 (첫 번째 행만 읽어서)
    with open(chunk_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required_cols = {"nctid", "chunk_id", "chunk"}
        missing = [col for col in required_cols if col not in set(reader.fieldnames or [])]
        if missing:
            raise ValueError(f"chunk CSV에 필요한 컬럼이 없습니다: {missing}")

    try:
        # 청크 단위로 읽기 또는 전체 DataFrame 사용
        if CHUNK_READ_SIZE > 0:
            # 청크 단위로 읽기
            chunk_iter = pd.read_csv(
                chunk_path,
                dtype=str,
                encoding="utf-8-sig",
                chunksize=CHUNK_READ_SIZE
            )
            row_idx = 0
            for chunk_df in chunk_iter:
                chunk_df = _strip_column_names(chunk_df).fillna("")
                for _, row in chunk_df.iterrows():
                    is_first_batch, success, skipped, errors = _process_single_row(
                        row_idx, row, total_rows, csv_rows, BATCH_SIZE, output_path, 
                        is_first_batch, success, skipped, errors
                    )
                    row_idx += 1
        else:
            # 전체 DataFrame 사용 (기존 방식)
            for idx, row in df.iterrows():
                is_first_batch, success, skipped, errors = _process_single_row(
                    idx, row, total_rows, csv_rows, BATCH_SIZE, output_path,
                    is_first_batch, success, skipped, errors
                )

        # 마지막 남은 데이터 저장
        if csv_rows:
            print(f"[EMBED][NIH]   💾 최종 배치 저장 중: {len(csv_rows)}개 행...", flush=True)
            batch_df = pd.DataFrame(csv_rows)
            batch_df.to_csv(
                output_path,
                mode="w" if is_first_batch else "a",
                index=False,
                header=is_first_batch,
                encoding="utf-8-sig" if is_first_batch else "utf-8",
                quoting=csv.QUOTE_ALL,
            )
            print(f"[EMBED][NIH]   ✓ 최종 저장 완료", flush=True)
            logger.info(
                "[EMBED][NIH] 최종 저장: %s개 행 (총 %s/%s, skipped=%s, errors=%s)",
                len(csv_rows),
                success,
                total_rows,
                skipped,
                len(errors),
            )
        
        print(f"[EMBED][NIH] ✅ 임베딩 완료: 성공 {success}개, 건너뜀 {skipped}개, 오류 {len(errors)}개", flush=True)

    except Exception as e:
        # 예외 발생 시에도 지금까지 저장된 데이터는 보존됨
        logger.error("[EMBED][NIH] 임베딩 중 오류 발생: %s (이미 저장된 데이터는 보존됨)", e)
        # 남은 데이터가 있으면 저장 시도
        if csv_rows:
            try:
                batch_df = pd.DataFrame(csv_rows)
                batch_df.to_csv(
                    output_path,
                    mode="w" if is_first_batch else "a",
                    index=False,
                    header=is_first_batch,
                    encoding="utf-8-sig" if is_first_batch else "utf-8",
                    quoting=csv.QUOTE_ALL,
                )
                logger.info("[EMBED][NIH] 오류 발생 전까지의 데이터 저장 완료: %s개 행", len(csv_rows))
            except Exception as save_error:
                logger.error("[EMBED][NIH] 부분 저장 실패: %s", save_error)
        raise

    manifest = {
        "source_chunk": str(chunk_path),
        "output_file": str(output_path),
        "record_count": success,
        "skipped": skipped,
        "errors": errors,
        "model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
        "started_at": start_ts,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_manifest(embed_dir / MANIFEST_FILENAME, manifest)
    mirror_path = _mirror_to_embeddings_dir(output_path, embeddings_dir)
    if mirror_path:
        logger.info("[EMBED][NIH] embeddings_dir copy=%s", mirror_path)

    return output_path, manifest


def run(chunks_dir: str | None = None, embeddings_dir: str = "") -> None:
    """pipeline_runner 에서 호출되는 엔트리 포인트."""
    print(f"[EMBED][NIH] =========================================")
    print(f"[EMBED][NIH] NIH 임베딩 프로세스 시작")
    print(f"[EMBED][NIH] =========================================")
    print(f"[EMBED][NIH] chunks_dir: {chunks_dir}")
    print(f"[EMBED][NIH] embeddings_dir: {embeddings_dir}")
    logger.info("[EMBED][NIH] 시작 - chunks_dir=%s embeddings_dir=%s", chunks_dir, embeddings_dir)

    print(f"[EMBED][NIH] 🔍 chunk 파일 검색 중...")
    success_root = _resolve_success_root(chunks_dir)
    print(f"[EMBED][NIH]   검색 경로: {success_root}")
    
    chunk_file = _pick_latest_chunk_file(success_root)
    if not chunk_file:
        print(f"[EMBED][NIH] ❌ 처리할 chunk.csv 파일을 찾지 못했습니다.")
        logger.warning(
            "[EMBED][NIH] 처리할 chunk.csv 파일을 찾지 못했습니다. 검색경로=%s",
            success_root,
        )
        return

    print(f"[EMBED][NIH] ✓ chunk 파일 발견: {chunk_file}")
    print(f"[EMBED][NIH] 📊 파일 크기: {chunk_file.stat().st_size / (1024*1024):.2f} MB")
    
    output_path, manifest = process_chunk_file(chunk_file, embeddings_dir)
    
    print(f"[EMBED][NIH] =========================================")
    print(f"[EMBED][NIH] ✅ NIH 임베딩 프로세스 완료")
    print(f"[EMBED][NIH] =========================================")
    print(f"[EMBED][NIH] 출력 파일: {output_path}")
    print(f"[EMBED][NIH] 총 레코드: {manifest['record_count']}개")
    print(f"[EMBED][NIH] 건너뜀: {manifest['skipped']}개")
    print(f"[EMBED][NIH] 오류: {len(manifest['errors'])}개")
    logger.info(
        "[EMBED][NIH] 완료 - output=%s, records=%s (errors=%s)",
        output_path,
        manifest["record_count"],
        len(manifest["errors"]),
    )


def main() -> None:
    """단독 실행 시 기본 경로로 실행."""
    default_chunks = str(_default_success_root().parent)
    default_embeddings = str(_project_root() / "data" / "embeddings")
    run(chunks_dir=default_chunks, embeddings_dir=default_embeddings)


if __name__ == "__main__":
    main()
