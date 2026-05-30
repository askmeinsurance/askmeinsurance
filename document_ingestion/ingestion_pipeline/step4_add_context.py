from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import CreateCachedContentConfig
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from utils import GENERATION_MODEL, create_gemini_client_from_env, default_context_dir, default_mineru_dir, default_table_dir, find_jsonl_files, is_retryable_api_error, load_jsonl, save_jsonl_atomic

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600

CONTEXT_PROMPT = """Here is the chunk we want to situate within the whole document
<chunk>
{chunk_content}
</chunk>
Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

CONTEXT_PROMPT_WITH_FULL_DOC = """Here is the full document:
<document>
{full_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_content}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""


def resolve_full_doc_path(mineru_root: Path, source_id: str) -> Path:
    source_dir = mineru_root / source_id
    primary = source_dir / "full.md"
    if primary.exists():
        return primary

    alternate = source_dir / f"{source_id}.full.md"
    if alternate.exists():
        return alternate

    raise FileNotFoundError(
        f"Full document markdown not found for {source_id}. "
        f"Expected one of: {primary} or {alternate}"
    )


def load_existing_by_chunk_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {str(row["chunk_id"]): row for row in load_jsonl(path) if row.get("chunk_id")}


def chunk_id_for_record(record: dict[str, Any], source_id: str, idx: int) -> str:
    raw = record.get("chunk_id")
    if isinstance(raw, str) and raw.strip():
        return raw
    return f"{source_id}:{idx}"


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(is_retryable_api_error),
    reraise=True,
)
def _generate_context_with_cache(
    client: genai.Client,
    model: str,
    cache_name: str,
    chunk_text: str,
) -> str:
    prompt = CONTEXT_PROMPT.format(chunk_content=chunk_text)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(cached_content=cache_name),
    )
    return (response.text or "").strip()


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(is_retryable_api_error),
    reraise=True,
)
def _generate_context_without_cache(
    client: genai.Client,
    model: str,
    full_doc_text: str,
    chunk_text: str,
) -> str:
    prompt = CONTEXT_PROMPT_WITH_FULL_DOC.format(full_document=full_doc_text, chunk_content=chunk_text)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return (response.text or "").strip()


def _filter_pending(
    rows: list[dict[str, Any]],
    existing: dict[str, dict[str, Any]],
    source_id: str,
) -> list[tuple[int, dict[str, Any], str]]:
    pending: list[tuple[int, dict[str, Any], str]] = []
    for idx, row in enumerate(rows):
        chunk_id = chunk_id_for_record(row, source_id, idx)
        prev = existing.get(chunk_id)
        if prev and isinstance(prev.get("context"), str) and prev.get("context", "").strip():
            continue
        pending.append((idx, row, chunk_id))
    return pending


def _create_cache(
    client: genai.Client,
    model: str,
    full_doc_text: str,
    ttl_seconds: int,
    source_id: str,
) -> tuple[Any, bool]:
    try:
        cache = client.caches.create(
            model=model,
            config=CreateCachedContentConfig(
                contents=[
                    types.Part.from_bytes(
                        data=full_doc_text.encode("utf-8"),
                        mime_type="text/markdown",
                    )
                ],
                ttl=f"{ttl_seconds}s",
                display_name=source_id,
            ),
        )
        return cache, True
    except Exception as exc:
        if "Cached content is too small" in str(exc):
            logger.info("Skipping cache for %s because full document is below cache minimum token threshold.", source_id)
            return None, False
        raise


def _generate_contexts(
    client: genai.Client,
    model: str,
    cache: Any,
    use_cache: bool,
    full_doc_text: str,
    pending: list[tuple[int, dict[str, Any], str]],
) -> dict[str, dict[str, Any]]:
    generated: dict[str, dict[str, Any]] = {}
    try:
        for _, row, chunk_id in pending:
            text = str(row.get("text", ""))
            if use_cache and cache is not None:
                context = _generate_context_with_cache(client, model, cache.name, text)
            else:
                context = _generate_context_without_cache(client, model, full_doc_text, text)
            new_row = dict(row)
            new_row["chunk_id"] = chunk_id
            new_row["context"] = context
            new_row["combined_text"] = f"<context>{context}</context>\n{text}"
            generated[chunk_id] = new_row
    finally:
        if cache is not None:
            try:
                client.caches.delete(name=cache.name)
            except Exception as exc:
                logger.warning("Could not delete cache %s: %s", cache.name, exc)
    return generated


def _merge_ordered(
    rows: list[dict[str, Any]],
    generated: dict[str, dict[str, Any]],
    existing: dict[str, dict[str, Any]],
    source_id: str,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        chunk_id = chunk_id_for_record(row, source_id, idx)
        if chunk_id in generated:
            ordered.append(generated[chunk_id])
            continue

        if chunk_id in existing:
            prev = existing[chunk_id]
            if "combined_text" not in prev:
                prev = dict(prev)
                prev["combined_text"] = f"<context>{prev.get('context', '')}</context>\n{prev.get('text', '')}"
            ordered.append(prev)
            continue

        passthrough = dict(row)
        passthrough["chunk_id"] = chunk_id
        ordered.append(passthrough)
    return ordered


def enrich_file(
    input_path: Path,
    output_path: Path,
    mineru_root: Path,
    client: genai.Client,
    model: str,
    ttl_seconds: int,
    force: bool,
) -> None:
    source_id = input_path.stem
    rows = load_jsonl(input_path)
    if not rows:
        logger.info("Skipping %s because input is empty", source_id)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {} if force else load_existing_by_chunk_id(output_path)
    pending = _filter_pending(rows, existing, source_id)

    if not pending:
        logger.info("Skipping %s because all chunks already have context in %s", source_id, output_path)
        return

    full_doc_path = resolve_full_doc_path(mineru_root, source_id)
    full_doc_text = full_doc_path.read_text(encoding="utf-8")
    cache, use_cache = _create_cache(client, model, full_doc_text, ttl_seconds, source_id)

    logger.info(
        "Processing %s: %d pending chunks (%d already complete)",
        source_id,
        len(pending),
        len(rows) - len(pending),
    )

    generated = _generate_contexts(client, model, cache, use_cache, full_doc_text, pending)
    ordered = _merge_ordered(rows, generated, existing, source_id)

    save_jsonl_atomic(output_path, ordered)
    logger.info("Saved context-enriched chunks for %s to %s", source_id, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add retrieval context to chunks using full-doc cached context.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_table_dir())
    parser.add_argument("--output-dir", default=default_context_dir())
    parser.add_argument("--mineru-dir", default=default_mineru_dir())
    parser.add_argument("--model", default=GENERATION_MODEL)
    parser.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)
    parser.add_argument("--force", action="store_true", help="Recompute context even when output already has rows.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    client = create_gemini_client_from_env()
    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    mineru_root = Path(args.mineru_dir)

    for input_path in find_jsonl_files(input_root, args.file):
        output_path = output_root / input_path.name
        enrich_file(
            input_path=input_path,
            output_path=output_path,
            mineru_root=mineru_root,
            client=client,
            model=args.model,
            ttl_seconds=args.ttl_seconds,
            force=args.force,
        )


if __name__ == "__main__":
    main()
