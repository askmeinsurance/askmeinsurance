from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from utils import create_gemini_client_from_env, default_embedding_dir, default_metadata_dir, find_jsonl_files, load_jsonl, save_json_atomic

logger = logging.getLogger(__name__)

MODEL = "gemini-embedding-001"
MODEL_RESOURCE = f"models/{MODEL}"
DIMENSION = 1536
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}

DEFAULT_COLLECTION = "product_summary_test"
DEFAULT_BATCH_SIZE = 64
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_POLL_TIMEOUT_SECONDS = 900

_UUID_NAMESPACE = uuid.NAMESPACE_DNS


def default_collection() -> str:
    return os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_api_key_from_env() -> str:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in existing .env file")
    return api_key


def load_qdrant_client_from_env() -> QdrantClient:
    load_dotenv()
    url = os.getenv("QDRANT_URL", "").strip()
    if not url:
        raise ValueError("QDRANT_URL is not set in existing .env file")
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
    return QdrantClient(url=url, api_key=api_key, timeout=60)


def load_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        return {"jobs": {}}
    with registry_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry_path: Path, payload: dict[str, Any]) -> None:
    save_json_atomic(registry_path, payload)


def _text_for_embedding(row: dict[str, Any]) -> str:
    combined_text = row.get("combined_text")
    if isinstance(combined_text, str) and combined_text.strip():
        return combined_text
    text = row.get("text")
    if isinstance(text, str):
        return text
    return ""


def make_inline_requests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requests_payload: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        text = _text_for_embedding(row)
        requests_payload.append(
            {
                "request": {
                    "model": MODEL_RESOURCE,
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": DIMENSION,
                },
                "metadata": {
                    "index": idx,
                    "chunk_id": row.get("chunk_id"),
                    "source": row.get("source_id"),
                },
            }
        )
    return requests_payload


def submit_batch(api_key: str, source_id: str, inline_requests: list[dict[str, Any]]) -> dict[str, Any]:
    url = f"{API_BASE}/{MODEL_RESOURCE}:asyncBatchEmbedContent"
    body = {
        "batch": {
            "displayName": f"{source_id}-{utc_now_iso()}",
            "inputConfig": {
                "requests": {
                    "requests": inline_requests,
                }
            },
        }
    }
    resp = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Batch submit failed ({resp.status_code}): {resp.text}")
    return resp.json()


def get_batch(api_key: str, job_name: str) -> dict[str, Any]:
    url = f"{API_BASE}/{job_name}"
    resp = requests.get(url, headers={"x-goog-api-key": api_key}, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"Batch get failed ({resp.status_code}) for {job_name}: {resp.text}")
    return resp.json()


def poll_until_terminal(api_key: str, job_name: str, poll_interval: int, poll_timeout: int) -> dict[str, Any]:
    start = time.time()
    last_state: str | None = None
    poll_count = 0
    while True:
        batch = get_batch(api_key, job_name)
        state = _batch_state(batch)
        poll_count += 1
        elapsed = int(time.time() - start)
        if state != last_state or poll_count % 6 == 0:
            logger.info("Polling job %s: state=%s elapsed=%ss", job_name, state or "UNKNOWN", elapsed)
            last_state = state
        if state in TERMINAL_STATES:
            return batch

        elapsed = time.time() - start
        if elapsed > poll_timeout:
            raise TimeoutError(f"Timed out waiting for Gemini batch {job_name}; last state={state}")
        time.sleep(max(1, poll_interval))


def parse_jsonl_embed_responses(raw_text: str) -> list[dict[str, Any]]:
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _batch_output(batch: dict[str, Any]) -> dict[str, Any]:
    output = batch.get("output")
    if isinstance(output, dict):
        return output

    metadata = batch.get("metadata")
    if isinstance(metadata, dict):
        metadata_output = metadata.get("output")
        if isinstance(metadata_output, dict):
            return metadata_output
    return {}


def _batch_state(batch: dict[str, Any]) -> str:
    state = str(batch.get("state", "")).upper()
    if state:
        return state

    # Gemini may return completed batch responses with output nested under metadata
    # and without top-level state.
    if _batch_output(batch):
        return "JOB_STATE_SUCCEEDED"
    return "JOB_STATE_UNSPECIFIED"


def extract_embeddings_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata", {})
        resp = row.get("response")
        err = row.get("error")
        if err is not None:
            extracted.append({"metadata": metadata, "error": err})
            continue

        values = None
        if isinstance(resp, dict):
            embedding_obj = resp.get("embedding")
            if isinstance(embedding_obj, dict):
                values = embedding_obj.get("values")

        extracted.append({"metadata": metadata, "embedding": values})
    return extracted


def download_batch_extracted_embeddings(
    gemini_client: genai.Client,
    batch: dict[str, Any],
    output_raw_path: Path,
) -> list[dict[str, Any]]:
    output = _batch_output(batch)

    responses_file = output.get("responsesFile")
    if responses_file:
        raw_bytes = gemini_client.files.download(file=responses_file)
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = raw_bytes.decode("utf-8", errors="replace")
        output_raw_path.parent.mkdir(parents=True, exist_ok=True)
        output_raw_path.write_text(raw_text, encoding="utf-8")
        rows = parse_jsonl_embed_responses(raw_text)
        return extract_embeddings_from_rows(rows)

    inlined = output.get("inlinedResponses")
    if isinstance(inlined, dict):
        output_raw_path.parent.mkdir(parents=True, exist_ok=True)
        save_json_atomic(output_raw_path, inlined)
        inlined_rows = inlined.get("inlinedResponses")
        if isinstance(inlined_rows, list):
            return extract_embeddings_from_rows(inlined_rows)

    raise RuntimeError("No responsesFile or inlinedResponses found for successful Gemini batch")


def _is_numeric_embedding(values: Any) -> bool:
    if not isinstance(values, list) or len(values) != DIMENSION:
        return False
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)


def build_embedding_output(
    source_id: str,
    source_rows: list[dict[str, Any]],
    extracted: list[dict[str, Any]],
    job_name: str,
) -> dict[str, Any]:
    by_index: dict[int, dict[str, Any]] = {}
    for i, item in enumerate(extracted):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        idx = metadata.get("index")
        if isinstance(idx, int):
            by_index[idx] = item
        else:
            by_index[i] = item

    records: list[dict[str, Any]] = []
    policy_id = _derive_policy_id(source_id)
    for idx, row in enumerate(source_rows):
        found = by_index.get(idx, {})
        records.append(
            {
                "chunk_id": row.get("chunk_id"),
                "source_id": source_id,
                "policy_id": policy_id,
                "text": row.get("text"),
                "combined_text": row.get("combined_text"),
                "context": row.get("context"),
                "chapter": row.get("chapter"),
                "header": row.get("header"),
                "level": row.get("level"),
                "source_chunk_ids": row.get("source_chunk_ids", []),
                "has_table": row.get("has_table", False),
                "document_metadata": row.get("document_metadata"),
                "embedding": found.get("embedding"),
                "error": found.get("error"),
            }
        )

    return {
        "source_id": source_id,
        "model": MODEL,
        "dimension": DIMENSION,
        "job_name": job_name,
        "generated_at": utc_now_iso(),
        "record_count": len(records),
        "successful_embeddings": sum(1 for r in records if _is_numeric_embedding(r.get("embedding"))),
        "records": records,
    }


def ensure_collection(client: QdrantClient, collection: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=DIMENSION, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection %s", collection)

    for field, schema_type in [
        ("chunk_id", PayloadSchemaType.KEYWORD),
        ("source_id", PayloadSchemaType.KEYWORD),
        ("policy_id", PayloadSchemaType.KEYWORD),
        ("chapter", PayloadSchemaType.KEYWORD),
    ]:
        try:
            client.create_payload_index(collection_name=collection, field_name=field, field_schema=schema_type)
        except Exception as exc:
            logger.debug("Payload index for %s may already exist: %s", field, exc)


def _chunk_id_to_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_UUID_NAMESPACE, chunk_id))


def _batched(items: list[dict[str, Any]], batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def _derive_policy_id(value: Any) -> str | None:
    # Strips file extension if present; otherwise returns the value unchanged.
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return Path(value).stem


def _normalize_row_for_upsert(row: dict[str, Any]) -> dict[str, Any] | None:
    chunk_id = row.get("chunk_id")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        return None

    embedding = row.get("embedding")
    if not _is_numeric_embedding(embedding):
        return None

    text = row.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    source_chunk_ids = row.get("source_chunk_ids")
    if not isinstance(source_chunk_ids, list):
        source_chunk_ids = []

    has_table = row.get("has_table")
    if not isinstance(has_table, bool):
        has_table = False

    policy_id = _derive_policy_id(row.get("policy_id")) or _derive_policy_id(row.get("source_id"))

    return {
        "chunk_id": chunk_id.strip(),
        "embedding": embedding,
        "payload": {
            "chunk_id": chunk_id.strip(),
            "source_id": row.get("source_id"),
            "policy_id": policy_id,
            "text": text,
            "combined_text": row.get("combined_text"),
            "context": row.get("context"),
            "chapter": row.get("chapter"),
            "header": row.get("header"),
            "level": row.get("level"),
            "source_chunk_ids": source_chunk_ids,
            "has_table": has_table,
            "document_metadata": row.get("document_metadata"),
        },
    }


def upsert_embeddings(client: QdrantClient, collection: str, embedding_rows: list[dict[str, Any]], batch_size: int) -> int:
    valid_rows = [r for r in (_normalize_row_for_upsert(row) for row in embedding_rows) if r is not None]
    if not valid_rows:
        return 0

    upserted = 0
    for batch in _batched(valid_rows, batch_size):
        points = [
            PointStruct(
                id=_chunk_id_to_point_id(row["chunk_id"]),
                vector=row["embedding"],
                payload=row["payload"],
            )
            for row in batch
        ]
        client.upsert(collection_name=collection, points=points, timeout=120)
        upserted += len(points)
    return upserted


def submit_batch_job_if_needed(
    input_path: Path,
    output_root: Path,
    registry_path: Path,
    registry: dict[str, Any],
    api_key: str,
    force: bool,
) -> None:
    source_id = input_path.stem
    output_path = output_root / f"{source_id}.json"
    jobs = registry.setdefault("jobs", {})
    existing = jobs.get(source_id, {}) if isinstance(jobs.get(source_id), dict) else {}

    # Existing finalized output can be reused; no need to submit another batch unless forced.
    if output_path.exists() and not force:
        return

    job_entry: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    job_name = job_entry.get("job_name")
    state = str(job_entry.get("state", "")).upper()

    should_submit = force or not isinstance(job_name, str) or not job_name
    if not should_submit and state in {"JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}:
        should_submit = True

    if not should_submit:
        logger.info("Existing Gemini batch for %s: %s state=%s", source_id, job_name, state or "UNKNOWN")
        return

    source_rows = load_jsonl(input_path)
    inline_requests = make_inline_requests(source_rows)
    submitted = submit_batch(api_key, source_id, inline_requests)
    job_name = submitted.get("name")
    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError(f"No batch job name returned for {source_id}: {submitted}")

    jobs[source_id] = {
        "source_id": source_id,
        "source_file": str(input_path),
        "submitted_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "model": MODEL,
        "dimension": DIMENSION,
        "job_name": job_name,
        "state": str(submitted.get("state", "JOB_STATE_UNSPECIFIED")),
        "raw_submit_response": submitted,
    }
    save_registry(registry_path, registry)
    logger.info("Submitted new Gemini batch for %s: %s", source_id, job_name)


def process_file(
    input_path: Path,
    output_root: Path,
    raw_root: Path,
    registry_path: Path,
    registry: dict[str, Any],
    api_key: str,
    gemini_client: genai.Client,
    qdrant_client: QdrantClient,
    collection: str,
    batch_size: int,
    force: bool,
    poll_interval: int,
    poll_timeout: int,
) -> None:
    source_id = input_path.stem
    output_path = output_root / f"{source_id}.json"
    jobs = registry.setdefault("jobs", {})
    existing = jobs.get(source_id, {}) if isinstance(jobs.get(source_id), dict) else {}

    if output_path.exists() and not force:
        if existing.get("qdrant_upserted") and existing.get("qdrant_collection") == collection:
            logger.info("Skipping upsert for %s — already upserted to %s", source_id, collection)
            return
        output_doc = json.loads(output_path.read_text(encoding="utf-8"))
        rows = output_doc.get("records") if isinstance(output_doc.get("records"), list) else []
        upserted = upsert_embeddings(qdrant_client, collection, rows, batch_size)
        existing.update(
            {
                "state": "JOB_STATE_SUCCEEDED",
                "final_output_path": str(output_path),
                "qdrant_collection": collection,
                "qdrant_upserted": upserted,
                "qdrant_upserted_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            }
        )
        jobs[source_id] = existing
        logger.info("Reused existing embeddings for %s and upserted=%d", source_id, upserted)
        return

    source_rows = load_jsonl(input_path)
    job_entry: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    job_name = job_entry.get("job_name")

    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError(
            f"Missing job_name for {source_id} in embedding registry. "
            "Run submit phase first (or use --force)."
        )

    logger.info("Begin polling for %s (job=%s)", source_id, job_name)
    batch = poll_until_terminal(api_key, job_name, poll_interval, poll_timeout)
    state = _batch_state(batch)
    job_entry["state"] = state
    job_entry["updated_at"] = utc_now_iso()
    logger.info("Polling complete for %s (job=%s) with state=%s", source_id, job_name, state)

    raw_job_path = raw_root / f"{source_id}__job.json"
    save_json_atomic(raw_job_path, batch)
    job_entry["raw_job_path"] = str(raw_job_path)

    if state != "JOB_STATE_SUCCEEDED":
        job_entry["terminal_error"] = batch.get("error")
        jobs[source_id] = job_entry
        raise RuntimeError(f"Gemini batch did not succeed for {source_id}: state={state}")

    raw_response_path = raw_root / f"{source_id}__responses.jsonl"
    extracted = download_batch_extracted_embeddings(
        gemini_client=gemini_client,
        batch=batch,
        output_raw_path=raw_response_path,
    )

    final_doc = build_embedding_output(source_id, source_rows, extracted, job_name)
    save_json_atomic(output_path, final_doc)

    upserted = upsert_embeddings(qdrant_client, collection, final_doc["records"], batch_size)

    job_entry.update(
        {
            "raw_responses_path": str(raw_response_path),
            "final_output_path": str(output_path),
            "successful_embeddings": final_doc.get("successful_embeddings", 0),
            "completed_at": utc_now_iso(),
            "qdrant_collection": collection,
            "qdrant_upserted": upserted,
            "qdrant_upserted_at": utc_now_iso(),
        }
    )
    jobs[source_id] = job_entry
    logger.info(
        "Saved embeddings for %s to %s and upserted=%d to %s",
        source_id,
        output_path,
        upserted,
        collection,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Gemini embeddings (batch mode) from metadata chunks, save locally, then upsert to Qdrant."
    )
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_metadata_dir())
    parser.add_argument("--output-dir", default=default_embedding_dir())
    parser.add_argument("--collection", default=default_collection())
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--poll-timeout-seconds", type=int, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.poll_interval_seconds <= 0:
        raise ValueError("--poll-interval-seconds must be > 0")
    if args.poll_timeout_seconds <= 0:
        raise ValueError("--poll-timeout-seconds must be > 0")

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    raw_root = output_root / "raw_jobs"
    registry_path = output_root / "batch_jobs.json"
    output_root.mkdir(parents=True, exist_ok=True)

    files = find_jsonl_files(input_root, args.file)
    if not files:
        logger.warning("No input files found in %s", input_root)
        return

    api_key = load_api_key_from_env()
    gemini_client = create_gemini_client_from_env()
    qdrant_client = load_qdrant_client_from_env()

    registry = load_registry(registry_path)
    save_registry(registry_path, registry)
    try:
        ensure_collection(qdrant_client, args.collection)
        # Phase 1: submit all missing/invalid jobs first so they can run concurrently in Gemini.
        for input_path in files:
            submit_batch_job_if_needed(
                input_path=input_path,
                output_root=output_root,
                registry_path=registry_path,
                registry=registry,
                api_key=api_key,
                force=args.force,
            )
            save_registry(registry_path, registry)

        # Phase 2: poll and finalize each file.
        for input_path in files:
            process_file(
                input_path=input_path,
                output_root=output_root,
                raw_root=raw_root,
                registry_path=registry_path,
                registry=registry,
                api_key=api_key,
                gemini_client=gemini_client,
                qdrant_client=qdrant_client,
                collection=args.collection,
                batch_size=args.batch_size,
                force=args.force,
                poll_interval=args.poll_interval_seconds,
                poll_timeout=args.poll_timeout_seconds,
            )
            save_registry(registry_path, registry)
    finally:
        qdrant_client.close()


if __name__ == "__main__":
    main()
