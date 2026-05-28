import asyncio

from langchain_core.messages import HumanMessage

from app.src.agent_state.agent_state import (
    NameMatchStateInput,
    NameMatchStateOutput,
)
from app.src.schema.tool_schema import AppliedFilters, PolicyMatchResponse
from app.src.workflow.name_match import name_match_workflow


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

    async def _fake_ainvoke(agent_name, schema_model, timeout_seconds, config, messages):
        captured["prompt"] = messages[-1].content
        return output

    monkeypatch.setattr("app.src.workflow.name_match.ainvoke_structured_with_fallback", _fake_ainvoke)
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
