import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from build_agent import create_persona
from interview_agent import load_pool
from runtime_config import PROJECT_ROOT, load_settings


class RuntimePathTests(unittest.TestCase):
    def test_documented_root_environment_is_resolved(self):
        self.assertTrue((PROJECT_ROOT / ".env.example").exists())
        settings = load_settings()
        self.assertIn("CHAT_MODEL", settings)
        self.assertIn("EMB_MODEL", settings)

    def test_public_interview_pool_loads_from_examples(self):
        pool = load_pool("mbti_pool.json")
        self.assertIn("GEN", pool)
        self.assertTrue(pool["GEN"])

    def test_persona_builder_creates_only_expected_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            created = create_persona("demo persona", Path(directory))
            self.assertEqual(created.name, "demo-persona")
            self.assertTrue((created / "meta.json").exists())
            self.assertTrue((created / "memory_stream").is_dir())


if __name__ == "__main__":
    unittest.main()
