from types import SimpleNamespace

import pytest

from app.src.tools import textbook


def _point(chunk_id: str, text: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(
        payload={
            "chunk_id": chunk_id,
            "text": text,
            "chapter": "chapter",
            "header": "header",
            "level": 2,
            "has_table": False,
        },
        score=score,
    )


def test_query_textbook_returns_deduped_results_with_query_ids(monkeypatch):
    class _Embeddings:
        def embed_query(self, query: str):
            return query

    class _Client:
        def query_points(self, *, collection_name, query, limit, with_payload):
            assert collection_name == "insurance_text_book2"
            assert limit == 3
            assert with_payload is True
            if query == "q1":
                points = [_point("c1", "text-1", 0.91), _point("c2", "text-2", 0.84)]
            else:
                points = [_point("c1", "text-1", 0.88), _point("c3", "text-3", 0.81)]
            return SimpleNamespace(points=points)

    monkeypatch.setattr(textbook, "get_embeddings", lambda: _Embeddings())
    monkeypatch.setattr(textbook, "get_qdrant_client", lambda: _Client())
    monkeypatch.setattr(textbook, "get_textbook_top_k", lambda: 3)

    out = textbook.query_textbook.func(queries=[["q1"], "q2"])

    assert out["queries"] == [{"query": "q1", "query_id": 1}, {"query": "q2", "query_id": 2}]

    by_chunk_id = {chunk["chunk_id"]: chunk for chunk in out["results"]}
    assert set(by_chunk_id) == {"c1", "c2", "c3"}
    assert by_chunk_id["c1"]["query_ids"] == [1, 2]
    assert by_chunk_id["c2"]["query_ids"] == [1]
    assert by_chunk_id["c3"]["query_ids"] == [2]
    assert "score" not in by_chunk_id["c1"]
    assert "rank" not in by_chunk_id["c1"]


def test_query_textbook_fallback_dedupe_key_uses_text_when_chunk_id_missing(monkeypatch):
    class _Embeddings:
        def embed_query(self, query: str):
            return query

    class _Client:
        def query_points(self, *, collection_name, query, limit, with_payload):
            _ = collection_name, limit, with_payload
            if query == "q1":
                points = [_point("", "shared text", 0.9)]
            else:
                points = [_point(None, "shared text", 0.8)]
            return SimpleNamespace(points=points)

    monkeypatch.setattr(textbook, "get_embeddings", lambda: _Embeddings())
    monkeypatch.setattr(textbook, "get_qdrant_client", lambda: _Client())
    monkeypatch.setattr(textbook, "get_textbook_top_k", lambda: 3)

    out = textbook.query_textbook.func(queries=[["q1"], ["q2"]])
    assert len(out["results"]) == 1
    assert out["results"][0]["query_ids"] == [1, 2]


def test_query_textbook_raises_for_empty_queries():
    with pytest.raises(ValueError, match="requires at least one non-empty query"):
        textbook.query_textbook.func(queries=[[], "  "], query=" ")
