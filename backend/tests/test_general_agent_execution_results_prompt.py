import asyncio
import json
import re

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.src.agents.general_agent import get_general_agent_subgraph
from app.src.schema.agent_schema import ExecutionPlanModel, QuestionClassification
from app.src.utils.prompt_format import format_execution_results_for_prompt


class _SampleModel(BaseModel):
    policy_id: str
    confidence: float


class _Unserializable:
    def __str__(self) -> str:
        return "opaque-object"


def _extract_turn_payloads(formatted: str) -> list[dict]:
    matches = re.findall(
        r"===== EXECUTION TURN \d+ =====\n(.*?)(?=\n===== EXECUTION TURN |\Z)",
        formatted,
        flags=re.DOTALL,
    )
    return [json.loads(payload.strip()) for payload in matches]


def test_format_execution_results_with_mixed_types() -> None:
    execution_results = [
        {
            "status": "completed",
            "results": [
                {"step_id": "tool_1", "output": _SampleModel(policy_id="P123", confidence=0.91)},
                {"step_id": "tool_2", "output": [1, {"foo": "bar"}]},
            ],
            "debug": {
                "message": HumanMessage(content="hello"),
                "opaque": _Unserializable(),
            },
        },
        {"status": "failed", "failed_reason": "network timeout"},
    ]

    formatted = format_execution_results_for_prompt(execution_results)

    assert "===== EXECUTION TURN 1 =====" in formatted
    assert "===== EXECUTION TURN 2 =====" in formatted

    parsed_turns = _extract_turn_payloads(formatted)
    assert len(parsed_turns) == 2
    assert parsed_turns[0]["status"] == "completed"
    assert parsed_turns[0]["results"][0]["output"]["policy_id"] == "P123"
    assert parsed_turns[0]["debug"]["message"]["content"] == "hello"
    assert parsed_turns[0]["debug"]["opaque"] == "opaque-object"
    assert parsed_turns[1]["status"] == "failed"


def test_format_execution_results_empty() -> None:
    assert format_execution_results_for_prompt([]) == "[]"


def test_general_agent_prompts_use_formatted_execution_results(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _invoke_structured_with_fallback(*, agent_name, messages, schema_model):
        _ = agent_name
        if schema_model is QuestionClassification:
            return QuestionClassification(
                question_type="concept",
                core_question="What is term insurance?",
                reasoning="test",
            )
        if schema_model is ExecutionPlanModel:
            captured["planner_user_message"] = messages[-1].content
            return ExecutionPlanModel(
                reasoning="enough evidence",
                sufficiency_check="done",
                finish=True,
                steps=[],
            )
        raise AssertionError(f"Unexpected schema model: {schema_model}")

    class _DummySynthesisLLM:
        def invoke(self, messages):
            captured["synthesis_user_message"] = messages[-1].content
            return AIMessage(content="answer")

    monkeypatch.setattr(
        "app.src.agents.general_agent.invoke_structured_with_fallback",
        _invoke_structured_with_fallback,
    )
    monkeypatch.setattr(
        "app.src.agents.general_agent.get_llm",
        lambda _name: _DummySynthesisLLM(),
    )
    monkeypatch.setattr(
        "app.src.agents.general_agent.resolve_timeout_seconds",
        lambda _agent_name, _default: 1,
    )

    graph = asyncio.run(get_general_agent_subgraph())
    _ = asyncio.run(
        graph.ainvoke(
            {
                "messages": [HumanMessage(content="help me compare plans")],
                "conversation_history": [AIMessage(content="prior answer")],
                "execution_results": [
                    {"status": "completed", "results": [{"step_id": "s1", "output": "ok"}]}
                ],
            }
        )
    )

    planner_prompt = captured["planner_user_message"]
    synthesis_prompt = captured["synthesis_user_message"]

    assert "===== EXECUTION TURN 1 =====" in planner_prompt
    assert '"status": "completed"' in planner_prompt
    assert '"content": "help me compare plans"' in planner_prompt
    assert '"content": "prior answer"' in planner_prompt
    assert "===== EXECUTION TURN 1 =====" in synthesis_prompt
    assert '"status": "completed"' in synthesis_prompt
    assert '"content": "help me compare plans"' in synthesis_prompt
    assert '"content": "prior answer"' in synthesis_prompt
