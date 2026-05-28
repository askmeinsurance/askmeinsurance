from eval_utils.models import EvalResult
from eval_utils.reporting import collect_metric_names, summarize_scores


def _make_result(scores: dict) -> EvalResult:
    return EvalResult(question="q", answer="a", scores=scores, trace_id="t")


def test_collect_metric_names_preserves_first_seen_order():
    results = [
        _make_result({"helpfulness": (0.8, None), "honesty": (0.7, None)}),
        _make_result({"faithfulness": (0.6, None), "helpfulness": (0.9, None)}),
    ]

    assert collect_metric_names(results) == ["helpfulness", "honesty", "faithfulness"]


def test_summarize_scores_uses_threshold_for_pass_count():
    results = [
        _make_result({"helpfulness": (0.8, None)}),
        _make_result({"helpfulness": (0.6, None)}),
        _make_result({}),
    ]

    summary = summarize_scores(results, ["helpfulness"])

    assert summary == {"helpfulness": {"average": 0.7, "passing": 1, "total": 2}}
