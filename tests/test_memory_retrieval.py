import os
import sys
import time
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from memory_retrieval import DEFAULT_WEIGHTS, normalized_weights, score_candidate


class MemoryRetrievalTests(unittest.TestCase):
    def test_default_weights_match_product_model(self):
        self.assertEqual(
            DEFAULT_WEIGHTS,
            {"semantic": 0.55, "emotion": 0.20, "salience": 0.15, "recency": 0.10},
        )

    def test_weighted_score_exposes_inspectable_signals(self):
        now = time.time()
        result = score_candidate(
            semantic=0.8,
            emotion=0.5,
            importance=80,
            timestamp=now,
            now=now,
        )
        self.assertAlmostEqual(result["score"], 0.76, places=6)
        self.assertAlmostEqual(result["signals"]["salience"], 0.8)
        self.assertAlmostEqual(sum(result["weights"].values()), 1.0)

    def test_invalid_custom_weights_fall_back_safely(self):
        self.assertEqual(normalized_weights({}), DEFAULT_WEIGHTS)


if __name__ == "__main__":
    unittest.main()
