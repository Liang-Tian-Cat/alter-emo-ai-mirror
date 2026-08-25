<div align="center">
  <img src="https://liang-tian.com/images/works/alter-emo/exhibition-board.png" alt="Alter Emo exhibition board" width="100%" />
  <h1>Alter Emo — AI Mirror</h1>
  <p><strong>A reflective AI experience built from narrative memory, emotion, and the user's own communication patterns.</strong></p>
  <p><a href="https://liang-tian.com/works/aimirror">Full interactive case study →</a></p>
</div>

## Overview

Alter Emo explores what an AI companion could become when it does more than answer the current prompt. The project creates an evolving pixel-self from memories, daily narratives, feelings, choices, and ways of speaking that the user intentionally shares.

The goal is not to produce a perfect digital copy. It is to create a partial, transparent mirror that helps a person notice recurring patterns, revisit meaningful experiences, and make future choices with greater clarity.

> This repository documents the product concept, interaction model, and agent architecture. Private user data and production credentials are not included.

## The problem

Everyday experiences are fragmented across conversations, notes, emotions, and decisions. Conventional chat systems usually respond well to a single question, but rarely reconnect the long-term narrative: what repeatedly matters, how a person frames experience, and why similar choices return.

Alter Emo asks:

- How can an agent remember without reducing a person to a fixed profile?
- How can raw life stories and structured memory work together?
- How should a mirror-like agent choose when to ask, reframe, nudge, or simply reflect?
- How can an embodied interface make long-term reflection feel present without pretending to be the real person?

## Experience

The user meets a pixel character inside a Godot room. Everyday chat, diary-like input, and adaptive interviews gradually build a mirror-self. The character can recall relevant narrative windows, identify emotional and behavioral patterns, plan an appropriate response action, and write the new exchange back into memory.

The system is designed around user agency: the mirror grows only from material the user chooses to share.

## System architecture

```mermaid
flowchart LR
    A[Godot room / conversation / event] --> B[Flask bridge]
    B --> C[Narrative parser]
    C --> D[Memory index]
    C --> E[Narrative store]
    D --> F[Hybrid retrieval]
    E --> F
    F --> G[Reflection + planning]
    G --> H[Behavior policy]
    H --> I[Mirror reply]
    I --> B
    I --> D
    I --> E
```

### 1. Conversation capture

Godot presents the room, avatar movement, dialogue, recording state, and embodied cues. Flask coordinates conversational input, daily notes, adaptive interview questions, generated replies, and file export.

### 2. Dual memory representation

- **Structured memory nodes** support retrieval through event, topic, emotion, salience, and time.
- **Narrative windows** retain the surrounding story, language, framing, and conversational context.

This keeps the system searchable without throwing away the user's original voice.

### 3. Hybrid retrieval

Candidate memories are ranked using four signals:

| Signal | Weight | Purpose |
| --- | ---: | --- |
| Semantic similarity | 55% | Finds experiences with related meaning |
| Emotional similarity | 20% | Recovers a comparable affective state |
| Salience | 15% | Prioritizes personally significant events |
| Recency | 10% | Preserves continuity with recent experience |

After ranking, the system reopens the nearby narrative window rather than responding from an isolated memory summary.

The public Python core implements these weights in `src/memory_retrieval.py`. Every selected memory is logged with its four raw signals and weighted contribution, so retrieval decisions can be inspected instead of hidden inside one opaque similarity score.

### 4. Reflection and behavior policy

Retrieved evidence becomes a short reflection plan. A behavior policy then selects an interaction intent—ask, reframe, nudge, mirror, or pause—before the model writes the final response. This separates *what the agent should do* from *how the final sentence should sound*.

The policy is constrained to retrieved memory IDs and has a deterministic local fallback. When grounded context is missing, the mirror asks rather than inventing a personal claim.

## Technology

- **Godot:** embodied room, pixel avatar, interaction and dialogue states
- **Flask / Python:** orchestration, memory services, interviews, and export
- **GPT:** adaptive conversation, extraction, reflection, planning, and response generation
- **Structured files + embeddings:** persistent memory nodes, narrative windows, and retrieval

## Responsible design boundaries

- The interface identifies the character as a mirror, not the real person.
- New claims from a visitor do not silently become facts about the owner.
- The agent should not invent private memories or relationships.
- Memory should be inspectable, correctable, and removable by the user.
- Sensitive deployments require explicit retention, consent, and escalation policies.

## What I learned

The strongest sense of continuity did not come from saving more text. It came from restoring the right narrative context and selecting an appropriate response action before generation. Memory quality, behavior policy, and communication style need to be designed as separate layers.

## Status

Interactive research prototype and portfolio case study. The public demo uses curated public memory; it does not expose a visitor's conversation history to the portfolio owner.

## Source code

This repository includes the working Python core used by the prototype:

- `godot/` — clean Godot 4 client for interview, mirror chat, and event reflection
- `server/` — Flask bridge and compatibility routes for the original EMO GYM GDScript
- `src/mirror_agent.py` — command-line mirror chat, narrative restoration, and response orchestration
- `src/interview_agent.py` — adaptive interview and memory extraction
- `src/agent_io.py` — agent, session, and memory persistence helpers
- `src/memory_retrieval.py` — inspectable semantic, emotion, salience, and recency scoring
- `src/response_policy.py` — constrained reflection/action planning and safe fallbacks
- `src/build_agent.py` — persona workspace creation
- `examples/` — example interview and MBTI prompt pools
- `tests/` — offline unit tests for retrieval weights, grounding, and policy constraints

Private interview sessions, embeddings, recordings, generated agent memories, and API credentials are intentionally excluded.

The original exhibition folder also contains Godot import caches, local audio output, hardware-specific adapters, and artwork/font packages with separate provenance. Those are not copied into this public repository. The included Godot client is self-contained and uses only native controls, while preserving the actual HTTP send/receive architecture.

### Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # use `cp` on macOS/Linux
python src/mirror_agent.py
```

Add your own `OPENAI_API_KEY` to `.env`. Runtime memory is written under `agents/`, which is ignored by Git.

The command-line modules load `.env` from the repository root. They initialize the OpenAI client only when an API-backed operation starts, so local commands such as `--help` and `--list` work without a key.

### Verify API configuration

```bash
python src/mirror_agent.py --check
```

### Run an adaptive interview

```bash
python src/interview_agent.py
```

The interview question pools are read from `examples/`; session artifacts remain under the ignored `agents/` directory.

### Create an empty persona workspace

```bash
python src/build_agent.py --id demo-persona
```

### List personas

```bash
python src/mirror_agent.py --list
```

### Start a named mirror session

```bash
python src/mirror_agent.py --id demo-persona --interlocutor self
```

### Run the offline tests

```bash
python -m unittest discover -s tests -v
```

### Run the Godot bridge

Install the optional server dependencies and start Flask from the repository root:

```bash
pip install -r requirements-server.txt
python -m server.app
```

Then open `godot/project.godot` in Godot 4.4 or newer and run the main scene. The client connects to `http://127.0.0.1:5000`, starts an adaptive interview, sends answers and mirror messages, and displays structured event reflections.

The bridge also keeps the original prototype route names—`/next_question`, `/text_input`, `/simulate_event`, and `/reset_interview`—so the earlier EMO GYM GDScript can be migrated incrementally. Recording, TTS, and physical printing are intentionally reported as unavailable in the public build until explicit, credential-free adapters are configured.

### Dependency files

- `requirements.txt` contains the reusable AI and memory core.
- `requirements-server.txt` extends it with Flask for Godot integration.

No virtual environment, generated Godot cache, user memory, recording, or API key belongs in Git.

## Author

Designed and developed by [Liang Tian](https://liang-tian.com).
