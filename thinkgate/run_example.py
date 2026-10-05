import json
from pathlib import Path

from thinkgate.evaluation import evaluate_experiment


if __name__ == "__main__":
    path = Path(__file__).parent / "examples" / "traces.json"
    traces = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(evaluate_experiment(traces), indent=2))
