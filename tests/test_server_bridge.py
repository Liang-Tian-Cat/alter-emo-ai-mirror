import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.app import create_app
from server.bridge import BridgeService, SessionRepository


QUESTIONS = [
    {"id": "q1", "question": "First question?", "objective": "first"},
    {"id": "q2", "question": "Second question?", "objective": "second"},
]


class FakeAdapter:
    def __init__(self):
        self.ingested = []

    def ingest_interview(self, session):
        self.ingested.append(list(session.answers))

    def set_consent(self, _persona_id, granted, scope):
        return {"status": granted, "scope": scope}

    def reply(self, _session, content):
        return f"mirror:{content}"

    def reflect_event(self, _session, event):
        return {
            "first_person_recall": f"recall:{event}",
            "reflection": "reflection",
            "what_could_be_better": "next step",
            "supportive_self_talk": "self talk",
        }

    def list_memories(self, persona_id, *, limit=100, offset=0):
        return {"items": [{"id": "m1", "content": persona_id}], "total": 1, "limit": limit, "offset": offset}

    def revise_memory(self, _persona_id, memory_id, changes):
        return {"id": memory_id, **changes}

    def delete_memory(self, _persona_id, _memory_id):
        return None

    def set_memory_paused(self, persona_id, paused):
        return {"persona_id": persona_id, "memory_paused": paused}

    def delete_persona(self, _persona_id):
        return None

    def export_persona(self, _persona_id):
        return b"PK-fake-zip"

    def get_daily_narratives(self, _persona_id):
        return [{"id": "n1"}]

    def ingest_daily_narrative(self, _persona_id, text, narrative_date=None):
        return {"id": "n2", "original": text, "date": narrative_date}

    def compress_memories(self, _persona_id):
        return {"id": "c1", "source_ids": ["m1"]}


class FakeAudio:
    configured = True

    def start_recording(self):
        return {"recording": True, "sample_rate": 16000}

    def stop_recording(self, *, transcribe=True):
        return {"recording": False, "transcript": "voice answer" if transcribe else ""}

    def transcribe(self, _audio, _filename):
        return "transcribed"

    def synthesize(self, _text, _voice="alloy"):
        return b"fake-mp3"


class ServerBridgeTests(unittest.TestCase):
    def setUp(self):
        os.environ["ALTER_EMO_LEGACY_CONSENT"] = "true"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.adapter = FakeAdapter()
        repository = SessionRepository(Path(self.temp_dir.name))
        service = BridgeService(self.adapter, repository, QUESTIONS)
        app = create_app(service, FakeAudio())
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        os.environ.pop("ALTER_EMO_LEGACY_CONSENT", None)
        self.temp_dir.cleanup()

    def test_modern_session_contract_end_to_end(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.get_json()["capabilities"]["audio"])

        started = self.client.post("/v1/sessions", json={"persona_id": "leo", "consent": True})
        self.assertEqual(started.status_code, 201)
        state = started.get_json()
        session_id = state["session_id"]
        self.assertEqual(state["question"], "First question?")
        self.assertTrue(state["consent_granted"])
        self.assertEqual(len(self.client.get("/v1/perspectives").get_json()["items"]), 5)

        changed = self.client.put(
            f"/v1/sessions/{session_id}/perspective", json={"perspective": "clarity"}
        ).get_json()
        self.assertEqual(changed["perspective"], "clarity")

        first = self.client.post(
            f"/v1/sessions/{session_id}/messages", json={"content": "first answer"}
        ).get_json()
        self.assertEqual(first["question"], "Second question?")
        self.assertFalse(first["interview_complete"])

        second = self.client.post(
            f"/v1/sessions/{session_id}/messages", json={"content": "second answer"}
        ).get_json()
        self.assertEqual(second["stage"], "mirror")
        self.assertTrue(second["interview_complete"])
        self.assertEqual(len(self.adapter.ingested), 1)

        reply = self.client.post(
            f"/v1/sessions/{session_id}/messages", json={"content": "hello"}
        ).get_json()
        self.assertEqual(reply["reply"], "mirror:hello")

        reflection = self.client.post(
            f"/v1/sessions/{session_id}/events", json={"event": "a difficult meeting"}
        ).get_json()
        self.assertEqual(reflection["reflection"], "reflection")

        reset = self.client.delete(f"/v1/sessions/{session_id}")
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(self.client.get(f"/v1/sessions/{session_id}").status_code, 404)

    def test_original_emo_gym_route_contract(self):
        first = self.client.get("/next_question").get_json()
        self.assertEqual(first["question"], "First question?")

        answer = self.client.post("/text_input", json={"content": "answer one"}).get_json()
        self.assertEqual(answer["reply"], "Second question?")
        self.assertFalse(answer["stop"])

        completed = self.client.post("/text_input", json={"content": "answer two"}).get_json()
        self.assertTrue(completed["stop"])
        self.assertIn("ready", completed["reply"])

        reflection = self.client.post(
            "/simulate_event", json={"event": "missed a train"}
        ).get_json()
        self.assertEqual(reflection["first_person_recall"], "recall:missed a train")
        self.assertEqual(self.client.post("/reset_interview").status_code, 200)

    def test_audio_routes_are_implemented(self):
        response = self.client.get("/start_recording")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["recording"])

    def test_consent_is_required(self):
        started = self.client.post("/v1/sessions", json={"persona_id": "private"}).get_json()
        self.assertEqual(started["stage"], "consent")
        denied = self.client.post(
            f"/v1/sessions/{started['session_id']}/messages", json={"content": "private answer"}
        )
        self.assertEqual(denied.status_code, 400)

    def test_memory_narrative_export_and_audio_api_contracts(self):
        memories = self.client.get("/v1/personas/leo/memories").get_json()
        self.assertEqual(memories["items"][0]["id"], "m1")
        revised = self.client.patch(
            "/v1/personas/leo/memories/m1", json={"content": "revised"}
        ).get_json()
        self.assertEqual(revised["content"], "revised")
        self.assertEqual(self.client.delete("/v1/personas/leo/memories/m1").status_code, 200)
        self.assertEqual(self.client.put(
            "/v1/personas/leo/memory-state", json={"paused": True}
        ).get_json()["memory_paused"], True)
        self.assertEqual(self.client.post(
            "/v1/personas/leo/narratives", json={"content": "today"}
        ).status_code, 201)
        self.assertEqual(self.client.get("/v1/personas/leo/narratives").get_json()["items"][0]["id"], "n1")
        self.assertEqual(self.client.post("/v1/personas/leo/compress").get_json()["compression"]["id"], "c1")
        self.assertEqual(self.client.get("/v1/personas/leo/export").status_code, 200)
        self.assertEqual(self.client.post(
            "/v1/audio/transcriptions",
            data={"audio": (io.BytesIO(b"wav"), "voice.wav")},
            content_type="multipart/form-data",
        ).get_json()["transcript"], "transcribed")
        self.assertEqual(self.client.post(
            "/v1/audio/speech", json={"text": "hello"}
        ).data, b"fake-mp3")

    def test_adaptive_followup_is_inserted(self):
        class AdaptiveAdapter(FakeAdapter):
            def next_interview_question(self, _session, question, _answer):
                if question.get("kind") == "adaptive_followup":
                    return None
                return {"question": "What happened next?", "completion_score": 0.4}

        repository = SessionRepository(Path(self.temp_dir.name) / "adaptive")
        app = create_app(BridgeService(AdaptiveAdapter(), repository, QUESTIONS), FakeAudio())
        app.testing = True
        client = app.test_client()
        started = client.post("/v1/sessions", json={"persona_id": "leo", "consent": True}).get_json()
        result = client.post(
            f"/v1/sessions/{started['session_id']}/messages", json={"content": "a short answer"}
        ).get_json()
        self.assertEqual(result["question"], "What happened next?")
        self.assertEqual(result["adaptive_followups"], 1)

    def test_failed_interview_ingestion_keeps_last_answer_retryable(self):
        class FailingAdapter(FakeAdapter):
            def ingest_interview(self, _session):
                raise RuntimeError("model unavailable")

        repository = SessionRepository(Path(self.temp_dir.name) / "retry")
        service = BridgeService(FailingAdapter(), repository, QUESTIONS)
        app = create_app(service, FakeAudio())
        app.testing = True
        client = app.test_client()
        started = client.post("/v1/sessions", json={"persona_id": "leo", "consent": True}).get_json()
        session_id = started["session_id"]
        client.post(f"/v1/sessions/{session_id}/messages", json={"content": "one"})

        failed = client.post(
            f"/v1/sessions/{session_id}/messages", json={"content": "two"}
        )
        self.assertEqual(failed.status_code, 502)
        state = client.get(f"/v1/sessions/{session_id}").get_json()
        self.assertEqual(state["stage"], "interview")
        self.assertEqual(state["question"], "Second question?")


if __name__ == "__main__":
    unittest.main()
