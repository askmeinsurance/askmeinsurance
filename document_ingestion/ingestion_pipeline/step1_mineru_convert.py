from __future__ import annotations

import argparse
import io
import json
import logging
import os
import random
import time
import zipfile
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

from utils import default_input_dir, default_mineru_dir

# Suppress SSL warnings emitted by the MinerU upload endpoint (uses verify=False).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BATCH_SIZE = 200

logger = logging.getLogger(__name__)


def find_pdfs(input_dir: Path) -> list[Path]:
    return sorted(input_dir.rglob("*.pdf"))


def source_id_from_pdf(pdf_path: Path) -> str:
    return pdf_path.stem


def is_converted(pdf_path: Path, mineru_output_dir: Path) -> bool:
    source_id = source_id_from_pdf(pdf_path)
    out = mineru_output_dir / source_id
    return out.is_dir() and any(out.glob("*.json"))


def find_content_list_input_file(dest_dir: Path) -> Path | None:
    explicit = dest_dir / "content_list.json"
    if explicit.exists():
        return explicit
    candidates = sorted(dest_dir.glob("*_content_list.json"))
    if candidates:
        return candidates[0]
    return None


def get_upload_urls(session: requests.Session, base_url: str, files: list[dict]) -> dict:
    resp = session.post(f"{base_url}/file-urls/batch", json={"files": files})
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise RuntimeError(f"get_upload_urls failed: {body}")
    return body["data"]


def upload_files(files_with_urls: list[dict]) -> None:
    for item in files_with_urls:
        path: Path = item["path"]
        url: str = item["url"]
        logger.info("Uploading %s", path.name)
        with path.open("rb") as fh:
            resp = requests.put(url, data=fh, verify=False, timeout=120)
        resp.raise_for_status()
        time.sleep(random.uniform(0, 2))


def submit_batch(session: requests.Session, base_url: str, batch_id: str, files: list[dict]) -> None:
    resp = session.post(
        f"{base_url}/extract/task/batch",
        json={
            "batch_id": batch_id,
            "files": files,
            "enable_formula": False,
            "enable_table": True,
            "language": "en",
            "model_version": "pipeline",
        },
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise RuntimeError(f"submit_batch failed: {body}")


def poll_batch(session: requests.Session, base_url: str, batch_id: str, interval: int = 10, timeout: int = 1200) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = session.get(f"{base_url}/extract-results/batch/{batch_id}")
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(f"poll_batch error: {body}")
        results = body["data"]["extract_result"]
        running = [
            r for r in results if r.get("state") in {"pending", "running", "converting", "waiting-file"}
        ]
        if not running:
            return results
        logger.info("Batch %s progress: %d/%d pending", batch_id, len(running), len(results))
        time.sleep(interval)
    raise TimeoutError(f"Batch {batch_id} did not complete within {timeout}s")


def download_and_extract(zip_url: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if name.endswith(".json") or name.endswith(".md"):
                dst = dest_dir / Path(name).name
                dst.write_bytes(zf.read(name))
                logger.info("Saved %s", dst)


def create_chunk_id_content_list_file(dest_dir: Path, source_id: str) -> None:
    content_list_path = find_content_list_input_file(dest_dir)
    if content_list_path is None:
        return

    raw = json.loads(content_list_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("content_list"), list):
        items = raw["content_list"]
        wrapped = True
    elif isinstance(raw, list):
        items = raw
        wrapped = False
    else:
        logger.warning("Unexpected content_list schema for %s, skip enriched content list creation", content_list_path)
        return

    enriched_items: list[dict] = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            entry = dict(item)
        else:
            entry = {"value": item}
        entry["chunk_id"] = f"{source_id}:{idx}"
        enriched_items.append(entry)

    if wrapped:
        output_obj = dict(raw)
        output_obj["content_list"] = enriched_items
    else:
        output_obj = enriched_items

    enriched_path = dest_dir / f"{source_id}_content_list.json"
    enriched_path.write_text(json.dumps(output_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %s with embedded chunk_id", enriched_path)


def convert_pdfs(
    input_dir: str | Path,
    mineru_output_dir: str | Path,
    api_key: str | None = None,
    file_name: str | None = None,
) -> None:
    base_url = os.getenv("MINERU_BASE_URL", "https://mineru.net/api/v4")

    input_root = Path(input_dir)
    output_root = Path(mineru_output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    all_pdfs = find_pdfs(input_root)
    if file_name is not None:
        target = Path(file_name).name
        all_pdfs = [p for p in all_pdfs if p.name == target]
        if not all_pdfs:
            raise FileNotFoundError(f"No PDF named '{target}' found under {input_root}")

    pending = [p for p in all_pdfs if not is_converted(p, output_root)]
    # Backfill enriched *_content_list.json for already-converted PDFs.
    for pdf in all_pdfs:
        if pdf in pending:
            continue
        create_chunk_id_content_list_file(output_root / source_id_from_pdf(pdf), source_id_from_pdf(pdf))

    if not pending:
        logger.info("All %d PDF(s) already converted. Nothing to do.", len(all_pdfs))
        return

    api_key = api_key or os.getenv("MINERU_API_KEY")
    if not api_key:
        raise ValueError("MINERU_API_KEY not set. Copy .env.example to .env and set your key.")

    logger.info("%d PDF(s) to convert, %d already converted.", len(pending), len(all_pdfs) - len(pending))

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}"})

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        logger.info("Processing batch %d-%d of %d", start + 1, start + len(batch), len(pending))

        file_requests = [
            {"name": pdf.name, "is_ocr": False, "data_id": source_id_from_pdf(pdf)} for pdf in batch
        ]
        upload_data = get_upload_urls(session, base_url, file_requests)
        batch_id = upload_data["batch_id"]
        file_urls = upload_data["file_urls"]

        upload_files([{"path": p, "url": u} for p, u in zip(batch, file_urls, strict=False)])

        submit_payload = [
            {"name": p.name, "url": u, "data_id": source_id_from_pdf(p), "is_ocr": False}
            for p, u in zip(batch, file_urls, strict=False)
        ]
        submit_batch(session, base_url, batch_id, submit_payload)

        results = poll_batch(session, base_url, batch_id)
        for result in results:
            source_id = result.get("data_id") or Path(result.get("file_name", "unknown")).stem
            out_dir = output_root / source_id
            if result.get("state") == "done":
                zip_url = result.get("full_zip_url")
                if not zip_url:
                    logger.warning("No full_zip_url for %s, skipping", source_id)
                    continue
                download_and_extract(zip_url, out_dir)
                create_chunk_id_content_list_file(out_dir, source_id)
            else:
                logger.error("File %s finished with state=%s", source_id, result.get("state"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PDFs via MinerU and save JSON/MD artifacts.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_input_dir())
    parser.add_argument("--output-dir", default=default_mineru_dir())
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    convert_pdfs(args.input_dir, args.output_dir, file_name=args.file)


if __name__ == "__main__":
    main()
