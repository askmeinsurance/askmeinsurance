from eval_utils.dataset_loader import EvalCase
from eval_utils.metrics import MetricConfig
from eval_utils.retrieval import extract_retrieval_context
from eval_utils.runner import select_active_metrics


def _make_metric_config(**kwargs) -> MetricConfig:
    return MetricConfig(metric=object(), **kwargs)


def test_extract_retrieval_context_from_naive_rag_hits():
    result = {
        "hits": [
            {"text": "a"},
            {"text": "a"},
            {"text": "b"},
            {"text": ""},
            {},
        ]
    }

    assert extract_retrieval_context(result) == ["a", "b"]


def test_extract_retrieval_context_handles_missing_hits():
    assert extract_retrieval_context({"hits": []}) == []


def test_select_active_metrics_skips_retrieval_metrics_without_hit_text():
    metrics = {
        "always": _make_metric_config(),
        "expected": _make_metric_config(requires_expected_output=True),
        "retrieval": _make_metric_config(requires_retrieval_context=True),
    }
    case = EvalCase(question="q", expected_output="golden", source="test")

    active = select_active_metrics(metrics, case, retrieval_context=[])

    assert len(active) == 2
    assert metrics["always"].metric in active
    assert metrics["expected"].metric in active
