#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared chunking and helper utilities for PMC embedding pipeline.
"""
from pathlib import Path
import os
import re
from typing import List, Tuple, Set
from dotenv import load_dotenv

# -------------------
# Config & env
# -------------------
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIM = 1536
DEFAULT_CHUNK_SIZE = 600
DEFAULT_OVERLAP = 120
RATE_LIMIT_DELAY = float(os.getenv("EMBED_RATE_DELAY", "0.2"))

# .env 로드 (현재 디렉토리 또는 상위)
SCRIPT_DIR = Path(__file__).resolve().parent
env_path = SCRIPT_DIR / ".env"
if not env_path.exists():
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
    return f"SEC{section_id}_C{seq:02d}"


def split_into_sentences(text: str) -> List[Tuple[int, int]]:
    sentences: List[Tuple[int, int]] = []
    n = len(text)
    start = 0

    for m in re.finditer(r"[\.!?。！？]", text):
        end = m.end()
        seg = text[start:end].strip()
        if seg:
            sentences.append((start, end))
        start = end

    if start < n:
        seg = text[start:n].strip()
        if seg:
            sentences.append((start, n))

    if not sentences and n > 0:
        sentences.append((0, n))

    return sentences


def sentence_chunks(
    text: str,
    max_len: int,
    overlap: int,
) -> List[Tuple[int, int, str]]:
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
        start_idx = sents[i][0]
        end_idx = sents[i][1]

        j = i + 1
        while j < len(sents):
            cand_end = sents[j][1]
            if cand_end - start_idx <= max_len:
                end_idx = cand_end
                j += 1
            else:
                break

        chunk_text = text[start_idx:end_idx]
        chunks.append((start_idx, end_idx, chunk_text))

        if j >= len(sents):
            break

        target_start_char = max(0, end_idx - overlap)
        new_i = i
        for k in range(i, j):
            if sents[k][0] <= target_start_char:
                new_i = k

        if new_i == i and i + 1 < j:
            new_i = i + 1

        i = new_i

    return chunks


def to_pgvector_literal(vec: List[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def load_existing_chunk_ids(out_path: Path) -> Set[str]:
    import csv

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
