"""Flask application used by the Godot client."""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any, Dict

from flask import Flask, jsonify, request, send_file

from server.audio import AudioService
from server.bridge import BridgeService
from server.core_adapter import AlterEmoCoreAdapter
from src.perspectives import list_perspectives


def create_app(service: BridgeService | None = None, audio_service: AudioService | None = None) -> Flask:
    app = Flask(__name__)
    bridge = service or BridgeService(AlterEmoCoreAdapter())
    audio = audio_service or AudioService()
    legacy: Dict[str, str | None] = {"session_id": None}

    def json_body() -> Dict[str, Any]:
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def legacy_session() -> str:
        session_id = legacy.get("session_id")
        if not session_id:
            started = bridge.start_session(
                os.getenv("ALTER_EMO_PERSONA_ID", "demo-persona"),
                "self",
                consent_granted=os.getenv("ALTER_EMO_LEGACY_CONSENT", "false").lower() in {"1", "true", "yes"},
            )
            session_id = started["session_id"]
            legacy["session_id"] = session_id
        return str(session_id)

    @app.errorhandler(KeyError)
    def not_found(error):
        return jsonify({"error": str(error)}), 404

    @app.errorhandler(ValueError)
    def bad_request(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(RuntimeError)
    def upstream_error(error):
        return jsonify({"error": str(error)}), 502

    @app.get("/health")
    def health():
        return jsonify({
            "ok": True,
            "service": "alter-emo-godot-bridge",
            "capabilities": {
                "text": True,
                "events": True,
                "audio": True,
                "audio_configured": audio.configured,
                "export": True,
                "printing": False,
                "daily_narratives": True,
                "memory_controls": True,
                "perspectives": True,
            },
        })

    @app.get("/v1/perspectives")
    def perspectives():
        return jsonify({"items": list_perspectives()})

    @app.post("/v1/sessions")
    def start_session():
        body = json_body()
        return jsonify(bridge.start_session(
            str(body.get("persona_id", "demo-persona")),
            str(body.get("interlocutor", "self")),
            perspective=str(body.get("perspective", "balanced")),
            consent_granted=body.get("consent") is True,
            consent_scope=str(body.get("consent_scope", "private-reflection")),
        )), 201

    @app.put("/v1/sessions/<session_id>/consent")
    def consent(session_id: str):
        body = json_body()
        return jsonify(bridge.set_consent(
            session_id,
            body.get("granted") is True,
            str(body.get("scope", "private-reflection")),
        ))

    @app.put("/v1/sessions/<session_id>/perspective")
    def perspective(session_id: str):
        return jsonify(bridge.set_perspective(session_id, str(json_body().get("perspective", "balanced"))))

    @app.get("/v1/sessions/<session_id>")
    def get_session(session_id: str):
        return jsonify(bridge.get_session(session_id))

    @app.post("/v1/sessions/<session_id>/messages")
    def message(session_id: str):
        return jsonify(bridge.submit_message(session_id, str(json_body().get("content", ""))))

    @app.post("/v1/sessions/<session_id>/events")
    def event(session_id: str):
        return jsonify(bridge.reflect_event(session_id, str(json_body().get("event", ""))))

    @app.delete("/v1/sessions/<session_id>")
    def reset(session_id: str):
        return jsonify(bridge.reset_session(session_id))

    def core_method(name: str):
        method = getattr(bridge.adapter, name, None)
        if not callable(method):
            raise RuntimeError(f"Core adapter does not support {name}")
        return method

    @app.get("/v1/personas/<persona_id>/memories")
    def list_memories(persona_id: str):
        return jsonify(core_method("list_memories")(
            persona_id,
            limit=int(request.args.get("limit", 100)),
            offset=int(request.args.get("offset", 0)),
        ))

    @app.patch("/v1/personas/<persona_id>/memories/<memory_id>")
    def revise_memory(persona_id: str, memory_id: str):
        return jsonify(core_method("revise_memory")(persona_id, memory_id, json_body()))

    @app.delete("/v1/personas/<persona_id>/memories/<memory_id>")
    def delete_memory(persona_id: str, memory_id: str):
        core_method("delete_memory")(persona_id, memory_id)
        return jsonify({"ok": True, "memory_id": memory_id})

    @app.put("/v1/personas/<persona_id>/memory-state")
    def memory_state(persona_id: str):
        return jsonify(core_method("set_memory_paused")(persona_id, json_body().get("paused") is True))

    @app.put("/v1/personas/<persona_id>/consent")
    def persona_consent(persona_id: str):
        body = json_body()
        return jsonify(core_method("set_consent")(
            persona_id,
            body.get("granted") is True,
            str(body.get("scope", "private-reflection")),
        ))

    @app.delete("/v1/personas/<persona_id>")
    def delete_persona(persona_id: str):
        if json_body().get("confirm") != persona_id:
            raise ValueError("confirm must exactly match persona_id")
        core_method("delete_persona")(persona_id)
        return jsonify({"ok": True, "persona_id": persona_id})

    @app.get("/v1/personas/<persona_id>/export")
    def export_persona(persona_id: str):
        payload = core_method("export_persona")(persona_id)
        return send_file(
            BytesIO(payload),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{persona_id}-alter-emo-export.zip",
        )

    @app.get("/v1/personas/<persona_id>/narratives")
    def narratives(persona_id: str):
        return jsonify({"items": core_method("get_daily_narratives")(persona_id)})

    @app.post("/v1/personas/<persona_id>/narratives")
    def add_narrative(persona_id: str):
        body = json_body()
        text = str(body.get("content", "")).strip()
        if not text:
            raise ValueError("content is required")
        return jsonify(core_method("ingest_daily_narrative")(persona_id, text, body.get("date"))), 201

    @app.post("/v1/personas/<persona_id>/compress")
    def compress(persona_id: str):
        return jsonify({"compression": core_method("compress_memories")(persona_id)})

    @app.post("/v1/audio/transcriptions")
    def transcribe_audio():
        upload = request.files.get("audio")
        if upload is None:
            raise ValueError("multipart field 'audio' is required")
        return jsonify({"transcript": audio.transcribe(upload.read(), upload.filename or "recording.wav")})

    @app.post("/v1/audio/speech")
    def speech():
        body = json_body()
        payload = audio.synthesize(str(body.get("text", "")), str(body.get("voice", "alloy")))
        return send_file(BytesIO(payload), mimetype="audio/mpeg", download_name="mirror.mp3")

    # Compatibility routes used by the original EMO GYM GDScript.
    @app.get("/next_question")
    def legacy_next_question():
        state = bridge.get_session(legacy_session())
        return jsonify({
            "question": state.get("question"),
            "stop": state.get("stage") == "mirror",
            "agent_name": state.get("persona_id"),
            "session_id": state.get("session_id"),
        })

    @app.post("/text_input")
    def legacy_text_input():
        result = bridge.submit_message(legacy_session(), str(json_body().get("content", "")))
        return jsonify({
            **result,
            # The original EMO GYM panel renders `reply` immediately. During
            # interview mode the next question therefore becomes its reply.
            "reply": result.get("question") or result.get("reply"),
            "stop": result.get("stage") == "mirror",
            "agent_name": result.get("persona_id"),
        })

    @app.post("/simulate_event")
    def legacy_simulate_event():
        body = json_body()
        session_id = body.get("session_id") or legacy.get("session_id")
        if session_id:
            return jsonify(bridge.reflect_event(str(session_id), str(body.get("event", ""))))
        return jsonify(bridge.reflect_event_for_persona(
            str(body.get("agent_name", "demo-persona")),
            str(body.get("event", "")),
        ))

    @app.post("/reset_interview")
    def legacy_reset():
        session_id = legacy.get("session_id")
        if session_id:
            bridge.reset_session(str(session_id))
        legacy["session_id"] = None
        return jsonify({"ok": True})

    @app.route("/start_recording", methods=["GET", "POST"])
    def legacy_start_recording():
        return jsonify(audio.start_recording())

    @app.route("/stop_recording", methods=["GET", "POST"])
    def legacy_stop_recording():
        result = audio.stop_recording(transcribe=True)
        transcript = str(result.get("transcript", ""))
        if transcript:
            result.update(bridge.submit_message(legacy_session(), transcript))
        return jsonify(result)

    @app.post("/tts_speak")
    def legacy_tts():
        body = json_body()
        payload = audio.synthesize(str(body.get("text") or body.get("content") or ""), str(body.get("voice", "alloy")))
        return send_file(BytesIO(payload), mimetype="audio/mpeg", download_name="mirror.mp3")

    @app.post("/simulate_and_print")
    def legacy_print_export():
        body = json_body()
        persona_id = str(body.get("persona_id") or os.getenv("ALTER_EMO_PERSONA_ID", "demo-persona"))
        payload = core_method("export_persona")(persona_id)
        return send_file(BytesIO(payload), mimetype="application/zip", as_attachment=True, download_name=f"{persona_id}-reflection.zip")

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("ALTER_EMO_HOST", "127.0.0.1"),
        port=int(os.getenv("ALTER_EMO_PORT", "5000")),
        debug=False,
        threaded=False,
    )
