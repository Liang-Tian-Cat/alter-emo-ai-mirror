# Godot client

This is a clean Godot 4 client for the public Alter Emo bridge. It demonstrates the real request/response loop without bundling generated cache files, credentials, recordings, or third-party exhibition assets.

## Run

1. From the repository root, install `requirements.txt` and run `python -m server.app`.
2. Open `godot/project.godot` in Godot 4.4 or newer.
3. Run the project, start a mirror session, answer the interview, then send messages or reflect on an event.

The client talks to `http://127.0.0.1:5000` by default. Change `base_url` on the `Api` node if the Flask bridge runs elsewhere.

## Public scope

Text interview, mirror chat, event reflection, session reset, and the original EMO GYM route names are supported. Recording, speech synthesis, and physical printing remain optional deployment adapters; the public bridge reports them as unavailable instead of silently depending on local hardware.
