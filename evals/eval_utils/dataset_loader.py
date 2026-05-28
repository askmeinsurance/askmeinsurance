"""Load evaluation datasets from golden Q&A files."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from eval_utils.config import EVALS_ROOT


@dataclass
class EvalCase:
    question: str
    expected_output: str | None
    source: str
    case_id: str | None = None
    context: list[str] = field(default_factory=list)


def load_manual_evals(dataset_root: Path = EVALS_ROOT) -> list[EvalCase]:
    path = dataset_root / "dataset" / "manual_data.json"
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


def load_textbook_evals(dataset_root: Path = EVALS_ROOT) -> list[EvalCase]:
    path = dataset_root / "textbook_evals" / "generated_goldens.json"
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


