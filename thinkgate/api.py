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
    version="0.2.0",
    description="Adaptive compute stop/continue evaluator with train/tune/eval calibration",
)

static_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "thinkgate", "version": "0.2.0"}


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
