"""DeepEval metric configurations for the insurance chatbot."""
import os

from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from langchain_google_genai import ChatGoogleGenerativeAI


class GeminiJudge(DeepEvalBaseLLM):
    """Gemini-backed LLM judge for DeepEval metrics."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite") -> None:
        self._model_name = model_name
        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ["GEMINI_API_KEY"],
            temperature=0,
        )

    def load_model(self) -> ChatGoogleGenerativeAI:
        return self._llm

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        return (await self._llm.ainvoke(prompt)).content

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
            name="completeness",
            criteria=(
                "The response must completely address all aspects of the insurance question, "
                "covering key concepts, edge cases, limitations, and practical implications. "
                "A response that only partially answers the question should score low."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.7,
            model=judge,
        ),
        "insurance_accuracy": GEval(
            name="insurance_accuracy",
            criteria=(
                "The response must accurately explain insurance products, policies, and regulations. "
                "It must not fabricate policy terms, invent product features, make misleading claims, "
                "or provide incorrect financial advice. Factual errors should result in a low score."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.7,
            model=judge,
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
