# ThinkGate MVP

ThinkGate is an experimental metacognitive runtime evaluator: given a sequence of reasoning states, it decides whether an AI system should **STOP** or **CONTINUE** based on expected quality gain versus compute cost.

This MVP is deliberately small. It does not call an LLM. It evaluates saved or synthetic traces so the controller can be tested before any hosted product is built.

## Core question

> Can an adaptive stop/continue policy produce better quality-adjusted utility than simple fixed-compute baselines?

For each reasoning step:

```
net_value = predicted_gain - next_step_cost
decision = CONTINUE if net_value > margin else STOP
```

## Experiment gates

A run is reported as **SUCCESS** only when all primary gates pass on held-out traces:

1. Mean utility improves by at least **5%** over the stronger baseline.
2. Mean final quality is no more than **0.01** below the stronger baseline.
3. Mean compute cost is at least **10%** lower than the always-continue baseline.

Otherwise the run is **FAILED**.

These thresholds are intentionally explicit and can be changed only before evaluating a new held-out dataset.

## Baselines

- **always_continue** — consume the whole trace.
- **fixed_2** — stop after at most two reasoning steps.
- **thinkgate** — adaptive expected-gain-vs-cost controller.

The "stronger baseline" is whichever of always_continue and fixed_2 has higher mean utility on the evaluation set.

## Quick start

```bash
cd thinkgate
python -m unittest discover -s tests -v
python run_example.py
```

Expected unit-test result: all tests pass.

The example prints JSON containing metrics for every policy plus a top-level experiment `status` of `SUCCESS` or `FAILED`.

## Trace format

Each trace contains a starting quality and candidate future steps:

```json
{
  "id": "trace-1",
  "initial_quality": 0.40,
  "steps": [
    {"quality": 0.55, "cost": 0.05, "predicted_gain": 0.16},
    {"quality": 0.57, "cost": 0.08, "predicted_gain": 0.01}
  ]
}
```

- `quality`: observed quality after taking the step, normalized to [0, 1].
- `cost`: normalized compute/token/latency cost for taking that step.
- `predicted_gain`: information available before taking that step.
- ThinkGate never reads the future `quality` when deciding.

## What counts as evidence

The bundled example is only a wiring check. It is **not** evidence that adaptive compute works in real LLMs.

A meaningful next study should use frozen traces from one or more real models and a predeclared quality metric, cost conversion, train/tune/evaluation split, and thresholds.

## Hosting path

Once the evaluator is stable, expose it through a small FastAPI service and a Next.js/React UI:

- upload/paste trace JSON
- visualize quality and accumulated cost by step
- show STOP/CONTINUE decisions
- compare policies
- render SUCCESS/FAILED gate results

This branch is intentionally structured so that API and UI layers can be added without changing the evaluation contract.
