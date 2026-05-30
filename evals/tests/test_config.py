from datetime import datetime

from eval_utils.config import parse_run_config


def test_parse_run_config_uses_supplied_run_name_and_limit():
    config = parse_run_config(["--run-name", "smoke", "--limit", "3", "--flow", "naive_rag", "--top-k", "9"])

    assert config.run_name == "smoke"
    assert config.flow == "naive_rag"
    assert config.limit == 3
    assert config.top_k == 9


def test_parse_run_config_defaults_run_name_from_clock():
    now = datetime(2026, 5, 27, 12, 30, 5)

    config = parse_run_config([], now=lambda: now)

    assert config.run_name == "run_20260527_123005"
    assert config.flow == "simple_workflow"
    assert config.limit is None
    assert config.top_k == 5
