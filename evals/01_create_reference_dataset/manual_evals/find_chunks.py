#!/usr/bin/env python3
"""Search for chunk_ids containing a given string across all chapter JSON files."""

import json
import re
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

QUERY = "How much guaranteed cash back will I get each year if I buy the 5-year payment AIA Smart Flexi Rewards (II) plan?"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_chunks(query: str) -> list[str]:
    normalized_query = normalize(query)
    matches = []

    for path in sorted(STATIC_DIR.glob("chapter_*.json")):
        with open(path) as f:
            chunks = json.load(f)
        for chunk in chunks:
            if normalized_query in normalize(chunk.get("text", "")):
                matches.append(chunk["chunk_id"])

    return matches


if __name__ == "__main__":
    results = find_chunks(QUERY)

    if results:
        for chunk_id in results:
            print(chunk_id)
    else:
        print("No matching chunks found.")
