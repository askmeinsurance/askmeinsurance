"""Configuration and CLI parsing for eval runs."""

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Sequence

EVALS_ROOT = Path(__file__).parents[1]
BACKEND_ROOT = EVALS_ROOT.parent / "backend"
DATASET_NAME = "insurance_chatbot_evals"
LOGS_DIR = EVALS_ROOT / "logs"
DEFAULT_FLOW = "simple_workflow"
DEFAULT_TOP_K = 5
EvalFlow = Literal["simple_workflow", "naive_rag"]


@dataclass(frozen=True)
class RunConfig:
    run_name: str
    flow: EvalFlow = DEFAULT_FLOW
    limit: int | None = None
    top_k: int = DEFAULT_TOP_K


def parse_run_config(
    argv: Sequence[str] | None = None,
    now: Callable[[], datetime] = datetime.now,
) -> RunConfig:
    parser = argparse.ArgumentParser(description="Run insurance chatbot evaluations")
    parser.add_argument("--run-name", default=None, help="Label for this run in Langfuse")
    parser.add_argument(
        "--flow",
        choices=("simple_workflow", "naive_rag"),
        default=DEFAULT_FLOW,
        help="Evaluation flow to run.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap number of cases")
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of retrieved chunks for naive_rag.",
    )
    args = parser.parse_args(argv)

    run_name = args.run_name or f"run_{now().strftime('%Y%m%d_%H%M%S')}"
    return RunConfig(
        run_name=run_name,
        flow=args.flow,
        limit=args.limit,
        top_k=args.top_k,
    )
