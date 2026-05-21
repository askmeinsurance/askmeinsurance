"""Evaluate textbook chunk quality using LLM-as-judge across 8 criteria.

Usage:
    python evaluate_chunks.py --input input_chunks.json --output evaluation_results.json

Input JSON format:
    [{"chunk_id": "da32414", "text": "optional reference text"}]
    The "text" field is for human reference only — actual text is fetched from Qdrant.

Output JSON format:
    List of chunk evaluation results with per-criterion reasoning and scores.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import FieldCondition, Filter, MatchValue, PayloadSchemaType

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)

CRITERIA: dict[str, str] = {
    "Clarity": "Evaluate how clear and understandable the information is.",
    "Depth": "Assess the level of detailed analysis and presence of original insights.",
    "Structure": "Review the organization and logical progression of the content.",
    "Relevance": "Determine the content's pertinence to the main topic.",
    "Precision": "Gauge the accuracy and attention to detail.",
    "Novelty": "Assess the uniqueness and originality of the content.",
    "Conciseness": "Evaluate the brevity and efficiency of the communication.",
    "Impact": "Judge the potential effect of the content on the audience.",
}

TURN1_TEMPLATE = """\
Below is the chunk text:

{chunk_text}

Metric — {criterion_name}: {criterion_desc}

Based on this metric, provide a detailed reasoning about whether this chunk meets the criterion.\
"""

TURN2_TEMPLATE = """\
Based on your reasoning above, give this chunk a score for the metric "{criterion_name}".
Score 1 means the chunk is GOOD for this metric. Score 0 means it is BAD.
Respond ONLY with valid JSON in this exact format: {{"score": 0}} or {{"score": 1}}\
"""


def load_input_chunks(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Input file must be a JSON array, got {type(data)}")
    for item in data:
        if "chunk_id" not in item:
            raise ValueError(f"Each entry must have a 'chunk_id' field: {item}")
    return data


def fetch_chunk_text(client: QdrantClient, collection: str, chunk_id: str) -> str | None:
    results, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
        ),
        limit=1,
        with_payload=True,
    )
    if not results:
        return None
    return results[0].payload.get("text")


def _parse_score(response_text: str) -> int:
    text = response_text.strip()
    try:
        data = json.loads(text)
        return int(data["score"])
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    match = re.search(r'"score"\s*:\s*([01])', text)
    if match:
        return int(match.group(1))
    match = re.search(r'\b([01])\b', text)
    if match:
        return int(match.group(1))
    print(f"  [warn] Could not parse score from: {text!r}, defaulting to 0")
    return 0


def evaluate_criterion(
    client: genai.Client,
    llm_model: str,
    chunk_text: str,
    criterion_name: str,
    criterion_desc: str,
) -> dict:
    chat = client.chats.create(
        model=llm_model,
        config=types.GenerateContentConfig(temperature=0),
    )

    turn1_prompt = TURN1_TEMPLATE.format(
        chunk_text=chunk_text,
        criterion_name=criterion_name,
        criterion_desc=criterion_desc,
    )
    turn1_response = chat.send_message(turn1_prompt)
    reasoning = turn1_response.text.strip()

    turn2_prompt = TURN2_TEMPLATE.format(criterion_name=criterion_name)
    turn2_response = chat.send_message(turn2_prompt)
    score = _parse_score(turn2_response.text)

    return {"reasoning": reasoning, "score": score}


def evaluate_chunk(
    client: genai.Client,
    llm_model: str,
    chunk_id: str,
    chunk_text: str,
) -> dict:
    evaluations: dict[str, dict] = {}

    for criterion_name, criterion_desc in CRITERIA.items():
        print(f"    evaluating: {criterion_name}...", end=" ", flush=True)
        result = evaluate_criterion(client, llm_model, chunk_text, criterion_name, criterion_desc)
        evaluations[criterion_name] = result
        print(f"score={result['score']}")

    total_score = sum(v["score"] for v in evaluations.values())
    return {
        "chunk_id": chunk_id,
        "text": chunk_text,
        "evaluations": evaluations,
        "total_score": total_score,
        "max_score": len(CRITERIA),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate textbook chunks for quality.")
    parser.add_argument("--input", default="input_chunks.json", help="Path to input JSON file")
    parser.add_argument("--output", default="evaluation_results.json", help="Path to output JSON file")
    args = parser.parse_args()

    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if not google_api_key:
        print("ERROR: GOOGLE_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
    collection = os.environ.get("QDRANT_COLLECTION", "insurance_text_book")
    llm_model = os.environ.get("EVAL_LLM_MODEL", "gemini-2.5-flash-lite")

    input_chunks = load_input_chunks(args.input)
    print(f"Loaded {len(input_chunks)} chunk(s) from {args.input}")

    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    try:
        qdrant.create_payload_index(
            collection_name=collection,
            field_name="chunk_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except UnexpectedResponse:
        pass  # index already exists
    genai_client = genai.Client(api_key=google_api_key)

    results: list[dict] = []

    for i, entry in enumerate(input_chunks, start=1):
        chunk_id = entry["chunk_id"]
        print(f"\n[{i}/{len(input_chunks)}] chunk_id={chunk_id}")

        chunk_text = fetch_chunk_text(qdrant, collection, chunk_id)
        if chunk_text is None:
            print(f"  [skip] chunk_id={chunk_id!r} not found in Qdrant collection '{collection}'")
            continue

        print(f"  fetched {len(chunk_text)} chars from Qdrant")
        result = evaluate_chunk(genai_client, llm_model, chunk_id, chunk_text)
        results.append(result)
        print(f"  total_score={result['total_score']}/{result['max_score']}")

    output_path = args.output
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Results saved to {output_path}")
    print(f"Evaluated {len(results)} chunk(s). Review output and decide which chunks to use.")


if __name__ == "__main__":
    main()
