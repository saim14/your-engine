import unittest

from thinkgate.real_traces import prompt_hash, to_evaluator_trace, validate_real_trace


class RealTraceTests(unittest.TestCase):
    def sample(self):
        return {
            "task_id": "task-1",
            "model": "example-model",
            "prompt_hash": prompt_hash("What is 2+2?"),
            "initial_quality": 0.2,
            "steps": [
                {
                    "step_index": 1,
                    "quality": 0.8,
                    "cost": 0.1,
                    "predicted_gain": 0.7,
                    "latency_ms": 100,
                    "input_tokens": 10,
                    "output_tokens": 20,
                },
                {
                    "step_index": 2,
                    "quality": 0.81,
                    "cost": 0.1,
                    "predicted_gain": 0.01,
                    "latency_ms": 90,
                    "input_tokens": 15,
                    "output_tokens": 12,
                },
            ],
        }

    def test_valid_real_trace(self):
        validate_real_trace(self.sample())

    def test_rejects_missing_predicted_gain(self):
        trace = self.sample()
        del trace["steps"][0]["predicted_gain"]
        with self.assertRaises(ValueError):
            validate_real_trace(trace)

    def test_conversion_drops_metadata_but_keeps_online_fields(self):
        converted = to_evaluator_trace(self.sample())
        self.assertEqual(converted["id"], "task-1")
        self.assertEqual(len(converted["steps"]), 2)
        self.assertNotIn("latency_ms", converted["steps"][0])


if __name__ == "__main__":
    unittest.main()
