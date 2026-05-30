"""Evaluation runner for the insurance chatbot.

Usage:
    uv run python run_evals.py
    uv run python run_evals.py --flow simple_workflow
    uv run python run_evals.py --flow naive_rag
    uv run python run_evals.py --run-name "v2-synthesis-prompt"
    uv run python run_evals.py --flow naive_rag --run-name "baseline_20260530" --top-k 10
    uv run python run_evals.py --flow simple_workflow --run-name "structured_reasoning_20260530"
"""

import asyncio

from eval_utils.bootstrap import bootstrap_environment

bootstrap_environment()

from eval_utils.runner import main


if __name__ == "__main__":
    asyncio.run(main())
