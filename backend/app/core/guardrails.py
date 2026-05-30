import logging

import anyio
from deepeval.models.base_model import DeepEvalBaseLLM
from deepteam import Guardrails
from deepteam.guardrails import (
    IllegalGuard,
    PrivacyGuard,
    PromptInjectionGuard,
    ToxicityGuard
)
from deepteam.guardrails.guards.base_guard import BaseGuard, GuardType
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe

from app.agent.prompts.prompts import SIMPLEV2_RESOLVE_ABBREVIATION_SYSTEM
from app.agent.services.llm_service import ainvoke_structured_with_fallback, get_llm
from app.agent.tools.product_registry import get_product_names
from app.agent.workflows.simple_workflow_v2 import AbbreviationResolution
from app.core.config import get_settings

logger = logging.getLogger("askmeinsurance.guardrails")

_guardrails: Guardrails | None = None


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


@observe(as_type="span")
async def _resolve_abbreviation(user_message: str) -> str | None:
    product_names = get_product_names()
    product_name_list = [d["policy_name"] for d in product_names if "policy_name" in d]
    product_list_str = "\n".join(product_name_list)
    with anyio.fail_after(15):
        result = await ainvoke_structured_with_fallback(
            agent_name="simplev2_resolve_abbreviation",
            schema_model=AbbreviationResolution,
            timeout_seconds=15,
            config=None,
            messages=[
                SystemMessage(content=SIMPLEV2_RESOLVE_ABBREVIATION_SYSTEM),
                HumanMessage(content=f"User message: {user_message}\n\nProduct names:\n{product_list_str}"),
            ],
        )
    return result.abbreviation_context


class InsuranceTopicalGuard(BaseGuard):
    def __init__(self, model=None):
        super().__init__(model=model)
        self.guard_type = GuardType.INPUT

    @property
    def __name__(self):
        return "Insurance Topical Guard"

    def _build_guard_prompt(self, input: str, abbreviation_context: str | None) -> str:
        enriched = input
        if abbreviation_context:
            enriched = f"{input}\n\n[Abbreviation context] {abbreviation_context}"
        return (
            "You are a topic adherence expert for a Singapore insurance Q&A assistant.\n\n"
            "Determine if the user's message is related to insurance (policies, premiums, claims, coverage, products, benefits, etc.).\n\n"
            "Mark as:\n"
            '- "safe" if the message is about insurance or is a general greeting/clarification\n'
            '- "unsafe" if the message is clearly unrelated to insurance\n'
            '- "borderline" if ambiguous\n\n'
            f"Input to analyze: {enriched}\n\n"
            'Respond in JSON format: {"safety_level": "safe"/"unsafe"/"borderline", "reason": "explanation"}'
        )

    def guard_input(self, input: str) -> str:
        guard_prompt = self._build_guard_prompt(input, None)
        return self._guard(guard_prompt=guard_prompt)

    async def a_guard_input(self, input: str) -> str:
        abbreviation_context = await _resolve_abbreviation(input)
        guard_prompt = self._build_guard_prompt(input, abbreviation_context)
        return await self.a_guard(guard_prompt=guard_prompt)

    def guard_output(self, input: str, output: str) -> str:
        return "safe"

    async def a_guard_output(self, input: str, output: str) -> str:
        return "safe"


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
            InsuranceTopicalGuard(model=eval_llm),
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
