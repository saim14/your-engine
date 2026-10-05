from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from .controller import decide


@dataclass
class PolicyResult:
    name: str
    mean_quality: float
    mean_cost: float
    mean_utility: float


def _validate_trace(trace: dict) -> None:
    if "initial_quality" not in trace or "steps" not in trace:
        raise ValueError("trace needs initial_quality and steps")
    q = trace["initial_quality"]
    if not isinstance(q, (int, float)) or not 0 <= q <= 1:
        raise ValueError("initial_quality must be in [0, 1]")
    for step in trace["steps"]:
        if not {"quality", "cost", "predicted_gain"} <= set(step):
            raise ValueError("each step needs quality, cost, predicted_gain")
        if not 0 <= step["quality"] <= 1:
            raise ValueError("step quality must be in [0, 1]")
        if step["cost"] < 0:
            raise ValueError("step cost must be non-negative")


def _run_policy(trace: dict, policy: str, margin: float = 0.0) -> tuple[float, float]:
    _validate_trace(trace)
    quality = float(trace["initial_quality"])
    cost = 0.0

    for i, step in enumerate(trace["steps"]):
        if policy == "always_continue":
            take_step = True
        elif policy == "fixed_2":
            take_step = i < 2
        elif policy == "thinkgate":
            take_step = decide(step["predicted_gain"], step["cost"], margin) == "CONTINUE"
        else:
            raise ValueError(f"unknown policy: {policy}")

        if not take_step:
            break

        cost += float(step["cost"])
        quality = float(step["quality"])

    return quality, cost


def _aggregate(traces: list[dict], policy: str, margin: float) -> PolicyResult:
    qualities, costs, utilities = [], [], []
    for trace in traces:
        quality, cost = _run_policy(trace, policy, margin)
        qualities.append(quality)
        costs.append(cost)
        utilities.append(quality - cost)

    n = len(traces)
    return PolicyResult(
        name=policy,
        mean_quality=sum(qualities) / n,
        mean_cost=sum(costs) / n,
        mean_utility=sum(utilities) / n,
    )


def evaluate_experiment(
    traces: Iterable[dict],
    *,
    margin: float = 0.0,
    min_utility_improvement: float = 0.05,
    max_quality_drop: float = 0.01,
    min_cost_reduction: float = 0.10,
) -> dict:
    traces = list(traces)
    if not traces:
        raise ValueError("at least one trace is required")

    results = {
        p: _aggregate(traces, p, margin)
        for p in ("always_continue", "fixed_2", "thinkgate")
    }

    baseline = max(
        (results["always_continue"], results["fixed_2"]),
        key=lambda r: r.mean_utility,
    )
    adaptive = results["thinkgate"]
    always = results["always_continue"]

    denom = abs(baseline.mean_utility) if abs(baseline.mean_utility) > 1e-12 else 1.0
    utility_improvement = (adaptive.mean_utility - baseline.mean_utility) / denom
    quality_drop = baseline.mean_quality - adaptive.mean_quality
    cost_denom = always.mean_cost if always.mean_cost > 1e-12 else 1.0
    cost_reduction = (always.mean_cost - adaptive.mean_cost) / cost_denom

    gates = {
        "utility_gain": utility_improvement >= min_utility_improvement,
        "quality_retention": quality_drop <= max_quality_drop,
        "cost_reduction": cost_reduction >= min_cost_reduction,
    }

    return {
        "status": "SUCCESS" if all(gates.values()) else "FAILED",
        "stronger_baseline": baseline.name,
        "gates": gates,
        "observed": {
            "utility_improvement": utility_improvement,
            "quality_drop": quality_drop,
            "cost_reduction": cost_reduction,
        },
        "thresholds": {
            "min_utility_improvement": min_utility_improvement,
            "max_quality_drop": max_quality_drop,
            "min_cost_reduction": min_cost_reduction,
        },
        "policies": {name: asdict(result) for name, result in results.items()},
    }
