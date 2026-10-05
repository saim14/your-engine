import unittest

from thinkgate.controller import decide
from thinkgate.evaluation import evaluate_experiment


class ControllerTests(unittest.TestCase):
    def test_continue_when_gain_exceeds_cost(self):
        self.assertEqual(decide(0.20, 0.05), "CONTINUE")

    def test_stop_when_gain_does_not_exceed_cost(self):
        self.assertEqual(decide(0.04, 0.05), "STOP")

    def test_reject_negative_cost(self):
        with self.assertRaises(ValueError):
            decide(0.10, -0.01)


class EvaluationTests(unittest.TestCase):
    def test_success_when_adaptive_policy_clearly_wins(self):
        traces = [
            {
                "id": "a",
                "initial_quality": 0.40,
                "steps": [
                    {"quality": 0.70, "cost": 0.05, "predicted_gain": 0.30},
                    {"quality": 0.71, "cost": 0.20, "predicted_gain": 0.01},
                    {"quality": 0.72, "cost": 0.20, "predicted_gain": 0.01},
                ],
            },
            {
                "id": "b",
                "initial_quality": 0.50,
                "steps": [
                    {"quality": 0.80, "cost": 0.05, "predicted_gain": 0.25},
                    {"quality": 0.81, "cost": 0.20, "predicted_gain": 0.01},
                    {"quality": 0.82, "cost": 0.20, "predicted_gain": 0.01},
                ],
            },
        ]
        report = evaluate_experiment(traces)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertTrue(all(report["gates"].values()))

    def test_failed_when_controller_has_no_advantage(self):
        traces = [
            {
                "id": "flat",
                "initial_quality": 0.40,
                "steps": [
                    {"quality": 0.50, "cost": 0.02, "predicted_gain": 0.10},
                    {"quality": 0.60, "cost": 0.02, "predicted_gain": 0.10},
                ],
            }
        ]
        report = evaluate_experiment(traces)
        self.assertEqual(report["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
