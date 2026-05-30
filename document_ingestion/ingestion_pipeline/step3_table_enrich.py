from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from utils import GENERATION_MODEL, create_gemini_client_from_env, default_chunk_dir, default_table_dir, find_jsonl_files, is_retryable_api_error, strip_json_fences

logger = logging.getLogger(__name__)

TABLE_BLOCK_RE = re.compile(r"<table[\s\S]*?</table>", flags=re.IGNORECASE)


def parse_html_to_grid(html: str) -> list[list[str]] | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            return []

        rows = table.find_all("tr")
        if not rows:
            return []

        occupied: dict[tuple[int, int], str] = {}

        for r_idx, row in enumerate(rows):
            cells = row.find_all(["td", "th"])
            c_idx = 0
            for cell in cells:
                while (r_idx, c_idx) in occupied:
                    c_idx += 1

                rowspan = max(1, int(cell.get("rowspan", 1)))
                colspan = max(1, int(cell.get("colspan", 1)))
                text = cell.get_text(strip=True)

                occupied[(r_idx, c_idx)] = text
                for dr in range(rowspan):
                    for dc in range(colspan):
                        if dr == 0 and dc == 0:
                            continue
                        occupied[(r_idx + dr, c_idx + dc)] = ""

                c_idx += colspan

        if not occupied:
            return []

        max_row = max(r for r, _ in occupied) + 1
        max_col = max(c for _, c in occupied) + 1

        return [[occupied.get((r, c), "") for c in range(max_col)] for r in range(max_row)]
    except Exception as exc:
        logger.warning("HTML parse error: %s", exc)
        return None


def _is_single_spanning_title(row: list[str]) -> bool:
    nonempty = [c for c in row if c]
    return len(row) >= 2 and len(nonempty) == 1


def _row_is_data(row: list[str]) -> bool:
    for cell in row:
        if not cell:
            continue
        if re.search(r"\$\d", cell):
            return True
        if re.search(r"\d+\.?\d*%", cell):
            return True
        if len(cell) > 45:
            return True
    return False


def _all_distinct(values: list[str]) -> bool:
    return len(values) == len(set(values))


def _try_extract_row_headers(structure: dict[str, Any], data_body: list[list[str]], *, strip_first_col: bool) -> None:
    if not data_body:
        structure["data_rows"] = []
        return
    row_h_candidate = [r[0] for r in data_body if r]
    if row_h_candidate and all(row_h_candidate) and _all_distinct(row_h_candidate):
        structure["row_headers"] = row_h_candidate
        structure["data_rows"] = [r[1:] for r in data_body] if strip_first_col else data_body
    else:
        structure["data_rows"] = [r[1:] for r in data_body] if strip_first_col else data_body


def detect_structure(grid: list[list[str]]) -> dict[str, Any]:
    structure: dict[str, Any] = {
        "spanning_title": None,
        "col_headers": None,
        "row_headers": None,
        "data_rows": [],
    }

    if not grid:
        return structure

    working = [row[:] for row in grid]

    if len(working) > 1 and _is_single_spanning_title(working[0]):
        structure["spanning_title"] = next(c for c in working[0] if c)
        working = working[1:]

    if not working:
        return structure

    if structure["spanning_title"] is not None and _row_is_data(working[0]):
        structure["data_rows"] = working
        return structure

    first_row = working[0]

    if first_row[0] == "" and any(c for c in first_row[1:]):
        structure["col_headers"] = first_row[1:]
        data_body = working[1:]
        _try_extract_row_headers(structure, data_body, strip_first_col=True)
    elif all(c for c in first_row):
        data_body = working[1:]
        if data_body:
            row_h_candidate = [r[0] for r in data_body if r]
            if row_h_candidate and all(row_h_candidate) and _all_distinct(row_h_candidate):
                structure["col_headers"] = first_row[1:]
                structure["row_headers"] = row_h_candidate
                structure["data_rows"] = [r[1:] for r in data_body]
            else:
                structure["col_headers"] = first_row
                structure["data_rows"] = data_body
        else:
            structure["col_headers"] = first_row
    else:
        structure["data_rows"] = working

    return structure


def classify_archetype(structure: dict[str, Any]) -> str:
    col_headers: list[str] = structure.get("col_headers") or []
    row_headers: list[str] = structure.get("row_headers") or []
    data_rows: list[list[str]] = structure.get("data_rows") or []
    spanning_title = structure.get("spanning_title")

    col_lower = [c.lower() for c in col_headers]

    if any(re.match(r"^(19|20)\d{2}$", c.strip()) for c in col_headers):
        return "historical_performance"

    if any("target" in c for c in col_lower) and any("current" in c for c in col_lower):
        return "asset_allocation"

    if spanning_title and data_rows:
        numeric_rows = sum(1 for row in data_rows if any(re.match(r"^\d+$", cell.strip()) for cell in row if cell))
        if numeric_rows >= 3:
            return "benefit_schedule"

    plan_kw = ["pay", "plan", "option"]
    if col_headers and any(any(kw in h.lower() for kw in plan_kw) for h in col_headers):
        return "plan_comparison"

    if row_headers and all(re.match(r"^\d+$", rh.strip()) for rh in row_headers):
        return "rate_table"

    return "unknown"


def assign_parse_tier(structure: dict[str, Any], archetype: str) -> int:
    has_headers = structure.get("col_headers") is not None or structure.get("row_headers") is not None
    if archetype != "unknown" and has_headers:
        return 1
    if has_headers:
        return 2
    return 3


def build_hierarchical_json(table_id: str, grid: list[list[str]], structure: dict[str, Any], archetype: str, parse_tier: int) -> dict[str, Any]:
    col_headers: list[str] | None = structure.get("col_headers")
    row_headers: list[str] | None = structure.get("row_headers")
    data_rows: list[list[str]] = structure.get("data_rows") or []
    spanning_title: str | None = structure.get("spanning_title")

    result: dict[str, Any] = {
        "table_id": table_id,
        "table_type": archetype,
        "parse_tier": parse_tier,
        "caption": "",
        "footnotes": [],
        "raw_grid": grid,
    }

    if spanning_title:
        result["spanning_title"] = spanning_title

    if col_headers is not None:
        result["headers"] = {
            "column_headers": col_headers,
            "row_headers": row_headers or [],
        }

        rows_out = []
        for r_idx, row in enumerate(data_rows):
            row_header = row_headers[r_idx] if row_headers and r_idx < len(row_headers) else f"row_{r_idx}"
            cells = []
            for c_idx, value in enumerate(row):
                col_header = col_headers[c_idx] if col_headers and c_idx < len(col_headers) else f"col_{c_idx}"
                cells.append({"column_header": col_header, "value": value})
            rows_out.append({"row_header": row_header, "cells": cells})

        result["rows"] = rows_out

    return result


_KNOWN_PURPOSE_PROMPT = """You are an expert at reading insurance product tables and writing clear, grounded sentences.

## Surrounding document context
{context}

## Table (hierarchical JSON)
{hierarchical_json}

## Footnotes
None

## Table type hint
{table_type}

## Task
Analyse the table and return a JSON object with exactly these fields:

{{
  "purpose": "<one of: compare_options | show_schedule | show_allocation | show_performance | define_benefit | disclaimer | unknown>",
  "dimensions": {{
    "row": "<what each row represents>",
    "col": "<what each column represents>",
    "value": "<what the cell values represent>"
  }},
  "narrative": ["<sentence 1>", "<sentence 2>"]
}}

Return only the JSON object.
"""

_OPEN_ENDED_PROMPT = """You are an expert at reading insurance product tables and writing clear, grounded sentences.

## Surrounding document context
{context}

## Table data
{table_data}

## Footnotes
None

## Task
Return a JSON object:
{{
  "purpose": "<compare_options | show_schedule | show_allocation | show_performance | define_benefit | disclaimer | unknown>",
  "dimensions": {{
    "row": "<description>",
    "col": "<description>",
    "value": "<description>"
  }},
  "narrative": ["<sentence>", ...]
}}

Return only the JSON object.
"""


def _extract_context(text: str) -> str:
    return TABLE_BLOCK_RE.sub("[TABLE]", text).strip()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=5, max=60), retry=retry_if_exception(is_retryable_api_error), reraise=True)
def _generate(client: genai.Client, prompt: str, model: str) -> str:
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text.strip()


def _call_llm(client: genai.Client, prompt: str, model: str) -> dict[str, Any] | None:
    try:
        raw = _generate(client, prompt, model)
        raw = strip_json_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed.get("narrative"), list):
            return parsed
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
    return None


def generate_narrative(chunk_text: str, hierarchical_json: dict[str, Any], client: genai.Client, model: str) -> dict[str, Any]:
    parse_tier = hierarchical_json.get("parse_tier", 4)
    table_type = hierarchical_json.get("table_type", "unknown")
    context = _extract_context(chunk_text)

    result = None
    if parse_tier == 1 and table_type != "unknown":
        prompt = _KNOWN_PURPOSE_PROMPT.format(
            context=context,
            hierarchical_json=json.dumps(hierarchical_json, ensure_ascii=False, indent=2),
            table_type=table_type,
        )
        result = _call_llm(client, prompt, model)

    if result is None:
        table_data = json.dumps(hierarchical_json if hierarchical_json.get("rows") else hierarchical_json.get("raw_grid", []), ensure_ascii=False, indent=2)
        prompt = _OPEN_ENDED_PROMPT.format(context=context, table_data=table_data)
        result = _call_llm(client, prompt, model)

    if result is None:
        return {"purpose": "unknown", "dimensions": {}, "narrative": []}

    return result


def process_one_table(table_html: str, table_id: str, chunk_text: str, client: genai.Client, model: str) -> tuple[dict[str, Any], dict[str, Any], bool]:
    grid = parse_html_to_grid(table_html)

    if grid is None:
        hier = {
            "table_id": table_id,
            "table_type": "unknown",
            "parse_tier": 4,
            "caption": "",
            "footnotes": [],
            "raw_grid": [[table_html]],
        }
        narr = {"purpose": "unknown", "dimensions": {}, "narrative": []}
        return hier, narr, False

    if not grid:
        hier = {
            "table_id": table_id,
            "table_type": "unknown",
            "parse_tier": 4,
            "caption": "",
            "footnotes": [],
            "raw_grid": [],
        }
        narr = {"purpose": "unknown", "dimensions": {}, "narrative": []}
        return hier, narr, False

    structure = detect_structure(grid)
    archetype = classify_archetype(structure)
    parse_tier = assign_parse_tier(structure, archetype)
    hier = build_hierarchical_json(table_id, grid, structure, archetype, parse_tier)

    narr = generate_narrative(chunk_text, hier, client, model)
    ok = len(narr.get("narrative", [])) > 0 or narr.get("purpose") != "unknown"
    return hier, narr, ok


def replacement_text(hierarchical_json: dict[str, Any], table_narrative: dict[str, Any]) -> str:
    hier_min = json.dumps(hierarchical_json, ensure_ascii=False, separators=(",", ":"))
    narr_min = json.dumps(table_narrative, ensure_ascii=False, separators=(",", ":"))
    return f"hierarchical_json = {hier_min}\ntable_narrative={narr_min}"


def enrich_record(record: dict[str, Any], source_id: str, record_idx: int, client: genai.Client, model: str) -> dict[str, Any]:
    text = str(record.get("text", ""))
    tables = list(TABLE_BLOCK_RE.finditer(text))
    if not tables:
        return record

    new_text_parts: list[str] = []
    cursor = 0
    table_failures = 0

    for table_idx, match in enumerate(tables):
        start, end = match.span()
        table_html = match.group(0)
        table_id = f"{source_id}:{record_idx}:table:{table_idx}"

        hier, narr, ok = process_one_table(table_html, table_id, text, client, model)
        if not ok:
            table_failures += 1

        new_text_parts.append(text[cursor:start])
        new_text_parts.append(replacement_text(hier, narr))
        cursor = end

    new_text_parts.append(text[cursor:])

    enriched = dict(record)
    enriched["text"] = "".join(new_text_parts)

    meta = dict(enriched.get("meta") or {})
    meta["table_enrich_count"] = len(tables)
    meta["table_enrich_failures"] = table_failures
    enriched["meta"] = meta
    return enriched


def enrich_file(input_path: Path, output_path: Path, client: genai.Client, model: str) -> None:
    if output_path.exists():
        logger.info("Skipping %s because output already exists: %s", input_path.stem, output_path)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as in_f, output_path.open("w", encoding="utf-8") as out_f:
        for idx, line in enumerate(in_f):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            enriched = enrich_record(record, input_path.stem, idx, client, model)
            out_f.write(json.dumps(enriched, ensure_ascii=False) + "\n")

    logger.info("Saved enriched chunks for %s to %s", input_path.stem, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Step-2 chunks by replacing table HTML with hierarchical JSON + narrative.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--chunk-dir", default=default_chunk_dir())
    parser.add_argument("--output-dir", default=default_table_dir())
    parser.add_argument("--model", default=GENERATION_MODEL)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    client = create_gemini_client_from_env()
    chunk_root = Path(args.chunk_dir)
    output_root = Path(args.output_dir)

    for input_path in find_jsonl_files(chunk_root, args.file):
        output_path = output_root / input_path.name
        enrich_file(input_path, output_path, client, args.model)


if __name__ == "__main__":
    main()
