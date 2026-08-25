# Alter Emo AI Mirror

Alter Emo is a local Flask + Python prototype for building a conversational "AI mirror" from an adaptive interview and a persistent narrative-memory store.

This repository contains the runnable public implementation: an HTTP bridge, interview ingestion, memory retrieval, response planning, mirror chat, event reflection, and offline tests. Private memories, recordings, credentials, generated caches, and third-party exhibition assets are not included.

## Current status

Verified on Windows with Python 3.10:

- clean virtual-environment installation from `requirements.txt`;
- all 27 locked Python packages installed and `pip check` passed;
- 16 offline tests passed;
- Flask started locally and returned HTTP 200 from `/health`;
- Flask started locally and returned the expected session and health responses.

Live GPT generation requires a valid `OPENAI_API_KEY`. The repository can be installed and tested without a key, but interview ingestion, mirror replies, embeddings, and event reflection call the OpenAI API.

## Architecture

```text
CLI or HTTP client
    │ JSON
    ▼
Flask bridge (server/)
    ├── session and interview state
    ├── legacy EMO GYM compatibility routes
    └── AlterEmoCoreAdapter
            │
            ▼
Python agent core (src/)
    ├── interview extraction
    ├── structured memory + narrative windows
    ├── semantic/emotional/salience/recency retrieval
    ├── reflection and response policy
    └── mirror response generation
```

The default retrieval score uses four inspectable signals:

| Signal | Weight |
| --- | ---: |
| Semantic similarity | 0.55 |
| Emotional similarity | 0.20 |
| Salience | 0.15 |
| Recency | 0.10 |

## Repository layout

```text
alter-emo-ai-mirror/
├── legacy/emo-gym-godot/   # Sanitized original EMO GYM source snapshot (reference only)
├── server/                 # Flask application and core adapter
│   ├── app.py
│   ├── bridge.py
│   └── core_adapter.py
├── src/                    # Interview, memory, retrieval, and mirror core
├── examples/               # Public interview and prompt pools
├── tests/                  # Offline unit and integration tests
├── .env.example            # Environment-variable template
└── requirements.txt        # Complete locked Python dependency set
```

The following runtime directories are generated locally and ignored by Git:

- `agents/` — persona metadata, interview sessions, memories, and embeddings;
- `runtime/bridge_sessions/` — Flask bridge session snapshots;
- `.godot/` — Godot import/editor cache;
- `.venv/` — Python virtual environment.

## Requirements

- Windows, macOS, or Linux;
- Python 3.10 (the committed lock file was verified with Python 3.10);
- a valid OpenAI API key for live AI operations.

`requirements.txt` explicitly pins both direct and transitive Python packages.

## Installation

Clone the repository and enter it:

```bash
git clone https://github.com/Liang-Tian-Cat/alter-emo-ai-mirror.git
cd alter-emo-ai-mirror
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Verify the installed dependency graph:

```bash
python -m pip check
```

## Configuration

Create a private `.env` file from the template.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_PROJECT=
CHAT_MODEL=gpt-4o-mini
EMB_MODEL=text-embedding-3-small
ALTER_EMO_HOST=127.0.0.1
ALTER_EMO_PORT=5000
ALTER_EMO_PERSONA_ID=demo-persona
```

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | For live AI calls | none | OpenAI authentication |
| `OPENAI_PROJECT` | No | empty | Optional OpenAI project ID |
| `CHAT_MODEL` | No | `gpt-4o-mini` | Interview and response model |
| `EMB_MODEL` | No | `text-embedding-3-small` | Memory embedding model |
| `ALTER_EMO_HOST` | No | `127.0.0.1` | Flask bind address |
| `ALTER_EMO_PORT` | No | `5000` | Flask port |
| `ALTER_EMO_PERSONA_ID` | No | `demo-persona` | Persona used by legacy routes |

Never commit `.env` or paste a real API key into Python, GDScript, screenshots, or Git history.

## Run the HTTP bridge

From the repository root, with the virtual environment active:

```bash
python -m server.app
```

Expected output includes:

```text
Running on http://127.0.0.1:5000
```

Check the bridge in another terminal.

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

macOS/Linux:

```bash
curl http://127.0.0.1:5000/health
```

Expected response:

```json
{
  "ok": true,
  "service": "alter-emo-godot-bridge",
  "capabilities": {
    "text": true,
    "events": true,
    "audio": false,
    "printing": false
  }
}
```

## Command-line usage

The Python core can run without the HTTP bridge.

Check API credentials and network access:

```bash
python src/mirror_agent.py --check
```

Create a persona workspace:

```bash
python src/build_agent.py --id demo-persona
```

Run the adaptive interview:

```bash
python src/interview_agent.py
```

List existing personas:

```bash
python src/mirror_agent.py --list
```

Start mirror chat:

```bash
python src/mirror_agent.py --id demo-persona --interlocutor self
```

Use `--interlocutor self` when the persona owner is speaking. Other interlocutor names are treated as visitor sessions and are prevented from writing visitor claims into the owner's main memory stream.

## HTTP API

### Current API

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Service status and capability flags |
| `POST` | `/v1/sessions` | Create an interview session |
| `GET` | `/v1/sessions/<session_id>` | Read session state/current question |
| `POST` | `/v1/sessions/<session_id>/messages` | Submit an interview answer or mirror message |
| `POST` | `/v1/sessions/<session_id>/events` | Generate a structured event reflection |
| `DELETE` | `/v1/sessions/<session_id>` | Delete the bridge session |

Create a session:

```bash
curl -X POST http://127.0.0.1:5000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"demo-persona","interlocutor":"self"}'
```

Submit an answer or message:

```bash
curl -X POST http://127.0.0.1:5000/v1/sessions/SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"I usually pause before making a difficult decision."}'
```

Reflect on an event after the interview is complete:

```bash
curl -X POST http://127.0.0.1:5000/v1/sessions/SESSION_ID/events \
  -H "Content-Type: application/json" \
  -d '{"event":"I avoided speaking during a difficult meeting."}'
```

### Original EMO GYM compatibility API

The bridge preserves the original GDScript route names for incremental migration:

| Method | Endpoint | Status |
| --- | --- | --- |
| `GET` | `/next_question` | Supported |
| `POST` | `/text_input` | Supported |
| `POST` | `/simulate_event` | Supported |
| `POST` | `/reset_interview` | Supported |
| `GET/POST` | `/start_recording` | Returns 501 |
| `GET/POST` | `/stop_recording` | Returns 501 |
| `POST` | `/tts_speak` | Returns 501 |
| `POST` | `/simulate_and_print` | Returns 501 |

Audio recording, speech synthesis, and physical printing are hardware-specific optional adapters and are not enabled in this public build.

## Testing

Run all offline tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

The suite covers:

- retrieval weights and score components;
- grounded response-policy constraints;
- visitor/persona/session memory isolation;
- runtime paths and persona creation;
- modern Flask API workflow;
- original EMO GYM compatibility routes;
- failed-ingestion retry behavior;
- sanitized legacy source-snapshot and embedded-key checks.

Tests use a fake core adapter for HTTP workflow tests, so the test suite does not spend API credits and does not require an OpenAI key.

## Data and persistence

Persona data is stored as local JSON/NDJSON files under `agents/<persona_id>/`:

- `meta.json` — persona identity, style, model metadata, and provenance;
- `memory_stream/nodes.ndjson` — structured memory nodes;
- `memory_stream/embeddings_event.ndjson` — semantic/event vectors;
- `memory_stream/embeddings_emotion.ndjson` — emotion vectors;
- `sessions/` — interview conversations and reflections;
- `mirror_sessions/` — mirror dialogue and retrieval logs.

Bridge state is stored under `runtime/bridge_sessions/`. Deleting a session through the API removes its bridge snapshot; it does not automatically erase the persona's long-term memory directory.

## Troubleshooting

### `401` or `invalid_api_key`

Replace `OPENAI_API_KEY` in `.env` with a currently valid key, then restart Flask. Do not reuse or commit an exposed key.

### Flask returns `502`

The bridge uses `502` for upstream model/configuration failures. Read the Flask terminal output, verify the API key and selected model names, then retry. A failed final interview ingestion rolls the answer back so the last answer can be submitted again safely.

### PowerShell blocks virtual-environment activation

Either allow the local activation script for the current process or call the virtual-environment interpreter directly:

```powershell
.venv\Scripts\python.exe -m server.app
```

### No audio/TTS/printing

This is expected in the public version. The health response reports `audio: false` and `printing: false`; the related compatibility routes return HTTP 501.

## Production limitations

This is a research prototype, not a production service:

- Flask's built-in development server is used;
- sessions and memories are local files rather than a transactional database;
- there is no authentication, authorization, encryption-at-rest, rate limiting, or multi-process coordination;
- the API should remain bound to `127.0.0.1` unless production security is added;
- model calls can incur cost and transmit submitted text to the configured provider.

Do not expose this server directly to the public internet without adding a production WSGI server, authentication, request validation, encrypted storage, retention controls, audit logging, and deployment-specific privacy review.

## License

MIT. See `LICENSE`.

## Author

Liang Tian — [liang-tian.com](https://liang-tian.com)
