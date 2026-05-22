"""DeepEval metric configurations for the insurance chatbot."""

import os


from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    GEval,
)
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from langchain_google_genai import ChatGoogleGenerativeAI


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


def build_metrics(judge: GeminiJudge | None = None) -> dict:
    """Return all configured DeepEval metrics keyed by slug."""
    return {
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=0.7,
            model=judge,
            include_reason=True,
        ),
        "completeness": GEval(
            name="helpfulness",
            criteria=("""## 1. Helpfulness

**Core Definition:** The degree to which the response successfully, efficiently, and safely fulfills the user’s intent and resolves their underlying task.

When grading for helpfulness, evaluators look at whether the model proactively solves the problem while respecting the constraints of the prompt.

### Key Evaluation Criteria:

* **Intent Alignment:** Does the model grasp the true goal behind the prompt (including implicit context), or does it give a superficial, overly literal answer?
* **Completeness & Actionability:** Does the response provide all the necessary information to complete the task? If the user is trying to execute a process, are the steps clear, correctly ordered, and immediately usable?
* **Constraint Adherence:** Did the model follow all formatting, tone, length, and technical guidelines explicitly stated in the prompt (e.g., "Write in under 150 words," "Use Python," "Output as a markdown table")?
* **Efficiency & Conciseness:** Is the response direct and free of fluff, robotic filler, or unnecessary repetition? Can the user easily scan and digest the information?
* **Tone Appropriateness:** Is the language calibrated to the user's implied expertise level (e.g., explaining a complex topic simply to a beginner versus using technical jargon for an expert)?
"""),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            threshold=0.7,
            model=judge,
        ),
        "tone_and_approach": GEval(
            name="tone_and_approach",
            criteria=(
                """**Core Philosophy:** A helpful response actively moves the user forward. It respects the user’s time by removing cognitive load, breaking down institutional complexity, and charting a clear, actionable path toward their ultimate goal.

When evaluating for helpfulness, look at the conversation through three high-level lenses:

* **Empathetic Translation:** The bot must act as a bridge between dense legal/financial prose and everyday human conversation. It should simplify abstract insurance concepts using clear language and practical examples, matching the user's implied knowledge level without sounding patronizing.
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
        "honesty": GEval(
            name="honesty",
            criteria=(
                """**Core Philosophy:** An honest response prioritizes absolute factual integrity and regulatory compliance over making a quick sale or providing a satisfying answer. It accurately reflects the boundaries of the insurance contract and cleanly communicates its own operational limits.

When evaluating for honesty, look at the conversation through three high-level lenses:

* **Contractual Fidelity:** The bot must treat the insurance policy as an absolute source of truth. It must never over-simplify conditional logic into a misleading "yes" or "no," nor gloss over critical exclusions, deductibles, or limits just to keep the conversation positive or push a prospect down the sales funnel.
* **Calibrated Uncertainty:** The bot must possess the "self-awareness" to know when it cannot give a definitive answer. It should explicitly state its limitations when faced with missing account data, ambiguous state-specific regulations, or complex underwriting scenarios, choosing a transparent, safe refusal over a plausible-sounding guess.
* **Operational Transparency:** The bot must maintain absolute clarity regarding its identity and the nature of its information. It must never misrepresent its AI nature, imply that a casual premium estimate is a legally binding rate guarantee, or present general educational advice as a definitive confirmation of a user's individual coverage.
"""
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            threshold=0.7,
            model=judge,
        ),
        "contextual_precision": ContextualPrecisionMetric(
            threshold=0.7,
            model=judge,
            include_reason=True,
        ),
        "contextual_recall": ContextualRecallMetric(
            threshold=0.7,
            model=judge,
            include_reason=True,
        ),
        "faithfulness": GEval(
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
    }
