from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

FINAL_NUMBER = re.compile(r"FINAL\s*:\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass(frozen=True)
class CollectionConfig:
    base_url: str
    api_key: str
    model: str
    max_steps: int = 4
    timeout_seconds: float = 90.0
    token_budget_per_step: int = 1000

    @property
    def total_token_budget(self) -> int:
        return self.max_steps * self.token_budget_per_step


def prompt_hash(prompt: str) -> str:
    return sha256(prompt.encode("utf-8")).hexdigest()


def extract_final_number(text: str) -> float | None:
    matches = FINAL_NUMBER.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def numeric_quality(text: str, expected: float) -> float:
    predicted = extract_final_number(text)
    if predicted is None:
        return 0.0
    error = abs(predicted - expected)
    scale = max(1.0, abs(expected))
    relative_error = error / scale
    if relative_error <= 1e-12:
        return 1.0
    return 1.0 / (1.0 + relative_error)


def normalized_step_cost(total_tokens: int, total_token_budget: int) -> float:
    if total_tokens < 0 or total_token_budget <= 0:
        raise ValueError("token counts and budget must be valid")
    return float(total_tokens) / float(total_token_budget)


def _usage(payload: dict[str, Any]) -> tuple[int, int]:
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return input_tokens, output_tokens


def _answer(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("provider response did not contain choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("provider response did not contain text content")
    return content


def call_model(client: httpx.Client, config: CollectionConfig, messages: list[dict[str, str]]) -> tuple[str, int, int, int]:
    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    started = time.perf_counter()
    response = client.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.model,
            "messages": messages,
            "temperature": 0,
        },
        timeout=config.timeout_seconds,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    response.raise_for_status()
    payload = response.json()
    answer = _answer(payload)
    input_tokens, output_tokens = _usage(payload)
    return answer, input_tokens, output_tokens, latency_ms


def collect_task(client: httpx.Client, config: CollectionConfig, task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task["task_id"])
    prompt = str(task["prompt"])
    expected = float(task["expected"])

    system = (
        "Solve the task carefully. End every response with exactly one line in the form "
        "'FINAL: <number>'. Do not reveal or assume access to the reference answer."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    steps: list[dict[str, Any]] = []
    previous_answer = ""

    for step_index in range(1, config.max_steps + 1):
        if step_index > 1:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Review your previous answer for arithmetic, reasoning, or interpretation errors. "
                        "Improve it if needed. End with FINAL: <number>."
                    ),
                }
            )

        answer, input_tokens, output_tokens, latency_ms = call_model(client, config, messages)
        total_tokens = input_tokens + output_tokens
        steps.append(
            {
                "step_index": step_index,
                "quality": numeric_quality(answer, expected),
                "cost": normalized_step_cost(total_tokens, config.total_token_budget),
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "answer_text": answer,
            }
        )
        messages.append({"role": "assistant", "content": answer})
        previous_answer = answer

    return {
        "task_id": task_id,
        "model": config.model,
        "prompt_hash": prompt_hash(prompt),
        "initial_quality": 0.0,
        "steps": steps,
        "collection": {
            "protocol": "pilot-numeric-v1",
            "temperature": 0,
            "max_steps": config.max_steps,
            "token_budget_per_step": config.token_budget_per_step,
            "quality_scorer": "graded_numeric_v1",
            "cost_scorer": "total_tokens / (max_steps * token_budget_per_step)",
        },
    }


def collect_dataset(tasks: list[dict[str, Any]], config: CollectionConfig) -> list[dict[str, Any]]:
    with httpx.Client() as client:
        return [collect_task(client, config, task) for task in tasks]


def config_from_env() -> CollectionConfig:
    base_url = os.environ.get("THINKGATE_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("THINKGATE_API_KEY", "")
    model = os.environ.get("THINKGATE_MODEL", "")
    max_steps = int(os.environ.get("THINKGATE_MAX_STEPS", "4"))
    if not api_key:
        raise ValueError("THINKGATE_API_KEY is required")
    if not model:
        raise ValueError("THINKGATE_MODEL is required")
    return CollectionConfig(base_url=base_url, api_key=api_key, model=model, max_steps=max_steps)


def load_tasks(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("task file must contain a non-empty JSON array")
    for task in payload:
        if not {"task_id", "prompt", "expected"} <= set(task):
            raise ValueError("each task requires task_id, prompt, expected")
    return payload
