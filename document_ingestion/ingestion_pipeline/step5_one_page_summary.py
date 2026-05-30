from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils import GENERATION_MODEL, create_gemini_client_from_env, default_input_dir, default_summary_dir, save_json_atomic

logger = logging.getLogger(__name__)


def default_prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "ref" / "one_page_summary.md"


def find_pdfs(input_root: Path, target_file: str | None = None) -> list[Path]:
    files = sorted(input_root.rglob("*.pdf"))
    if target_file:
        target = Path(target_file).name
        files = [p for p in files if p.name == target]
    return files


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_idempotency_key(source_id: str, model: str, prompt_sha256: str, pdf_sha256: str) -> str:
    raw = f"{source_id}|{model}|{prompt_sha256}|{pdf_sha256}".encode("utf-8")
    return sha256_bytes(raw)


def load_existing_output(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not parse existing summary file %s: %s", path, exc)
        return None


def should_skip(existing: dict[str, Any] | None, idempotency_key: str) -> bool:
    if not existing:
        return False
    return str(existing.get("idempotency_key", "")) == idempotency_key and bool(
        str(existing.get("generated_summary", "")).strip()
    )


def generate_summary(
    client: genai.Client,
    model: str,
    prompt_text: str,
    pdf_bytes: bytes,
) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt_text,
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        ],
    )
    return (response.text or "").strip()


def process_pdf(
    pdf_path: Path,
    output_root: Path,
    prompt_path: Path,
    client: genai.Client,
    model: str,
    force: bool,
) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    source_id = pdf_path.stem
    output_path = output_root / f"{source_id}.json"

    prompt_text = prompt_path.read_text(encoding="utf-8")
    pdf_bytes = pdf_path.read_bytes()

    prompt_sha256 = sha256_bytes(prompt_text.encode("utf-8"))
    pdf_sha256 = sha256_bytes(pdf_bytes)
    idempotency_key = compute_idempotency_key(source_id, model, prompt_sha256, pdf_sha256)

    existing = None if force else load_existing_output(output_path)
    if not force and should_skip(existing, idempotency_key):
        logger.info("Skipping %s because idempotent summary already exists at %s", source_id, output_path)
        return

    logger.info("Generating one-page summary for %s", source_id)
    summary = generate_summary(client, model, prompt_text, pdf_bytes)

    payload: dict[str, Any] = {
        "source_id": source_id,
        "pdf_path": str(pdf_path),
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_sha256": prompt_sha256,
        "pdf_sha256": pdf_sha256,
        "idempotency_key": idempotency_key,
        "generated_summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json_atomic(output_path, payload)
    logger.info("Saved one-page summary for %s to %s", source_id, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one-page product summaries from PDF using LLM.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_input_dir())
    parser.add_argument("--output-dir", default=default_summary_dir())
    parser.add_argument("--model", default=GENERATION_MODEL)
    parser.add_argument("--prompt-path", default=str(default_prompt_path()))
    parser.add_argument("--force", action="store_true", help="Regenerate summary even if idempotent output exists.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    prompt_path = Path(args.prompt_path)

    files = find_pdfs(input_root, args.file)
    if args.file and not files:
        raise FileNotFoundError(f"No PDF named '{Path(args.file).name}' found under {input_root}")
    if not files:
        logger.info("No PDF files found under %s", input_root)
        return

    client = create_gemini_client_from_env()
    for pdf_path in files:
        process_pdf(
            pdf_path=pdf_path,
            output_root=output_root,
            prompt_path=prompt_path,
            client=client,
            model=args.model,
            force=args.force,
        )


if __name__ == "__main__":
    main()
