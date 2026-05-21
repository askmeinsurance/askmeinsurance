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
        _graph = await get_compiled_graph()
    return _graph


def extract_retrieval_context(execution_results: list[dict]) -> list[str]:
    """Extract retrieved text chunks from graph execution_results."""
    chunks = []
    seen = set()
    for batch in execution_results:
        for step in batch.get("results", []):
            if step.get("kind") != "tool":
                continue
            if step.get("target") not in ("query_textbook", "query_product_summary"):
                continue
            for chunk in step.get("output") or []:
                text = chunk.get("text") or chunk.get("combined_text") or ""
                if text and text not in seen:
                    seen.add(text)
                    chunks.append(text)
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
