import unittest

from thinkgate.collector import extract_final_number, normalized_step_cost, numeric_quality


class CollectorTests(unittest.TestCase):
    def test_extracts_last_final_number(self):
        self.assertEqual(extract_final_number("draft FINAL: 4\nrecheck\nFINAL: 5.5"), 5.5)

    def test_exact_numeric_quality(self):
        self.assertEqual(numeric_quality("FINAL: 42", 42), 1.0)

    def test_graded_numeric_quality(self):
        score = numeric_quality("FINAL: 90", 100)
        self.assertGreater(score, 0.9)
        self.assertLess(score, 1.0)

    def test_missing_final_is_zero(self):
        self.assertEqual(numeric_quality("I think it is forty two", 42), 0.0)

    def test_normalized_cost(self):
        self.assertAlmostEqual(normalized_step_cost(250, 4000), 0.0625)


if __name__ == "__main__":
    unittest.main()
