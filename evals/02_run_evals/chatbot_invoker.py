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
