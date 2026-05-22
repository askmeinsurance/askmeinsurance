"""DeepEval metric configurations for the insurance chatbot."""
import os


from deepeval.metrics import AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric, GEval
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
            name="balanced_explanation",
            criteria=(
                "Evaluate if the output explains complex insurance terminology using an easy-to-understand analogy or simple math. "
                "It must avoid looping back into more jargon and ensure a baseline user can grasp who pays what, and when. "
                "It needs to have a good balance that is not too simplistic and not too complicated with jargon."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
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
