import csv
import json
import os
from pathlib import Path
from typing import List, Dict

import pandas as pd


def normalize_string(value: str) -> str:
    if value is None:
        return ""
    # Strip whitespace and normalize typical "null" tokens
    trimmed = str(value).strip()
    if trimmed.lower() in {"null", "none", "nan"}:
        return ""
    return trimmed


def drop_rows_with_any_null(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize all string-like cells
    normalized_df = df.applymap(normalize_string)
    # Replace empty strings with NaN then drop rows with any NaN
    cleaned = normalized_df.replace("", pd.NA).dropna(how="any")
    return cleaned


def to_jsonl_rows(df: pd.DataFrame) -> List[Dict[str, str]]:
    # Expect columns: question, answer
    if "question" not in df.columns or "answer" not in df.columns:
        raise ValueError("CSV must contain 'question' and 'answer' columns to build a fine-tune JSONL.")
    rows: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        prompt = normalize_string(row["question"])
        completion = normalize_string(row["answer"])
        if not prompt or not completion:
            continue
        rows.append({"prompt": prompt, "completion": completion})
    return rows


def main():
    project_root = Path(__file__).resolve().parents[1]
    source_csv = project_root / "data" / "interview" / "interview_final_db.csv"
    output_dir = project_root / "data" / "finetune"
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaned_csv_path = output_dir / "interview_final_db.cleaned.csv"
    jsonl_path = output_dir / "interview_qa.jsonl"

    if not source_csv.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_csv}")

    df = pd.read_csv(source_csv, dtype=str)  # read all as string to preserve content
    cleaned_df = drop_rows_with_any_null(df)
    cleaned_df.to_csv(cleaned_csv_path, index=False)

    qa_rows = to_jsonl_rows(cleaned_df)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for obj in qa_rows:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"Cleaned CSV rows: {len(cleaned_df)} -> {cleaned_csv_path}")
    print(f"JSONL QA rows: {len(qa_rows)} -> {jsonl_path}")


if __name__ == "__main__":
    main()


