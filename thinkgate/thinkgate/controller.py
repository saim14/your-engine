from __future__ import annotations


def decide(predicted_gain: float, next_step_cost: float, margin: float = 0.0) -> str:
    """Return CONTINUE only when predicted benefit exceeds cost plus margin."""
    if not all(isinstance(x, (int, float)) for x in (predicted_gain, next_step_cost, margin)):
        raise TypeError("predicted_gain, next_step_cost, and margin must be numeric")
    if next_step_cost < 0:
        raise ValueError("next_step_cost must be non-negative")
    return "CONTINUE" if predicted_gain - next_step_cost > margin else "STOP"
