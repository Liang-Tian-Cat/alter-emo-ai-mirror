import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_io import save_memory_node_dual
from salience import WEIGHTS, evaluate_salience


class SalienceGateTests(unittest.TestCase):
    def test_product_formula_and_components_are_inspectable(self):
        decision = evaluate_salience(
            "我决定以后拒绝违背我边界的安排，因为这对我很重要。",
            emotion_tag={"emotion": "anger", "intensity": 0.9},
            importance=90,
        )
        self.assertEqual(WEIGHTS, {
            "emotion": 0.30, "identity": 0.25, "recurrence": 0.20,
            "decision": 0.15, "novelty": 0.10,
        })
        self.assertTrue(decision.store)
        self.assertAlmostEqual(
            decision.score,
            sum(decision.components[key] * WEIGHTS[key] for key in WEIGHTS),
            places=5,
        )

    def test_low_salience_turn_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            node = save_memory_node_dual(
                directory, "ok", "ok", "chat", importance=1,
                emotion_tag={"emotion": "neutral"}, evt_vec=[1.0], emo_vec=[1.0],
            )
            self.assertFalse(node["persisted"])
            self.assertFalse((Path(directory) / "memory_stream" / "nodes.ndjson").exists())


if __name__ == "__main__":
    unittest.main()
