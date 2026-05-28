# askmeinsurance-evals

Evaluation tooling and scripts for the AskMeInsurance project.

## Run Evaluations

From this directory:

```bash
uv run python run_evals.py
uv run python run_evals.py --run-name "my-run"
uv run python run_evals.py --limit 5
```

Copy `example.env` to `.env` and fill in the Gemini, Qdrant, Langfuse, and backend settings required by the chatbot graph.

## Layout

- `run_evals.py` - thin CLI entrypoint.
- `eval_utils/` - active eval runner modules.
- `dataset/manual_data.json` - manual golden Q&A cases.
- `01_create_reference_dataset/` - one-off reference dataset creation scripts.
- `logs/` - local run summaries, ignored by git.

## Verify

```bash
uv run pytest tests
uv run python -m compileall run_evals.py eval_utils
```
