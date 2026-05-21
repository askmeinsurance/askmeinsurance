from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

StepKind = Literal["tool", "sub_agent"]
QuestionType = Literal["concept", "specific_product", "comparison", "needs_based"]


class QuestionClassification(BaseModel):
    question_type: QuestionType = Field(
        description=(
            "The type of question: "
            "'concept' for definitions/explanations, "
            "'specific_product' for a named product, "
            "'comparison' for comparing products/approaches, "
            "'needs_based' for situation-based recommendations"
        )
    )
    core_question: str = Field(
        description="The single most specific question the user is asking, distilled to one sentence. "
        "This is the anchor the planner uses to evaluate evidence sufficiency."
    )
    reasoning: str = Field(
        default="",
        description="Brief reasoning for the classification",
    )


class ExecutionStepModel(BaseModel):
    step_id: str | None = Field(
        default=None,
        description="Optional stable identifier. If omitted, executor may auto-generate.",
    )
    kind: StepKind = Field(description="Step type: tool or sub_agent")
    target: str = Field(min_length=1, description="Registry key for tool/sub-agent")
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input payload passed to the callable",
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="Dependencies as indices of steps in the original plan",
    )
    timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Optional per-step timeout in seconds",
    )
    enabled: bool = Field(
        default=True,
        description="If false, step is marked skipped and not executed",
    )

    @field_validator("target")
    @classmethod
    def _target_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("target cannot be blank")
        return value

    @field_validator("step_id")
    @classmethod
    def _step_id_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("step_id cannot be blank when provided")
        return value

    @field_validator("depends_on")
    @classmethod
    def _depends_non_negative(cls, value: list[int]) -> list[int]:
        if any(index < 0 for index in value):
            raise ValueError("depends_on must contain non-negative indices")
        return value


class ExecutionPlanModel(BaseModel):
    reasoning: str = Field(
        default="",
        description="Planner reasoning on known evidence and remaining gaps",
    )
    sufficiency_check: str = Field(
        default="",
        description="Why current evidence is sufficient or insufficient",
    )
    finish: bool = Field(
        default=False,
        description="Whether planner has enough evidence to stop planning",
    )
    steps: list[ExecutionStepModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_cross_step_rules(self) -> "ExecutionPlanModel":
        step_ids = [step.step_id for step in self.steps if step.step_id is not None]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step_id values are not allowed")

        total_steps = len(self.steps)
        for step_index, step in enumerate(self.steps):
            for dependency in step.depends_on:
                if dependency >= total_steps:
                    raise ValueError(
                        f"Step index {step_index} has invalid depends_on={dependency}; "
                        f"max index is {total_steps - 1}"
                    )
        if self.finish and self.steps:
            raise ValueError("When finish=true, steps must be empty")
        if not self.finish and not self.steps:
            raise ValueError("When finish=false, steps must contain at least one step")
        return self
