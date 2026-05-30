"""Retrieval context extraction from eval results."""

import itertools
from collections.abc import Iterator

TEXTBOOK_TOOL = "query_textbook"
PRODUCT_TOOL = "query_product_summary"
NAIVE_RAG_TOOL = "naive_rag_hits"


def extract_retrieval_context(result: dict) -> list[str]:
    chunks, _ = _collect_retrieval(result)
    return chunks


def summarize_retrieval_hits(result: dict) -> dict[str, int]:
    _, hits = _collect_retrieval(result)
    return hits


def _collect_retrieval(result: dict) -> tuple[list[str], dict[str, int]]:
    seen: set[str] = set()
    chunks: list[str] = []
    hits: dict[str, int] = {}

    sources = itertools.chain(
        _iter_naive_rag_hits(result.get("hits", [])),
        _iter_execution_chunks(result),
        _iter_product_chunks(result.get("product_chunks", [])),
        _iter_textbook_chunks(result.get("concept_chunks") or {}),
    )
    for text, source in sources:
        if not text or text in seen:
            continue
        seen.add(text)
        chunks.append(text)
        hits[source] = hits.get(source, 0) + 1

    return chunks, hits


def _iter_execution_chunks(result: dict) -> Iterator[tuple[str, str]]:
    for batch in result.get("execution_results", []):
        for step in batch.get("results", []):
            if step.get("kind") != "tool":
                continue
            target = step.get("target")
            if target == PRODUCT_TOOL:
                yield from _iter_product_chunks(step.get("output") or [])
            elif target == TEXTBOOK_TOOL:
                yield from _iter_textbook_chunks(step.get("output") or {})


def _iter_naive_rag_hits(hits: list[dict]) -> Iterator[tuple[str, str]]:
    for hit in hits:
        yield (hit.get("text") or "").strip(), NAIVE_RAG_TOOL


def _iter_product_chunks(groups: list[dict]) -> Iterator[tuple[str, str]]:
    for group in groups:
        for chunk in group.get("chunks", []):
            text = chunk.get("text") or chunk.get("combined_text") or ""
            yield text, PRODUCT_TOOL


def _iter_textbook_chunks(output: dict) -> Iterator[tuple[str, str]]:
    for chunk in output.get("results", []):
        yield chunk.get("text") or "", TEXTBOOK_TOOL
