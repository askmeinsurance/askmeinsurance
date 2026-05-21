from pathlib import Path
from typing import List, Optional
import json

from langchain_core.tools import tool

from app.src.schema.tool_schema import (
    FindPolicyDetailsWithPolicyIdInput,
    FindPolicyDetailsWithPolicyIdOutput,
    FindPolicyIdWithCriteriaInput,
    FindPolicyIdWithCriteriaOutput,
)

_STATIC_DATA = Path(__file__).parent.parent / "static_data"
_REGISTRY_PATH = _STATIC_DATA / "product_registry.json"
_REGISTRY_FLATTEN_PATH = _STATIC_DATA / "product_registry_flatten.json"


def get_product_names() -> list:
    """Return all products in scope as a list of {policy_name, policy_id} dicts."""
    with open(_REGISTRY_PATH) as f:
        lst_dct = json.load(f)
    lst_out = []
    for dct in lst_dct:
        lst_out.extend([{k: v} for k, v in dct.items() if k in ["policy_name", "policy_id"]])
    return lst_out


@tool(args_schema=FindPolicyDetailsWithPolicyIdInput)
def find_policy_details_with_policy_id(
    policy_id: str, criteria: List[str]
) -> FindPolicyDetailsWithPolicyIdOutput:
    """Given a policy_id and criteria, return the catalog values."""
    with open(_REGISTRY_PATH) as f:
        lst_dct = json.load(f)
    for dct in lst_dct:
        if dct["policy_id"] == policy_id:
            return FindPolicyDetailsWithPolicyIdOutput(
                root=[
                    {
                        "key": one_criteria,
                        "value": dct["details"][one_criteria],
                        "policy_id": dct["policy_id"],
                    }
                    for one_criteria in criteria
                ]
            )


@tool(args_schema=FindPolicyIdWithCriteriaInput)
def find_policy_id_with_criteria(
    criteria: List[str],
    policy_category: Optional[str] = "None",
    is_rider: Optional[bool] = None,
) -> FindPolicyIdWithCriteriaOutput:
    """Given the list of criteria and optional filters, return all criteria rows
    for matching policies in product_registry_flatten.json."""
    with open(_REGISTRY_FLATTEN_PATH) as f:
        lst_dct = json.load(f)
    lst_out = []
    for dct in lst_dct:
        policy_id = dct["policy_id"]
        if policy_category != "None" and policy_category not in str(dct.get("policy_category", "")):
            continue
        if is_rider is not None and dct.get("is_rider") != is_rider:
            continue
        for one_criteria in criteria:
            lst_out.append(
                {
                    "key": one_criteria,
                    "value": dct.get(one_criteria),
                    "policy_id": policy_id,
                }
            )
    return FindPolicyIdWithCriteriaOutput(root=lst_out)
