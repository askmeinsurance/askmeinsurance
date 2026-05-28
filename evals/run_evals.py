"""Evaluation runner for the insurance chatbot.

Usage:
    python run_evals.py
    python run_evals.py --run-name "v2-synthesis-prompt"
    python run_evals.py --run-name "v3-classifier" --limit 5
"""

import asyncio

from eval_utils.bootstrap import bootstrap_environment

bootstrap_environment()

from eval_utils.runner import main


if __name__ == "__main__":
    asyncio.run(main())
