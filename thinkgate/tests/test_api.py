import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from thinkgate.production import PilotGateway


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_evaluate(self):
        response = self.client.post(
            "/api/evaluate",
            json={
                "traces": [
                    {
                        "id": "a",
                        "initial_quality": 0.4,
                        "steps": [
                            {"quality": 0.7, "cost": 0.05, "predicted_gain": 0.3},
                            {"quality": 0.71, "cost": 0.2, "predicted_gain": 0.01},
                            {"quality": 0.72, "cost": 0.2, "predicted_gain": 0.01}
                        ]
                    },
                    {
                        "id": "b",
                        "initial_quality": 0.5,
                        "steps": [
                            {"quality": 0.8, "cost": 0.05, "predicted_gain": 0.25},
                            {"quality": 0.81, "cost": 0.2, "predicted_gain": 0.01},
                            {"quality": 0.82, "cost": 0.2, "predicted_gain": 0.01}
                        ]
                    }
                ],
                "margin": 0
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"SUCCESS", "FAILED"})


    def test_evaluate_real(self):
        response = self.client.post(
            "/api/evaluate-real",
            json={
                "traces": [
                    {
                        "task_id": "real-1",
                        "model": "example/model",
                        "prompt_hash": "abc123",
                        "initial_quality": 0.2,
                        "steps": [
                            {
                                "step_index": 1,
                                "quality": 0.7,
                                "cost": 0.05,
                                "predicted_gain": 0.3,
                                "latency_ms": 100,
                                "input_tokens": 10,
                                "output_tokens": 20,
                            },
                            {
                                "step_index": 2,
                                "quality": 0.71,
                                "cost": 0.2,
                                "predicted_gain": 0.01,
                                "latency_ms": 100,
                                "input_tokens": 10,
                                "output_tokens": 20,
                            },
                        ],
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["experiment_type"], "REAL_TRACE")


    def test_calibrate_evaluate(self):
        traces = []
        for i in range(6):
            base = 0.2 + i * 0.02
            traces.append({
                "task_id": f"cal-{i}",
                "model": "example/model",
                "prompt_hash": f"hash-{i}",
                "initial_quality": base,
                "steps": [
                    {"step_index": 1, "quality": base + 0.28, "cost": 0.05},
                    {"step_index": 2, "quality": base + 0.34, "cost": 0.08},
                    {"step_index": 3, "quality": base + 0.35, "cost": 0.12},
                ],
            })
        response = self.client.post("/api/calibrate-evaluate", json={"traces": traces})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["experiment_type"], "CALIBRATED_REAL_TRACE")
        self.assertEqual(sum(response.json()["split"][k] for k in ("train", "tune", "eval")), 6)


    def test_collection_protocol(self):
        response = self.client.get("/api/collection-protocol")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["protocol"], "pilot-numeric-v1")
        self.assertEqual(data["benchmark_tasks"], 30)


    def test_production_decision_sandbox(self):
        response = self.client.post(
            "/api/v1/decision",
            json={
                "predicted_gain": 0.01,
                "next_step_cost": 0.10,
                "margin": 0.0,
                "current_quality": 0.8,
                "step_index": 1,
                "max_steps": 4,
                "trace_id": "api-test-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["api_version"], "v1")
        self.assertEqual(data["decision"], "STOP")
        self.assertEqual(data["trace_id"], "api-test-1")

    def test_production_usage_sandbox(self):
        self.client.post(
            "/api/v1/decision",
            json={
                "predicted_gain": 0.20,
                "next_step_cost": 0.05,
                "step_index": 1,
                "max_steps": 4,
            },
        )
        response = self.client.get("/api/v1/usage")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["api_version"], "v1")
        self.assertGreaterEqual(data["requests"], 1)
        self.assertEqual(data["persistence"], "in_memory_pilot_only")

    def test_pilot_provisioning_and_billing_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "billing.db")
            env = {
                "THINKGATE_USAGE_DB_PATH": db_path,
                "THINKGATE_ADMIN_KEY": "admin-test-secret",
                "THINKGATE_PRICE_PER_1000_DECISIONS": "10",
            }
            with patch.dict(os.environ, env, clear=False):
                provision = self.client.post(
                    "/api/v1/admin/customers",
                    headers={"X-ThinkGate-Admin-Key": "admin-test-secret"},
                    json={"customer_id": "pilot-billing"},
                )
                self.assertEqual(provision.status_code, 200)
                api_key = provision.json()["api_key"]
                self.assertTrue(api_key.startswith("tg_"))

                decision = self.client.post(
                    "/api/v1/decision",
                    headers={"X-ThinkGate-Key": api_key},
                    json={
                        "predicted_gain": 0.01,
                        "next_step_cost": 0.10,
                        "step_index": 1,
                        "max_steps": 4,
                    },
                )
                self.assertEqual(decision.status_code, 200)
                self.assertEqual(decision.json()["customer_mode"], "pilot")

                now = int(__import__("time").time())
                billing = self.client.get(
                    "/api/v1/billing-summary",
                    headers={"X-ThinkGate-Key": api_key},
                    params={"start_ts": now - 60, "end_ts": now + 60},
                )
                self.assertEqual(billing.status_code, 200)
                data = billing.json()
                self.assertEqual(data["customer_id"], "pilot-billing")
                self.assertEqual(data["billable_decisions"], 1)
                self.assertEqual(data["stop"], 1)
                self.assertEqual(data["metering_source"], "sqlite_usage_events")
                self.assertEqual(data["estimated_charge_usd"], 0.01)

    def test_persistent_usage_survives_gateway_recreation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "usage.db")
            with patch.dict(os.environ, {"THINKGATE_USAGE_DB_PATH": db_path}, clear=False):
                first = PilotGateway()
                first.make_decision(
                    customer_id="pilot-a",
                    predicted_gain=0.01,
                    next_step_cost=0.10,
                    margin=0.0,
                    step_index=1,
                    max_steps=4,
                )
                second = PilotGateway()
                usage = second.usage("pilot-a")

        self.assertEqual(usage["requests"], 1)
        self.assertEqual(usage["stop"], 1)
        self.assertEqual(usage["persistence"], "sqlite_persistent")
        self.assertGreater(usage["estimated_avoided_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
