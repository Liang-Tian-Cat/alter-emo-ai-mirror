import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class LegacyGodotSourceTests(unittest.TestCase):
    def test_legacy_emo_gym_logic_snapshot_is_present_and_sanitized(self):
        legacy = ROOT / "legacy" / "emo-gym-godot"
        expected = {
            "node R.gd",
            "node.gd",
            "panel.gd",
            "player.gd",
            "player_cafe.gd",
            "player_talk_input.gd",
            "reflection.gd",
            "reset_ui_panel.gd",
            "restart_button.gd",
            "test.gd",
            "test.tscn",
            "TEST2.tscn",
            "tilesetmap.tres",
            "project.godot",
        }

        self.assertTrue(expected.issubset({path.name for path in legacy.iterdir()}))
        self.assertIn('run/main_scene="res://test.tscn"', (legacy / "project.godot").read_text(encoding="utf-8"))
        self.assertIn("OPENAI_API_KEY", (legacy / "node.gd").read_text(encoding="utf-8"))
        scripts = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.gd"))
        self.assertNotIn("sk-", scripts)


if __name__ == "__main__":
    unittest.main()
