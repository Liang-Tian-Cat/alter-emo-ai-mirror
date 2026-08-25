"""Session orchestration for Godot and other interactive clients."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CoreAdapter(Protocol):
    def ingest_interview(self, session: "SessionState") -> None: ...

    def reply(self, session: "SessionState", content: str) -> str: ...

    def reflect_event(self, session: "SessionState", event: str) -> Dict[str, str]: ...


@dataclass
class SessionState:
    id: str
    persona_id: str
    interlocutor: str
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]] = field(default_factory=list)
    question_index: int = 0
    stage: str = "interview"

    @property
    def current_question(self) -> Dict[str, Any] | None:
        if self.stage != "interview" or self.question_index >= len(self.questions):
            return None
        return self.questions[self.question_index]


class SessionRepository:
    def __init__(self, runtime_root: Path | None = None):
        self.runtime_root = runtime_root or (PROJECT_ROOT / "runtime" / "bridge_sessions")
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def create(self, persona_id: str, interlocutor: str, questions: List[Dict[str, Any]]) -> SessionState:
        with self._lock:
            session = SessionState(
                id=uuid.uuid4().hex[:12],
                persona_id=persona_id,
                interlocutor=interlocutor,
                questions=questions,
            )
            self._sessions[session.id] = session
            self.save(session)
            return session

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                target = self.runtime_root / f"{session_id}.json"
                if target.exists():
                    payload = json.loads(target.read_text(encoding="utf-8"))
                    session = SessionState(**payload)
                    self._sessions[session.id] = session
            if session is None:
                raise KeyError(f"Unknown session: {session_id}")
            return session

    def save(self, session: SessionState) -> None:
        with self._lock:
            self._sessions[session.id] = session
            self.runtime_root.mkdir(parents=True, exist_ok=True)
            target = self.runtime_root / f"{session.id}.json"
            target.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2), encoding="utf-8")

    def delete(self, session_id: str) -> None:
        with self._lock:
            target = self.runtime_root / f"{session_id}.json"
            if session_id not in self._sessions and not target.exists():
                raise KeyError(f"Unknown session: {session_id}")
            self._sessions.pop(session_id, None)
            if target.exists():
                target.unlink()


def load_questions(path: Path | None = None) -> List[Dict[str, Any]]:
    source = path or (PROJECT_ROOT / "examples" / "interview_script.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"Interview script must be a non-empty JSON list: {source}")
    return [item for item in data if isinstance(item, dict) and str(item.get("question", "")).strip()]


class BridgeService:
    def __init__(
        self,
        adapter: CoreAdapter,
        repository: SessionRepository | None = None,
        questions: List[Dict[str, Any]] | None = None,
    ):
        self.adapter = adapter
        self.repository = repository or SessionRepository()
        self.questions = questions or load_questions()

    def start_session(self, persona_id: str, interlocutor: str = "self") -> Dict[str, Any]:
        persona = persona_id.strip() or "demo-persona"
        speaker = interlocutor.strip() or "self"
        session = self.repository.create(persona, speaker, list(self.questions))
        return self._snapshot(session)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._snapshot(self.repository.get(session_id))

    def submit_message(self, session_id: str, content: str) -> Dict[str, Any]:
        session = self.repository.get(session_id)
        message = content.strip()
        if not message:
            raise ValueError("content is required")

        if session.stage == "interview":
            question = session.current_question
            if question is None:
                raise RuntimeError("Interview state is inconsistent")
            session.answers.append({
                "question_id": question.get("id"),
                "question": question.get("question", ""),
                "objective": question.get("objective", ""),
                "answer": message,
            })
            previous_index = session.question_index
            session.question_index += 1
            completed = session.question_index >= len(session.questions)
            if completed:
                try:
                    self.adapter.ingest_interview(session)
                except Exception:
                    # Keep the session retryable when an upstream model call fails.
                    session.answers.pop()
                    session.question_index = previous_index
                    self.repository.save(session)
                    raise
                session.stage = "mirror"
            self.repository.save(session)
            result = self._snapshot(session)
            result.update({
                "reply": "Interview captured. Your mirror is ready." if completed else "Answer captured.",
                "interview_complete": completed,
            })
            return result

        reply = self.adapter.reply(session, message)
        self.repository.save(session)
        result = self._snapshot(session)
        result.update({"reply": reply, "interview_complete": True})
        return result

    def reflect_event(self, session_id: str, event: str) -> Dict[str, Any]:
        session = self.repository.get(session_id)
        text = event.strip()
        if not text:
            raise ValueError("event is required")
        if session.stage != "mirror":
            raise ValueError("Complete the interview before reflecting on an event")
        return {
            "session_id": session.id,
            "persona_id": session.persona_id,
            **self.adapter.reflect_event(session, text),
        }

    def reflect_event_for_persona(self, persona_id: str, event: str) -> Dict[str, Any]:
        session = self.repository.create(persona_id.strip() or "demo-persona", "self", list(self.questions))
        session.stage = "mirror"
        session.question_index = len(session.questions)
        self.repository.save(session)
        return self.reflect_event(session.id, event)

    def reset_session(self, session_id: str) -> Dict[str, Any]:
        self.repository.delete(session_id)
        return {"ok": True, "session_id": session_id}

    @staticmethod
    def _snapshot(session: SessionState) -> Dict[str, Any]:
        question = session.current_question
        return {
            "session_id": session.id,
            "persona_id": session.persona_id,
            "interlocutor": session.interlocutor,
            "stage": session.stage,
            "question": question.get("question") if question else None,
            "question_id": question.get("id") if question else None,
            "question_index": session.question_index,
            "question_count": len(session.questions),
        }
