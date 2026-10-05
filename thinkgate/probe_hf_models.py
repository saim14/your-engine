from __future__ import annotations
import json, os, time
import httpx

MODELS = [
    "Qwen/Qwen3-4B-Instruct-2507:nscale",
    "google/gemma-3-4b-it:deepinfra",
    "openai/gpt-oss-20b:deepinfra",
]
PROMPT = "Solve carefully and end with exactly FINAL: <number>. A warehouse starts with 480 units. It ships 37.5% of them, then receives 96 new units. How many units are now in the warehouse?"

base = os.environ.get("THINKGATE_BASE_URL", "https://router.huggingface.co/v1").rstrip("/")
key = os.environ["THINKGATE_API_KEY"]

for model in MODELS:
    started = time.perf_counter()
    try:
        r = httpx.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages":[{"role":"user","content":PROMPT}], "temperature":0},
            timeout=90.0,
        )
        latency = int((time.perf_counter()-started)*1000)
        payload = r.json()
        if r.is_success:
            msg = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage", {})
            print("THINKGATE_HF_PROBE " + json.dumps({
                "model": model,
                "status": r.status_code,
                "latency_ms": latency,
                "answer_tail": msg[-120:],
                "usage": usage,
            }, ensure_ascii=False))
        else:
            print("THINKGATE_HF_PROBE " + json.dumps({
                "model": model, "status": r.status_code, "latency_ms": latency,
                "error": str(payload)[:300]
            }))
    except Exception as exc:
        print("THINKGATE_HF_PROBE " + json.dumps({"model":model,"error":repr(exc)}))
