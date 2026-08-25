# Original EMO GYM Godot logic snapshot

This directory preserves the original Godot control and Flask request/response scripts that informed the cleaned public client under `godot/`.

Included source:

- `player.gd` — manual movement, target navigation and autonomous patrol;
- `node R.gd` — interview recording/text request and server-response flow;
- `node.gd` — original dialogue/game-manager experiment;
- `panel.gd`, `reflection.gd`, `reset_ui_panel.gd`, and `restart_button.gd` — UI and reflection lifecycle;
- `player_cafe.gd` and `player_talk_input.gd` — café movement and dialogue input;
- `test.gd`, `test.tscn`, `Main B.gd`, and `TEST2.tscn` — legacy Flask route harnesses;
- `tilesetmap.tres` — original TileSet atlas metadata;
- matching `.gd.uid` files and the original project input actions.

## Safety and scope

The original commented direct-provider API key was removed and replaced with an `OPENAI_API_KEY` environment-variable reference. Never place credentials in GDScript or commit `.env` files.

The large third-party exhibition art/font packs are intentionally not redistributed. `tilesetmap.tres` therefore uses the repository icon as a harmless placeholder texture while retaining the original atlas metadata. The complete runnable, asset-independent implementation is `godot/scenes/MirrorWorld.tscn`.

## Run the legacy HTTP test harness

1. Start the repository bridge with `python -m server.app`.
2. Import `legacy/emo-gym-godot/project.godot` in Godot 4.4 or newer.
3. Run the project. Its safe default scene is `test.tscn`, which posts a sample event to the local compatibility endpoint.

The other scripts are preserved as source references because their original scenes depended on private exhibition assets and hardware adapters.
