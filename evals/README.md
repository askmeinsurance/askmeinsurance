# Evals

Evaluation uses [DeepEval](https://github.com/confident-ai/deepeval) with Gemini Flash Lite as the judge. Test cases are managed in a Langfuse dataset (`insurance_chatbot_evals`) and results are linked back to the traces that produced them.

## Folder structure

```
evals/
├── run_evals.py              # entry point — parse args, wire flow, run
├── eval_utils/
│   ├── config.py             # RunConfig dataclass, CLI arg parsing, EvalFlow type
│   ├── runner.py             # orchestration: load cases → invoke → score → report
│   ├── chatbot_invoker.py    # invokes the backend LangGraph directly (no running server)
│   ├── dataset_loader.py     # loads manual_data.json into EvalCase objects
│   ├── metrics.py            # GeminiJudge + MetricConfig wrappers around DeepEval metrics
│   ├── criteria.py           # GEval rubrics: helpfulness, honesty, tone, faithfulness
│   ├── retrieval.py          # extracts retrieved chunks from workflow output for context metrics
│   ├── langfuse_reporter.py  # pushes scores and links runs back to Langfuse dataset
│   ├── reporting.py          # terminal summary table + log file writer
│   ├── models.py             # EvalResult, ScoreMap — shared data types
│   └── bootstrap.py          # loads .env and prepends backend/ to sys.path
├── naive_rag/
│   └── naive_rag_demo.py     # self-contained RAG baseline: embed → Qdrant → Gemini
├── dataset/
│   └── manual_data.json      # curated test cases (question + base_answer + source tag)
├── tests/                    # unit tests for each eval_utils module; mock the LLM judge
│   │                         # and Langfuse so they run offline without API keys
│   └── test_naive_rag_runner.py
└── logs/                     # run outputs written here (gitignored)
```

**naive_rag/** is a minimal straight-retrieval pipeline — embed the query, pull top-K chunks from Qdrant, synthesise with Gemini. It is not a toy: it deliberately uses the same synthesis system prompt as the main workflow (`SIMPLEV2_SYNTHESIS_SYSTEM`) so that any Helpfulness delta is attributable to the agent architecture (intent expansion, decomposition, parallel retrieval) rather than prompting differences.

## Dataset

Two test case sources, both under `evals/dataset/`:

- `manual_data.json` — curated cases covering specific insurance products and concepts
- `evals/01_create_reference_dataset/textbook_evals/generated_goldens.json` — generated cases from the insurance textbook corpus

**How `manual_data.json` was built:**

Questions were generated using ChatGPT and Gemini, some by prompting the models directly and some by attaching the product PDFs and asking them to generate questions from the document content.

Base answers were generated using NotebookLM. All product PDFs were loaded into NotebookLM, then each question was asked and the response was manually copied as the `base_answer`. NotebookLM was chosen because it grounds its answers strictly in the uploaded documents, making hallucination less likely and the base answers more factually reliable than asking a general-purpose LLM from memory.

Each case has a question, an expected output (the base answer written for the exact intent), and a source tag. The expected output is what `IntentCoverage` and `Faithfulness` score against.

**Why a base answer is needed**

The workflow is designed to produce answers that go beyond the original question — intent expansion deliberately adds angles the user didn't ask for. This creates an evaluation problem: a standard metric that scores the actual output against the input query will penalise the extra content as irrelevant, even though that content is the whole point.

The base answer solves this by defining the minimum acceptable coverage for the original intent only. It answers the question directly and nothing more. The eval then checks whether the workflow's richer answer contains at least everything in the base answer — extra content is ignored.

```
base answer = A + B + C  (covers the original intent exactly)

workflow answer = A + B + C + D + E  → pass  (original intent covered, extra content allowed)
workflow answer = A + C + D + E      → fail  (B is missing, original intent not fully covered)
```

Without a base answer, there's no way to separate "did the workflow cover what was asked?" from "did the workflow add useful depth?" — they'd collapse into a single score that can't tell the difference.

## Running evals

```bash
# From evals/ — copy example.env to .env and fill in GEMINI_API_KEY, QDRANT_URL, LANGFUSE_* keys
uv run python run_evals.py                        # full run
uv run python run_evals.py --flow simple_workflow
uv run python run_evals.py --flow naive_rag
uv run python run_evals.py --run-name "my-run"    # named run for Langfuse tracking
uv run python run_evals.py --limit 5              # quick smoke test
uv run python run_evals.py --flow naive_rag --top-k 10
```

Results are printed to the terminal and saved under `evals/logs/`. Each run is also linked in Langfuse under Datasets → `insurance_chatbot_evals` → Runs.

| Metric | What it measures |
|---|---|
| Helpfulness | Intent alignment, completeness, and tone |
| Tone & approach | Empathy, decisiveness, contextual fit |
| Honesty | Factual fidelity, calibrated uncertainty |
| Faithfulness | Consistency with expected output |
| Intent coverage | Custom two-phase metric: decomposes expected output into atomic coverage points, then binary-checks each in the actual output |
| Contextual precision / recall | Whether retrieved chunks are relevant and complete |

The same suite runs against the naive RAG baseline by switching `--flow naive_rag`. The primary claim of this project lives or dies by the Helpfulness delta between the two.

## Naive Rag Vs Structured Reasoning Workflow Eval Results (30 test cases)

> These results are the quantitative proof for the hypothesis stated in the [Problem Statement](../README.md#problem-statement).

| Metric | Naive RAG | Structured workflow | Delta |
|---|---|---|---|
| Helpfulness | 0.893 | 0.953 | +0.060 |
| Tone & approach | 0.613 | 0.737 | +0.123 |
| Honesty | 0.757 | 0.687 | -0.070 |
| Faithfulness | 0.507 | 0.857 | +0.350 |
| Intent coverage | 0.407 | 0.761 | +0.354 |
| Contextual precision | 0.374 | 0.726 | +0.352 |
| Contextual recall | 0.488 | 0.946 | +0.457 |

Raw logs: [`naive_rag_results.txt`](../assets/naive_rag_results.txt) | [`structured_reasoning_results.txt`](../assets/structured_reasoning_results.txt)

**Findings:**

The biggest gains are in retrieval quality. Contextual recall went from 0.49 to 0.95 — the structured workflow retrieves nearly everything needed to answer the question, while naive RAG frequently misses relevant chunks entirely. Intent coverage followed the same pattern: the structured workflow covers the original intent far more completely (0.76 vs 0.41).

Helpfulness improved only modestly (+0.06). This is because naive RAG scored surprisingly well on helpfulness by politely saying "I don't have that information" — which the judge rewarded as transparent and appropriate. The structured workflow actually answers the question, which the judge holds to a higher standard.

Honesty dropped slightly (-0.07) for the same reason. Naive RAG hedged constantly; the structured workflow commits to answers. Occasionally the judge reads that commitment as less calibrated uncertainty, even when the answer is factually correct.

The hypothesis holds: the structured workflow produces more complete, better-grounded answers. The helpfulness metric alone doesn't capture the full picture — intent coverage and faithfulness are more honest measures of answer quality here.

## Why not AnswerRelevancyMetric

DeepEval's `AnswerRelevancyMetric` scores answers using this ratio:

```
relevant statements / total statements
```

It decomposes the actual output into atomic statements, then checks each one against the original input query. If the statement addresses the query, it's relevant. If not, it drags the score down.

That formula actively punishes the behaviour this workflow is designed to produce. If the base answer covers A+B+C and the workflow adds D+E (non-guaranteed bonuses, break-even analysis), D and E get classified as irrelevant to the original query and lower the score. A minimal answer that only covers A+B+C would score higher than a richer one that covers everything plus more.

The custom `IntentCoverageMetric` flips the direction. Instead of starting from the actual output and asking "is this relevant?", it starts from the expected output (a base answer written for the exact intent) and asks "is this covered?". It decomposes the base answer into atomic coverage points, then binary-checks each one in the actual output. Score = covered points / total points. Extra content in the actual output is ignored — it neither helps nor hurts. What matters is whether the original intent was fully addressed.
