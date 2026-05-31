from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from google import genai
from google.genai import types
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient


def load_environment() -> tuple[Path, Path, Path]:
    script_path = Path(__file__).resolve()
    examples_dir = script_path.parent
    evals_dir = examples_dir.parent
    repo_root = evals_dir.parent
    backend_dir = repo_root / "backend"

    for candidate in [
        examples_dir / ".env",
        evals_dir / ".env",
        backend_dir / ".env",
        repo_root / ".env",
    ]:
        if candidate.exists():
            load_dotenv(candidate, override=False)

    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    return repo_root, examples_dir, backend_dir


REPO_ROOT, EXAMPLES_DIR, BACKEND_DIR = load_environment()

from app.agent.prompts.prompts import SIMPLEV2_SYNTHESIS_SYSTEM


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gemini-2.5-flash-lite")
SYNTHESIS_TEMPERATURE = float(os.getenv("SYNTHESIS_TEMPERATURE", "0"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "product_summary")
TOP_K = int(os.getenv("TOP_K", "5"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY. Set it in evals/naive_rag/.env, evals/.env, backend/.env, or your shell.")
if not QDRANT_URL:
    raise ValueError("Missing QDRANT_URL. Set it in evals/naive_rag/.env, evals/.env, backend/.env, or your shell.")

genai_client = genai.Client(api_key=GEMINI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30)


class NaiveRagState(TypedDict, total=False):
    user_query: str
    top_k: int
    query_vector: list[float]
    hits: list[dict]
    answer: str


def embed_query(query: str) -> list[float]:
    response = genai_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="retrieval_query",
            output_dimensionality=EMBEDDING_DIMENSION,
        ),
    )
    return response.embeddings[0].values


def search_qdrant(query_vector: list[float], top_k: int = TOP_K) -> list[dict]:
    try:
        points = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        ).points
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "dimension" in message.lower() or "vector" in message.lower():
            raise RuntimeError(
                "Qdrant rejected the query vector. Confirm that the target collection was indexed with "
                f"{EMBEDDING_DIMENSION}-dim embeddings. Original error: {message}"
            ) from exc
        raise

    results = []
    for point in points:
        payload = point.payload or {}
        results.append(
            {
                "score": point.score,
                "chunk_id": payload.get("chunk_id"),
                "chapter": payload.get("chapter"),
                "header": payload.get("header"),
                "level": payload.get("level"),
                "has_table": payload.get("has_table"),
                "text": payload.get("text"),
            }
        )
    return results


def format_retrieval_hits(hits: list[dict]) -> str:
    if not hits:
        return "[]"
    return json.dumps(hits, indent=2, ensure_ascii=False)


def build_synthesis_prompt(user_query: str, hits: list[dict]) -> str:
    user_question_json = json.dumps(
        [{"role": "user", "content": user_query}],
        indent=2,
        ensure_ascii=False,
    )
    retrieval_angles_json = json.dumps(
        [{"intent_description": user_query, "source_type": "textbook"}],
        indent=2,
        ensure_ascii=False,
    )
    return (
        "Conversation history:\n[]\n\n"
        f"User question:\n{user_question_json}\n\n"
        f"Condensed intent:\n{user_query}\n\n"
        f"Retrieval angles used:\n{retrieval_angles_json}\n\n"
        "Product evidence:\n[]\n\n"
        f"Concept evidence:\n{format_retrieval_hits(hits)}"
    )


def synthesize_answer(user_query: str, hits: list[dict]) -> str:
    user_message = build_synthesis_prompt(user_query, hits)
    response = genai_client.models.generate_content(
        model=GENERATION_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SIMPLEV2_SYNTHESIS_SYSTEM,
            temperature=SYNTHESIS_TEMPERATURE,
        ),
        contents=user_message,
    )
    return response.text or ""


def embed_query_node(state: NaiveRagState) -> NaiveRagState:
    return {"query_vector": embed_query(state["user_query"])}


def retrieve_qdrant_node(state: NaiveRagState) -> NaiveRagState:
    return {
        "hits": search_qdrant(
            state["query_vector"],
            top_k=state.get("top_k", TOP_K),
        )
    }


def synthesize_answer_node(state: NaiveRagState) -> NaiveRagState:
    return {
        "answer": synthesize_answer(
            state["user_query"],
            state.get("hits", []),
        )
    }


def build_naive_rag_graph():
    builder = StateGraph(NaiveRagState)
    builder.add_node("embed_query", embed_query_node)
    builder.add_node("retrieve_qdrant", retrieve_qdrant_node)
    builder.add_node("synthesize_answer", synthesize_answer_node)
    builder.add_edge(START, "embed_query")
    builder.add_edge("embed_query", "retrieve_qdrant")
    builder.add_edge("retrieve_qdrant", "synthesize_answer")
    builder.add_edge("synthesize_answer", END)
    return builder.compile()


naive_rag_graph = build_naive_rag_graph()


def run_naive_rag(user_query: str, top_k: int = TOP_K, callbacks: list | None = None) -> dict:
    final_state = naive_rag_graph.invoke(
        {"user_query": user_query, "top_k": top_k},
        config={"callbacks": callbacks or []},
    )
    return {
        "query": final_state["user_query"],
        "hits": final_state.get("hits", []),
        "answer": final_state.get("answer", ""),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the naive RAG demo against Qdrant.")
    parser.add_argument(
        "query",
        nargs="?",
        default="Tell me more about guaranteed protect plus",
        help="User query to send through the RAG flow.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help="Number of Qdrant results to retrieve.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Repo root: {REPO_ROOT}")
    print(f"Backend dir on sys.path: {BACKEND_DIR}")
    print(
        {
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "generation_model": GENERATION_MODEL,
            "collection_name": COLLECTION_NAME,
            "top_k": args.top_k,
            "synthesis_temperature": SYNTHESIS_TEMPERATURE,
        }
    )

    result = run_naive_rag(args.query, top_k=args.top_k)

    print("Query:\n")
    print(result["query"])

    print("\nTop hits:\n")
    for index, hit in enumerate(result["hits"], start=1):
        print(f"[{index}] score={hit['score']:.6f} chunk_id={hit['chunk_id']}")
        print(f"header={hit['header']!r} chapter={hit['chapter']!r}")
        snippet = (hit.get("text") or "").replace("\n", " ")
        print(snippet[:280] + ("..." if len(snippet) > 280 else ""))
        print()

    print("Final answer:\n")
    print(result["answer"])


if __name__ == "__main__":
    main()
