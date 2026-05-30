from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils import default_chunk_dir, default_mineru_dir

logger = logging.getLogger(__name__)

WORD_CHUNK_SIZE = 200
WORD_OVERLAP = 50

TABLE_TOKEN_RE = re.compile(r"\[\[TABLE:(?P<idx>\d+)\]\]")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


@dataclass
class MiniChunk:
    text: str
    bbox: tuple[float, float, float, float] | None
    source_id: str
    is_table: bool = False
    table_index: int | None = None
    payload: str | None = None


@dataclass
class TokenUnit:
    text: str
    source_index: int


def flatten_numbers(values: Any) -> list[float]:
    nums: list[float] = []
    if isinstance(values, (int, float)):
        nums.append(float(values))
    elif isinstance(values, list):
        for item in values:
            nums.extend(flatten_numbers(item))
    elif isinstance(values, dict):
        for item in values.values():
            nums.extend(flatten_numbers(item))
    return nums


def normalize_bbox(value: Any) -> tuple[float, float, float, float] | None:
    nums = flatten_numbers(value)
    if len(nums) < 4:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def merge_bbox(bboxes: list[tuple[float, float, float, float] | None]) -> tuple[float, float, float, float] | None:
    valid = [b for b in bboxes if b is not None]
    if not valid:
        return None
    return (
        min(b[0] for b in valid),
        min(b[1] for b in valid),
        max(b[2] for b in valid),
        max(b[3] for b in valid),
    )


def clean_text(text: str) -> str:
    # Remove markdown image references from extracted text.
    text = MARKDOWN_IMAGE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_content_list_json(mineru_dir: Path) -> Path:
    enriched_candidates = sorted(mineru_dir.glob("*_content_list.json"))
    if enriched_candidates:
        return enriched_candidates[0]

    explicit = mineru_dir / "content_list.json"
    if explicit.exists():
        return explicit
    candidates = sorted(mineru_dir.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(f"No JSON file found in {mineru_dir}")
    for c in candidates:
        if "content_list" in c.name.lower():
            return c
    for c in candidates:
        if "content" in c.name.lower():
            return c
    return candidates[0]


def is_probably_table_block(block: dict[str, Any]) -> bool:
    keys = {k.lower() for k in block.keys()}
    if "table" in " ".join(keys):
        return True
    block_type = str(block.get("type", "")).lower()
    if "table" in block_type:
        return True
    text = str(block.get("text", ""))
    if "|" in text and text.count("|") >= 4:
        return True
    return False


def extract_table_content(block: dict[str, Any]) -> str:
    # Prefer raw table HTML so merged text stores table content only, not full JSON.
    table_body = block.get("table_body")
    if isinstance(table_body, str) and table_body.strip():
        return clean_text(table_body)

    markdown = block.get("markdown")
    if isinstance(markdown, str) and markdown.strip():
        return clean_text(markdown)

    text = block.get("text")
    if isinstance(text, str) and text.strip():
        return clean_text(text)

    return ""


def extract_lines_from_json(json_obj: Any, source_id: str) -> list[MiniChunk]:
    mini_chunks: list[MiniChunk] = []
    table_index = 0

    if isinstance(json_obj, dict) and isinstance(json_obj.get("content_list"), list):
        blocks = json_obj["content_list"]
    elif isinstance(json_obj, dict) and isinstance(json_obj.get("content"), list):
        blocks = json_obj["content"]
    elif isinstance(json_obj, dict) and isinstance(json_obj.get("blocks"), list):
        blocks = json_obj["blocks"]
    elif isinstance(json_obj, list):
        blocks = json_obj
    else:
        blocks = [json_obj] if isinstance(json_obj, dict) else []

    for block_idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue

        item_source_id = str(block.get("chunk_id") or f"{source_id}:{block_idx}")
        bbox = normalize_bbox(block.get("bbox") or block.get("box") or block.get("position") or block.get("poly"))

        if is_probably_table_block(block):
            table_text = extract_table_content(block)
            mini_chunks.append(MiniChunk(
                text=f"[[TABLE:{table_index}]]",
                bbox=bbox,
                source_id=item_source_id,
                is_table=True,
                table_index=table_index,
                payload=table_text,
            ))
            table_index += 1
            continue

        raw_text = block.get("text")
        if isinstance(raw_text, str) and raw_text.strip():
            lines = [clean_text(ln) for ln in raw_text.splitlines()]
            lines = [ln for ln in lines if ln]
            for line in lines:
                mini_chunks.append(MiniChunk(text=line, bbox=bbox, source_id=item_source_id))
            continue

        lines_field = block.get("lines")
        if isinstance(lines_field, list):
            for ln in lines_field:
                if isinstance(ln, dict):
                    txt = clean_text(str(ln.get("text", "")))
                    lbbox = normalize_bbox(ln.get("bbox") or ln.get("box") or ln.get("poly") or block.get("bbox"))
                else:
                    txt = clean_text(str(ln))
                    lbbox = bbox
                if txt:
                    mini_chunks.append(MiniChunk(text=txt, bbox=lbbox, source_id=item_source_id))

    return mini_chunks


def table_payload_map(minis: list[MiniChunk]) -> dict[int, str]:
    return {m.table_index: m.payload or "" for m in minis if m.is_table and m.table_index is not None}


def mini_chunks_to_tokens(minis: list[MiniChunk]) -> list[TokenUnit]:
    tokens: list[TokenUnit] = []
    for i, mini in enumerate(minis):
        if mini.is_table and mini.table_index is not None:
            tokens.append(TokenUnit(text=f"[[TABLE:{mini.table_index}]]", source_index=i))
            continue
        for word in mini.text.split():
            tokens.append(TokenUnit(text=word, source_index=i))
    return tokens


def build_ranges(total_words: int, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    if total_words == 0:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    ranges: list[tuple[int, int]] = []
    start = 0
    step = chunk_size - overlap
    while start < total_words:
        end = min(start + chunk_size, total_words)
        ranges.append((start, end))
        if end == total_words:
            break
        start += step
    return ranges


def restore_tables(text: str, table_map: dict[int, str]) -> tuple[str, bool, int]:
    has_table = False
    table_count = 0

    def replacer(match: re.Match[str]) -> str:
        nonlocal has_table, table_count
        has_table = True
        table_count += 1
        idx = int(match.group("idx"))
        payload = table_map.get(idx, "")
        return payload

    restored = TABLE_TOKEN_RE.sub(replacer, text)
    return restored, has_table, table_count


def chunk_from_json(json_path: Path, source_id: str, output_path: Path) -> None:
    if output_path.exists():
        logger.info("Skipping %s because chunk output already exists: %s", source_id, output_path)
        return

    data = json.loads(json_path.read_text(encoding="utf-8"))
    minis = extract_lines_from_json(data, source_id)
    table_map = table_payload_map(minis)
    tokens = mini_chunks_to_tokens(minis)

    ranges = build_ranges(len(tokens), WORD_CHUNK_SIZE, WORD_OVERLAP)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as fh:
        for idx, (start, end) in enumerate(ranges):
            slice_tokens = tokens[start:end]
            text = " ".join(t.text for t in slice_tokens)
            source_indices = sorted({t.source_index for t in slice_tokens})
            source_minis = [minis[i] for i in source_indices]
            bbox = merge_bbox([m.bbox for m in source_minis])
            source_ids = sorted({m.source_id for m in source_minis})

            restored_text, has_table, table_count = restore_tables(text, table_map)
            record = {
                "chunk_id": f"{source_id}:{idx}",
                "source_id": source_ids,
                "text": restored_text,
                "has_table": has_table,
                "bbox": (
                    {
                        "x_min": bbox[0],
                        "y_min": bbox[1],
                        "x_max": bbox[2],
                        "y_max": bbox[3],
                    }
                    if bbox
                    else None
                ),
                "meta": {
                    "order": idx,
                    "mini_chunk_count": len(source_indices),
                    "table_count": table_count,
                    "word_count_effective": len(slice_tokens),
                    "chunk_size": WORD_CHUNK_SIZE,
                    "overlap": WORD_OVERLAP,
                },
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Saved %d chunks for %s to %s", len(ranges), source_id, output_path)


def process_all(mineru_root: Path, chunk_root: Path, target_file: str | None = None) -> None:
    target_source = Path(target_file).stem if target_file else None

    for dir_entry in sorted(mineru_root.iterdir()):
        if not dir_entry.is_dir():
            continue
        source_id = dir_entry.name
        if target_source and source_id != target_source:
            continue
        json_path = find_content_list_json(dir_entry)
        output_path = chunk_root / f"{source_id}.jsonl"
        chunk_from_json(json_path, source_id, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk MinerU JSON output into overlap chunks with bbox metadata.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--mineru-dir", default=default_mineru_dir())
    parser.add_argument("--chunk-dir", default=default_chunk_dir())
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    process_all(Path(args.mineru_dir), Path(args.chunk_dir), args.file)


if __name__ == "__main__":
    main()
