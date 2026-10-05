from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from thinkgate.calibration import calibrate_and_evaluate
from thinkgate.evaluation import evaluate_experiment
from thinkgate.real_traces import to_evaluator_trace, validate_dataset


class Step(BaseModel):
    quality: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0)
    predicted_gain: float


class Trace(BaseModel):
    id: str
    initial_quality: float = Field(ge=0.0, le=1.0)
    steps: list[Step]


class EvaluateRequest(BaseModel):
    traces: list[Trace]
    margin: float = 0.0


app = FastAPI(
    title="ThinkGate",
    version="0.3.0",
    description="Adaptive compute stop/continue evaluator with calibrated real-trace collection",
)

static_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "thinkgate", "version": "0.3.0"}


@app.post("/api/evaluate")
def evaluate(payload: EvaluateRequest) -> dict:
    if not payload.traces:
        raise HTTPException(status_code=400, detail="at least one trace is required")

    traces = [trace.model_dump() for trace in payload.traces]
    try:
        return evaluate_experiment(traces, margin=payload.margin)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/experiment")
def experiment_manifest() -> dict:
    import json
    manifest_path = Path(__file__).parent / "experiment_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@app.post("/api/evaluate-real")
def evaluate_real(payload: dict) -> dict:
    traces = payload.get("traces", [])
    margin = float(payload.get("margin", 0.0))
    try:
        validated = validate_dataset(traces)
        evaluator_traces = [to_evaluator_trace(trace) for trace in validated]
        report = evaluate_experiment(evaluator_traces, margin=margin)
        report["experiment_type"] = "REAL_TRACE"
        report["trace_count"] = len(validated)
        report["validation"] = "real-trace schema passed; externally supplied predicted_gain used"
        return report
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibrate-evaluate")
def calibrate_evaluate(payload: dict) -> dict:
    traces = payload.get("traces", [])
    try:
        return calibrate_and_evaluate(traces)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/collection-protocol")
def collection_protocol() -> dict:
    import json
    benchmark_path = Path(__file__).parent / "benchmarks" / "pilot_numeric_v1.json"
    tasks = json.loads(benchmark_path.read_text(encoding="utf-8"))
    return {
        "protocol": "pilot-numeric-v1",
        "status": "FROZEN_FOR_PILOT_COLLECTION",
        "benchmark_tasks": len(tasks),
        "max_steps": 4,
        "temperature": 0,
        "quality_scorer": "graded_numeric_v1",
        "cost_scorer": "step total tokens / 4000-token task budget",
        "collector": "OpenAI-compatible /chat/completions endpoint",
        "required_env": ["THINKGATE_API_KEY", "THINKGATE_MODEL"],
        "optional_env": ["THINKGATE_BASE_URL", "THINKGATE_MAX_STEPS"],
        "claim_policy": "Pilot traces validate the collection and calibration pipeline; they are not broad evidence of general adaptive-compute performance.",
    }


@app.get("/api/internal/hf-probe")
def hf_probe(key: str) -> dict:
    import os
    import time
    import httpx

    expected_key = os.environ.get("THINKGATE_PROBE_KEY")
    if not expected_key or key != expected_key:
        raise HTTPException(status_code=404, detail="not found")

    api_key = os.environ.get("THINKGATE_API_KEY")
    base_url = os.environ.get("THINKGATE_BASE_URL", "https://router.huggingface.co/v1").rstrip("/")
    if not api_key:
        raise HTTPException(status_code=503, detail="model API credential is not configured")

    models = [
        "Qwen/Qwen3-4B-Instruct-2507:nscale",
        "google/gemma-3-4b-it:deepinfra",
        "openai/gpt-oss-20b:deepinfra",
    ]
    prompt = (
        "Solve carefully and end with exactly FINAL: <number>. "
        "A warehouse starts with 480 units. It ships 37.5% of them, "
        "then receives 96 new units. How many units are now in the warehouse?"
    )
    results = []
    with httpx.Client(timeout=90.0) as client:
        for model in models:
            started = time.perf_counter()
            try:
                response = client.post(
                    base_url + "/chat/completions",
                    headers={
                        "Authorization": "Bearer " + api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                    },
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                try:
                    payload = response.json()
                except Exception:
                    payload = {"raw": response.text[:300]}
                if response.is_success:
                    message = payload["choices"][0]["message"]["content"]
                    results.append({
                        "model": model,
                        "status": response.status_code,
                        "latency_ms": latency_ms,
                        "answer_tail": message[-160:],
                        "usage": payload.get("usage", {}),
                    })
                else:
                    results.append({
                        "model": model,
                        "status": response.status_code,
                        "latency_ms": latency_ms,
                        "error": str(payload)[:400],
                    })
            except Exception as exc:
                results.append({"model": model, "error": repr(exc)})
    return {"task_expected": 396, "results": results}
