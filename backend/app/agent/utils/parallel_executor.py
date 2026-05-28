"""Generic dependency-aware parallel executor for tools and sub-agents.

This module is intentionally framework-agnostic so it can be used from
LangGraph nodes (or any async orchestration surface) without importing
project-specific runtime code.

State ownership model:
- Caller-owned state: passed via ``context`` and merged by caller after run.
- Executor-owned state: dependency scheduling and per-step runtime bookkeeping.
- Callable-owned state: internal state of each tool/sub-agent implementation.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Awaitable, Callable, Literal

from app.agent.schemas.agent import StepKind

StepStatus = Literal["pending", "running", "success", "failed", "skipped"]

ToolCallable = Callable[[dict[str, Any], dict[str, Any]], Any | Awaitable[Any]]
AgentCallable = Callable[[dict[str, Any], dict[str, Any]], Any | Awaitable[Any]]


@lru_cache(maxsize=1)
def _build_default_registries() -> tuple[dict[str, ToolCallable], dict[str, AgentCallable]]:
    """Build and cache the default tool and sub-agent registries on first call."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from app.agent.workflows.find_product_with_criteria import FindProductWithCriteriaStateInput
    from app.agent.workflows.name_match import NameMatchStateInput
    from app.agent.tools.product_registry import find_policy_details_with_policy_id
    from app.agent.tools.product_summary import query_product_summary
    from app.agent.tools.textbook import TextbookOutput, query_textbook
    from app.agent.workflows.find_product_with_criteria import find_product_with_criteria_workflow
    from app.agent.workflows.name_match import name_match_workflow

    _ROLE_MAP = {
        "user": HumanMessage,
        "human": HumanMessage,
        "assistant": AIMessage,
        "ai": AIMessage,
        "system": SystemMessage,
    }

    def _coerce_messages(raw: list) -> list:
        result = []
        for msg in raw:
            if hasattr(msg, "content"):
                result.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role") or msg.get("type", "user")
                content = msg.get("content", "")
                cls = _ROLE_MAP.get(role, HumanMessage)
                result.append(cls(content=content))
        return result

    async def _tool_find_policy_details_with_policy_id(step_input: dict, _context: dict) -> dict:
        return find_policy_details_with_policy_id.invoke(step_input)

    async def _tool_query_product_summary(step_input: dict, _context: dict) -> list[dict]:
        return query_product_summary.invoke(step_input)

    async def _tool_query_textbook(step_input: dict, _context: dict) -> TextbookOutput:
        return query_textbook.invoke(step_input)

    async def _subagent_find_product_with_criteria_workflow(step_input: dict, _context: dict) -> dict:
        state = dict(step_input) if isinstance(step_input, dict) else {}
        state["messages"] = _coerce_messages(state.get("messages") or [])
        output = await find_product_with_criteria_workflow(
            FindProductWithCriteriaStateInput(**state)
        )
        return output.model_dump()

    async def _subagent_name_match_workflow(step_input: dict, _context: dict) -> dict:
        state = dict(step_input) if isinstance(step_input, dict) else {}
        state["messages"] = _coerce_messages(state.get("messages") or [])
        state["conversation_history"] = _coerce_messages(state.get("conversation_history") or [])
        output = await name_match_workflow(NameMatchStateInput(**state))
        return output.model_dump()

    tools: dict[str, ToolCallable] = {
        "find_policy_details_with_policy_id": _tool_find_policy_details_with_policy_id,
        "query_product_summary": _tool_query_product_summary,
        "query_textbook": _tool_query_textbook,
    }
    sub_agents: dict[str, AgentCallable] = {
        "find_product_with_criteria_workflow": _subagent_find_product_with_criteria_workflow,
        "name_match_workflow": _subagent_name_match_workflow,
    }
    return tools, sub_agents


@dataclass(slots=True)
class ExecutionStep:
    """A single execution-plan step."""

    step_id: str
    kind: StepKind
    target: str
    input: dict[str, Any]
    depends_on: list[int]
    timeout_seconds: float | None = None
    enabled: bool = True
    original_index: int = -1


@dataclass(slots=True)
class StepResult:
    """Result payload for each normalized step."""

    step_id: str
    original_index: int
    kind: StepKind
    target: str
    status: StepStatus
    input: dict[str, Any]
    upstream_step_ids: list[str]
    upstream_results: list[dict[str, Any]]
    output: Any | None = None
    error: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    duration_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "original_index": self.original_index,
            "kind": self.kind,
            "target": self.target,
            "status": self.status,
            "input": self.input,
            "upstream_step_ids": self.upstream_step_ids,
            "upstream_results": self.upstream_results,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
        }


class PlanValidationError(RuntimeError):
    """Execution plan is invalid."""


class StepExecutionError(RuntimeError):
    """A step failed during execution."""


class StepTimeoutError(StepExecutionError):
    """A step timed out."""


def _now() -> float:
    return time.time()


def _duration_ms(started_at: float, ended_at: float) -> int:
    return int((ended_at - started_at) * 1000)


async def _call_target(
    fn: Callable[[dict[str, Any], dict[str, Any]], Any | Awaitable[Any]],
    step_input: dict[str, Any],
    context: dict[str, Any],
) -> Any:
    """Invoke a tool/sub-agent callable regardless of sync/async type."""
    if inspect.iscoroutinefunction(fn):
        return await fn(step_input, context)
    return await asyncio.to_thread(fn, step_input, context)


def _normalize_steps(
    execution_plan: list[dict[str, Any]],
    tools: dict[str, ToolCallable],
    sub_agents: dict[str, AgentCallable],
) -> list[ExecutionStep]:
    """Filter and normalize raw plan entries into validated execution steps."""
    accepted: list[tuple[int, dict[str, Any]]] = []
    for original_idx, raw in enumerate(execution_plan):
        if not isinstance(raw, dict):
            continue
        kind = raw.get("kind")
        target = raw.get("target")
        if kind not in {"tool", "sub_agent"}:
            continue
        if not isinstance(target, str) or not target.strip():
            continue
        if kind == "tool" and target not in tools:
            raise PlanValidationError(
                f"Unknown tool target '{target}'. Only registered tools are allowed."
            )
        if kind == "sub_agent" and target not in sub_agents:
            raise PlanValidationError(
                f"Unknown sub-agent target '{target}'. Only registered sub-agents are allowed."
            )
        accepted.append((original_idx, raw))

    if not accepted:
        return []

    idx_map = {old_idx: new_idx for new_idx, (old_idx, _) in enumerate(accepted)}
    normalized: list[ExecutionStep] = []

    seen_step_ids: set[str] = set()
    for new_idx, (old_idx, raw) in enumerate(accepted):
        raw_id = raw.get("step_id")
        step_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else f"step_{new_idx}"
        if step_id in seen_step_ids:
            raise PlanValidationError(f"Duplicate step_id detected: {step_id}")
        seen_step_ids.add(step_id)

        deps = raw.get("depends_on") or []
        remapped_deps: list[int] = []
        for dep in deps:
            if not isinstance(dep, int):
                continue
            if dep in idx_map:
                remapped_deps.append(idx_map[dep])

        timeout_seconds = raw.get("timeout_seconds")
        if timeout_seconds is not None and not isinstance(timeout_seconds, (int, float)):
            raise PlanValidationError(f"Invalid timeout_seconds for step {step_id}")
        if isinstance(timeout_seconds, (int, float)) and timeout_seconds <= 0:
            raise PlanValidationError(f"timeout_seconds must be > 0 for step {step_id}")

        enabled = bool(raw.get("enabled", True))

        payload = raw.get("input") or {}
        if not isinstance(payload, dict):
            raise PlanValidationError(f"input must be a dict for step {step_id}")

        normalized.append(
            ExecutionStep(
                step_id=step_id,
                kind=raw["kind"],
                target=raw["target"],
                input=dict(payload),
                depends_on=remapped_deps,
                timeout_seconds=float(timeout_seconds) if timeout_seconds else None,
                enabled=enabled,
                original_index=old_idx,
            )
        )

    return normalized


def _ensure_acyclic_or_raise(steps: list[ExecutionStep]) -> None:
    """Validate that dependency graph is acyclic (Kahn's algorithm)."""
    if not steps:
        return

    in_degree = {i: 0 for i in range(len(steps))}
    children: dict[int, list[int]] = {i: [] for i in range(len(steps))}
    for i, step in enumerate(steps):
        for dep in step.depends_on:
            in_degree[i] += 1
            children[dep].append(i)

    queue = [i for i, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        idx = queue.pop()
        visited += 1
        for nxt in children[idx]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if visited != len(steps):
        raise PlanValidationError("Execution plan contains cyclic dependencies.")


async def execute_parallel_plan(
    *,
    execution_plan: list[dict[str, Any]],
    tools: dict[str, ToolCallable] | None = None,
    sub_agents: dict[str, AgentCallable] | None = None,
    context: dict[str, Any] | None = None,
    default_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Execute a dependency-aware plan with generic tools and sub-agents.

    Fail-fast: if any running step errors or times out, execution stops immediately.
    """

    default_tools, default_agents = _build_default_registries()
    tools = {**default_tools, **(tools or {})}
    sub_agents = {**default_agents, **(sub_agents or {})}
    context = context or {}

    if default_timeout_seconds is not None and default_timeout_seconds <= 0:
        raise PlanValidationError("default_timeout_seconds must be > 0 when provided.")

    steps = _normalize_steps(execution_plan, tools, sub_agents)
    _ensure_acyclic_or_raise(steps)

    if not steps:
        return {
            "status": "completed",
            "results": [],
            "completed_steps": 0,
            "failed_step": None,
            "failed_reason": None,
            "total_duration_ms": 0,
        }

    step_results: dict[int, StepResult] = {}
    completed: set[int] = set()
    remaining: set[int] = set(range(len(steps)))

    run_started = _now()
    failed_step_id: str | None = None
    failed_reason: str | None = None

    async def _execute_single(step_idx: int) -> StepResult:
        step = steps[step_idx]
        upstream = [step_results[d] for d in step.depends_on if d in step_results]
        upstream_dicts = [u.as_dict() for u in upstream]

        step_input = dict(step.input)

        result = StepResult(
            step_id=step.step_id,
            original_index=step.original_index,
            kind=step.kind,
            target=step.target,
            status="running",
            input=step_input,
            upstream_step_ids=[u.step_id for u in upstream],
            upstream_results=upstream_dicts,
        )
        started = _now()
        result.started_at = started

        if not step.enabled:
            ended = _now()
            result.status = "skipped"
            result.ended_at = ended
            result.duration_ms = _duration_ms(started, ended)
            return result

        target_fn = tools[step.target] if step.kind == "tool" else sub_agents[step.target]
        timeout_seconds = step.timeout_seconds or default_timeout_seconds

        try:
            task = _call_target(target_fn, step_input, context)
            output = (
                await asyncio.wait_for(task, timeout_seconds)
                if timeout_seconds
                else await task
            )
            ended = _now()
            result.output = output
            result.status = "success"
            result.ended_at = ended
            result.duration_ms = _duration_ms(started, ended)
            return result
        except TimeoutError as exc:
            ended = _now()
            result.status = "failed"
            result.error = (
                f"Step '{step.step_id}' ({step.kind}:{step.target}) timed out "
                f"after {timeout_seconds}s."
            )
            result.ended_at = ended
            result.duration_ms = _duration_ms(started, ended)
            raise StepTimeoutError(result.error) from exc
        except Exception as exc:  # noqa: BLE001
            ended = _now()
            result.status = "failed"
            result.error = f"Step '{step.step_id}' ({step.kind}:{step.target}) failed: {exc}"
            result.ended_at = ended
            result.duration_ms = _duration_ms(started, ended)
            raise StepExecutionError(result.error) from exc

    while remaining:
        ready = {
            idx
            for idx in remaining
            if all(dep in completed for dep in steps[idx].depends_on)
        }
        if not ready:
            raise PlanValidationError(
                "No executable steps found; dependency graph may be malformed."
            )

        ordered_ready = sorted(ready)
        try:
            wave = await asyncio.gather(*[_execute_single(i) for i in ordered_ready])
        except (StepExecutionError, StepTimeoutError) as exc:
            failed_reason = str(exc)
            for i in ordered_ready:
                if i in step_results:
                    continue
                failed_step_id = steps[i].step_id
                break
            break

        for i, step_result in zip(ordered_ready, wave):
            step_results[i] = step_result
            completed.add(i)
        remaining -= ready

    run_ended = _now()
    ordered_results = [step_results[i].as_dict() for i in sorted(step_results.keys())]

    status = "failed" if failed_reason else "completed"
    return {
        "status": status,
        "results": ordered_results,
        "completed_steps": len(completed),
        "failed_step": failed_step_id,
        "failed_reason": failed_reason,
        "total_duration_ms": _duration_ms(run_started, run_ended),
    }
