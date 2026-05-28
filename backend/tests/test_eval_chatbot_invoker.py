import sys
from pathlib import Path


def test_extract_retrieval_context_supports_deduped_textbook_output():
    evals_root = Path(__file__).resolve().parents[2] / "evals"
    sys.path.insert(0, str(evals_root))

    from eval_utils.retrieval import extract_retrieval_context

    graph_result = {
        "execution_results": [
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
                                {"text": "text-a", "query_ids": [2]},
                            ],
                        },
                    },
                    {
                        "kind": "tool",
                        "target": "query_product_summary",
                        "output": [
                            {
                                "policy_id": "P001",
                                "document_metadata": {},
                                "chunks": [
                                    {"chunk_id": "c1", "combined_text": "prod-a", "score": 0.9},
                                ],
                            }
                        ],
                    },
                ]
            }
        ]
    }

    context = extract_retrieval_context(graph_result)
    assert context == ["text-a", "text-b", "prod-a"]
