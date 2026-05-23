#!/usr/bin/env python3
"""Search for chunk_ids containing a given string across all chapter JSON files."""

import json
import re
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

QUERY = "non-forfeiture option1 to prevent the policy from lapsing; the premium cost is the lowest compared to other types of life insurance for coverage o"


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
