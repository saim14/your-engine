from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable


REQUIRED_STEP_FIELDS = {
    "step_index",
    "quality",
    "cost",
    "predicted_gain",
}


def prompt_hash(prompt: str) -> str:
    return sha256(prompt.encode("utf-8")).hexdigest()


def validate_real_trace(trace: dict[str, Any]) -> None:
    required = {"task_id", "model", "prompt_hash", "initial_quality", "steps"}
    missing = required - trace.keys()
    if missing:
        raise ValueError(f"trace missing required fields: {sorted(missing)}")

    if not isinstance(trace["steps"], list) or not trace["steps"]:
        raise ValueError("trace.steps must be a non-empty list")

    expected_index = 1
    for step in trace["steps"]:
        missing_step = REQUIRED_STEP_FIELDS - step.keys()
        if missing_step:
            raise ValueError(
                f"step {expected_index} missing required fields: {sorted(missing_step)}"
            )
        if step["step_index"] != expected_index:
            raise ValueError(
                f"step_index must be contiguous starting at 1; expected {expected_index}"
            )
        if not 0.0 <= float(step["quality"]) <= 1.0:
            raise ValueError("step quality must be in [0, 1]")
        if float(step["cost"]) < 0.0:
            raise ValueError("step cost must be non-negative")
        expected_index += 1


def to_evaluator_trace(trace: dict[str, Any]) -> dict[str, Any]:
    validate_real_trace(trace)
    return {
        "id": trace["task_id"],
        "initial_quality": float(trace["initial_quality"]),
        "steps": [
            {
                "quality": float(step["quality"]),
                "cost": float(step["cost"]),
                "predicted_gain": float(step["predicted_gain"]),
            }
            for step in trace["steps"]
        ],
    }


def validate_dataset(traces: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    materialized = list(traces)
    if not materialized:
        raise ValueError("dataset must contain at least one trace")

    seen_task_ids: set[str] = set()
    for trace in materialized:
        validate_real_trace(trace)
        task_id = str(trace["task_id"])
        if task_id in seen_task_ids:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen_task_ids.add(task_id)

    return materialized
