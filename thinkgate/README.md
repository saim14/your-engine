# ThinkGate MVP v0.2

ThinkGate is an experimental **adaptive-compute control layer** for AI reasoning. Its job is to decide whether an AI system should **STOP** or **CONTINUE** based on the expected value of another reasoning step relative to its compute cost.

The original MVP accepted `predicted_gain` as an input. v0.2 removes that shortcut in the calibrated workflow: ThinkGate can now **learn predicted gain from historical reasoning traces**, tune its decision margin on a separate split, and apply frozen success gates only on held-out evaluation tasks.

## Core decision

```
net_value = predicted_gain - next_step_cost
decision = CONTINUE if net_value > margin else STOP
```

## Three evaluation modes

1. **Synthetic demo** — wiring and UI sanity checks only.
2. **Real trace** — evaluates externally supplied `predicted_gain`.
3. **Calibrated real trace** — learns `predicted_gain` from observed traces and performs a leakage-resistant train/tune/eval study.

The calibrated mode is now the main research path.

## Learned gain estimator

v0.2 includes a transparent ridge-linear estimator using only information available before the next step:

- current quality
- next step index
- previous observed quality gain
- previous step cost
- intercept

Training labels are the **observed quality gain of the next step**. The model is fit on train tasks only.

The decision margin is selected separately on tune tasks. Frozen experiment gates are then evaluated on untouched eval tasks.

This structure is intentionally simple and auditable before moving to richer estimators.

## Split discipline

Task IDs are stably ordered with SHA-256, then divided approximately:

- 60% train
- 20% tune
- 20% eval

All steps from one task remain in exactly one split.

At least 5 task traces are required for calibrated evaluation.

## Frozen experiment gates

A held-out run is **SUCCESS** only if all three gates pass:

1. Mean utility improves by at least **5%** over the stronger fixed baseline.
2. Mean final quality is no more than **0.01** below the stronger baseline.
3. Mean compute cost is at least **10%** lower than always-continue.

Baselines:

- `always_continue`
- `fixed_2`
- `thinkgate`

Utility is currently defined as:

```
utility = final_quality - accumulated_cost
```

## Observed trace format for calibrated mode

```json
{
  "task_id": "task-001",
  "model": "provider/model-name",
  "prompt_hash": "sha256-of-original-prompt",
  "initial_quality": 0.20,
  "steps": [
    {
      "step_index": 1,
      "quality": 0.55,
      "cost": 0.05,
      "latency_ms": 900,
      "input_tokens": 120,
      "output_tokens": 80
    },
    {
      "step_index": 2,
      "quality": 0.72,
      "cost": 0.08,
      "latency_ms": 1100,
      "input_tokens": 180,
      "output_tokens": 110
    }
  ]
}
```

Do **not** provide `predicted_gain` in calibrated mode; ThinkGate generates it.

## API

- `GET /health`
- `GET /api/experiment`
- `POST /api/evaluate`
- `POST /api/evaluate-real`
- `POST /api/calibrate-evaluate`

## Local run

```bash
cd thinkgate
python -m unittest discover -s tests -v
uvicorn api:app --reload
```

## Research status

**Engineering milestone:** learned gain calibration pipeline implemented.

**Scientific status:** not yet validated. Synthetic examples and hand-constructed traces are not evidence of real-world adaptive-compute advantage.

The next evidence milestone is to collect a sufficiently large corpus of genuine multi-step LLM traces with a frozen quality scorer and cost conversion, then run the preregistered held-out evaluation without modifying gates after seeing eval results.

## Product direction

ThinkGate is intended to evolve from an evaluator into a runtime compute-governance layer:

```
agent / RAG / coding system
        ↓
reasoning trace + online quality signals
        ↓
predicted marginal gain
        ↓
ThinkGate policy
        ↓
STOP / CONTINUE / later: ROUTE / ESCALATE
```

Potential integration targets include agent frameworks, OpenAI-compatible inference pipelines, RAG systems, coding assistants, and enterprise AI workflows where latency, token spend, and reliability must be controlled together.
