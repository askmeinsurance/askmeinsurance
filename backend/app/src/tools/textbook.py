from concurrent.futures import ThreadPoolExecutor

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.src.utils.misc import get_embeddings, get_qdrant_client, get_textbook_top_k

COLLECTION = "insurance_text_book2"


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
    k: int | None = Field(default=None, description="Legacy field. Retrieval depth is controlled by TEXTBOOK_TOP_K.")


@tool(args_schema=TextbookInput)
def query_textbook(
    queries: list[list | str] | None = None,
    query: str | None = None,
    k: int | None = None,
) -> list[dict]:
    """Search the insurance textbook for conceptual definitions, regulatory frameworks,
    and general product knowledge. Use for 'what is X' or 'how does X work' questions.
    Do NOT use for specific policy benefit details or insurer-specific terms."""
    embeddings = get_embeddings()
    client = get_qdrant_client()

    _ = k
    top_k = get_textbook_top_k()
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
        return client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        ).points

    with ThreadPoolExecutor(max_workers=len(normalized_queries)) as executor:
        points_groups = list(executor.map(_retrieve_one, normalized_queries))

    deduped_points = []
    seen_chunk_ids: set[str] = set()
    for points in points_groups:
        for point in points:
            chunk_id = point.payload.get("chunk_id")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            deduped_points.append(point)

    return [
        {
            "chunk_id": r.payload.get("chunk_id"),
            "text": r.payload.get("text"),
            "chapter": r.payload.get("chapter"),
            "header": r.payload.get("header"),
            "level": r.payload.get("level"),
            "has_table": r.payload.get("has_table"),
            "score": r.score,
        }
        for r in deduped_points
    ]
