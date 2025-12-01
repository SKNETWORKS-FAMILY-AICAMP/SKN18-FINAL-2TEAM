#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMC section embeddings
- Input: CSV with columns [section_id, title, text]  (예: pmc_vector_source.csv)
- Output: pmc_vector.csv with chunk-level embeddings

청킹:
    - title + '\n\n' + text 를 하나로 합쳐서 사용
    - char 기반 max_len (기본 400), overlap 100
    - boundary: '.', '!', '?', 공백 등 가능한 문장 경계 근처에서 자르려고 시도

재시작(resume):
    - pmc_vector.csv가 이미 있으면 해당 파일에서 chunk_id를 모두 읽어와
      다음 실행 시 동일 chunk_id는 건너뜀
    - 중간에 끊어져도 재실행하면 나머지 chunk만 계속 임베딩
"""

import os
import sys
import re
import csv
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Set

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# -------------------
# Config & env
# -------------------

DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIM = 1536
DEFAULT_CHUNK_SIZE = 400
DEFAULT_OVERLAP = 100
RATE_LIMIT_DELAY = float(os.getenv("EMBED_RATE_DELAY", "0.2"))  # 초

# .env 로드 (현재 디렉토리 또는 상위)
SCRIPT_DIR = Path(__file__).resolve().parent
env_path = SCRIPT_DIR / ".env"
if not env_path.exists():
    # 한 단계 위도 시도
    env_path = SCRIPT_DIR.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# -------------------
# Helpers
# -------------------

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def combine_title_text(title: str, text: str) -> str:
    t = normalize_text(title)
    body = normalize_text(text)
    if not t:
        return body
    if not body:
        return t
    return f"{t}\n\n{body}"


def make_chunk_id(section_id: str, seq: int) -> str:
    """
    section_id + chunk sequence 기반 고유 ID
    예: section_id=534526154, seq=1 -> "SEC534526154_C01"
    """
    return f"SEC{section_id}_C{seq:02d}"


def split_into_sentences(text: str) -> List[Tuple[int, int]]:
    """
    아주 단순한 문장 분리기.
    - '.', '!', '?', '。', '！', '？' 를 문장 끝으로 취급
    - 각 문장의 (start_idx, end_idx)를 반환
    """
    sentences: List[Tuple[int, int]] = []
    n = len(text)
    start = 0

    for m in re.finditer(r"[\.!?。！？]", text):
        end = m.end()
        # 해당 구두점까지 하나의 문장으로 본다
        seg = text[start:end].strip()
        if seg:
            sentences.append((start, end))
        start = end

    # 마지막 구두점 이후에 남은 텍스트
    if start < n:
        seg = text[start:n].strip()
        if seg:
            sentences.append((start, n))

    # 문장을 하나도 못 만들면 전체를 하나로
    if not sentences and n > 0:
        sentences.append((0, n))

    return sentences


def sentence_chunks(
    text: str,
    max_len: int,
    overlap: int,
) -> List[Tuple[int, int, str]]:
    """
    문장 단위 청킹 + 실제 오버랩(겹치는 문장) 보장 버전.

    - 전체 텍스트를 문장 단위로 나눈 뒤
    - 여러 문장을 묶어서 길이 <= max_len 이 되도록 chunk 생성
    - 다음 chunk는 항상 "이전 chunk 안에 있던 문장 중 하나"에서 시작
      → 같은 문장이 두 개 chunk에 들어가므로 실제 오버랩이 생김
    - overlap 파라미터는 '대략 이 정도 문자 길이만큼' 겹치도록
      다음 chunk 시작 문장을 선택할 때 사용
    """
    text = text or ""
    n = len(text)
    if n == 0:
        return []

    sents = split_into_sentences(text)
    if not sents:
        return [(0, n, text)]

    chunks: List[Tuple[int, int, str]] = []
    i = 0

    while i < len(sents):
        # 현재 chunk의 시작은 문장 i의 시작
        start_idx = sents[i][0]
        end_idx = sents[i][1]  # 최소 한 문장은 항상 포함

        # 가능한 만큼 다음 문장들을 붙여서 max_len 이하 유지
        j = i + 1
        while j < len(sents):
            cand_end = sents[j][1]
            if cand_end - start_idx <= max_len:
                end_idx = cand_end
                j += 1
            else:
                break

        # 이 chunk 추가
        chunk_text = text[start_idx:end_idx]
        chunks.append((start_idx, end_idx, chunk_text))

        # 더 붙일 문장이 없으면 종료
        if j >= len(sents):
            break

        # ----- 다음 chunk 시작 문장 결정 (실제 오버랩 만들기) -----
        # 이전 chunk의 끝 end_idx에서 overlap 만큼 되돌아간 지점
        target_start_char = max(0, end_idx - overlap)

        # i..(j-1) 범위(이번 chunk에 포함된 문장들) 중에서
        # start <= target_start_char 이면서 가장 뒤에 있는 문장을 선택
        new_i = i
        for k in range(i, j):
            if sents[k][0] <= target_start_char:
                new_i = k

        # 안전장치: 최소 한 문장은 앞으로 나가게
        if new_i == i and i + 1 < j:
            new_i = i + 1

        # 다음 루프에서 이 문장부터 새 chunk 시작
        i = new_i

    return chunks




def to_pgvector_literal(vec: List[float]) -> str:
    """
    pgvector용 문자열 리터럴: '[0.1,0.2,...]'
    CSV에 그냥 저장해두면, 나중에 COPY + ::vector 로 적재 가능.
    """
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def load_existing_chunk_ids(out_path: Path) -> Set[str]:
    """
    이미 생성된 pmc_vector.csv가 있으면, 그 안의 chunk_id를 모두 읽어서 반환.
    """
    if not out_path.exists():
        return set()

    existing_ids: Set[str] = set()
    with out_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "chunk_id" not in reader.fieldnames:
            return set()
        for row in reader:
            cid = row.get("chunk_id")
            if cid:
                existing_ids.add(str(cid))
    return existing_ids


# -------------------
# Main embedder
# -------------------

class PMCSectionEmbedder:
    def __init__(
        self,
        input_csv: str,
        output_csv: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        embed_model: str = DEFAULT_EMBED_MODEL,
        embed_dim: int = DEFAULT_EMBED_DIM,
    ):
        self.input_csv = Path(input_csv)
        self.output_csv = Path(output_csv)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.embed_model = embed_model
        self.embed_dim = embed_dim

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY 가 설정되어 있지 않습니다 (.env 확인).")

        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(
            model=self.embed_model,
            input=text,
            encoding_format="float",
        )
        return resp.data[0].embedding

    def run(self, resume: bool = True):
        if not self.input_csv.exists():
            raise FileNotFoundError(f"Input CSV not found: {self.input_csv}")

        df = pd.read_csv(self.input_csv, encoding="utf-8-sig")
        required_cols = ["section_id", "title", "text"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"입력 CSV에 필요한 컬럼이 없습니다: {missing}")

        # 🔹 1) title + text 미리 합치고, 비어 있는 row는 제거
        def _combine(row):
            return combine_title_text(row.get("title", ""), row.get("text", ""))

        df["combined"] = df.apply(_combine, axis=1)
        df["combined"] = df["combined"].fillna("").astype(str).str.strip()
        df = df[df["combined"].str.len() > 0].copy()

        total_sections = len(df)
        if total_sections == 0:
            print("[WARN] 임베딩할 섹션이 없습니다 (title+text 모두 비어 있음).")
            return



        # 기존 chunk_id 읽기 (resume)
        existing_chunk_ids: Set[str] = set()
        if resume:
            existing_chunk_ids = load_existing_chunk_ids(self.output_csv)
            if existing_chunk_ids:
                print(f"✓ Found {len(existing_chunk_ids)} existing chunks (resume mode)")

        # 출력 CSV 준비
        fieldnames = [
            "chunk_id",
            "section_id",
            "chunk_seq",
            "start_char",
            "end_char",
            "emb_model",
            "emb_dim",
            "text_chunk",
            "embedding",
        ]
        file_exists = self.output_csv.exists()
        out_f = self.output_csv.open(
            "a", encoding="utf-8-sig", newline=""
        )
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        done_sections = 0
        skipped_sections = 0
        error_count = 0
        total_new_chunks = 0

        pbar = tqdm(
            total=total_sections,
            desc="Embedding sections",
            unit="sec",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )

        try:
            for _, row in df.iterrows():
                try:
                    section_id_raw = row["section_id"]
                    section_id = str(section_id_raw)

                    combined = row.get("combined", "")
                    if not isinstance(combined, str):
                        combined = str(combined)
                    if not combined.strip():
                        skipped_sections += 1
                        pbar.update(1)
                        pbar.set_postfix(
                            {"done": done_sections, "skipped": skipped_sections, "errors": error_count}
                        )
                        continue

                    chunks = sentence_chunks(combined, self.chunk_size, self.overlap)


                    # 이미 존재하는 chunk_id는 제외
                    new_chunks = []
                    for seq, (start, end, ch_text) in enumerate(chunks, start=1):
                        chunk_id = make_chunk_id(section_id, seq)
                        if resume and chunk_id in existing_chunk_ids:
                            continue
                        new_chunks.append((chunk_id, seq, start, end, ch_text))

                    if not new_chunks:
                        # 이 섹션의 모든 chunk가 이미 있음
                        skipped_sections += 1
                        pbar.update(1)
                        pbar.set_postfix(
                            {"done": done_sections, "skipped": skipped_sections, "errors": error_count}
                        )
                        continue

                    # 새 chunk들만 임베딩
                    for (chunk_id, seq, start, end, ch_text) in new_chunks:
                        emb = self.embed(ch_text)
                        embedding_literal = to_pgvector_literal(emb)

                        writer.writerow(
                            {
                                "chunk_id": chunk_id,
                                "section_id": section_id,
                                "chunk_seq": seq,
                                "start_char": start,
                                "end_char": end,
                                "emb_model": self.embed_model,
                                "emb_dim": self.embed_dim,
                                "text_chunk": ch_text,
                                "embedding": embedding_literal,
                            }
                        )
                        out_f.flush()
                        existing_chunk_ids.add(chunk_id)
                        total_new_chunks += 1
                        time.sleep(RATE_LIMIT_DELAY)

                    done_sections += 1

                except Exception as e:
                    error_count += 1
                    print(f"\n✗ section_id={row.get('section_id')}: {e}")

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "done": done_sections,
                        "skipped": skipped_sections,
                        "errors": error_count,
                        "chunks": total_new_chunks,
                    }
                )

        except KeyboardInterrupt:
            print("\n! Interrupted by user. Progress saved so far.")
        finally:
            pbar.close()
            out_f.close()
            print(
                f"\n✅ Finished. sections_done={done_sections}, "
                f"sections_skipped={skipped_sections}, errors={error_count}, "
                f"new_chunks={total_new_chunks}"
            )


# -------------------
# CLI
# -------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        required=True,
        help="섹션 CSV 경로 (예: pmc_vector_source.csv 또는 section.csv)",
    )
    ap.add_argument(
        "--output",
        default="pmc_vector.csv",
        help="임베딩 결과 CSV 경로 (default: pmc_vector.csv)",
    )
    ap.add_argument(
        "--chunk",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"chunk char length (default {DEFAULT_CHUNK_SIZE})",
    )
    ap.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_OVERLAP,
        help=f"overlap char length (default {DEFAULT_OVERLAP})",
    )
    ap.add_argument(
        "--model",
        default=DEFAULT_EMBED_MODEL,
        help=f"OpenAI embedding model (default: {DEFAULT_EMBED_MODEL})",
    )
    ap.add_argument(
        "--no-resume",
        action="store_true",
        help="기존 pmc_vector.csv를 무시하고 처음부터 다시 수행",
    )

    args = ap.parse_args()

    embedder = PMCSectionEmbedder(
        input_csv=args.input,
        output_csv=args.output,
        chunk_size=args.chunk,
        overlap=args.overlap,
        embed_model=args.model,
        embed_dim=DEFAULT_EMBED_DIM,
    )
    embedder.run(resume=(not args.no_resume))


if __name__ == "__main__":
    main()
