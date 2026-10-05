from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .calibration import calibrate_and_evaluate
from .collector import collect_task, config_from_env, load_tasks

import httpx


def _compact_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": trace["task_id"],
        "model": trace["model"],
        "prompt_hash": trace["prompt_hash"],
        "initial_quality": trace["initial_quality"],
        "steps": [
            {
                "step_index": s["step_index"],
                "quality": s["quality"],
                "cost": s["cost"],
                "latency_ms": s["latency_ms"],
                "input_tokens": s["input_tokens"],
                "output_tokens": s["output_tokens"],
            }
            for s in trace["steps"]
        ],
        "collection": trace.get("collection", {}),
    }


def run_pilot() -> None:
    config = config_from_env()
    tasks_path = Path(__file__).resolve().parent.parent / "benchmarks" / "pilot_numeric_v1.json"
    tasks = load_tasks(tasks_path)

    traces: list[dict[str, Any]] = []
    print(
        "THINKGATE_PILOT_START "
        + json.dumps(
            {
                "model": config.model,
                "tasks": len(tasks),
                "max_steps": config.max_steps,
                "protocol": "pilot-numeric-v1",
            }
        ),
        flush=True,
    )

    with httpx.Client() as client:
        for index, task in enumerate(tasks, start=1):
            trace = collect_task(client, config, task)
            compact = _compact_trace(trace)
            traces.append(compact)
            print(
                "THINKGATE_PILOT_TRACE "
                + json.dumps(
                    {
                        "index": index,
                        "total": len(tasks),
                        "trace": compact,
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )

    report = calibrate_and_evaluate(traces)
    summary = {
        "model": config.model,
        "tasks": len(traces),
        "steps": sum(len(t["steps"]) for t in traces),
        "mean_final_quality": sum(t["steps"][-1]["quality"] for t in traces) / len(traces),
        "mean_total_cost": sum(sum(s["cost"] for s in t["steps"]) for t in traces) / len(traces),
        "mean_total_latency_ms": sum(sum(s["latency_ms"] for s in t["steps"]) for t in traces) / len(traces),
        "report": report,
    }
    print("THINKGATE_PILOT_RESULT " + json.dumps(summary, separators=(",", ":")), flush=True)


def start_pilot_background() -> None:
    threading.Thread(target=run_pilot, daemon=True, name="thinkgate-hf-pilot").start()
