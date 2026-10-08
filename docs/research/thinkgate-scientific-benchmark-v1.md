# ThinkGate Scientific Benchmark v1

Frozen: 2026-10-08 (Asia/Dhaka)

## Hypothesis
ThinkGate should reduce unnecessary inference compute while preserving final answer quality, and continue when an additional inference attempt produces measurable quality gain.

## Frozen protocol
- 60 deterministic numeric-reasoning tasks: 20 easy, 20 medium, 20 hard.
- 4 answer attempts maximum per task.
- Temperature 0.
- Store visible answers and usage metadata only; do not require or store private chain-of-thought.
- Primary quality: exact numeric correctness.
- Cost: provider-reported total tokens when available.
- Split: 36 train / 12 tune / 12 untouched test.
- Baselines: fixed-1, fixed-2, always-continue, ThinkGate adaptive stop.

## Untouched-test success gates
- Accuracy degradation vs always-continue <= 1 percentage point.
- Compute reduction vs always-continue >= 20%.
- Utility improvement vs fixed-2 > 0.
- Continuation recall >= 80% for positive-gain transitions.
- Stop precision >= 80% for zero/negative-gain transitions.

## Benchmark adequacy gates
The benchmark itself must show enough cases where continuing matters:
- positive-gain transitions >= 20% overall;
- >= 8 positive-gain transitions in untouched test;
- >= 3 untouched-test tasks where attempt 1 is wrong and a later attempt is correct.

If adequacy fails, report benchmark-under-challenging rather than claiming ThinkGate success.

## Leakage control
Prompts, expected answers, split assignment, scorer, maximum attempts, cost normalization, adequacy gates, and success gates are fixed before model calls. Train/tune may select policy parameters; untouched test is not used for tuning.

## Validation
After one complete run, repeat the identical frozen benchmark on at least two additional model families.
