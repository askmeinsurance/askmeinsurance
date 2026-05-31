from concurrent.futures import ThreadPoolExecutor
from typing_extensions import TypedDict

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from app.agent.utils.misc import get_bm25_model, get_embeddings, get_qdrant_client
from app.core.config import get_settings

COLLECTION = "insurance_text_book2"


class TextbookChunk(TypedDict):
    chunk_id: str | None
    text: str | None
    chapter: str | None
    header: str | None
    level: int | None
    has_table: bool | None
    query_ids: list[int]


class TextbookQueryItem(TypedDict):
    query_id: int
    query: str


class TextbookOutput(TypedDict):
    queries: list[TextbookQueryItem]
    results: list[TextbookChunk]


class TextbookInput(BaseModel):
    queries: list[list | str] | None = Field(
        default=None,
        description=(
            "List of textbook queries. Preferred format is list entries: [[query], ...] or list[str]. "
            "Use this tool for definitions, regulatory concepts, product categories, and industry terminology."
        ),
    )
    query: str | None = Field(
        default=None,
        description=(
            "Optional legacy single query. Prefer `queries`. "
            "Do NOT use for questions about a specific insurer's policy terms or benefits — "
            "use query_product_summary instead."
        ),
    )


@tool(args_schema=TextbookInput)
def query_textbook(
    queries: list[list | str] | None = None,
    query: str | None = None,
) -> TextbookOutput:
    """Search the insurance textbook for conceptual definitions, regulatory frameworks,
    and general product knowledge. Use for 'what is X' or 'how does X work' questions.
    Do NOT use for specific policy benefit details or insurer-specific terms."""
    embeddings = get_embeddings()
    client = get_qdrant_client()

    s = get_settings()
    top_k = s.textbook_top_k
    score_threshold = s.textbook_score_threshold
    normalized_queries: list[str] = []
    for item in (queries or []):
        if isinstance(item, str):
            one_query = item.strip()
            if one_query:
                normalized_queries.append(one_query)
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            one_query = item[0]
            if isinstance(one_query, str) and one_query.strip():
                normalized_queries.append(one_query.strip())
            continue

    if not normalized_queries and query and query.strip():
        normalized_queries = [query.strip()]
    if not normalized_queries:
        raise ValueError("query_textbook requires at least one non-empty query.")

    def _retrieve_one(one_query: str):
        query_vector = embeddings.embed_query(one_query)
        bm25 = get_bm25_model()
        sparse_result = list(bm25.embed([one_query]))[0]
        sparse_vec = SparseVector(
            indices=sparse_result.indices.tolist(),
            values=sparse_result.values.tolist(),
        )
        return client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=query_vector, using="dense", limit=top_k * 3),
                Prefetch(query=sparse_vec, using="bm25", limit=top_k * 3),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            with_payload=True,
        ).points

    with ThreadPoolExecutor(max_workers=len(normalized_queries)) as executor:
        points_groups = list(executor.map(_retrieve_one, normalized_queries))

    query_items: list[TextbookQueryItem] = [
        {"query": q, "query_id": idx}
        for idx, q in enumerate(normalized_queries, start=1)
    ]

    deduped_by_key: dict[str, TextbookChunk] = {}
    for query_item, points in zip(query_items, points_groups):
        query_id = query_item["query_id"]
        for point in points:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id")
            text = payload.get("text")
            dedupe_key = str(chunk_id) if chunk_id else f"text::{(text or '').strip()}"
            if dedupe_key not in deduped_by_key:
                deduped_by_key[dedupe_key] = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "chapter": payload.get("chapter"),
                    "header": payload.get("header"),
                    "level": payload.get("level"),
                    "has_table": payload.get("has_table"),
                    "query_ids": [query_id],
                }
                continue
            if query_id not in deduped_by_key[dedupe_key]["query_ids"]:
                deduped_by_key[dedupe_key]["query_ids"].append(query_id)

    for chunk in deduped_by_key.values():
        chunk["query_ids"].sort()

    return {
        "queries": query_items,
        "results": list(deduped_by_key.values()),
    }
