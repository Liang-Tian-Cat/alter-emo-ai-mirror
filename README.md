# Alter Emo AI Mirror

A local AI mirror built with Godot 4, Flask, and Python. It learns from consented interviews and daily narratives, retrieves relevant memories, and generates grounded reflections in the user's communication style.

## Features

- Adaptive interview and follow-up questions
- Narrative memory with event and emotion embeddings
- Salience-based storage and four-signal retrieval
- Five selectable reflection perspectives
- Voice recording, transcription, and speech playback
- Godot TileMap world and private memory controls

## Requirements

- Python 3.10+
- Godot 4.4+
- OpenAI API key
- Microphone for voice input

## Setup

```bash
git clone https://github.com/Liang-Tian-Cat/alter-emo-ai-mirror.git
cd alter-emo-ai-mirror
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS or Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add your API key to `.env`:

```dotenv
OPENAI_API_KEY=your_private_key
```

## Run

Start the local bridge:

```bash
python -m server.app
```

Then open `godot/project.godot` in Godot and press **F5**.

In the application:

1. Enter a persona ID.
2. Select a reflection perspective.
3. Grant consent for local memory.
4. Complete the interview and begin chatting.

The privacy screen can inspect, revise, delete, pause, revoke, or export stored memory.

## Verification

```bash
python -m unittest discover -s verification -p "*_checks.py" -v
```

The verification suite runs without an API key.

## Local data

Generated memories, sessions, recordings, credentials, and Godot cache files are ignored by Git. Model-backed operations send submitted content to the configured model provider.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
