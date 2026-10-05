from __future__ import annotations

import argparse
import json
from pathlib import Path

from thinkgate.collector import collect_dataset, config_from_env, load_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect genuine multi-step LLM traces for ThinkGate.")
    parser.add_argument("--tasks", default="benchmarks/pilot_numeric_v1.json")
    parser.add_argument("--output", default="artifacts/real_traces.json")
    args = parser.parse_args()

    config = config_from_env()
    tasks = load_tasks(args.tasks)
    traces = collect_dataset(tasks, config)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(traces, indent=2), encoding="utf-8")
    print(f"wrote {len(traces)} traces to {output}")


if __name__ == "__main__":
    main()
