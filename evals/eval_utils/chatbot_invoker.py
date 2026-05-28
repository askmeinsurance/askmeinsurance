"""Direct LangGraph graph invocation for evaluation.

Caller is responsible for running load_dotenv() and sys.path setup
before importing this module (done at the top of run_evals.py).
"""

import asyncio

from app.src.graph import get_compiled_graph

_graph = None
_graph_lock = asyncio.Lock()


async def get_graph():
    """Return the singleton compiled LangGraph (initialised once).

    Protected by a lock so concurrent eval tasks can't trigger double
    initialisation if get_graph() is ever called in parallel.
    """
    global _graph
    async with _graph_lock:
        if _graph is None:
            print("  [graph] compiling LangGraph...")
            _graph = await get_compiled_graph()
            print("  [graph] ready")
    return _graph
