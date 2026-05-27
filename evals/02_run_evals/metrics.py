"""DeepEval metric configurations for the insurance chatbot."""

import asyncio
import json
import os
from dataclasses import dataclass

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    GEval,
)
from deepeval.metrics.base_metric import BaseMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from langchain_google_genai import ChatGoogleGenerativeAI


@dataclass
class MetricConfig:
    """Wraps a DeepEval metric with its data requirements."""

    metric: BaseMetric
    requires_expected_output: bool = False
    requires_retrieval_context: bool = False


class GeminiJudge(DeepEvalBaseLLM):
    """Gemini-backed LLM judge for DeepEval metrics."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite") -> None:
        model_name = "gemini-flash-lite-latest"
        self._model_name = model_name
        _timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0,
            request_timeout=_timeout,
        )

    def load_model(self) -> ChatGoogleGenerativeAI:
        return self._llm

    def generate(self, prompt: str) -> str:
        content = self._llm.invoke(prompt).content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content

    async def a_generate(self, prompt: str) -> str:
        content = (await self._llm.ainvoke(prompt)).content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content

    def get_model_name(self) -> str:
        return self._model_name


class IntentCoverageMetric(BaseMetric):
    """Two-phase coverage metric: decompose base_answer, then binary-check each point.

    Phase 1: LLM decomposes expected_output into a list of discrete coverage points.
    Phase 2: For each point, a binary LLM check determines if actual_output covers it.
    Score = covered_points / total_points (true ratio, not holistic judgment).
    Extra content in actual_output beyond expected_output is irrelevant to the score.
    """

    name = "intent_coverage"

    def __init__(self, model: "GeminiJudge", threshold: float = 0.7) -> None:
        if model is None:
            raise ValueError("IntentCoverageMetric requires an explicit judge model")
        self.model = model
        self.threshold = threshold

    def measure(self, test_case, *args, **kwargs) -> float:
        raise NotImplementedError("Use a_measure; sync execution is not supported.")

    async def a_measure(self, test_case, *args, **kwargs) -> float:
        expected = (test_case.expected_output or "").strip()
        actual = test_case.actual_output or ""

        if not expected:
            self.score = 0.0
            self.reason = "Empty base_answer; no coverage points to evaluate."
            self.success = False
            return self.score

        points = await self._decompose(expected)

        if not points:
            self.score = 0.0
            self.reason = "Decomposition returned no points."
            self.success = False
            return self.score

        verdicts: tuple[bool, ...] = await asyncio.gather(
            *[self._check_point(p, actual) for p in points]
        )

        covered = sum(verdicts)
        total = len(points)
        self.score = covered / total
        verdict_lines = [
            f"  {'[COVERED]' if v else '[MISSING]'} {p}"
            for p, v in zip(points, verdicts)
        ]
        self.reason = (
            f"Covered {covered}/{total} points ({self.score:.0%}):\n"
            + "\n".join(verdict_lines)
        )
        self.success = self.is_successful()
        return self.score

    async def _decompose(self, expected_output: str) -> list[str]:
        """Ask the judge LLM to break expected_output into atomic coverage points."""
        prompt = (
            "You are an evaluation assistant. Decompose the following reference answer "
            "into discrete, atomic coverage points.\n\n"
            f"Reference answer:\n{expected_output}\n\n"
            "Instructions:\n"
            "- Extract each distinct factual claim, condition, or piece of information as a separate point.\n"
            "- Each point must be self-contained and independently verifiable against a chatbot response.\n"
            "- Do not add information not present in the reference answer.\n"
            "- Return ONLY a valid JSON array of strings, with no markdown fencing, no preamble, and no explanation.\n\n"
            'Example output format:\n["The minimum premium is $3,600.", "This applies to the 10-year payment option only."]'
        )
        raw = await self.model.a_generate(prompt)
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [str(p).strip() for p in result if str(p).strip()]
        except json.JSONDecodeError:
            return ["[decomposition_failed: could not parse LLM output]"]
        return []

    async def _check_point(self, point: str, actual_output: str) -> bool:
        """Binary check: does actual_output cover this single coverage point?"""
        prompt = (
            "You are an evaluation assistant checking whether a chatbot response covers a specific point.\n\n"
            f"Point to check:\n{point}\n\n"
            f"Chatbot response:\n{actual_output}\n\n"
            "Does the chatbot response cover this point, either explicitly or with equivalent meaning? "
            "Answer with exactly one word: YES or NO."
        )
        raw = await self.model.a_generate(prompt)
        return raw.strip().upper().startswith("YES")

    def is_successful(self) -> bool:
        return (self.score or 0.0) >= self.threshold


def build_metrics(judge: GeminiJudge | None = None) -> dict[str, MetricConfig]:
    """Return all configured DeepEval metrics keyed by slug."""
    return {
        # "answer_relevancy": MetricConfig(
        #     metric=AnswerRelevancyMetric(
        #         threshold=0.7,
        #         model=judge,
        #         include_reason=True,
        #     ),
        # ),
        "helpfulness": MetricConfig(
            metric=GEval(
                name="helpfulness",
                criteria=("""## 1. Helpfulness

**Core Definition:** The degree to which the response successfully, efficiently, and safely fulfills the user’s intent and resolves their underlying task.

When grading for helpfulness, evaluators look at whether the model proactively solves the problem while respecting the constraints of the prompt.

### Key Evaluation Criteria:

* **Intent Alignment:** Does the model grasp the true goal behind the prompt (including implicit context), or does it give a superficial, overly literal answer?
* **Completeness & Actionability:** Does the response provide all the necessary information to complete the task? If the user is trying to execute a process, are the steps clear, correctly ordered, and immediately usable?
* **Constraint Adherence:** Did the model follow all formatting, tone, length, and technical guidelines explicitly stated in the prompt (e.g., "Write in under 150 words," "Use Python," "Output as a markdown table")?
* **Efficiency & Conciseness:** Is the response direct and free of fluff, robotic filler, or unnecessary repetition? Can the user easily scan and digest the information?
* **Tone Appropriateness:** Is the language calibrated to the user’s implied expertise level (e.g., explaining a complex topic simply to a beginner versus using technical jargon for an expert)?
"""),
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=0.7,
                model=judge,
            ),
        ),
        "tone_and_approach": MetricConfig(
            metric=GEval(
                name="tone_and_approach",
                criteria=(
                    """**Core Philosophy:** A helpful response actively moves the user forward. It respects the user’s time by removing cognitive load, breaking down institutional complexity, and charting a clear, actionable path toward their ultimate goal.

When evaluating for helpfulness, look at the conversation through three high-level lenses:

* **Empathetic Translation:** The bot must act as a bridge between dense legal/financial prose and everyday human conversation. It should simplify abstract insurance concepts using clear language and practical examples, matching the user’s implied knowledge level without sounding patronizing.
* **Decisive Actionability:** The response should never leave the user guessing about their next step. Whether they are asking about an abstract concept, a specific policy limit, or buying a new plan, the bot must seamlessly connect its answer to a logical resolution—such as generating a quote, opening a claim, or gracefully transitioning to a licensed human agent.
* **Contextual Intuition:** The bot must read between the lines of a query. It should recognize the underlying intent behind a question, capture relevant customer details naturally, and retrieve precise information directly from policy documents rather than forcing the user to dig through a wall of text.
"""
                ),
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=0.7,
                model=judge,
            ),
        ),
        "honesty": MetricConfig(
            metric=GEval(
                name="honesty",
                criteria=(
                    """**Core Philosophy:** An honest response prioritizes absolute factual integrity and regulatory compliance over making a quick sale or providing a satisfying answer. It accurately reflects the boundaries of the insurance contract and cleanly communicates its own operational limits.

When evaluating for honesty, look at the conversation through three high-level lenses:

* **Contractual Fidelity:** The bot must treat the insurance policy as an absolute source of truth. It must never over-simplify conditional logic into a misleading "yes" or "no," nor gloss over critical exclusions, deductibles, or limits just to keep the conversation positive or push a prospect down the sales funnel.
* **Calibrated Uncertainty:** The bot must possess the "self-awareness" to know when it cannot give a definitive answer. It should explicitly state its limitations when faced with missing account data, ambiguous state-specific regulations, or complex underwriting scenarios, choosing a transparent, safe refusal over a plausible-sounding guess.
* **Operational Transparency:** The bot must maintain absolute clarity regarding its identity and the nature of its information. It must never misrepresent its AI nature, imply that a casual premium estimate is a legally binding rate guarantee, or present general educational advice as a definitive confirmation of a user’s individual coverage.
"""
                ),
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=0.7,
                model=judge,
            ),
        ),
        "contextual_precision": MetricConfig(
            metric=ContextualPrecisionMetric(
                threshold=0.7,
                model=judge,
                include_reason=True,
            ),
            requires_expected_output=True,
            requires_retrieval_context=True,
        ),
        "contextual_recall": MetricConfig(
            metric=ContextualRecallMetric(
                threshold=0.7,
                model=judge,
                include_reason=True,
            ),
            requires_expected_output=True,
            requires_retrieval_context=True,
        ),
        "faithfulness": MetricConfig(
            metric=GEval(
                name="faithfulness",
                criteria=(
                    "The actual output must be factually consistent with the expected output. "
                    "It should cover the same key points without contradicting the reference answer. "
                    "Missing minor details is acceptable; contradicting key facts is not."
                ),
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                    LLMTestCaseParams.EXPECTED_OUTPUT,
                ],
                threshold=0.6,
                model=judge,
            ),
            requires_expected_output=True,
        ),
        "intent_coverage": MetricConfig(
            metric=IntentCoverageMetric(model=judge, threshold=0.7),
            requires_expected_output=True,
        ),
    }
