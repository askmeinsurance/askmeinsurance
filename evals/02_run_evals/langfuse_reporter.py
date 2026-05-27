"""Langfuse dataset and scoring utilities."""
import hashlib
import os
from typing import Optional

from langfuse import Langfuse


def get_langfuse_client() -> Langfuse:
    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )


def _item_id(case) -> str:
    """Stable deterministic ID so re-runs don't create duplicate dataset items.

    Uses the human-readable case_id when present (manual dataset), otherwise
    falls back to an MD5 hash of the question text (textbook / auto-generated).
    """
    if getattr(case, "case_id", None):
        return case.case_id
    return hashlib.md5(case.question.encode()).hexdigest()


def get_processed_item_ids(client: Langfuse, dataset_name: str, run_name: str) -> set[str]:
    """Return the set of dataset_item_ids already linked to run_name.

    Uses the same low-level client.api path as link_to_dataset_run so both
    reads and writes go through the same SDK layer.

    Returns an empty set only when the run genuinely doesn't exist yet.
    Raises on unexpected errors so they are visible instead of silently
    resetting idempotency.
    """
    try:
        run = client.api.datasets.get_run(
            dataset_name=dataset_name,
            run_name=run_name,
        )
        return {item.dataset_item_id for item in run.dataset_run_items}
    except Exception as exc:
        msg = str(exc).lower()
        if "not found" in msg or "404" in msg or "does not exist" in msg:
            return set()
        print(f"[idempotency] WARNING: failed to fetch processed items — {type(exc).__name__}: {exc}")
        print("[idempotency] Falling back to high-level client...")
        try:
            run = client.get_dataset_run(
                dataset_name=dataset_name,
                run_name=run_name,
            )
            return {item.dataset_item_id for item in run.dataset_run_items}
        except Exception as exc2:
            msg2 = str(exc2).lower()
            if "not found" in msg2 or "404" in msg2 or "does not exist" in msg2:
                return set()
            print(f"[idempotency] ERROR: both API paths failed — {type(exc2).__name__}: {exc2}")
            print("[idempotency] Idempotency disabled for this run — all cases will be processed")
            return set()


def fetch_prior_results(
    client: Langfuse,
    dataset_name: str,
    run_name: str,
    current_item_ids: set[str],
) -> list[dict]:
    """Fetch question, answer, and scores for all run items NOT in current_item_ids.

    current_item_ids: item IDs processed in the current session (already in `results`).
    Returns a list of result dicts in the same shape as _eval_case returns, so they
    can be merged directly with the current session's results for a complete summary.
    """
    try:
        run = client.api.datasets.get_run(
            dataset_name=dataset_name,
            run_name=run_name,
        )
    except Exception as exc:
        print(f"[summary] Could not fetch prior results from Langfuse: {exc}")
        return []

    prior: list[dict] = []
    for item in run.dataset_run_items:
        if item.dataset_item_id in current_item_ids:
            continue  # already captured in the current session's results

        try:
            # Request io + scores field groups so input/output/scores are populated
            trace = client.api.trace.get(item.trace_id, fields="core,io,scores")

            inp = trace.input or {}
            out = trace.output or {}
            messages_in = inp.get("messages", []) if isinstance(inp, dict) else []
            messages_out = out.get("messages", []) if isinstance(out, dict) else []

            question = messages_in[0].get("content", "") if messages_in else ""
            answer = messages_out[-1].get("content", "") if messages_out else ""

            # Scores are embedded in TraceWithFullDetails — no extra API call needed
            score_map: dict[str, tuple[float, str | None]] = {
                s.name: (s.value, s.comment)
                for s in trace.scores
            }
            prior.append({
                "question": question,
                "answer": answer,
                "scores": score_map,
                "trace_id": item.trace_id,
            })
        except Exception as exc:
            print(f"[summary] Skipping trace {item.trace_id}: {exc}")

    return prior


def ensure_dataset(client: Langfuse, name: str) -> None:
    try:
        client.get_dataset(name)
    except Exception:
        client.create_dataset(
            name=name,
            description="Insurance chatbot evaluation dataset",
        )


def upsert_dataset_items(client: Langfuse, dataset_name: str, cases: list) -> dict[str, str]:
    """Upsert eval cases into a Langfuse dataset.

    Uses a deterministic item ID (MD5 of question text) so repeated runs are
    idempotent. Returns {question: dataset_item_id}.
    """
    question_to_id: dict[str, str] = {}
    for case in cases:
        item_id = _item_id(case)
        item = client.create_dataset_item(
            dataset_name=dataset_name,
            input=case.question,
            expected_output=case.expected_output,
            id=item_id,
            metadata={"source": case.source},
        )
        question_to_id[case.question] = item.id
    return question_to_id


def post_scores(
    client: Langfuse,
    trace_id: str,
    scores: dict[str, tuple[float, Optional[str]]],
) -> None:
    """Attach DeepEval scores to a Langfuse trace.

    scores: {metric_name: (value, reason_or_None)}
    """
    for name, (value, reason) in scores.items():
        client.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=reason,
            data_type="NUMERIC",
        )


def link_to_dataset_run(
    client: Langfuse,
    run_name: str,
    dataset_item_id: str,
    trace_id: str,
) -> None:
    client.api.dataset_run_items.create(
        run_name=run_name,
        dataset_item_id=dataset_item_id,
        trace_id=trace_id,
    )
