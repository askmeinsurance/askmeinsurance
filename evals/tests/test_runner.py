from eval_utils.dataset_loader import EvalCase
from eval_utils.metrics import MetricConfig
from eval_utils.runner import select_active_metrics


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
