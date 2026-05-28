"""Langfuse dataset and scoring utilities."""

import hashlib
import os

from langfuse import Langfuse

from eval_utils.models import EvalResult, ScoreMap


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
    return hashlib.md5(case.question.encode(), usedforsecurity=False).hexdigest()


def _is_not_found_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "not found" in msg or "404" in msg or "does not exist" in msg


def _fetch_run_item_ids_low_level(
    client: Langfuse, dataset_name: str, run_name: str
) -> set[str] | None:
    """Returns processed item IDs via the low-level API, or None when the run doesn't exist yet."""
    try:
        run = client.api.datasets.get_run(dataset_name=dataset_name, run_name=run_name)
        return {item.dataset_item_id for item in run.dataset_run_items}
    except Exception as exc:
        if _is_not_found_error(exc):
            return None
        raise


def _fetch_run_item_ids_high_level(
    client: Langfuse, dataset_name: str, run_name: str
) -> set[str] | None:
    """Returns processed item IDs via the high-level SDK, or None when the run doesn't exist yet."""
    try:
        run = client.get_dataset_run(dataset_name=dataset_name, run_name=run_name)
        return {item.dataset_item_id for item in run.dataset_run_items}
    except Exception as exc:
        if _is_not_found_error(exc):
            return None
        raise


def get_processed_item_ids(client: Langfuse, dataset_name: str, run_name: str) -> set[str]:
    """Return the set of dataset_item_ids already linked to run_name.

    Returns an empty set when the run genuinely doesn't exist yet.
    Raises on unexpected errors so they are visible instead of silently
    resetting idempotency.
    """
    try:
        result = _fetch_run_item_ids_low_level(client, dataset_name, run_name)
        return result if result is not None else set()
    except Exception as exc:
        print(f"[idempotency] WARNING: low-level API failed — {type(exc).__name__}: {exc}")
        print("[idempotency] Falling back to high-level client...")

    try:
        result = _fetch_run_item_ids_high_level(client, dataset_name, run_name)
        return result if result is not None else set()
    except Exception as exc:
        print(f"[idempotency] ERROR: both API paths failed — {type(exc).__name__}: {exc}")
        print("[idempotency] Idempotency disabled for this run — all cases will be processed")
        return set()


def _extract_answer_from_observations(observations: list) -> str:
    """Scan LangChain callback observations for the last AI message content.

    The LangChain CallbackHandler serialises LangGraph state messages as plain
    dicts when stored in Langfuse observations, whereas the graph itself returns
    LangChain message objects. Both shapes must be handled here.
    """
    for obs in observations:
        out = getattr(obs, "output", None)
        if not isinstance(out, dict):
            continue
        msgs = out.get("messages", [])
        if not msgs:
            continue
        last = msgs[-1]
        if isinstance(last, dict):
            content = last.get("content", "")
        else:
            content = getattr(last, "content", "")
        if content:
            return content
    return ""


def fetch_prior_results(
    client: Langfuse,
    dataset_name: str,
    run_name: str,
    current_item_ids: set[str],
    item_id_to_question: dict[str, str],
) -> list[EvalResult]:
    """Fetch question, answer, and scores for all run items NOT in current_item_ids.

    current_item_ids: item IDs processed in the current session (already in `results`).
    item_id_to_question: reverse mapping of question_to_item_id — used to reliably
        recover the question text without relying on trace.input (which is None because
        lf.start_as_current_observation is called without an explicit input= argument).
    """
    try:
        run = client.api.datasets.get_run(dataset_name=dataset_name, run_name=run_name)
    except Exception as exc:
        print(f"[summary] Could not fetch prior results from Langfuse: {exc}")
        return []

    prior: list[EvalResult] = []
    for item in run.dataset_run_items:
        if item.dataset_item_id in current_item_ids:
            continue

        try:
            trace = client.api.trace.get(item.trace_id, fields="core,scores,observations")
            question = item_id_to_question.get(item.dataset_item_id, "")
            answer = _extract_answer_from_observations(trace.observations)
            score_map: ScoreMap = {
                s.name: (s.value, s.comment) for s in trace.scores
            }
            prior.append(EvalResult(
                question=question,
                answer=answer,
                scores=score_map,
                trace_id=item.trace_id,
            ))
        except Exception as exc:
            print(f"[summary] Skipping trace {item.trace_id}: {exc}")

    return prior


def ensure_dataset(client: Langfuse, name: str) -> None:
    try:
        client.get_dataset(name)
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise
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


def post_scores(client: Langfuse, trace_id: str, scores: ScoreMap) -> None:
    """Attach DeepEval scores to a Langfuse trace."""
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
