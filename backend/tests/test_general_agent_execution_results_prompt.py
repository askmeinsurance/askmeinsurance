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
            "completed_steps": 2,
            "total_duration_ms": 1500,
            "failed_step": None,
            "failed_reason": None,
            "results": [
                {
                    "step_id": "tool_1",
                    "target": "query_textbook",
                    "kind": "tool",
                    "status": "success",
                    "output": _SampleModel(policy_id="P123", confidence=0.91),
                    "error": None,
                    "input": {"queries": ["what is term life?"], "messages": [HumanMessage(content="user q")]},
                    "original_index": 0,
                    "upstream_step_ids": [],
                    "upstream_results": [{"step_id": "prior", "output": "old data"}],
                    "started_at": 1700000000.0,
                    "ended_at": 1700000001.0,
                    "duration_ms": 1000,
                },
                {
                    "step_id": "tool_2",
                    "target": "query_product_summary",
                    "kind": "tool",
                    "status": "success",
                    "output": [1, {"foo": "bar"}],
                    "error": None,
                    "input": {"queries": [["benefit query", "pol_001"]]},
                    "original_index": 1,
                    "upstream_step_ids": ["tool_1"],
                    "upstream_results": [],
                    "started_at": 1700000001.0,
                    "ended_at": 1700000001.5,
                    "duration_ms": 500,
                },
            ],
        },
        {"status": "failed", "failed_reason": "network timeout", "failed_step": "tool_2"},
    ]

    formatted = format_execution_results_for_prompt(execution_results)

    assert "===== EXECUTION TURN 1 =====" in formatted
    assert "===== EXECUTION TURN 2 =====" in formatted

    parsed_turns = _extract_turn_payloads(formatted)
    assert len(parsed_turns) == 2

    turn1 = parsed_turns[0]
    # Outer envelope: kept fields
    assert turn1["status"] == "completed"
    assert turn1["failed_step"] is None
    assert turn1["failed_reason"] is None
    # Outer envelope: noise fields stripped
    assert "completed_steps" not in turn1
    assert "total_duration_ms" not in turn1

    step1 = turn1["results"][0]
    # Per-step: kept fields
    assert step1["step_id"] == "tool_1"
    assert step1["target"] == "query_textbook"
    assert step1["status"] == "success"
    assert step1["output"]["policy_id"] == "P123"
    assert step1["error"] is None
    # input: query kept, messages stripped
    assert step1["input"]["queries"] == ["what is term life?"]
    assert "messages" not in step1["input"]
    # Per-step: noise fields stripped
    assert "duration_ms" not in step1
    assert "started_at" not in step1
    assert "ended_at" not in step1
    assert "upstream_results" not in step1
    assert "upstream_step_ids" not in step1
    assert "original_index" not in step1
    assert "kind" not in step1

    step2 = turn1["results"][1]
    assert step2["step_id"] == "tool_2"
    assert step2["input"] == {"queries": [["benefit query", "pol_001"]]}

    turn2 = parsed_turns[1]
    assert turn2["status"] == "failed"
    assert turn2["failed_reason"] == "network timeout"
    assert turn2["failed_step"] == "tool_2"


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
