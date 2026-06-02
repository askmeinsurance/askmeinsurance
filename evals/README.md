# Evals

Evaluation uses [DeepEval](https://github.com/confident-ai/deepeval) with Gemini Flash Lite as the judge. Test cases are managed in a Langfuse dataset (`insurance_chatbot_evals`) and results are linked back to the traces that produced them.

## Hypothesis

The hypothesis is stated in the [Problem Statement](../README.md#problem-statement): naive RAG systematically fails to provide complete information on insurance questions, because it retrieves against the user's literal words rather than the full scope of what they need to know. The evals exist to test that claim.

**naive_rag/** is a minimal straight-retrieval pipeline — embed the query, pull top-K chunks from Qdrant, synthesise with Gemini. It deliberately uses the same synthesis system prompt as the main workflow (`SIMPLEV2_SYNTHESIS_SYSTEM`) so any score difference is attributable to the agent architecture, not prompting.


## The custom IntentCoverageMetric using G-Eval

IntentCoverage measures in the opposite direction. Instead of starting from the actual output and asking "is this relevant?", it starts from the expected output and asks "is this covered?"

Each test case has a **base answer** — a minimal answer written for the exact intent, nothing more. It defines what the workflow must cover.

```
base answer = A + B + C  (covers the original intent exactly)

workflow answer = A + B + C + D + E  → pass  (original intent covered, extra content allowed)
workflow answer = A + C + D + E      → fail  (B is missing, original intent not fully covered)
```

The scoring:
1. An LLM decomposes the base answer into atomic coverage points — each a binary, independently verifiable fact.
2. Each point is checked against the actual output: covered or missing.
3. Score = covered points / total points.

Extra content in the actual output is ignored. Tone and confidence don't factor in. The only question is whether the original intent was fully addressed.

Base answers were generated using NotebookLM — all product PDFs were loaded in, each question was asked, and the response was manually copied as the `base_answer`. NotebookLM grounds its answers strictly in uploaded documents, which makes the base answers more reliable than asking a general-purpose LLM from memory. It generates a sufficient baseline reference dataset that can be used for evaluation. The ideal eval dataset should be obtained from Financial Consultants. There are limitations to NotebookLM, but for the scope of this project we treat it as the reference dataset.

## Results (30 test cases)

> These results show naive RAG's completeness failure across 30 test cases. The hypothesis — that naive RAG fails to surface complete information on insurance questions — is stated in the [Problem Statement](../README.md#problem-statement).

| Metric | Naive RAG | Structured workflow | Delta |
|---|---|---|---|
| Intent coverage | 0.412 | 0.743 | +0.331 |
| Helpfulness | 0.867 | 0.960 | +0.093 |
| Tone & approach | 0.630 | 0.733 | +0.103 |
| Honesty | 0.730 | 0.703 | -0.027 |
| Faithfulness | 0.500 | 0.847 | +0.347 |
| Contextual precision | 0.417 | 0.652 | +0.235 |
| Contextual recall | 0.491 | 0.909 | +0.418 |

Raw logs: [`naive_rag_results.txt`](../assets/naive_rag_results.txt) | [`structured_reasoning_results.txt`](../assets/structured_reasoning_results.txt)

**Findings:**

The intent coverage gap (0.41 → 0.74) is the primary result. It directly measures whether the actual answer contains all the facts the user needed, and it shows naive RAG covers the original intent less than half as completely as the structured workflow.

Contextual recall (0.49 → 0.91) tells the same story at the retrieval layer. Naive RAG frequently misses the relevant product documents entirely — when the context doesn't contain the right chunks, the model either guesses or refuses, and intent coverage falls in both cases.

The helpfulness gap (+0.09) looks small by comparison, and it is intentionally deprioritized here. Naive RAG scored 0.867 partly because the judge rewards a well-worded refusal ("I don't have that information, please contact AIA") almost as highly as a correct answer. Helpfulness can't distinguish between answering and not answering, so a small helpfulness delta coexists with a large completeness gap. The structured workflow scored 0.960 because it actually answered — not because it sounded better.

Honesty dropped slightly (-0.03). Naive RAG hedged constantly. The structured workflow commits to answers, and occasionally the judge reads that commitment as less calibrated, even when the answer is correct.

The hypothesis holds. Naive RAG fails to provide complete information, and the metrics that actually measure coverage show it clearly.

## Examples: Naive RAG vs Structured Workflow

Three representative cases from the 30-case eval run. These aren't just cases where naive RAG scored lower — they're cases where it gave dangerously incomplete information that could lead a user to believe they have coverage they don't, or miss critical conditions before filing a claim.

---

### Example 1: Product comparison requiring specific figures

**Question:** Assuming the funds grow at 4.25%, which plan gives a better annual bonus: the 5-year payment AIA Smart Flexi Growth or the AIA Smart Goal 10? And by how much?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 1/8 (12%) | 8/8 (100%) |
| Faithfulness | 0.00 | 0.80 |
| Contextual precision | 0.00 | 0.78 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "The provided information does not contain specific details about the AIA Smart Flexi Growth (5-year payment) or AIA Smart Goal 10 plans that would allow for a direct comparison of their annual bonuses under a 4.25% growth rate[...]"

**Structured workflow:**
> "When comparing the AIA Smart Flexi Growth (5-Pay option) and AIA Smart Goal 10 plans, the AIA Smart Flexi Growth 5-Pay plan shows a higher illustrated annual Reversionary Bonus (RB) rate at an assumed investment rate of return of 4.25%[...]"

Naive RAG retrieved general textbook content on how reversionary bonuses work, but none of the chunks contained the product-specific illustrated rates. The structured workflow's name-matching and parallel product retrieval steps found the right product documents.

---

### Example 2: Renewal schedule in later ages

**Question:** I'm considering the 10-year AIA Secure Flexi Term (R&C) plan. How does the guaranteed renewal period change as I reach my 90s?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 0/9 (0%) | 9/9 (100%) |
| Faithfulness | 0.00 | 1.00 |
| Contextual precision | 0.00 | 0.57 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "The AIA Secure Flexi Term (R&C) plan, like many term insurance policies with a renewable option, typically has limitations on how long you can renew the policy[...]"

**Structured workflow:**
> "The AIA Secure Flexi Term (R&C) plan allows for successive renewals up to the insured's 101st birthday. However, the duration of the guaranteed renewal period changes as you get older[...]"

Naive RAG retrieved general content on renewable term insurance but nothing specific to this product. Its answer was not only incomplete — the claim that renewal "would likely not extend past the 80s or early 90s" is factually wrong for a plan that covers to age 101.

---

### Example 3: Simple product-specific fact

**Question:** How much guaranteed cash back will I get each year if I buy the 5-year payment AIA Smart Flexi Rewards (II) plan?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 1/6 (17%) | 6/6 (100%) |
| Faithfulness | 0.20 | 1.00 |
| Contextual precision | 0.00 | 0.83 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "I cannot provide specific details about the guaranteed cash back amounts for the AIA Smart Flexi Rewards (II) plan with a 5-year payment term. The information I have access to does not contain product-specific payout schedules[...]"

**Structured workflow:**
> "The AIA Smart Flexi Rewards (II) (5-Pay) plan offers a **guaranteed yearly coupon** benefit. This coupon is equivalent to **15% of the Insured Amount** and is payable starting from the 2nd policy anniversary until one year before the policy maturity[...]"

Naive RAG retrieved general textbook content on cash dividend structures instead of the product document. The structured workflow's name-match step retrieved the AIA Smart Flexi Rewards product summary and answered with the exact percentage in the first sentence.

---

## Running evals

### Setup

```bash
cd evals/
cp example.env .env
```

Fill in `evals/.env`:

| Key | What it's for |
|---|---|
| `GEMINI_API_KEY` | LLM judge (Gemini Flash Lite) and chatbot invocation |
| `QDRANT_URL` | Vector store for retrieval |
| `QDRANT_API_KEY` | Vector store auth (leave blank for local) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Tracing and run reporting (optional) |
| `LANGFUSE_HOST` | Langfuse instance URL |

The evals invoke the backend LangGraph directly — no running server needed. They also need the backend env vars (Qdrant, LLM provider keys). The simplest setup is to copy `backend/.env` into `evals/.env` and add the eval-specific keys on top.

### Running

```bash
# From evals/
uv run python run_evals.py                                              # full run, both flows
uv run python run_evals.py --flow simple_workflow                       # structured workflow only
uv run python run_evals.py --flow naive_rag                             # naive RAG baseline only
uv run python run_evals.py --flow naive_rag --top-k 10                  # baseline with top-10 retrieval
uv run python run_evals.py --run-name "my-run"                          # named run for Langfuse tracking
uv run python run_evals.py --limit 5                                    # smoke test with 5 cases
```

Results print to the terminal and are saved under `evals/logs/`. Each run is also linked in Langfuse under Datasets → `insurance_chatbot_evals` → Runs.

## Dataset

Two test case sources, both under `evals/dataset/`:

- `manual_data.json` — curated cases covering specific insurance products and concepts
- `evals/01_create_reference_dataset/textbook_evals/generated_goldens.json` — generated cases from the insurance textbook corpus

Questions were generated using ChatGPT and Gemini, some by prompting the models directly and some by attaching product PDFs. Each case has a question, an expected output (the base answer), and a source tag.

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

