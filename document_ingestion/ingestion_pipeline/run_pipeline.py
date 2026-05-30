from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

import step7_embed_and_upsert as step7
from step1_mineru_convert import convert_pdfs
from step2_chunk_content import process_all
from step3_table_enrich import enrich_file
from step4_add_context import enrich_file as add_context_file
from step5_one_page_summary import process_pdf as summarize_pdf
from step6_add_document_metadata import enrich_file as add_document_metadata_file
from utils import (
    create_gemini_client_from_env,
    default_chunk_dir,
    default_context_dir,
    default_document_metadata_dir,
    default_embedding_dir,
    default_input_dir,
    default_metadata_dir,
    default_mineru_dir,
    default_summary_dir,
    default_table_dir,
    find_jsonl_files,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run full ingestion pipeline: MinerU convert + chunking + table enrichment + context enrichment + one-page summary + chunk document metadata + Gemini embeddings + Qdrant upsert."
    )
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_input_dir())
    parser.add_argument("--mineru-dir", default=default_mineru_dir())
    parser.add_argument("--chunk-dir", default=default_chunk_dir())
    parser.add_argument("--table-output-dir", default=default_table_dir())
    parser.add_argument("--table-model", default="gemini-2.5-flash-lite")
    parser.add_argument("--context-output-dir", default=default_context_dir())
    parser.add_argument("--context-model", default="gemini-2.5-flash-lite")
    parser.add_argument("--context-ttl-seconds", type=int, default=600)
    parser.add_argument("--context-force", action="store_true")
    parser.add_argument("--summary-output-dir", default=default_summary_dir())
    parser.add_argument("--summary-model", default="gemini-2.5-flash-lite")
    parser.add_argument("--summary-force", action="store_true")
    parser.add_argument("--prompt-path", default=str(Path(__file__).resolve().parent.parent / "ref" / "one_page_summary.md"))
    parser.add_argument("--metadata-output-dir", default=default_metadata_dir())
    parser.add_argument("--document-metadata-output-dir", default=default_document_metadata_dir())
    parser.add_argument("--metadata-model", default="gemini-2.5-flash-lite")
    parser.add_argument("--metadata-force", action="store_true")
    parser.add_argument("--embedding-input-dir", default=default_metadata_dir())
    parser.add_argument("--embedding-output-dir", default=default_embedding_dir())
    parser.add_argument("--qdrant-collection", default=step7.default_collection())
    parser.add_argument("--embedding-batch-size", type=int, default=64)
    parser.add_argument("--embedding-poll-interval-seconds", type=int, default=5)
    parser.add_argument("--embedding-poll-timeout-seconds", type=int, default=900)
    parser.add_argument("--embedding-force", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    # Step 1: convert PDFs to structured JSON/MD via MinerU API.
    logger.info("=== Step 1: MinerU PDF conversion ===")
    convert_pdfs(
        input_dir=args.input_dir,
        mineru_output_dir=args.mineru_dir,
        file_name=args.file,
    )

    # Step 2: chunk MinerU JSON output into overlapping text chunks with bbox metadata.
    logger.info("=== Step 2: chunking ===")
    process_all(
        mineru_root=Path(args.mineru_dir),
        chunk_root=Path(args.chunk_dir),
        target_file=args.file,
    )

    client = create_gemini_client_from_env()

    # Step 3: replace raw table HTML in each chunk with hierarchical JSON + LLM narrative.
    logger.info("=== Step 3: table enrichment ===")
    chunk_root = Path(args.chunk_dir)
    output_root = Path(args.table_output_dir)
    for input_path in find_jsonl_files(chunk_root, args.file):
        output_path = output_root / input_path.name
        enrich_file(input_path, output_path, client, args.table_model)

    # Step 4: prepend a short retrieval context sentence to each chunk using the full document.
    logger.info("=== Step 4: context enrichment ===")
    table_chunk_root = Path(args.table_output_dir)
    context_output_root = Path(args.context_output_dir)
    for input_path in find_jsonl_files(table_chunk_root, args.file):
        output_path = context_output_root / input_path.name
        add_context_file(
            input_path=input_path,
            output_path=output_path,
            mineru_root=Path(args.mineru_dir),
            client=client,
            model=args.context_model,
            ttl_seconds=args.context_ttl_seconds,
            force=args.context_force,
        )

    # Step 5: generate a one-page product summary from the raw PDF via LLM.
    logger.info("=== Step 5: one-page summary ===")
    input_root = Path(args.input_dir)
    summary_output_root = Path(args.summary_output_dir)
    prompt_path = Path(args.prompt_path)
    if args.file:
        target_pdf = input_root / Path(args.file).name
        if not target_pdf.exists():
            raise FileNotFoundError(f"PDF file not found for summary step: {target_pdf}")
        summarize_pdf(
            pdf_path=target_pdf,
            output_root=summary_output_root,
            prompt_path=prompt_path,
            client=client,
            model=args.summary_model,
            force=args.summary_force,
        )
    else:
        for pdf_path in sorted(input_root.rglob("*.pdf")):
            summarize_pdf(
                pdf_path=pdf_path,
                output_root=summary_output_root,
                prompt_path=prompt_path,
                client=client,
                model=args.summary_model,
                force=args.summary_force,
            )

    # Step 6: extract structured document metadata from the summary and attach it to every chunk.
    logger.info("=== Step 6: document metadata extraction ===")
    metadata_input_root = Path(args.context_output_dir)
    metadata_output_root = Path(args.metadata_output_dir)
    document_metadata_output_root = Path(args.document_metadata_output_dir)
    for input_path in find_jsonl_files(metadata_input_root, args.file):
        output_path = metadata_output_root / input_path.name
        document_metadata_path = document_metadata_output_root / f"{input_path.stem}.json"
        add_document_metadata_file(
            input_path=input_path,
            output_path=output_path,
            document_metadata_path=document_metadata_path,
            summary_root=summary_output_root,
            client=client,
            model=args.metadata_model,
            force=args.metadata_force,
        )

    # Step 7: embed each chunk via Gemini batch API and upsert vectors to Qdrant.
    logger.info("=== Step 7: embedding and Qdrant upsert ===")
    embedding_input_root = Path(args.embedding_input_dir)
    embedding_output_root = Path(args.embedding_output_dir)
    embedding_raw_root = embedding_output_root / "raw_jobs"
    embedding_registry_path = embedding_output_root / "batch_jobs.json"
    embedding_registry = step7.load_registry(embedding_registry_path)

    embedding_api_key = step7.load_api_key_from_env()
    qdrant_client = step7.load_qdrant_client_from_env()
    try:
        step7.ensure_collection(qdrant_client, args.qdrant_collection)
        embedding_files = find_jsonl_files(embedding_input_root, args.file)

        # Phase 1: submit missing/invalid embedding jobs for all files first.
        for input_path in embedding_files:
            step7.submit_batch_job_if_needed(
                input_path=input_path,
                output_root=embedding_output_root,
                registry_path=embedding_registry_path,
                registry=embedding_registry,
                api_key=embedding_api_key,
                force=args.embedding_force,
            )
            step7.save_registry(embedding_registry_path, embedding_registry)

        # Phase 2: poll/finalize each file and upsert to Qdrant.
        for input_path in embedding_files:
            step7.process_file(
                input_path=input_path,
                output_root=embedding_output_root,
                raw_root=embedding_raw_root,
                registry_path=embedding_registry_path,
                registry=embedding_registry,
                api_key=embedding_api_key,
                gemini_client=client,
                qdrant_client=qdrant_client,
                collection=args.qdrant_collection,
                batch_size=args.embedding_batch_size,
                force=args.embedding_force,
                poll_interval=args.embedding_poll_interval_seconds,
                poll_timeout=args.embedding_poll_timeout_seconds,
            )
            step7.save_registry(embedding_registry_path, embedding_registry)
    finally:
        qdrant_client.close()


if __name__ == "__main__":
    main()
