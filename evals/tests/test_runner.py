import asyncio

from eval_utils.dataset_loader import EvalCase
from eval_utils.config import RunConfig
from eval_utils.metrics import MetricConfig
from eval_utils.runner import _extract_answer, _get_flow_runtime, select_active_metrics


def _make_metric_config(**kwargs) -> MetricConfig:
    return MetricConfig(metric=object(), **kwargs)


def test_select_active_metrics_filters_unavailable_inputs():
    metrics = {
        "always": _make_metric_config(),
        "expected": _make_metric_config(requires_expected_output=True),
        "retrieval": _make_metric_config(requires_retrieval_context=True),
    }
    case = EvalCase(question="q", expected_output=None, source="test")

    active = select_active_metrics(metrics, case, retrieval_context=[])

    assert len(active) == 1
    assert active[0] is metrics["always"].metric


def test_get_flow_runtime_uses_simple_workflow_graph(monkeypatch):
    graph = object()

    async def fake_get_graph():
        return graph

    async def fake_invoke_graph(compiled_graph, case, run_name):
        return compiled_graph, "trace"

    monkeypatch.setattr("eval_utils.runner._get_graph", fake_get_graph)
    monkeypatch.setattr("eval_utils.runner._invoke_graph", fake_invoke_graph)

    async def run_test():
        runtime = await _get_flow_runtime(RunConfig(run_name="r", flow="simple_workflow"))
        result, trace_id = await runtime.invoke(
            EvalCase(question="q", expected_output=None, source="test"),
            "run",
        )
        assert runtime.flow == "simple_workflow"
        assert trace_id == "trace"
        assert result is graph

    asyncio.run(run_test())


def test_get_flow_runtime_uses_naive_rag_callable(monkeypatch):
    called = {}

    def fake_run_naive_rag(question: str, top_k: int):
        called["question"] = question
        called["top_k"] = top_k
        return {"answer": "baseline"}

    async def fake_invoke_naive_rag(run_naive_rag, case, run_name, top_k):
        return run_naive_rag(case.question, top_k), "trace"

    monkeypatch.setattr("eval_utils.runner._get_run_naive_rag", lambda: fake_run_naive_rag)
    monkeypatch.setattr("eval_utils.runner._invoke_naive_rag", fake_invoke_naive_rag)

    async def run_test():
        runtime = await _get_flow_runtime(RunConfig(run_name="r", flow="naive_rag", top_k=7))
        result, trace_id = await runtime.invoke(
            EvalCase(question="what is term insurance", expected_output=None, source="test"),
            "run",
        )
        assert runtime.flow == "naive_rag"
        assert trace_id == "trace"
        assert result == {"answer": "baseline"}

    asyncio.run(run_test())
    assert called == {"question": "what is term insurance", "top_k": 7}


def test_extract_answer_supports_both_flows():
    assert _extract_answer({"answer": "baseline"}, "naive_rag") == "baseline"
    assert _extract_answer({"messages": [type("Msg", (), {"content": "agent"})()]}, "simple_workflow") == "agent"
