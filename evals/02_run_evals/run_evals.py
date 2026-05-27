"""Evaluation runner for the insurance chatbot.

Usage:
    python run_evals.py
    python run_evals.py --run-name "v2-synthesis-prompt"
    python run_evals.py --run-name "v3-classifier" --limit 5
    python run_evals.py --dataset manual
"""
# ── Bootstrap ────────────────────────────────────────────────────────────────
# load_dotenv and sys.path MUST come before any backend imports because
# get_settings() uses @lru_cache and reads os.environ on first call.
import sys
from pathlib import Path
from dotenv import load_dotenv

_EVALS_ROOT = Path(__file__).parents[1]
_ENV_CANDIDATES = [
    _EVALS_ROOT / ".env",          # preferred: evals/.env
    Path(__file__).parent / ".env" # fallback: evals/02_run_evals/.env
]
for _env_path in _ENV_CANDIDATES:
    if _env_path.exists():
        load_dotenv(_env_path, override=True)
        break

_BACKEND_ROOT = Path(__file__).parents[2] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
# ─────────────────────────────────────────────────────────────────────────────

import argparse
import asyncio
import uuid
from datetime import datetime

from deepeval.test_case import LLMTestCase
from langchain_core.messages import HumanMessage
from langfuse import get_client
from langfuse._client.propagation import propagate_attributes
from langfuse.langchain import CallbackHandler

from chatbot_invoker import extract_retrieval_context, get_graph
from dataset_loader import EvalCase, load_all_evals, load_manual_evals, load_textbook_evals
from langfuse_reporter import (
    ensure_dataset,
    fetch_prior_results,
    get_langfuse_client,
    get_processed_item_ids,
    link_to_dataset_run,
    post_scores,
    upsert_dataset_items,
)
from metrics import GeminiJudge, build_metrics

DATASET_NAME = "insurance_chatbot_evals"
_LOGS_DIR = Path(__file__).parents[2] / "evals" / "logs"


def _save_log(
    run_name: str,
    results: list[dict],
    all_metric_names: list[str],
    total_cases: int,
) -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOGS_DIR / f"{run_name}.txt"
    with_gt = sum(1 for r in results if r["scores"])
    lines: list[str] = [
        f"Run    : {run_name}",
        f"Date   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Cases  : {total_cases} total  ({with_gt} with scores)",
        "─" * 64,
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"\n[{i}/{total_cases}] {r['question']}")
        answer_preview = r["answer"][:200].replace("\n", " ")
        if len(r["answer"]) > 200:
            answer_preview += "..."
        lines.append(f"  Answer : {answer_preview}")
        for metric, (score, reason) in r["scores"].items():
            reason_str = f"  — {reason}" if reason else ""
            lines.append(f"  {metric:<22} : {score:.2f}{reason_str}")
    lines.append(f"\n{'─' * 64}")
    lines.append("Summary")
    for metric in all_metric_names:
        vals = [r["scores"][metric][0] for r in results if metric in r["scores"]]
        if vals:
            avg = sum(vals) / len(vals)
            passing = sum(1 for v in vals if v >= 0.7)
            lines.append(f"  {metric:<22} avg={avg:.3f}  pass={passing}/{len(vals)}")
    lines.append(f"\nLangfuse: Datasets → {DATASET_NAME} → Runs → {run_name}")
    log_path.write_text("\n".join(lines))
    print(f"Log saved: {log_path}")


async def _eval_case(
    graph,
    case: EvalCase,
    run_name: str,
    lf_client,
    dataset_item_id: str,
    metrics_map: dict,
) -> dict:
    """Run one eval case: invoke chatbot, score with DeepEval, push to Langfuse."""
    trace_id = uuid.uuid4().hex
    handler = CallbackHandler()
    lf = get_client()

    # Invoke chatbot inside a named Langfuse span so LangChain callbacks nest within it
    with lf.start_as_current_observation(
        name="eval_chatbot",
        as_type="span",
        trace_context={"trace_id": trace_id},
    ):
        with propagate_attributes(session_id=f"eval_{run_name}", user_id="eval_system"):
            result = await graph.ainvoke(
                {
                    "messages": [HumanMessage(content=case.question)],
                    "conversation_history": [],
                },
                config={"callbacks": [handler]},
            )

    messages = result.get("messages", [])
    answer = messages[-1].content if messages else ""
    retrieval_context = extract_retrieval_context(result)

    test_case = LLMTestCase(
        input=case.question,
        actual_output=answer,
        expected_output=case.expected_output,
        retrieval_context=retrieval_context or None,
    )

    active_metrics = [
        cfg.metric
        for cfg in metrics_map.values()
        if (not cfg.requires_expected_output or case.expected_output)
        and (not cfg.requires_retrieval_context or retrieval_context)
    ]

    def _metric_name(m) -> str:
        return getattr(m, "name", type(m).__name__)

    metric_names = [_metric_name(m) for m in active_metrics]
    print(f"  [metrics] running: {', '.join(metric_names)}")

    async def measure_and_log(metric):
        await metric.a_measure(test_case)
        reason = getattr(metric, "reason", None)
        reason_str = f" — {reason}" if reason else ""
        print(f"  [score]  {_metric_name(metric):<22} {metric.score:.2f}{reason_str}")

    await asyncio.gather(*[measure_and_log(m) for m in active_metrics])

    scores: dict[str, tuple[float, str | None]] = {
        _metric_name(m): (m.score, getattr(m, "reason", None)) for m in active_metrics
    }

    post_scores(lf_client, trace_id, scores)
    link_to_dataset_run(lf_client, run_name, dataset_item_id, trace_id)

    return {"question": case.question, "answer": answer, "scores": scores, "trace_id": trace_id}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run insurance chatbot evaluations")
    parser.add_argument("--run-name", default=None, help="Label for this run in Langfuse")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of cases")
    parser.add_argument(
        "--dataset",
        choices=["manual", "textbook", "all"],
        default="all",
        help="Source dataset (default: all)",
    )
    args = parser.parse_args()

    run_name = args.run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if args.dataset == "manual":
        cases = load_manual_evals()
    elif args.dataset == "textbook":
        cases = load_textbook_evals()
    else:
        cases = load_all_evals()

    if args.limit:
        cases = cases[: args.limit]

    with_gt = sum(1 for c in cases if c.expected_output)
    print(f"Run  : {run_name}")
    print(f"Cases: {len(cases)} total  ({with_gt} with expected output)")

    lf_client = get_langfuse_client()
    ensure_dataset(lf_client, DATASET_NAME)
    question_to_item_id = upsert_dataset_items(lf_client, DATASET_NAME, cases)

    processed_ids = get_processed_item_ids(lf_client, DATASET_NAME, run_name)
    if processed_ids:
        print(f"Resuming '{run_name}' — skipping {len(processed_ids)} already-processed case(s)")

    graph = await get_graph()
    judge = GeminiJudge()
    metrics_map = build_metrics(judge)

    results: list[dict] = []
    for i, case in enumerate(cases, 1):
        item_id = question_to_item_id.get(case.question, "")
        if item_id in processed_ids:
            print(f"\n[{i}/{len(cases)}] SKIP: {case.question[:80]}{'...' if len(case.question) > 80 else ''}")
            continue
        print(f"\n[{i}/{len(cases)}] {case.question[:80]}{'...' if len(case.question) > 80 else ''}")
        result = await _eval_case(graph, case, run_name, lf_client, item_id, metrics_map)
        results.append(result)

        score_parts = [f"{k}={v:.2f}" for k, (v, _) in result["scores"].items()]
        print(f"  {' | '.join(score_parts)}")

    # Merge prior-session results so the summary covers the full run
    current_item_ids = {question_to_item_id.get(r["question"], "") for r in results}
    prior_results = fetch_prior_results(lf_client, DATASET_NAME, run_name, current_item_ids)
    if prior_results:
        print(f"[summary] Loaded {len(prior_results)} prior result(s) from Langfuse")
    all_results = prior_results + results  # prior first to preserve original order

    # Aggregate summary
    print(f"\n{'─' * 64}")
    print(f"Run '{run_name}'  ({len(all_results)} cases evaluated)")
    all_metric_names: list[str] = []
    for r in all_results:
        for k in r["scores"]:
            if k not in all_metric_names:
                all_metric_names.append(k)

    for metric in all_metric_names:
        vals = [r["scores"][metric][0] for r in all_results if metric in r["scores"]]
        if vals:
            avg = sum(vals) / len(vals)
            passing = sum(1 for v in vals if v >= 0.7)
            print(f"  {metric:<22} avg={avg:.3f}  pass={passing}/{len(vals)}")

    print(f"\nLangfuse: Datasets → {DATASET_NAME} → Runs → {run_name}")
    _save_log(run_name, all_results, all_metric_names, len(cases))
    lf_client.flush()


if __name__ == "__main__":
    asyncio.run(main())
