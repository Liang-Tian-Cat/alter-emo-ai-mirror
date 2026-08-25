# Godot client

This is a clean Godot 4 client for the public Alter Emo bridge. It includes both the HTTP interview/mirror interface and an embodied 2D world without bundling generated cache files, credentials, recordings, or third-party exhibition assets.

## Run

1. From the repository root, install `requirements.txt` and run `python -m server.app`.
2. Open `godot/project.godot` in Godot 4.4 or newer.
3. Run the project, start a mirror session, answer the interview, then send messages or reflect on an event.
4. Select **Open embodied mirror world** to enter the TileMap/navigation scene.

The client talks to `http://127.0.0.1:5000` by default. Change `base_url` on the `Api` node if the Flask bridge runs elsewhere.

## Embodied world controls

`scenes/MirrorWorld.tscn` is a runnable Godot 4 scene with a real `TileMapLayer`, a generated public-domain-style placeholder TileSet, navigation mesh, collision bounds, destination markers, and a `CharacterBody2D` controller.

| Input | Action |
| --- | --- |
| Arrow keys | Take manual control of the character |
| `1` | Navigate to Sofa |
| `2` | Navigate to Eat |
| `3` | Navigate to Cook |
| `4` | Navigate to Study |
| Destination buttons | Trigger the same navigation actions on touch devices |

When the player is idle, autonomous patrol selects one of the four destinations. The world also calls `/health` through `AlterEmoApi` and displays whether the local Flask bridge is online. Select **Back to AI mirror** to return to the interview/chat interface.

The TileSet texture is generated in `scripts/world_controller.gd`; this keeps the public project runnable without redistributing the original exhibition asset packs. Replace that generated atlas with licensed artwork in a private deployment without changing the movement or navigation logic.

## Godot structure

```text
godot/
├── project.godot
├── Main.tscn                       # HTTP interview and AI mirror UI
├── scenes/
│   └── MirrorWorld.tscn            # TileMap, navigation, collision and world UI
└── scripts/
    ├── alter_emo_api.gd            # Flask JSON request/response client
    ├── main.gd                     # Interview/mirror UI controller
    ├── player_controller.gd        # Manual movement and autonomous navigation
    └── world_controller.gd         # TileMap, targets, bridge status and scene flow
```

## Public scope

Text interview, mirror chat, event reflection, session reset, TileMap movement/navigation, and the original EMO GYM route names are supported. Recording, speech synthesis, and physical printing remain optional deployment adapters; the public bridge reports them as unavailable instead of silently depending on local hardware.
