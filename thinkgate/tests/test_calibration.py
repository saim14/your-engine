import unittest

from thinkgate.calibration import add_model_predictions, calibrate_and_evaluate, fit_gain_model, split_dataset


def make_trace(i: int):
    base = 0.2 + (i % 3) * 0.05
    return {
        "task_id": f"task-{i}",
        "model": "example/model",
        "prompt_hash": f"hash-{i}",
        "initial_quality": base,
        "steps": [
            {"step_index": 1, "quality": min(base + 0.28, 1.0), "cost": 0.05},
            {"step_index": 2, "quality": min(base + 0.34, 1.0), "cost": 0.08},
            {"step_index": 3, "quality": min(base + 0.35, 1.0), "cost": 0.12},
        ],
    }


class CalibrationTests(unittest.TestCase):
    def test_split_keeps_tasks_disjoint(self):
        traces = [make_trace(i) for i in range(10)]
        train, tune, evaluation = split_dataset(traces)
        sets = [set(t["task_id"] for t in s) for s in (train, tune, evaluation)]
        self.assertFalse(sets[0] & sets[1])
        self.assertFalse(sets[0] & sets[2])
        self.assertFalse(sets[1] & sets[2])
        self.assertEqual(sum(map(len, sets)), 10)

    def test_fit_adds_predictions(self):
        traces = [make_trace(i) for i in range(6)]
        model = fit_gain_model(traces)
        predicted = add_model_predictions(make_trace(99), model)
        self.assertIn("predicted_gain", predicted["steps"][0])

    def test_calibrated_eval_uses_untouched_eval_split(self):
        report = calibrate_and_evaluate([make_trace(i) for i in range(12)])
        self.assertEqual(report["experiment_type"], "CALIBRATED_REAL_TRACE")
        self.assertEqual(report["split"]["train"] + report["split"]["tune"] + report["split"]["eval"], 12)
        self.assertIn(report["selected_margin"], {-0.05, -0.02, 0.0, 0.01, 0.02, 0.05, 0.10})
        self.assertEqual(report["estimator"]["type"], "ridge_linear_v1")


if __name__ == "__main__":
    unittest.main()
