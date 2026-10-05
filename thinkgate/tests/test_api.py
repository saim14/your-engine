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


if __name__ == "__main__":
    unittest.main()
