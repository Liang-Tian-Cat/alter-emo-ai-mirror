"""Flask application used by the Godot client."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Flask, jsonify, request

from server.bridge import BridgeService
from server.core_adapter import AlterEmoCoreAdapter


def create_app(service: BridgeService | None = None) -> Flask:
    app = Flask(__name__)
    bridge = service or BridgeService(AlterEmoCoreAdapter())
    legacy: Dict[str, str | None] = {"session_id": None}

    def json_body() -> Dict[str, Any]:
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def legacy_session() -> str:
        session_id = legacy.get("session_id")
        if not session_id:
            started = bridge.start_session(os.getenv("ALTER_EMO_PERSONA_ID", "demo-persona"), "self")
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
            "capabilities": {"text": True, "events": True, "audio": False, "printing": False},
        })

    @app.post("/v1/sessions")
    def start_session():
        body = json_body()
        return jsonify(bridge.start_session(
            str(body.get("persona_id", "demo-persona")),
            str(body.get("interlocutor", "self")),
        )), 201

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
    @app.route("/stop_recording", methods=["GET", "POST"])
    @app.route("/tts_speak", methods=["POST"])
    @app.route("/simulate_and_print", methods=["POST"])
    def optional_hardware_unavailable():
        return jsonify({
            "error": "Optional audio/printing hardware is not enabled in the public bridge.",
            "capabilities": {"audio": False, "printing": False},
        }), 501

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("ALTER_EMO_HOST", "127.0.0.1"),
        port=int(os.getenv("ALTER_EMO_PORT", "5000")),
        debug=False,
        threaded=False,
    )
