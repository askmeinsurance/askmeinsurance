import re
from concurrent.futures import ThreadPoolExecutor

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.src.utils.misc import get_embeddings, get_qdrant_client, get_product_summary_top_k

COLLECTION = "product_summary"
_CONTEXT_RE = re.compile(r"<context>.*?</context>", re.DOTALL)


def _strip_context(text: str) -> str:
    return _CONTEXT_RE.sub("", text).strip()


class ProductSummaryInput(BaseModel):
    queries: list[list | str] = Field(
        description=(
            "List of product-summary queries. Preferred format is list entries: "
            "[[query, policy_id_or_null], ...]. "
            "You may also pass list[str], which defaults to policy_id=null per item. "
            "Use for benefits, exclusions, premium details, riders, and policy limits."
        ),
    )
    context: str | None = Field(
        default=None,
        description="Optional caller context. Ignored by retrieval logic.",
    )


@tool(args_schema=ProductSummaryInput)
def query_product_summary(
    queries: list[list | str],
    context: str | None = None,
) -> list[dict]:
    """Search insurance product summaries (policy documents) for specific benefit details,
    exclusions, premiums, riders, and policy terms. Use when the question is about a
    named insurer, a specific policy, or a concrete benefit amount/condition.
    Do NOT use for general insurance concept definitions — use query_textbook instead."""
    embeddings = get_embeddings()
    client = get_qdrant_client()
    top_k = get_product_summary_top_k()

    _ = context
    normalized_queries: list[tuple[str, str | None]] = []
    for item in (queries or []):
        if isinstance(item, str):
            one_query = item.strip()
            if one_query:
                normalized_queries.append((one_query, None))
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            one_query, one_policy_id = item[0], item[1]
            if isinstance(one_query, str) and one_query.strip():
                if one_policy_id is not None and not isinstance(one_policy_id, str):
                    raise ValueError("Each product-summary query entry policy_id must be a string or null.")
                normalized_queries.append((one_query.strip(), one_policy_id))
            continue

    if not normalized_queries:
        raise ValueError("query_product_summary requires at least one non-empty query.")

    def _retrieve_one(args: tuple[str, str | None]):
        one_query, one_policy_id = args
        qdrant_filter = None
        if one_policy_id:
            qdrant_filter = Filter(
                must=[FieldCondition(key="policy_id", match=MatchValue(value=one_policy_id))]
            )
        query_vector = embeddings.embed_query(one_query)
        return client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=qdrant_filter,
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
            "policy_id": r.payload.get("policy_id"),
            "combined_text": _strip_context(r.payload.get("combined_text", "")),
            "document_metadata": r.payload.get("document_metadata", {}),
            "score": r.score,
        }
        for r in deduped_points
    ]
