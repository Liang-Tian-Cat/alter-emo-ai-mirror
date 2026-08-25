import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from response_policy import fallback_response_plan, normalize_response_plan


class ResponsePolicyTests(unittest.TestCase):
    def test_missing_context_asks_instead_of_inventing(self):
        plan = fallback_response_plan("Tell me why I do this", has_context=False)
        self.assertEqual(plan["action"], "question")

    def test_model_action_is_constrained(self):
        plan = normalize_response_plan(
            {"action": "diagnose", "grounding_ids": ["private", "memory-1"]},
            user_text="我为什么总是这样？",
            retrieved_ids=["memory-1"],
        )
        self.assertEqual(plan["action"], "reframe")
        self.assertEqual(plan["grounding_ids"], ["memory-1"])

    def test_grounding_cannot_escape_retrieved_set(self):
        plan = normalize_response_plan(
            {"action": "mirror", "grounding_ids": ["not-retrieved"]},
            user_text="今天有点累。",
            retrieved_ids=["memory-2"],
        )
        self.assertEqual(plan["grounding_ids"], ["memory-2"])


if __name__ == "__main__":
    unittest.main()
