"""Regenerate an eval log file from Langfuse without re-running evaluations.

Usage:
    uv run python regenerate_log.py --run-name baseline_20260530
    uv run python regenerate_log.py --run-name baseline_20260530 --output ../assets/naive_rag_results.txt
"""

import argparse
import sys
from pathlib import Path

from eval_utils.bootstrap import bootstrap_environment

bootstrap_environment()

from eval_utils.config import DATASET_NAME, LOGS_DIR  # noqa: E402
from eval_utils.langfuse_reporter import get_langfuse_client  # noqa: E402
from eval_utils.models import EvalResult, ScoreMap  # noqa: E402
from eval_utils.reporting import collect_metric_names, save_log  # noqa: E402


def _extract_answer(trace) -> str:
    """Try multiple strategies to recover the answer from a Langfuse trace.

    simple_workflow: LangChain CallbackHandler stores AI messages in child
        observation outputs as {"messages": [...]} dicts.
    naive_rag: The span output (if captured) is {"answer": ..., "query": ..., "hits": [...]}.
        Also check the trace-level output field.
    """
    observations = trace.observations or []

    # Strategy 1 — LangChain messages in child observations (simple_workflow)
    for obs in observations:
        out = getattr(obs, "output", None)
        if not isinstance(out, dict):
            continue
        msgs = out.get("messages", [])
        if not msgs:
            continue
        last = msgs[-1]
        content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
        if content:
            return content

    # Strategy 2 — "answer" key in any observation output (naive_rag span)
    for obs in observations:
        out = getattr(obs, "output", None)
        if isinstance(out, dict) and out.get("answer"):
            return out["answer"]

    # Strategy 3 — trace-level output field
    trace_output = getattr(trace, "output", None)
    if isinstance(trace_output, dict):
        if trace_output.get("answer"):
            return trace_output["answer"]
        msgs = trace_output.get("messages", [])
        if msgs:
            last = msgs[-1]
            content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
            if content:
                return content

    return ""


def fetch_results(run_name: str) -> list[EvalResult]:
    client = get_langfuse_client()

    dataset = client.get_dataset(DATASET_NAME)
    item_id_to_question: dict[str, str] = {
        item.id: (item.input if isinstance(item.input, str) else str(item.input))
        for item in dataset.items
    }

    run = client.api.datasets.get_run(dataset_name=DATASET_NAME, run_name=run_name)
    if not run.dataset_run_items:
        print(f"No items found for run '{run_name}'")
        sys.exit(1)

    results: list[EvalResult] = []
    empty_answer_count = 0
    total = len(run.dataset_run_items)
    for i, item in enumerate(run.dataset_run_items, 1):
        try:
            trace = client.api.trace.get(item.trace_id, fields="core,scores,observations")
            question = item_id_to_question.get(item.dataset_item_id, "")
            answer = _extract_answer(trace)
            if not answer:
                empty_answer_count += 1
            score_map: ScoreMap = {s.name: (s.value, s.comment) for s in (trace.scores or [])}
            results.append(EvalResult(
                question=question,
                answer=answer,
                scores=score_map,
                trace_id=item.trace_id,
            ))
            status = "ok" if answer else "NO ANSWER"
            print(f"  [{i}/{total}] {status} — trace {item.trace_id[:8]}...")
        except Exception as exc:
            print(f"  [{i}/{total}] SKIP trace {item.trace_id}: {exc}")

    if empty_answer_count:
        print(
            f"\nWARNING: {empty_answer_count}/{total} traces have no recoverable answer.\n"
            "This happens when the run used a flow (e.g. naive_rag) that does not\n"
            "persist the answer text to Langfuse observations. The answers were only\n"
            "held in memory during the original run and are not recoverable from Langfuse."
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate eval log from Langfuse")
    parser.add_argument("--run-name", required=True, help="Langfuse run name to fetch")
    parser.add_argument("--output", default=None, help="Output file path (default: logs/<run-name>.txt)")
    args = parser.parse_args()

    print(f"Fetching results for run '{args.run_name}' from Langfuse...")
    results = fetch_results(args.run_name)
    print(f"Fetched {len(results)} results")

    metric_names = collect_metric_names(results)
    output_path = Path(args.output) if args.output else None

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from eval_utils.reporting import _format_log
        output_path.write_text(_format_log(args.run_name, results, metric_names, len(results)))
        print(f"Log saved: {output_path}")
    else:
        save_log(args.run_name, results, metric_names, len(results), logs_dir=LOGS_DIR)


if __name__ == "__main__":
    main()
