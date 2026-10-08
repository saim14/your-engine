from __future__ import annotations

import hmac
import os
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from thinkgate.calibration import calibrate_and_evaluate
from thinkgate.evaluation import evaluate_experiment
from thinkgate.pilot_runner import start_pilot_background
from thinkgate.production import gateway
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


class ProvisionCustomerRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=80)


class DecisionRequest(BaseModel):
    predicted_gain: float = Field(description="Expected quality/utility gain from one more step")
    next_step_cost: float = Field(ge=0.0, description="Normalized cost of the next inference step")
    margin: float = Field(default=0.0, description="Safety margin required before continuing")
    current_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    step_index: int = Field(default=1, ge=1)
    max_steps: int = Field(default=4, ge=1)
    trace_id: str | None = Field(default=None, max_length=128)


app = FastAPI(
    title="ThinkGate",
    version="0.4.0",
    description="Adaptive reasoning control for production AI plus reproducible evaluation tooling",
)

static_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "thinkgate", "version": "0.4.0"}


def _auth_admin(x_thinkgate_admin_key: str | None) -> None:
    configured = os.environ.get("THINKGATE_ADMIN_KEY", "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="admin provisioning is not configured")
    if not x_thinkgate_admin_key or not hmac.compare_digest(
        x_thinkgate_admin_key,
        configured,
    ):
        raise HTTPException(status_code=401, detail="invalid admin key")


def _auth_customer(x_thinkgate_key: str | None):
    try:
        context = gateway.authenticate(x_thinkgate_key)
        gateway.enforce_rate_limit(context.customer_id)
        return context
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.post("/api/v1/admin/customers")
def provision_customer(
    payload: ProvisionCustomerRequest,
    x_thinkgate_admin_key: str | None = Header(
        default=None,
        alias="X-ThinkGate-Admin-Key",
    ),
) -> dict:
    _auth_admin(x_thinkgate_admin_key)
    try:
        provisioned = gateway.provision_customer(payload.customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "api_version": "v1",
        "credential_delivery": "returned_once_plaintext",
        **provisioned,
    }


@app.delete("/api/v1/admin/customers/{customer_id}")
def revoke_customer(
    customer_id: str,
    x_thinkgate_admin_key: str | None = Header(
        default=None,
        alias="X-ThinkGate-Admin-Key",
    ),
) -> dict:
    _auth_admin(x_thinkgate_admin_key)
    try:
        result = gateway.revoke_customer(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"api_version": "v1", **result}


@app.post("/api/v1/decision")
def production_decision(
    payload: DecisionRequest,
    x_thinkgate_key: str | None = Header(default=None, alias="X-ThinkGate-Key"),
) -> dict:
    context = _auth_customer(x_thinkgate_key)
    try:
        result = gateway.make_decision(
            customer_id=context.customer_id,
            predicted_gain=payload.predicted_gain,
            next_step_cost=payload.next_step_cost,
            margin=payload.margin,
            step_index=payload.step_index,
            max_steps=payload.max_steps,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "api_version": "v1",
        "customer_mode": "sandbox" if context.sandbox else "pilot",
        "trace_id": payload.trace_id,
        "current_quality": payload.current_quality,
        **result,
    }


@app.get("/api/v1/usage")
def production_usage(
    x_thinkgate_key: str | None = Header(default=None, alias="X-ThinkGate-Key"),
) -> dict:
    context = _auth_customer(x_thinkgate_key)
    return {
        "api_version": "v1",
        "customer_mode": "sandbox" if context.sandbox else "pilot",
        **gateway.usage(context.customer_id),
    }


@app.get("/api/v1/billing-summary")
def production_billing_summary(
    start_ts: int,
    end_ts: int,
    x_thinkgate_key: str | None = Header(default=None, alias="X-ThinkGate-Key"),
) -> dict:
    context = _auth_customer(x_thinkgate_key)
    try:
        summary = gateway.billing_summary(
            context.customer_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "api_version": "v1",
        "customer_mode": "sandbox" if context.sandbox else "pilot",
        "generated_at": int(time.time()),
        **summary,
    }


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


@app.on_event("startup")
def maybe_start_hf_pilot() -> None:
    import os
    if os.environ.get("THINKGATE_RUN_PILOT") == "1":
        start_pilot_background()
