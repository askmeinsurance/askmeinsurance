import logging

from deepeval.models.base_model import DeepEvalBaseLLM
from deepteam import Guardrails
from deepteam.guardrails import (
    IllegalGuard,
    PrivacyGuard,
    PromptInjectionGuard,
    TopicalGuard,
    ToxicityGuard,
)

from app.agent.services.llm_service import get_llm
from app.core.config import get_settings

logger = logging.getLogger("askmeinsurance.guardrails")

_guardrails: Guardrails | None = None

INSURANCE_TOPICS = [
    "insurance",
    "life insurance",
    "health insurance",
    "motor insurance",
    "travel insurance",
    "policy",
    "premiums",
    "claims",
    "coverage",
    "benefits",
]


class OpenRouterEvalLLM(DeepEvalBaseLLM):
    """Wraps get_llm() so deepteam can use the existing OpenRouter setup as its evaluation model."""

    def __init__(self) -> None:
        self._llm = get_llm("guardrails")

    def get_model_name(self) -> str:
        return "openrouter-guardrails"

    def load_model(self):
        return self._llm

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        res = await self._llm.ainvoke(prompt)
        return res.content


def get_guardrails() -> Guardrails | None:
    return _guardrails


def init_guardrails() -> bool:
    global _guardrails
    settings = get_settings()
    if not settings.guardrails_enabled:
        logger.info("guardrails disabled (GUARDRAILS_ENABLED=false)")
        return False
    # To add a guard: import it and append to input_guards or output_guards below.
    # To remove a guard: delete its line. No other file needs to change.
    # Each guard receives the model explicitly — deepteam initializes its own model
    # in __init__ before Guardrails.evaluation_model can override it.
    eval_llm = OpenRouterEvalLLM()
    _guardrails = Guardrails(
        input_guards=[
            PromptInjectionGuard(model=eval_llm),
            IllegalGuard(model=eval_llm),
            TopicalGuard(allowed_topics=INSURANCE_TOPICS, model=eval_llm),
        ],
        output_guards=[
            ToxicityGuard(model=eval_llm),
            PrivacyGuard(model=eval_llm),
        ],
        evaluation_model=eval_llm,
        sample_rate=settings.guardrails_sample_rate,
    )
    logger.info("guardrails initialized: sample_rate=%s", settings.guardrails_sample_rate)
    return True
