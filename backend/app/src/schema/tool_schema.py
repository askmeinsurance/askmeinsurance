from typing import Any, List, Literal, Optional

from pydantic import BaseModel, field_validator


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
    provider: Optional[str] = None
    category: Optional[str] = None


class PolicyMatchResponse(BaseModel):
    mode: Literal["specific_match", "explore_filters", "no_match", "general_match"]
    selected_policy_ids: Optional[List[str]] = None
    applied_filters: Optional[AppliedFilters] = None
    confidence: Literal["low", "medium", "high"]
    reason: str

    @field_validator("applied_filters", mode="before")
    @classmethod
    def _empty_filters_to_none(cls, value):
        if isinstance(value, dict) and not value:
            return None
        return value


class FindPolicyDetailsWithPolicyIdInput(BaseModel):
    policy_id: str
    criteria: List[str]


class FindPolicyDetailsWithPolicyId(BaseModel):
    key: str
    value: Any
    policy_id: str


class FindPolicyDetailsWithPolicyIdOutput(BaseModel):
    root: List[FindPolicyDetailsWithPolicyId]
