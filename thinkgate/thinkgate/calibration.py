from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable

from .evaluation import evaluate_experiment
from .real_traces import validate_dataset


FEATURE_NAMES = (
    "bias",
    "current_quality",
    "step_index",
    "previous_observed_gain",
    "previous_cost",
)


@dataclass(frozen=True)
class GainModel:
    coefficients: tuple[float, ...]
    ridge: float = 1e-3

    def predict(self, features: tuple[float, ...]) -> float:
        return sum(w * x for w, x in zip(self.coefficients, features))


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("gain estimator is singular")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [v / scale for v in a[col]]
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor:
                a[row] = [x - factor * y for x, y in zip(a[row], a[col])]
    return [a[i][-1] for i in range(n)]


def _step_features(current_quality: float, step_index: int, previous_gain: float, previous_cost: float) -> tuple[float, ...]:
    return (1.0, float(current_quality), float(step_index), float(previous_gain), float(previous_cost))


def _samples(traces: Iterable[dict[str, Any]]) -> list[tuple[tuple[float, ...], float]]:
    samples: list[tuple[tuple[float, ...], float]] = []
    for trace in traces:
        current = float(trace["initial_quality"])
        previous_gain = 0.0
        previous_cost = 0.0
        for step in trace["steps"]:
            features = _step_features(current, int(step["step_index"]), previous_gain, previous_cost)
            next_quality = float(step["quality"])
            gain = next_quality - current
            samples.append((features, gain))
            previous_gain = gain
            previous_cost = float(step["cost"])
            current = next_quality
    return samples


def fit_gain_model(traces: Iterable[dict[str, Any]], ridge: float = 1e-3) -> GainModel:
    traces = list(traces)
    samples = _samples(traces)
    if len(samples) < len(FEATURE_NAMES):
        raise ValueError(f"need at least {len(FEATURE_NAMES)} observed steps to fit gain estimator")
    p = len(FEATURE_NAMES)
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [0.0 for _ in range(p)]
    for x, y in samples:
        for i in range(p):
            xty[i] += x[i] * y
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
    for i in range(1, p):
        xtx[i][i] += ridge
    return GainModel(tuple(_solve(xtx, xty)), ridge=ridge)


def add_model_predictions(trace: dict[str, Any], model: GainModel) -> dict[str, Any]:
    current = float(trace["initial_quality"])
    previous_gain = 0.0
    previous_cost = 0.0
    steps = []
    for step in trace["steps"]:
        features = _step_features(current, int(step["step_index"]), previous_gain, previous_cost)
        predicted = model.predict(features)
        copied = dict(step)
        copied["predicted_gain"] = predicted
        steps.append(copied)
        next_quality = float(step["quality"])
        previous_gain = next_quality - current
        previous_cost = float(step["cost"])
        current = next_quality
    copied_trace = dict(trace)
    copied_trace["steps"] = steps
    return copied_trace


def split_dataset(traces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if len(traces) < 5:
        raise ValueError("calibrated evaluation requires at least 5 task traces")
    ordered = sorted(
        traces,
        key=lambda t: sha256(str(t["task_id"]).encode("utf-8")).hexdigest(),
    )
    n = len(ordered)
    n_eval = max(1, round(n * 0.2))
    n_tune = max(1, round(n * 0.2))
    train_end = n - n_tune - n_eval
    if train_end < 1:
        raise ValueError("dataset too small for train/tune/eval split")
    return ordered[:train_end], ordered[train_end:train_end + n_tune], ordered[train_end + n_tune:]


def _to_eval(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(trace["task_id"]),
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


def _select_margin(tune: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    candidates = (-0.05, -0.02, 0.0, 0.01, 0.02, 0.05, 0.10)
    scored = []
    eval_traces = [_to_eval(t) for t in tune]
    for margin in candidates:
        report = evaluate_experiment(eval_traces, margin=margin)
        p = report["policies"]["thinkgate"]
        scored.append((p["mean_utility"], -p["mean_cost"], -abs(margin), margin, report))
    best = max(scored, key=lambda row: row[:3])
    return best[3], best[4]


def calibrate_and_evaluate(traces: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = validate_dataset(traces, require_predicted_gain=False)
    train, tune, evaluation = split_dataset(materialized)
    model = fit_gain_model(train)
    tune_predicted = [add_model_predictions(t, model) for t in tune]
    margin, tune_report = _select_margin(tune_predicted)
    eval_predicted = [add_model_predictions(t, model) for t in evaluation]
    report = evaluate_experiment([_to_eval(t) for t in eval_predicted], margin=margin)
    report["experiment_type"] = "CALIBRATED_REAL_TRACE"
    report["estimator"] = {
        "type": "ridge_linear_v1",
        "feature_names": list(FEATURE_NAMES),
        "coefficients": list(model.coefficients),
        "ridge": model.ridge,
    }
    report["split"] = {
        "train": len(train),
        "tune": len(tune),
        "eval": len(evaluation),
        "policy": "stable SHA-256 ordering by task_id; 60/20/20 approximate split",
    }
    report["selected_margin"] = margin
    report["tune_thinkgate_utility"] = tune_report["policies"]["thinkgate"]["mean_utility"]
    report["validation"] = "predicted_gain learned from train only; margin selected on tune only; frozen gates evaluated on untouched eval split"
    return report
