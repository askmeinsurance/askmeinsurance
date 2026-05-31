"""Console and file reporting helpers for eval runs."""

from datetime import datetime
from pathlib import Path

from eval_utils.config import DATASET_NAME, LOGS_DIR
from eval_utils.metrics import DEFAULT_METRIC_THRESHOLD
from eval_utils.models import EvalResult


def truncate(text: str, limit: int = 80) -> str:
    return f"{text[:limit]}..." if len(text) > limit else text


def collect_metric_names(results: list[EvalResult]) -> list[str]:
    seen: dict[str, None] = {}
    for result in results:
        seen.update(dict.fromkeys(result.scores))
    return list(seen)


def summarize_scores(results: list[EvalResult], metric_names: list[str]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for metric_name in metric_names:
        values = [
            result.scores[metric_name][0]
            for result in results
            if metric_name in result.scores
        ]
        if not values:
            continue

        summary[metric_name] = {
            "average": sum(values) / len(values),
            "passing": sum(1 for value in values if value >= DEFAULT_METRIC_THRESHOLD),
            "total": len(values),
        }
    return summary


def print_summary(run_name: str, results: list[EvalResult], metric_names: list[str]) -> None:
    print(f"\n{'-' * 64}")
    print(f"Run '{run_name}'  ({len(results)} cases evaluated)")
    for metric_name, values in summarize_scores(results, metric_names).items():
        print(
            f"  {metric_name:<22} "
            f"avg={values['average']:.3f}  pass={values['passing']}/{values['total']}"
        )
    print(f"\nLangfuse: Datasets -> {DATASET_NAME} -> Runs -> {run_name}")


def save_log(
    run_name: str,
    results: list[EvalResult],
    metric_names: list[str],
    total_cases: int,
    logs_dir: Path = LOGS_DIR,
) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{run_name}.txt"
    log_path.write_text(_format_log(run_name, results, metric_names, total_cases))
    print(f"Log saved: {log_path}")


def _format_log(
    run_name: str,
    results: list[EvalResult],
    metric_names: list[str],
    total_cases: int,
) -> str:
    with_scores = sum(1 for result in results if result.scores)
    lines = [
        f"Run    : {run_name}",
        f"Date   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Cases  : {total_cases} total  ({with_scores} with scores)",
        "-" * 64,
    ]

    for index, result in enumerate(results, 1):
        lines.extend(_format_case(index, total_cases, result))

    lines.append(f"\n{'-' * 64}")
    lines.append("Summary")
    for metric_name, values in summarize_scores(results, metric_names).items():
        lines.append(
            f"  {metric_name:<22} "
            f"avg={values['average']:.3f}  pass={values['passing']}/{values['total']}"
        )
    lines.append(f"\nLangfuse: Datasets -> {DATASET_NAME} -> Runs -> {run_name}")
    return "\n".join(lines)


def _format_case(index: int, total_cases: int, result: EvalResult) -> list[str]:
    answer_preview = result.answer.replace("\n", " ")
    lines = [f"\n[{index}/{total_cases}] {result.question}", f"  Answer : {answer_preview}"]
    for metric_name, (score, reason) in result.scores.items():
        reason_text = f" - {reason}" if reason else ""
        lines.append(f"  {metric_name:<22} : {score:.2f}{reason_text}")
    return lines
