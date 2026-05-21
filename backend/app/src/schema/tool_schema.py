from typing import Any, List, Literal, Optional

from pydantic import BaseModel


class FindPolicyIdWithCriteriaInput(BaseModel):
    criteria: List[str]
    policy_category: Optional[str] = None
    is_rider: Optional[bool] = None


class CriteriaMatch(BaseModel):
    key: str
    value: Any
    policy_id: str


class FindPolicyIdWithCriteriaOutput(BaseModel):
    root: List[CriteriaMatch]


class AppliedFilters(BaseModel):
    provider: str
    category: str


class PolicyMatchResponse(BaseModel):
    mode: Literal["specific_match", "general_match"]
    selected_policy_ids: List[str]
    applied_filters: AppliedFilters
    confidence: Literal["low", "medium", "high"]
    reason: str


class FindPolicyDetailsWithPolicyIdInput(BaseModel):
    policy_id: str
    criteria: List[str]


class FindPolicyDetailsWithPolicyId(BaseModel):
    key: str
    value: Any
    policy_id: str


class FindPolicyDetailsWithPolicyIdOutput(BaseModel):
    root: List[FindPolicyDetailsWithPolicyId]
