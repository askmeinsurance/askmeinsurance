import operator
from typing import Annotated, List, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.src.schema.tool_schema import PolicyMatchResponse


# ---------------------------------------------------------------------------
# simple_workflow_v2 state models
# ---------------------------------------------------------------------------


class AbbreviationResolution(BaseModel):
    abbreviation_context: str | None


class IntentSummary(BaseModel):
    condensed_intent: str
    product_name_mentioned: str | None
    reasoning: str


class ExtendedQuery(BaseModel):
    query: str
    reasoning: str
    source_type: Literal["textbook", "product", "both"]


class IntentExtension(BaseModel):
    extended_queries: List[ExtendedQuery]


class DecomposedIntent(BaseModel):
    intent_description: str
    source_type: Literal["textbook", "product", "both"]


class IntentsDecomposition(BaseModel):
    decomposed_intents: List[DecomposedIntent]


class ResolvedIntent(BaseModel):
    intent_description: str
    source_type: Literal["textbook", "product", "both"]
    policy_ids: List[str] = []


class RephrasedQuerySet(BaseModel):
    textbook_queries: List[str]
    product_queries: List[str]


class NameMatchStateInput(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    retrieval_query: str = ""
    conversation_history: Annotated[list[BaseMessage], add_messages] = []


class NameMatchStateOutput(BaseModel):
    lst_policy_matched: Annotated[list[PolicyMatchResponse], operator.add]


class OnePolicyMatchOutput(BaseModel):
    policy_id: str | None
    confidence: Literal["low", "medium", "high"]
    reason: str


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
