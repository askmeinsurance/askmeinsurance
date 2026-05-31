"""Search Qdrant for chunks similar to a free-text query using cosine similarity.

Edit the CONFIG section below, then run:
    python search_similar_chunks.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from qdrant_client import QdrantClient

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)

# ---------------------------------------------------------------------------
# CONFIG — edit these before running
# ---------------------------------------------------------------------------
QUERY_TEXT = """How much guaranteed cash back will I get each year if I buy the 5-year payment AIA Smart Flexi Rewards (II) plan?"""
TOP_K = 5
OUTPUT_FILE = "similar.json"  # set to a path like "similar.json" to save results, or None to skip
# ---------------------------------------------------------------------------


def embed_query(text: str, api_key: str) -> list[float]:
    model = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
    dimension = int(os.environ.get("EMBEDDING_DIMENSION", "1536"))
    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="retrieval_query",
            output_dimensionality=dimension,
        ),
    )
    return response.embeddings[0].values


def search_similar(
    client: QdrantClient,
    collection: str,
    vector: list[float],
    top_k: int,
) -> list[dict]:
    hits = client.query_points(
        collection_name=collection,
        query=vector,
        using="dense",
        limit=top_k,
        with_payload=True,
    ).points

    return [
        {
            "chunk_id": hit.payload.get("chunk_id"),
            "score": round(hit.score, 6),
            "text": hit.payload.get("text"),
            "chapter": hit.payload.get("chapter"),
            "header": hit.payload.get("header"),
            "level": hit.payload.get("level"),
            "has_table": hit.payload.get("has_table"),
        }
        for hit in hits
    ]


def main() -> None:
    print(f"Loading .env from: {_env_path} (exists={_env_path.exists()})")

    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if not google_api_key:
        print("ERROR: GOOGLE_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
    # collection = os.environ.get("QDRANT_COLLECTION", "insurance_text_book")
    collection = "product_summary"

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    print(f"Embedding query: {QUERY_TEXT!r}")
    vector = embed_query(QUERY_TEXT, google_api_key)

    print(f"Searching top {TOP_K} similar chunks in '{collection}'...\n")
    results = search_similar(client, collection, vector, TOP_K)

    for i, r in enumerate(results, start=1):
        print(f"[{i}] chunk_id={r['chunk_id']}  score={r['score']}")
        print(f"     chapter={r['chapter']!r}  header={r['header']!r}")
        print(f"     {str(r['text'] or '')[:120]}...")
        print()

    if OUTPUT_FILE:
        output = {"query": QUERY_TEXT, "results": results}
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
