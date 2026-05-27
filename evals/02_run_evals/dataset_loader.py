"""Load evaluation datasets from golden Q&A files."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_DATASET_ROOT = Path(__file__).parents[1] 


@dataclass
class EvalCase:
    question: str
    expected_output: Optional[str]
    source: str
    case_id: Optional[str] = None
    context: list[str] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)


def load_manual_evals() -> list[EvalCase]:
    path = _DATASET_ROOT / "dataset" / "manual_data.json"
    data = json.loads(path.read_text())
    return [
        EvalCase(
            question=item["question"],
            expected_output=item.get("base_answer"),
            source="manual",
            case_id=item.get("id"),
        )
        for item in data
    ]


def load_textbook_evals() -> list[EvalCase]:
    path = _DATASET_ROOT / "textbook_evals" / "generated_goldens.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [
        EvalCase(
            question=item["input"],
            expected_output=item.get("expected_output"),
            source="textbook",
            context=item.get("context") or [],
        )
        for item in data
        if item.get("input")
    ]


def load_all_evals() -> list[EvalCase]:
    return load_manual_evals() + load_textbook_evals()
