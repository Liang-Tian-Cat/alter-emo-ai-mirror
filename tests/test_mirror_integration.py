import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mirror_agent


class MirrorIntegrationTests(unittest.TestCase):
    def setUp(self):
        mirror_agent.memory_cache.clear()

    def tearDown(self):
        mirror_agent.memory_cache.clear()

    def test_visitor_reply_runs_full_policy_loop_without_polluting_persona_memory(self):
        memory = {
            "id": "memory-1",
            "summary": "The person tends to pause before making a difficult choice.",
            "content": "I usually step back and think before deciding.",
            "importance": 90,
            "ts": time.time(),
            "evt_vec": [1.0, 0.0],
            "emo_vec": [1.0, 0.0],
            "emotion_tag": {"emotion": "neutral", "tone": ["reflective"]},
            "source": {},
        }

        def fake_chat(prompt, **_kwargs):
            if prompt.startswith("Plan one grounded mirror response"):
                return json.dumps({
                    "reflection": "A familiar pause is present before choosing.",
                    "action": "mirror",
                    "confidence": 0.8,
                    "grounding_ids": ["memory-1"],
                })
            return "我通常会先停一下，想清楚再决定。"

        with tempfile.TemporaryDirectory() as directory:
            agent_dir = Path(directory) / "demo"
            agent_dir.mkdir()

            with (
                patch.object(mirror_agent, "build_corpus", return_value=[memory]),
                patch.object(mirror_agent, "get_embedding", return_value=[1.0, 0.0]),
                patch.object(
                    mirror_agent,
                    "extract_emotion_tag",
                    return_value={"emotion": "neutral", "tone": ["reflective"]},
                ),
                patch.object(mirror_agent, "call_gpt", side_effect=fake_chat),
            ):
                reply = mirror_agent.mirror_reply(
                    "demo",
                    str(agent_dir),
                    "遇到选择时你会怎么做？",
                    "visitor",
                    "session-1",
                    win_ctx=2,
                )

            self.assertEqual(reply, "我通常会先停一下，想清楚再决定。")
            self.assertFalse((agent_dir / "memory_stream" / "nodes.ndjson").exists())

            session_dir = agent_dir / "mirror_sessions" / "visitor" / "session-1"
            conversation = json.loads((session_dir / "conversation.json").read_text(encoding="utf-8"))
            log = json.loads((session_dir / "retrieval_log.jsonl").read_text(encoding="utf-8"))
            self.assertEqual([turn["role"] for turn in conversation], ["user", "mirror"])
            self.assertEqual(log["response_plan"]["action"], "mirror")
            self.assertEqual(log["response_plan"]["grounding_ids"], ["memory-1"])
            self.assertEqual(log["retrieval_weights"], mirror_agent.RETRIEVAL_WEIGHTS)


if __name__ == "__main__":
    unittest.main()
