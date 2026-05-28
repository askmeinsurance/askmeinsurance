"""Evaluation run orchestration."""

import asyncio
import uuid
from typing import Any

from deepeval.test_case import LLMTestCase
from langchain_core.messages import HumanMessage
from langfuse import Langfuse, get_client
from langfuse._client.propagation import propagate_attributes
from langfuse.langchain import CallbackHandler

from eval_utils.config import DATASET_NAME, RunConfig, parse_run_config
from eval_utils.dataset_loader import EvalCase, load_manual_evals
from eval_utils.langfuse_reporter import (
    ensure_dataset,
    fetch_prior_results,
    get_langfuse_client,
    get_processed_item_ids,
    link_to_dataset_run,
    post_scores,
    upsert_dataset_items,
)
from eval_utils.metrics import GeminiJudge, MetricConfig, build_metrics
from eval_utils.models import EvalResult, ScoreMap
from eval_utils.reporting import collect_metric_names, print_summary, save_log, truncate
from eval_utils.retrieval import extract_retrieval_context, summarize_retrieval_hits


def select_active_metrics(
    metrics_map: dict[str, MetricConfig],
    case: EvalCase,
    retrieval_context: list[str],
) -> list:
    return [cfg.metric for cfg in metrics_map.values() if cfg.is_applicable(case, retrieval_context)]


def get_metric_name(metric: Any) -> str:
    return getattr(metric, "name", type(metric).__name__)


async def main(argv: list[str] | None = None) -> None:
    await run_evaluations(parse_run_config(argv))


async def run_evaluations(config: RunConfig) -> None:
    all_cases = load_manual_evals()
    cases = all_cases[:config.limit] if config.limit else all_cases
    _print_run_header(config.run_name, cases)

    langfuse_client = get_langfuse_client()
    ensure_dataset(langfuse_client, DATASET_NAME)
    question_to_item_id = upsert_dataset_items(langfuse_client, DATASET_NAME, cases)
    processed_ids = get_processed_item_ids(langfuse_client, DATASET_NAME, config.run_name)
    if processed_ids:
        print(f"Resuming '{config.run_name}' - skipping {len(processed_ids)} already-processed case(s)")

    graph = await _get_graph()
    metrics_map = build_metrics(GeminiJudge())
    results = await _evaluate_cases(
        cases,
        graph,
        config.run_name,
        langfuse_client,
        question_to_item_id,
        processed_ids,
        metrics_map,
    )

    all_results = _merge_prior_results(
        langfuse_client,
        config.run_name,
        results,
        question_to_item_id,
    )
    metric_names = collect_metric_names(all_results)
    print_summary(config.run_name, all_results, metric_names)
    save_log(config.run_name, all_results, metric_names, len(cases))
    langfuse_client.flush()


async def evaluate_case(
    graph: Any,
    case: EvalCase,
    run_name: str,
    langfuse_client: Langfuse,
    dataset_item_id: str,
    metrics_map: dict[str, MetricConfig],
) -> EvalResult:
    result, trace_id = await _invoke_graph(graph, case, run_name)
    messages = result.get("messages", [])
    answer = messages[-1].content if messages else ""
    retrieval_context = extract_retrieval_context(result)
    _print_retrieval_summary(result, retrieval_context)

    test_case = LLMTestCase(
        input=case.question,
        actual_output=answer,
        expected_output=case.expected_output,
        retrieval_context=retrieval_context or None,
    )
    active_metrics = select_active_metrics(metrics_map, case, retrieval_context)
    await _measure_metrics(active_metrics, test_case)

    scores: ScoreMap = {
        get_metric_name(metric): (metric.score, getattr(metric, "reason", None))
        for metric in active_metrics
    }
    post_scores(langfuse_client, trace_id, scores)
    link_to_dataset_run(langfuse_client, run_name, dataset_item_id, trace_id)

    return EvalResult(question=case.question, answer=answer, scores=scores, trace_id=trace_id)


async def _get_graph() -> Any:
    from eval_utils.chatbot_invoker import get_graph

    return await get_graph()


async def _evaluate_cases(
    cases: list[EvalCase],
    graph: Any,
    run_name: str,
    langfuse_client: Langfuse,
    question_to_item_id: dict[str, str],
    processed_ids: set[str],
    metrics_map: dict[str, MetricConfig],
) -> list[EvalResult]:
    results: list[EvalResult] = []
    for index, case in enumerate(cases, 1):
        item_id = question_to_item_id.get(case.question, "")
        if item_id in processed_ids:
            print(f"\n[{index}/{len(cases)}] SKIP: {truncate(case.question)}")
            continue

        print(f"\n[{index}/{len(cases)}] {truncate(case.question)}")
        result = await evaluate_case(graph, case, run_name, langfuse_client, item_id, metrics_map)
        results.append(result)
        score_parts = [f"{name}={score:.2f}" for name, (score, _) in result.scores.items()]
        print(f"  {' | '.join(score_parts)}")
    return results


async def _invoke_graph(graph: Any, case: EvalCase, run_name: str) -> tuple[dict, str]:
    trace_id = uuid.uuid4().hex
    handler = CallbackHandler()
    langfuse_context = get_client()

    with langfuse_context.start_as_current_observation(
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
    return result, trace_id


async def _measure_metrics(metrics: list, test_case: Any) -> None:
    print(f"  [metrics] running: {', '.join(get_metric_name(m) for m in metrics)}")
    await asyncio.gather(*[_measure_metric(metric, test_case) for metric in metrics])


async def _measure_metric(metric: Any, test_case: Any) -> None:
    await metric.a_measure(test_case)
    reason = getattr(metric, "reason", None)
    reason_text = f" - {reason}" if reason else ""
    print(f"  [score]  {get_metric_name(metric):<22} {metric.score:.2f}{reason_text}")


def _merge_prior_results(
    langfuse_client: Langfuse,
    run_name: str,
    results: list[EvalResult],
    question_to_item_id: dict[str, str],
) -> list[EvalResult]:
    current_item_ids = {question_to_item_id.get(r.question, "") for r in results}
    item_id_to_question = {item_id: question for question, item_id in question_to_item_id.items()}
    prior_results = fetch_prior_results(
        langfuse_client,
        DATASET_NAME,
        run_name,
        current_item_ids,
        item_id_to_question,
    )
    if prior_results:
        print(f"[summary] Loaded {len(prior_results)} prior result(s) from Langfuse")
    return prior_results + results


def _print_run_header(run_name: str, cases: list[EvalCase]) -> None:
    with_expected = sum(1 for case in cases if case.expected_output)
    print(f"Run  : {run_name}")
    print(f"Cases: {len(cases)} total  ({with_expected} with expected output)")


def _print_retrieval_summary(result: dict, retrieval_context: list[str]) -> None:
    hits = summarize_retrieval_hits(result)
    if not hits:
        print("  [retrieval] no chunks retrieved")
        return

    summary = "  ".join(f"{tool}={count}" for tool, count in hits.items())
    print(f"  [retrieval] {len(retrieval_context)} chunks  ({summary})")
