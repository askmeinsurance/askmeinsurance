import asyncio

from langchain_core.messages import HumanMessage

from app.src.agent_state.agent_state import NameMatchStateInput, NameMatchStateOutput, SimpleQueryClassification
from app.src.schema.tool_schema import AppliedFilters, PolicyMatchResponse
from app.src.workflow import simple_workflow as simple_workflow_module
from app.src.workflow.name_match import name_match_workflow


class _DummyStructuredLLM:
    def __init__(self, result, captured: dict[str, str]):
        self._result = result
        self._captured = captured

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, messages, config=None):
        _ = config
        self._captured["prompt"] = messages[-1].content
        return self._result


def test_simple_workflow_classify_prompt_uses_json(monkeypatch) -> None:
    captured: dict[str, str] = {}
    llm = _DummyStructuredLLM(
        SimpleQueryClassification(
            question_type="concept",
            product_name_mentioned=None,
            reasoning="test",
        ),
        captured,
    )

    monkeypatch.setattr(
        "app.src.workflow.simple_workflow.get_llm",
        lambda _name: llm,
    )
    monkeypatch.setattr(
        "app.src.workflow.simple_workflow.resolve_timeout_seconds",
        lambda _agent_name, _default: 1,
    )

    state = simple_workflow_module.SimpleWorkflowGraphState(
        messages=[HumanMessage(content="What is term insurance?")],
        conversation_history=[HumanMessage(content="Earlier context")],
    )
    _ = asyncio.run(simple_workflow_module._classify_node(state, config={}))

    prompt = captured["prompt"]
    assert '"content": "What is term insurance?"' in prompt
    assert '"content": "Earlier context"' in prompt


def test_name_match_prompt_uses_json(monkeypatch) -> None:
    captured: dict[str, str] = {}
    output = NameMatchStateOutput(
        lst_policy_matched=[
            PolicyMatchResponse(
                mode="specific_match",
                selected_policy_ids=["P123"],
                applied_filters=AppliedFilters(provider="AIA", category="term"),
                confidence="high",
                reason="exact",
            )
        ]
    )
    llm = _DummyStructuredLLM(output, captured)

    monkeypatch.setattr("app.src.workflow.name_match.get_llm", lambda _name: llm)
    monkeypatch.setattr("app.src.workflow.name_match.get_product_names", lambda: ["AIA ProTerm"])
    monkeypatch.setattr(
        "app.src.workflow.name_match.resolve_timeout_seconds",
        lambda _agent_name, _default: 1,
    )

    state = NameMatchStateInput(
        messages=[HumanMessage(content="is AIA ProTerm good?")],
        retrieval_query="AIA ProTerm",
        conversation_history=[],
    )
    _ = asyncio.run(name_match_workflow(state, config={}))

    prompt = captured["prompt"]
    assert '"content": "is AIA ProTerm good?"' in prompt
    assert '"AIA ProTerm"' in prompt
