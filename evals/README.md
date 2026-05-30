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

### Why a custom IntentCoverageMetric

The workflow deliberately produces answers that go beyond what was literally asked. The `intent_extension` and `intents_decomposition` steps expand the original query into related angles — edge cases, exclusions, related riders, calculation methods — that a knowledgeable advisor would include even if the user didn't think to ask. This is the behaviour being tested: does structured retrieval cover the original intent more completely than naive RAG?

Standard metrics break down in two different ways here.

**AnswerRelevancyMetric** scores using:

```
relevant statements / total statements
```

It decomposes the actual output into atomic statements and checks each one against the original input. Statements that address the query are relevant; anything else drags the score down. That formula actively punishes the extra depth the workflow is designed to produce. If the workflow answers A+B+C (the original intent) and adds D+E (related edge cases and exclusions), D and E are scored as irrelevant — a terse answer covering only A+B+C would score higher than the richer one. The metric rewards minimalism, not completeness.

**Faithfulness** (in DeepEval's sense) checks whether each claim in the actual output is supported by the retrieved context. It catches hallucination but doesn't measure coverage: an answer that mentions only A from a base answer covering A+B+C scores perfectly on faithfulness while missing two-thirds of the expected content.

**IntentCoverageMetric** is designed for the opposite direction. Instead of starting from the actual output and asking "is this relevant?", it starts from the expected output and asks "is this covered?":

1. An LLM decomposes the base answer into atomic coverage points — each a binary, independently verifiable fact.
2. Each point is checked against the actual output: covered or missing.
3. Score = covered points / total points.

Extra content in the actual output is ignored entirely. What matters is whether the original intent was fully addressed, not how much else was said.

This separation is what makes the eval meaningful. Helpfulness and faithfulness score how good the answer sounds and whether it hallucinates. IntentCoverage scores whether the workflow actually retrieved and surfaced the right information. The large gap between naive RAG (0.41) and the structured workflow (0.76) on this metric is the quantitative evidence that the architecture works — not just that it sounds more confident.



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

**On intent coverage as the primary signal:**

Standard metrics like Helpfulness are not a fair measure for this workflow. Naive RAG scored 0.893 on helpfulness — close to the structured workflow's 0.953 — largely because the judge rewards a well-worded refusal ("I don't have that information") almost as highly as a correct answer. A metric that can't distinguish between answering and not answering isn't useful for evaluating retrieval architecture.

IntentCoverage is a fairer measure because it is indifferent to tone and confidence. It only asks: did the answer contain the facts? The structured workflow scores 0.76 against naive RAG's 0.41 — a gap that can't be explained by hedging or politeness. It reflects that the workflow retrieved the right product documents and surfaced their specific terms, while naive RAG pulled thematically related but product-generic chunks and left the actual policy details uncovered.

This is what the hypothesis predicts: that a structured retrieval architecture would cover the original intent more completely than single-pass retrieval given the same synthesis prompt. The intent coverage delta (+0.35) confirms it.

## Examples: Naive RAG vs Structured Workflow

Three representative cases from the 30-case eval run, chosen to show how the two approaches diverge on product-specific questions.

---

### Example 1: Product comparison requiring specific figures

**Question:** Assuming the funds grow at 4.25%, which plan gives a better annual bonus: the 5-year payment AIA Smart Flexi Growth or the AIA Smart Goal 10? And by how much?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 0/8 (0%) | 8/8 (100%) |
| Faithfulness | 0.00 | 1.00 |
| Contextual precision | 0.00 | 0.68 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "I cannot directly compare the annual bonuses for the AIA Smart Flexi Growth (5-year payment) and AIA Smart Goal 10 plans based on the information provided. The evidence discusses how **reversionary bo[...]"

**Structured workflow:**
> "Let's compare the annual bonus projections for the AIA Smart Flexi Growth (5-Pay option) and AIA Smart Goal 10, assuming a 4.25% fund growth rate. ### AIA Smart Flexi Growth (5-Pay Option) * **Rev[...]"

Naive RAG retrieved general textbook content on how reversionary bonuses work, but none of the chunks contained the product-specific illustrated rates. The structured workflow's name-matching and parallel product retrieval steps found the right product documents.

---

### Example 2: Renewal schedule in later ages

**Question:** I'm considering the 10-year AIA Secure Flexi Term (R&C) plan. How does the guaranteed renewal period change as I reach my 90s?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 0/9 (0%) | 9/9 (100%) |
| Faithfulness | 0.10 | 1.00 |
| Contextual precision | 0.00 | 0.92 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "The AIA Secure Flexi Term (R&C) plan is a 10-year term insurance policy. For term insurance policies with a renewable option, the ability to renew is typically limited by a specified age. Based on ge[...]"

**Structured workflow:**
> "The AIA Secure Flexi Term (R&C) plan offers a guaranteed renewal period that changes as you get older, particularly as you approach and enter your 90s. The renewal term is designed to shorten with inc[...]"

Naive RAG retrieved general content on renewable term insurance but nothing specific to this product. Its answer was not only incomplete — the claim that renewal "would likely not extend past the 80s or early 90s" is factually wrong for a plan that covers to age 101.

---

### Example 3: Simple product-specific fact

**Question:** Exactly how many years do I have to pay premiums if I sign up for the AIA Life Dividends plan?

| Metric | Naive RAG | Structured |
|---|---|---|
| Intent coverage | 0/1 (0%) | 1/1 (100%) |
| Faithfulness | 0.20 | 1.00 |
| Contextual precision | 0.00 | 1.00 |
| Contextual recall | 0.00 | 1.00 |

**Naive RAG:**
> "The AIA Life Dividends plan is a type of Whole Life Insurance. For this kind of policy, premiums can be structured in a few ways: * **Ordinary Whole Life Insurance:** Premiums are typically paid th[...]"

**Structured workflow:**
> "The AIA Life Dividends plan has a **limited premium payment term of 10 years**. This means you will pay premiums for 10 years, and then your policy will continue to provide coverage for your entire li[...]"

Naive RAG retrieved general textbook content on whole life premium structures instead of the product document. Its answer talks about "a few ways" premiums can work — accurate in general, but completely wrong for this specific plan. The structured workflow's name-match step retrieved the AIA Life Dividends product summary and answered in the first sentence.

---

