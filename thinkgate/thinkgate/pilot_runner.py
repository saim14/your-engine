from __future__ import annotations

import json
import os
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
    all_tasks = load_tasks(tasks_path)
    start_index = max(0, int(os.environ.get("THINKGATE_PILOT_START_INDEX", "0")))
    task_limit = int(os.environ.get("THINKGATE_PILOT_TASK_LIMIT", str(len(all_tasks))))
    tasks = all_tasks[start_index:start_index + task_limit]

    traces: list[dict[str, Any]] = []
    print(
        "THINKGATE_PILOT_START "
        + json.dumps(
            {
                "model": config.model,
                "tasks": len(tasks),
                "start_index": start_index,
                "max_steps": config.max_steps,
                "protocol": "pilot-numeric-v1",
            }
        ),
        flush=True,
    )

    with httpx.Client() as client:
        for index, task in enumerate(tasks, start=1):
            try:
                trace = collect_task(client, config, task)
            except Exception as exc:
                print(
                    "THINKGATE_PILOT_ERROR "
                    + json.dumps(
                        {
                            "index": index,
                            "task_id": task.get("task_id"),
                            "error": repr(exc),
                            "completed_tasks": len(traces),
                        },
                        separators=(",", ":"),
                    ),
                    flush=True,
                )
                return
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

    if len(traces) < 5:
        print(
            "THINKGATE_PILOT_PARTIAL "
            + json.dumps({"completed_tasks": len(traces), "reason": "fewer than 5 traces; calibration skipped"}),
            flush=True,
        )
        return

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
