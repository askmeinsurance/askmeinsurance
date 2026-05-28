"""Shared data types for evaluation results."""

from dataclasses import dataclass

ScoreMap = dict[str, tuple[float, str | None]]


@dataclass
class EvalResult:
    question: str
    answer: str
    scores: ScoreMap
    trace_id: str
