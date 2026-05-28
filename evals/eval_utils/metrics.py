"""DeepEval metric configurations for the insurance chatbot."""

import asyncio
import json
import os
from dataclasses import dataclass

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    GEval,
)
from deepeval.metrics.base_metric import BaseMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from langchain_google_genai import ChatGoogleGenerativeAI

from eval_utils.criteria import (
    FAITHFULNESS_CRITERIA,
    HELPFULNESS_CRITERIA,
    HONESTY_CRITERIA,
    TONE_AND_APPROACH_CRITERIA,
)
from eval_utils.dataset_loader import EvalCase

DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
DEFAULT_METRIC_THRESHOLD = 0.7


@dataclass
class MetricConfig:
    """Wraps a DeepEval metric with its data requirements."""

    metric: BaseMetric
    requires_expected_output: bool = False
    requires_retrieval_context: bool = False

    def is_applicable(self, case: EvalCase, retrieval_context: list[str]) -> bool:
        if self.requires_expected_output and not case.expected_output:
            return False
        return not self.requires_retrieval_context or bool(retrieval_context)


class GeminiJudge(DeepEvalBaseLLM):
    """Gemini-backed LLM judge for DeepEval metrics."""

    def __init__(self, model_name: str = DEFAULT_GEMINI_MODEL) -> None:
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
        return _content_to_text(self._llm.invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        return _content_to_text((await self._llm.ainvoke(prompt)).content)

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

    def __init__(self, model: "GeminiJudge", threshold: float = DEFAULT_METRIC_THRESHOLD) -> None:
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
        # Strip markdown fences if the model wraps its JSON output
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
        "helpfulness": MetricConfig(
            metric=GEval(
                name="helpfulness",
                criteria=HELPFULNESS_CRITERIA,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=DEFAULT_METRIC_THRESHOLD,
                model=judge,
            ),
        ),
        "tone_and_approach": MetricConfig(
            metric=GEval(
                name="tone_and_approach",
                criteria=TONE_AND_APPROACH_CRITERIA,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=DEFAULT_METRIC_THRESHOLD,
                model=judge,
            ),
        ),
        "honesty": MetricConfig(
            metric=GEval(
                name="honesty",
                criteria=HONESTY_CRITERIA,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                threshold=DEFAULT_METRIC_THRESHOLD,
                model=judge,
            ),
        ),
        "contextual_precision": MetricConfig(
            metric=ContextualPrecisionMetric(
                threshold=DEFAULT_METRIC_THRESHOLD,
                model=judge,
                include_reason=True,
            ),
            requires_expected_output=True,
            requires_retrieval_context=True,
        ),
        "contextual_recall": MetricConfig(
            metric=ContextualRecallMetric(
                threshold=DEFAULT_METRIC_THRESHOLD,
                model=judge,
                include_reason=True,
            ),
            requires_expected_output=True,
            requires_retrieval_context=True,
        ),
        "faithfulness": MetricConfig(
            metric=GEval(
                name="faithfulness",
                criteria=FAITHFULNESS_CRITERIA,
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
            metric=IntentCoverageMetric(model=judge, threshold=DEFAULT_METRIC_THRESHOLD),
            requires_expected_output=True,
        ),
    }


def _content_to_text(content) -> str:
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)
