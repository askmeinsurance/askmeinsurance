from eval_utils.retrieval import extract_retrieval_context, summarize_retrieval_hits


def test_extract_retrieval_context_supports_simple_workflow_output():
    result = {
        "product_chunks": [
            {"chunks": [{"combined_text": "product-a"}, {"text": "product-b"}]},
        ],
        "concept_chunks": {
            "results": [{"text": "concept-a"}, {"text": "product-a"}],
        },
    }

    assert extract_retrieval_context(result) == ["product-a", "product-b", "concept-a"]


def test_summarize_retrieval_hits_counts_deduped_sources():
    result = {
        "execution_results": [
            {
                "results": [
                    {
                        "kind": "tool",
                        "target": "query_textbook",
                        "output": {"results": [{"text": "a"}, {"text": "a"}]},
                    },
                    {
                        "kind": "tool",
                        "target": "query_product_summary",
                        "output": [{"chunks": [{"combined_text": "b"}]}],
                    },
                ]
            }
        ]
    }

    assert summarize_retrieval_hits(result) == {
        "query_textbook": 1,
        "query_product_summary": 1,
    }


def test_extract_retrieval_context_supports_naive_rag_output():
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


def test_summarize_retrieval_hits_supports_naive_rag_output():
    result = {
        "hits": [
            {"text": "a"},
            {"text": "a"},
            {"text": "b"},
        ]
    }

    assert summarize_retrieval_hits(result) == {"naive_rag_hits": 2}
