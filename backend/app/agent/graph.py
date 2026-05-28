from app.agent.agents.main_agent import get_main_agent_graph

_graph = None


async def get_compiled_graph():
    """Return the singleton compiled main agent graph."""
    global _graph
    if _graph is None:
        _graph = await get_main_agent_graph()
    return _graph
