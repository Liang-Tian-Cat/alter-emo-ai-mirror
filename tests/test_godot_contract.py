import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class GodotContractTests(unittest.TestCase):
    def test_project_has_runnable_main_scene_and_no_embedded_key(self):
        project = (ROOT / "godot" / "project.godot").read_text(encoding="utf-8")
        api = (ROOT / "godot" / "scripts" / "alter_emo_api.gd").read_text(encoding="utf-8")
        self.assertIn('run/main_scene="res://Main.tscn"', project)
        self.assertIn("/v1/sessions", api)
        self.assertNotIn("sk-", api)


if __name__ == "__main__":
    unittest.main()
