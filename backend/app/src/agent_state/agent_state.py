import operator
from typing import Annotated, List, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.src.schema.tool_schema import PolicyMatchResponse


class NameMatchStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    retrieval_query: str = ""
    conversation_history: Annotated[list[BaseMessage], add_messages] = []


class NameMatchStateOutput(BaseModel):
    lst_policy_matched: Annotated[list[PolicyMatchResponse], operator.add]


class FindProductWithCriteriaStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str


class PolicyMatch(BaseModel):
    policy_id: str
    reasoning: str


class FindProductWithCriteriaStateOutput(BaseModel):
    matching_product: List[PolicyMatch]


class SimpleQueryClassification(BaseModel):
    question_type: Literal["specific_product", "concept", "both", "lookup"]
    product_name_mentioned: str | None
    reasoning: str


class ExpandedQueries(BaseModel):
    product_queries: list[str]
    concept_queries: list[str]
