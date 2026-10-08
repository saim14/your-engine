from __future__ import annotations

import json
import os
import threading
import time

import httpx


def _run() -> None:
    time.sleep(2.0)
    port = os.environ.get("PORT", "8000")
    base_url = f"http://127.0.0.1:{port}"
    admin_key = os.environ.get("THINKGATE_ADMIN_KEY", "").strip()
    customer_id = f"smoke-{int(time.time())}"
    result: dict[str, object] = {
        "customer_id": customer_id,
        "success": False,
    }

    try:
        if not admin_key:
            raise RuntimeError("THINKGATE_ADMIN_KEY is not configured")

        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            unauth = client.post(
                "/api/v1/decision",
                json={
                    "predicted_gain": 0.01,
                    "next_step_cost": 0.10,
                    "step_index": 1,
                    "max_steps": 4,
                },
            )
            result["unauthenticated_status"] = unauth.status_code

            provision = client.post(
                "/api/v1/admin/customers",
                headers={"X-ThinkGate-Admin-Key": admin_key},
                json={"customer_id": customer_id},
            )
            result["provision_status"] = provision.status_code
            provision.raise_for_status()
            api_key = provision.json()["api_key"]

            customer_headers = {"X-ThinkGate-Key": api_key}
            decision = client.post(
                "/api/v1/decision",
                headers=customer_headers,
                json={
                    "predicted_gain": 0.01,
                    "next_step_cost": 0.10,
                    "margin": 0.0,
                    "current_quality": 0.8,
                    "step_index": 1,
                    "max_steps": 4,
                    "trace_id": "production-auth-smoke",
                },
            )
            result["decision_status"] = decision.status_code
            decision.raise_for_status()
            result["decision"] = decision.json().get("decision")

            usage = client.get("/api/v1/usage", headers=customer_headers)
            result["usage_status"] = usage.status_code
            usage.raise_for_status()
            result["usage_requests"] = usage.json().get("requests")

            now = int(time.time())
            billing = client.get(
                "/api/v1/billing-summary",
                headers=customer_headers,
                params={"start_ts": now - 60, "end_ts": now + 60},
            )
            result["billing_status"] = billing.status_code
            billing.raise_for_status()
            result["billable_decisions"] = billing.json().get("billable_decisions")

            revoke = client.delete(
                f"/api/v1/admin/customers/{customer_id}",
                headers={"X-ThinkGate-Admin-Key": admin_key},
            )
            result["revoke_status"] = revoke.status_code
            revoke.raise_for_status()

            revoked = client.post(
                "/api/v1/decision",
                headers=customer_headers,
                json={
                    "predicted_gain": 0.01,
                    "next_step_cost": 0.10,
                    "step_index": 1,
                    "max_steps": 4,
                },
            )
            result["revoked_key_status"] = revoked.status_code

            result["success"] = (
                unauth.status_code == 401
                and provision.status_code == 200
                and decision.status_code == 200
                and usage.status_code == 200
                and int(usage.json().get("requests", 0)) >= 1
                and billing.status_code == 200
                and int(billing.json().get("billable_decisions", 0)) >= 1
                and revoke.status_code == 200
                and revoked.status_code == 401
            )
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:300]

    print(
        "THINKGATE_AUTH_SMOKE_RESULT "
        + json.dumps(result, sort_keys=True, separators=(",", ":")),
        flush=True,
    )


def start_auth_smoke_background() -> None:
    threading.Thread(target=_run, daemon=True, name="thinkgate-auth-smoke").start()
