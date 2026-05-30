from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai

GENERATION_MODEL = "gemini-2.5-flash-lite"

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def default_input_dir() -> str:
    return os.getenv("INPUT_DIR", "../input")


def default_mineru_dir() -> str:
    return os.getenv("MINERU_OUTPUT_DIR", "output/mineru")


def default_chunk_dir() -> str:
    return os.getenv("CHUNK_OUTPUT_DIR", "output/chunks")


def default_table_dir() -> str:
    return os.getenv("TABLE_ENRICHED_OUTPUT_DIR", "output/chunks_with_tables")


def default_context_dir() -> str:
    return os.getenv("CONTEXT_OUTPUT_DIR", "output/chunks_with_context")


def default_summary_dir() -> str:
    return os.getenv("SUMMARY_OUTPUT_DIR", "output/one_page_summary")


def default_metadata_dir() -> str:
    return os.getenv("METADATA_OUTPUT_DIR", "output/chunks_with_metadata")


def default_document_metadata_dir() -> str:
    return os.getenv("DOCUMENT_METADATA_OUTPUT_DIR", "output/document_metadata")


def default_embedding_dir() -> str:
    return os.getenv("EMBEDDING_OUTPUT_DIR", "output/embeddings")


def strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


def find_jsonl_files(chunk_root: Path, target_file: str | None = None) -> list[Path]:
    target_source = Path(target_file).stem if target_file else None
    files = sorted(chunk_root.glob("*.jsonl"))
    if target_source:
        files = [p for p in files if p.stem == target_source]
    return files


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def create_gemini_client_from_env() -> genai.Client:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in existing .env file")
    return genai.Client(api_key=api_key)


def save_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as out_f:
        json.dump(payload, out_f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def save_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as out_f:
        for row in rows:
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def is_retryable_api_error(exc: BaseException) -> bool:
    message = str(exc)
    return any(code in message for code in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
