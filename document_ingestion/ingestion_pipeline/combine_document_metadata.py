from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from utils import save_json_atomic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine all JSON files in a directory into one JSON list, "
            "adding the source filename to each dictionary before merge."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/document_metadata"),
        help="Directory containing source .json files (default: output/document_metadata)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("output/document_metadata_merged.json"),
        help="Path to write merged JSON list (default: output/document_metadata_merged.json)",
    )
    parser.add_argument(
        "--filename-key",
        type=str,
        default="source_filename",
        help="Key name used to store source filename (default: source_filename)",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_metadata_files(input_dir: Path, filename_key: str) -> list[dict[str, Any]]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    merged: list[dict[str, Any]] = []
    json_files = sorted(input_dir.glob("*.json"))

    for file_path in json_files:
        data = load_json(file_path)

        if isinstance(data, dict):
            row = dict(data)
            row[filename_key] = file_path.name
            merged.append(row)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    row = dict(item)
                    row[filename_key] = file_path.name
                    merged.append(row)
        else:
            # Skip non-dict/non-list JSON payloads.
            continue

    return merged


def write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    save_json_atomic(path, payload)


def main() -> None:
    args = parse_args()
    merged = merge_metadata_files(args.input_dir, args.filename_key)
    write_json(args.output_file, merged)
    print(f"Wrote {len(merged)} records to {args.output_file}")


if __name__ == "__main__":
    main()
