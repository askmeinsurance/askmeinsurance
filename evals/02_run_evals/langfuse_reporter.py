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


def _item_id(question: str) -> str:
    """Stable deterministic ID so re-runs don't create duplicate dataset items."""
    return hashlib.md5(question.encode()).hexdigest()


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
        item_id = _item_id(case.question)
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
        client.score(
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
    client.create_dataset_run_item(
        run_name=run_name,
        dataset_item_id=dataset_item_id,
        observation_id=trace_id,
    )
