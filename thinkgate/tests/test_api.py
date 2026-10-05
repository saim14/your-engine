import unittest

from fastapi.testclient import TestClient

from api import app


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


if __name__ == "__main__":
    unittest.main()
