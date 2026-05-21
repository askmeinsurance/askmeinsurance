"""
REACT PLANNER-EXECUTOR agent

planner plans the next steps (tools or agentic workflow)
executor executes the plan in async manner
planner reviews the results, stop if sufficient information to synthesis/reason the answer
synthesis/reasoner LLM will generate grounded answer based on the context given.

tools:
1. textbook_retriever
2. policy_retriever
3. find_policy_details_with_policy_id

agent workflow:
1. find_product_with_criteria
2. name_match
"""

import asyncio
from typing import Annotated, List

import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.src.prompts.prompts import (
    GENERAL_AGENT_PLANNER_SYSTEM,
    GENERAL_AGENT_SYNTHESIS_SYSTEM,
    QUESTION_CLASSIFIER_SYSTEM,
)
from app.src.schema.agent_schema import ExecutionPlanModel, QuestionClassification
from app.src.services.llm_service import get_llm
from app.src.utils.parallel_executor import execute_parallel_plan


class GeneralAgentStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add]


class GeneralAgentStateOutput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add]


class GeneralAgentStateReact(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_history: Annotated[list[BaseMessage], operator.add]
    question_type: str = ""
    core_question: str = ""
    execution_plan: List[dict] = Field(default_factory=list)
    execution_results: Annotated[List[dict], operator.add] = Field(default_factory=list)
    curr_iteration_count: int = 0
    max_iteration_count: int = 5
    react_finish: bool = False


async def get_general_agent_subgraph() -> GeneralAgentStateOutput:

    async def classifier_node(state: GeneralAgentStateReact) -> GeneralAgentStateReact:
        """Runs once before the REACT loop. Classifies the question type and
        extracts core_question so the planner has a stable, scoped anchor for
        all subsequent finish decisions."""
        user_message_text = "\n".join(
            m.content if hasattr(m, "content") else str(m)
            for m in state.messages
        )
        llm = get_llm("general_agent_planner").with_structured_output(QuestionClassification)
        classification: QuestionClassification = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [
                    SystemMessage(content=QUESTION_CLASSIFIER_SYSTEM),
                    HumanMessage(content=user_message_text),
                ],
            ),
            timeout=30,
        )
        return {
            "question_type": classification.question_type,
            "core_question": classification.core_question,
        }

    async def planner_node(state: GeneralAgentStateReact) -> GeneralAgentStateReact:
        planner_user_message = f"""question_type: {state.question_type}
core_question: {state.core_question}
current iteration count: {state.curr_iteration_count}
user query = {state.messages}
conversation history = {state.conversation_history}
execution results = {state.execution_results}
"""
        llm = get_llm("general_agent_planner").with_structured_output(ExecutionPlanModel)
        execution_plan: ExecutionPlanModel = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [
                    SystemMessage(content=GENERAL_AGENT_PLANNER_SYSTEM),
                    HumanMessage(content=planner_user_message),
                ],
            ),
            timeout=60,
        )
        return {
            "execution_plan": [step.model_dump() for step in execution_plan.steps],
            "react_finish": execution_plan.finish,
        }

    async def executor_node(state: GeneralAgentStateReact) -> GeneralAgentStateReact:
        executor_output = await execute_parallel_plan(
            execution_plan=state.execution_plan,
        )
        return {
            "execution_results": [executor_output],
            "curr_iteration_count": state.curr_iteration_count + 1,
        }

    async def synthesis_node(state: GeneralAgentStateReact):
        user_message = f"""question_type: {state.question_type}
core_question: {state.core_question}
current iteration count: {state.curr_iteration_count}
user query = {state.messages}
conversation history = {state.conversation_history}
execution results = {state.execution_results}
"""
        llm = get_llm("general_agent_synthesis")
        res = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [
                    SystemMessage(content=GENERAL_AGENT_SYNTHESIS_SYSTEM),
                    HumanMessage(content=user_message),
                ],
            ),
            timeout=60,
        )
        return {"messages": [res]}

    async def react_stop_edge(state):
        if state.react_finish or state.curr_iteration_count >= state.max_iteration_count:
            return "synthesis"
        return "planner"

    async def planner_route_edge(state):
        if state.react_finish:
            return "synthesis"
        return "executor"

    sub_builder = StateGraph(GeneralAgentStateReact)
    sub_builder.add_node("classifier", classifier_node)
    sub_builder.add_node("planner", planner_node)
    sub_builder.add_node("synthesis", synthesis_node)
    sub_builder.add_node("executor", executor_node)

    sub_builder.add_edge(START, "classifier")
    sub_builder.add_edge("classifier", "planner")
    sub_builder.add_conditional_edges(
        "planner",
        planner_route_edge,
        {"executor": "executor", "synthesis": "synthesis"},
    )
    sub_builder.add_conditional_edges(
        "executor",
        react_stop_edge,
        {"synthesis": "synthesis", "planner": "planner"},
    )
    sub_builder.add_edge("synthesis", END)

    return sub_builder.compile()
