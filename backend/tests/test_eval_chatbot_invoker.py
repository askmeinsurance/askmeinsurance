from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_chatbot_invoker_module():
    module_path = Path(__file__).resolve().parents[2] / "evals" / "02_run_evals" / "chatbot_invoker.py"
    spec = spec_from_file_location("chatbot_invoker_for_test", module_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_retrieval_context_supports_deduped_textbook_output():
    chatbot_invoker = _load_chatbot_invoker_module()
    execution_results = [
        {
            "results": [
                {
                    "kind": "tool",
                    "target": "query_textbook",
                    "output": {
                        "queries": [
                            {"query": "q1", "query_id": 1},
                            {"query": "q2", "query_id": 2},
                        ],
                        "results": [
                            {"text": "text-a", "query_ids": [1, 2]},
                            {"text": "text-b", "query_ids": [1]},
                        ],
                    },
                },
                {
                    "kind": "tool",
                    "target": "query_product_summary",
                    "output": [
                        {"combined_text": "prod-a"},
                    ],
                },
            ]
        }
    ]

    context = chatbot_invoker.extract_retrieval_context(execution_results)
    assert context == ["text-a", "text-b", "prod-a"]
