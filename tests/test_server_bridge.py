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

    def reply(self, _session, content):
        return f"mirror:{content}"

    def reflect_event(self, _session, event):
        return {
            "first_person_recall": f"recall:{event}",
            "reflection": "reflection",
            "what_could_be_better": "next step",
            "supportive_self_talk": "self talk",
        }


class ServerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.adapter = FakeAdapter()
        repository = SessionRepository(Path(self.temp_dir.name))
        service = BridgeService(self.adapter, repository, QUESTIONS)
        app = create_app(service)
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_modern_session_contract_end_to_end(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertFalse(health.get_json()["capabilities"]["audio"])

        started = self.client.post("/v1/sessions", json={"persona_id": "leo"})
        self.assertEqual(started.status_code, 201)
        state = started.get_json()
        session_id = state["session_id"]
        self.assertEqual(state["question"], "First question?")

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

    def test_optional_hardware_is_explicitly_unavailable(self):
        response = self.client.get("/start_recording")
        self.assertEqual(response.status_code, 501)
        self.assertFalse(response.get_json()["capabilities"]["audio"])

    def test_failed_interview_ingestion_keeps_last_answer_retryable(self):
        class FailingAdapter(FakeAdapter):
            def ingest_interview(self, _session):
                raise RuntimeError("model unavailable")

        repository = SessionRepository(Path(self.temp_dir.name) / "retry")
        service = BridgeService(FailingAdapter(), repository, QUESTIONS)
        app = create_app(service)
        app.testing = True
        client = app.test_client()
        started = client.post("/v1/sessions", json={"persona_id": "leo"}).get_json()
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
