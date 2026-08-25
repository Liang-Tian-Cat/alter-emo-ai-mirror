import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class GodotContractTests(unittest.TestCase):
    def test_project_has_runnable_main_scene_and_no_embedded_key(self):
        project = (ROOT / "godot" / "project.godot").read_text(encoding="utf-8")
        api = (ROOT / "godot" / "scripts" / "alter_emo_api.gd").read_text(encoding="utf-8")
        self.assertIn('run/main_scene="res://Main.tscn"', project)
        self.assertIn("/v1/sessions", api)
        scripts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "godot" / "scripts").glob("*.gd")
        )
        self.assertNotIn("sk-", scripts)

    def test_embodied_world_has_tilemap_navigation_and_bridge(self):
        scene = (ROOT / "godot" / "scenes" / "MirrorWorld.tscn").read_text(encoding="utf-8")
        world = (ROOT / "godot" / "scripts" / "world_controller.gd").read_text(encoding="utf-8")
        player = (ROOT / "godot" / "scripts" / "player_controller.gd").read_text(encoding="utf-8")
        main_scene = (ROOT / "godot" / "Main.tscn").read_text(encoding="utf-8")
        main_script = (ROOT / "godot" / "scripts" / "main.gd").read_text(encoding="utf-8")

        self.assertIn('type="TileMapLayer"', scene)
        self.assertIn('type="NavigationRegion2D"', scene)
        self.assertIn('type="NavigationAgent2D"', scene)
        self.assertIn('path="res://scripts/alter_emo_api.gd"', scene)
        self.assertIn("TileSetAtlasSource.new()", world)
        self.assertIn("api.check_health()", world)
        self.assertIn('Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")', player)
        self.assertIn("autonomous_patrol", player)
        self.assertIn('name="World"', main_scene)
        self.assertIn('res://scenes/MirrorWorld.tscn', main_script)


if __name__ == "__main__":
    unittest.main()
