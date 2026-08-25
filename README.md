# Alter Emo AI Mirror

Local-first AI mirror application implemented with Godot 4, Flask, and Python. The system conducts an adaptive interview, builds a consent-controlled narrative memory, retrieves grounded personal context, plans a reflection action, and responds through a selectable perspective.

This document covers installation, execution, data flow, API contracts, and verification. Personal data, generated memories, API credentials, recordings, and Godot cache files are excluded from the repository.

## Implemented system

- Adaptive interviewing with objective-completion scoring and generated follow-up questions.
- Structured daily narratives containing events, feelings, choices, values, and recurring patterns.
- Separate semantic-event and emotional embeddings.
- Five-factor long-term-memory gate:

  ```text
  S = 0.30E + 0.25I + 0.20R + 0.15D + 0.10N
  ```

  `E` is emotional intensity, `I` identity relevance, `R` recurrence, `D` decision relevance, and `N` novelty. The default persistence threshold is `0.42`; rejected turns remain in the current session but are not written to long-term memory.

- Four-signal retrieval: semantic similarity 55%, emotional similarity 20%, stored salience 15%, and recency 10%.
- Narrative context-window restoration and grounded memory IDs in response plans.
- Memory compression with source-node traceability.
- Measured message length, sentence rhythm, response cadence, and recurring vocabulary, combined with model-assisted value and boundary extraction.
- Constrained reflection policies: question, reflect, reframe, ground, guide, validate, gently challenge, or pause.
- Five selectable perspectives: balanced, efficiency-focused, relationship-focused, clarity-seeking, and tone-sensitive.
- Godot TileMap world, collision, manual movement, target navigation, and autonomous patrol.
- Microphone capture, speech-to-text, and text-to-speech through the local Flask bridge.
- Explicit consent, pause/resume, view, revise, delete, revoke, and ZIP export controls for personal memory.
- Compatibility endpoints and a sanitized source snapshot for the original EMO GYM Godot project.

## Requirements

- Python 3.10 or newer.
- Godot 4.4 or newer.
- A microphone for recording.
- An OpenAI API key for embeddings, adaptive interviews, mirror responses, transcription, and speech synthesis.

Godot is installed separately. Every Python runtime dependency, including microphone capture, is listed in `requirements.txt`.

## Installation

```bash
git clone https://github.com/Liang-Tian-Cat/alter-emo-ai-mirror.git
cd alter-emo-ai-mirror
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
Copy-Item .env.example .env
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
cp .env.example .env
```

Set at least the API key in `.env`:

```dotenv
OPENAI_API_KEY=your_private_key
OPENAI_PROJECT=
CHAT_MODEL=gpt-4o-mini
EMB_MODEL=text-embedding-3-small
ALTER_EMO_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
ALTER_EMO_TTS_MODEL=gpt-4o-mini-tts
ALTER_EMO_HOST=127.0.0.1
ALTER_EMO_PORT=5000
ALTER_EMO_PERSONA_ID=demo-persona
ALTER_EMO_LEGACY_CONSENT=false
```

Do not commit `.env`. The modern Godot client records explicit consent in persona metadata. Set `ALTER_EMO_LEGACY_CONSENT=true` only when intentionally running the original compatibility scene, which has no consent widget.

## Run the application

Start the bridge from the repository root:

```bash
python -m server.app
```

Verify it in another terminal:

```bash
curl http://127.0.0.1:5000/health
```

Then:

1. Open Godot 4.4 or newer and import `godot/project.godot`.
2. Press **F5** to run `Main.tscn`.
3. Enter a persona ID, select a perspective, read the consent label, and opt in.
4. Complete the adaptive interview. A short answer can cause a relevant follow-up before the next base question.
5. Chat with the mirror, reflect on an event, or save a daily narrative.
6. Use **Record** / **Stop & transcribe** for microphone input and **Speak last reply** for playback.
7. Open the privacy screen to inspect, revise, delete, pause, revoke, or export personal memory.
8. Open the embodied world for TileMap navigation. Arrow keys move manually; keys `1`–`4` select destinations; idle mode resumes autonomous patrol.

The client defaults to `http://127.0.0.1:5000`. Change `base_url` on a Godot `Api` node when the bridge uses another address.

## Command-line operation

```bash
python src/mirror_agent.py --check
python src/build_agent.py --id demo-persona
python src/interview_agent.py
python src/mirror_agent.py --id demo-persona --interlocutor self
```

The interview asks for an explicit `YES` before writing memory. Non-`self` interlocutors are isolated visitor sessions and cannot write claims into the owner's long-term memory.

## HTTP API

### Session and reflection

| Method | Endpoint | Function |
| --- | --- | --- |
| `GET` | `/health` | Runtime capability and configuration status |
| `GET` | `/v1/perspectives` | List reflection perspectives |
| `POST` | `/v1/sessions` | Create a consent-aware interview session |
| `GET` | `/v1/sessions/<id>` | Read stage and current question |
| `PUT` | `/v1/sessions/<id>/consent` | Grant or revoke session consent |
| `PUT` | `/v1/sessions/<id>/perspective` | Change active perspective |
| `POST` | `/v1/sessions/<id>/messages` | Submit an answer or mirror message |
| `POST` | `/v1/sessions/<id>/events` | Generate structured event reflection |
| `DELETE` | `/v1/sessions/<id>` | Delete the bridge-session snapshot |

Create a session with explicit consent:

```bash
curl -X POST http://127.0.0.1:5000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"demo-persona","interlocutor":"self","perspective":"clarity","consent":true}'
```

### Narrative, memory, and privacy

| Method | Endpoint | Function |
| --- | --- | --- |
| `POST` | `/v1/personas/<id>/narratives` | Parse and store daily narrative |
| `GET` | `/v1/personas/<id>/narratives` | List structured narratives |
| `POST` | `/v1/personas/<id>/compress` | Compress next eligible memory chunk |
| `GET` | `/v1/personas/<id>/memories` | View memories and salience components |
| `PATCH` | `/v1/personas/<id>/memories/<memory_id>` | Revise memory and refresh semantic vector |
| `DELETE` | `/v1/personas/<id>/memories/<memory_id>` | Delete memory and both vectors |
| `PUT` | `/v1/personas/<id>/memory-state` | Pause or resume future writes |
| `PUT` | `/v1/personas/<id>/consent` | Revoke or update persona consent |
| `GET` | `/v1/personas/<id>/export` | Export complete persona directory as ZIP |
| `DELETE` | `/v1/personas/<id>` | Delete all persona data; confirmation must equal ID |

Full deletion requires an exact body:

```bash
curl -X DELETE http://127.0.0.1:5000/v1/personas/demo-persona \
  -H "Content-Type: application/json" \
  -d '{"confirm":"demo-persona"}'
```

### Audio and compatibility

| Method | Endpoint | Function |
| --- | --- | --- |
| `POST` | `/v1/audio/transcriptions` | Transcribe multipart field `audio` |
| `POST` | `/v1/audio/speech` | Return MP3 speech |
| `GET/POST` | `/start_recording` | Start server-host microphone capture |
| `GET/POST` | `/stop_recording` | Stop, transcribe, and submit voice turn |
| `POST` | `/tts_speak` | Compatibility speech endpoint |
| `POST` | `/simulate_and_print` | Compatibility export endpoint returning ZIP |

The original `/next_question`, `/text_input`, `/simulate_event`, and `/reset_interview` routes remain supported.

## Data and privacy behavior

- New personas default to `consent.status=false`. Personal-memory operations require an explicit grant.
- Revoking consent stops long-term memory immediately. Pause/resume is a temporary control.
- Low-salience turns are not written to nodes or embedding files.
- Every stored node contains E/I/R/D/N components, threshold, weighted score, and persistence decision.
- Revision refreshes the semantic vector. Deletion removes the node and both vector records.
- Visitor conversations are session-scoped and excluded from owner memory.
- Data is local and ignored by Git. Model-backed operations transmit submitted input to the configured provider.
- The bridge binds to loopback by default. Do not expose the development server directly to the internet.

## Verification

Run all offline verification checks without an API key:

```bash
python -m unittest discover -s verification -p "*_checks.py" -v
```

The verification suite covers retrieval weights, the five-factor salience gate, memory controls and ZIP export, narrative compression, response-policy constraints, consent, adaptive follow-ups, rollback, audio contracts, visitor isolation, runtime paths, and Godot scene/API contracts.

For live verification, configure `.env`, start Flask, complete one Godot interview, create a daily narrative, inspect it from the privacy screen, record a voice turn, and export the persona ZIP.

## Troubleshooting

### Invalid API key or HTTP 502

Confirm the API key, model names, and network access, then restart Flask. Failed final interview ingestion is rolled back so the answer can be retried.

### Microphone cannot start

Allow microphone access for Python, confirm an operating-system input device is selected, and reinstall `requirements.txt` if `sounddevice` is missing.

### Godot cannot reach Flask

Confirm Flask is running, open `/health`, and verify `Api.base_url` in Godot.

### Consent error

Use the modern client's consent checkbox. API callers must send `"consent": true` or grant consent through the session endpoint before submitting personal content.

## Operational boundary

This repository is a complete local application. Public multi-user deployment is a separate operational concern and requires authentication, authorization, TLS, encrypted storage, rate limits, a production WSGI server, retention policies, and deployment-specific privacy review.

## License

MIT. See `LICENSE`.
