"""Direct LangGraph graph invocation for evaluation.

Caller is responsible for running load_dotenv() and sys.path setup
before importing this module (done at the top of run_evals.py).
"""
from langchain_core.messages import HumanMessage

from app.src.graph import get_compiled_graph

_graph = None


async def get_graph():
    """Return the singleton compiled LangGraph (initialised once)."""
    global _graph
    if _graph is None:
        print("  [graph] compiling LangGraph...")
        _graph = await get_compiled_graph()
        print("  [graph] ready")
    return _graph


def extract_retrieval_context(execution_results: list[dict]) -> list[str]:
    """Extract retrieved text chunks from graph execution_results."""
    chunks = []
    seen = set()
    tool_hits: dict[str, int] = {}
    for batch in execution_results:
        for step in batch.get("results", []):
            if step.get("kind") != "tool":
                continue
            target = step.get("target")
            if target not in ("query_textbook", "query_product_summary"):
                continue
            output = step.get("output") or []

            # query_product_summary output is grouped by policy_id.
            if target == "query_product_summary":
                for group in output:
                    for chunk in group.get("chunks", []):
                        text = chunk.get("text") or chunk.get("combined_text") or ""
                        if text and text not in seen:
                            seen.add(text)
                            chunks.append(text)
                            tool_hits[target] = tool_hits.get(target, 0) + 1
                continue

            # query_textbook output is {"queries": [...], "results": [...]}
            for chunk in (output.get("results") if isinstance(output, dict) else []):
                text = chunk.get("text") or ""
                if text and text not in seen:
                    seen.add(text)
                    chunks.append(text)
                    tool_hits[target] = tool_hits.get(target, 0) + 1
    if tool_hits:
        summary = "  ".join(f"{t}={n}" for t, n in tool_hits.items())
        print(f"  [retrieval] {len(chunks)} chunks  ({summary})")
    else:
        print("  [retrieval] no chunks retrieved")
    return chunks


async def invoke_chatbot(question: str, callbacks: list | None = None) -> str:
    """Invoke the chatbot graph and return the full text response."""
    graph = await get_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=question)],
            "conversation_history": [],
        },
        config={"callbacks": callbacks or []},
    )
    messages = result.get("messages", [])
    return messages[-1].content if messages else ""
