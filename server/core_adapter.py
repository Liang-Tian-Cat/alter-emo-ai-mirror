"""Adapter that connects the HTTP bridge to the existing Alter Emo core."""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent_io import load_or_init_meta, save_memory_node_dual, save_meta  # noqa: E402
from build_agent import create_persona  # noqa: E402
from interview_agent import (  # noqa: E402
    MODEL_CHAT,
    MODEL_EMB,
    _emo_embed_from_tag,
    assess_importance,
    extract_emotion_tag,
    get_embedding,
    reflect_empathic_style,
    summarize_answer,
)
from mirror_agent import call_gpt, memory_cache, mirror_reply  # noqa: E402
from memory_store import PersonaMemoryStore, read_ndjson, write_ndjson  # noqa: E402
from narrative_memory import (  # noqa: E402
    compress_memory_stream,
    list_narratives,
    normalize_narrative,
    save_narrative,
)
from style_analysis import measure_style  # noqa: E402
from server.bridge import SessionState  # noqa: E402


REFLECTION_KEYS = (
    "first_person_recall",
    "reflection",
    "what_could_be_better",
    "supportive_self_talk",
)


class AlterEmoCoreAdapter:
    """Serialize core calls because the in-process memory cache is process-local."""

    def __init__(self):
        self._lock = threading.RLock()

    @staticmethod
    def _meta(agent_dir: Path, persona_id: str) -> tuple[Path, Dict[str, Any]]:
        path = agent_dir / "meta.json"
        return path, load_or_init_meta(str(path), persona_id)

    def set_consent(self, persona_id: str, granted: bool, scope: str) -> Dict[str, Any]:
        with self._lock:
            agent_dir = create_persona(persona_id)
            path, meta = self._meta(agent_dir, persona_id)
            meta["consent"] = {
                "status": bool(granted),
                "scope": scope if granted else "none",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if not granted:
                meta["memory_paused"] = True
            else:
                meta["memory_paused"] = False
            path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return dict(meta["consent"])

    def set_memory_paused(self, persona_id: str, paused: bool) -> Dict[str, Any]:
        with self._lock:
            agent_dir = create_persona(persona_id)
            path, meta = self._meta(agent_dir, persona_id)
            if not bool((meta.get("consent") or {}).get("status")) and not paused:
                raise ValueError("Grant consent before resuming long-term memory")
            meta["memory_paused"] = bool(paused)
            path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"persona_id": persona_id, "memory_paused": bool(paused)}

    def _require_consent(self, agent_dir: Path, persona_id: str) -> Dict[str, Any]:
        _, meta = self._meta(agent_dir, persona_id)
        if not bool((meta.get("consent") or {}).get("status")):
            raise ValueError("Explicit consent is required for persona memory")
        return meta

    def next_interview_question(
        self, session: SessionState, question: Dict[str, Any], answer: str
    ) -> Dict[str, Any] | None:
        """Assess objective completion and create a genuinely adaptive follow-up."""
        prompt = (
            "Evaluate whether the answer satisfies the interview objective. Return only JSON: "
            '{"completion_score":0.0,"follow_up":"one concise question or empty","reason":"short"}. '
            "Ask a follow-up only when a meaningful detail, example, feeling, value, or consequence is missing. "
            "Use the same language as the answer.\n"
            f"Objective: {question.get('objective', '')}\n"
            f"Question: {question.get('question', '')}\nAnswer: {answer}"
        )
        try:
            raw = json.loads(call_gpt(
                prompt,
                sys="You are Alter Emo's adaptive interview planner. Return valid JSON only.",
                temperature=0.1,
                json_only=True,
            ))
            score = max(0.0, min(1.0, float(raw.get("completion_score", 0.0))))
            follow_up = str(raw.get("follow_up", "")).strip()
        except Exception:
            score = min(1.0, len(answer.strip()) / 80.0)
            follow_up = "能说一个具体发生过的例子吗？" if score < 0.72 else ""
        if score >= 0.72 or not follow_up:
            return None
        return {
            "question": follow_up,
            "objective": question.get("objective", "deepen the narrative"),
            "completion_score": score,
        }

    def ingest_interview(self, session: SessionState) -> None:
        with self._lock:
            agent_dir = create_persona(session.persona_id)
            meta = self._require_consent(agent_dir, session.persona_id)
            if meta.get("memory_paused"):
                raise ValueError("Long-term memory is paused")
            conversation = []
            for index, item in enumerate(session.answers):
                question = str(item.get("question", "")).strip()
                answer = str(item.get("answer", "")).strip()
                conversation.extend([
                    {"role": "interviewer", "content": question},
                    {"role": "user", "content": answer},
                ])

                event_text = f"{question}\n{answer}".strip()
                emotion = extract_emotion_tag(answer)
                save_memory_node_dual(
                    agent_dir=str(agent_dir),
                    text=answer,
                    summary=summarize_answer(answer),
                    mtype="bridge_interview_answer",
                    qid=item.get("question_id"),
                    importance=assess_importance(answer),
                    emotion_tag=emotion,
                    evt_vec=get_embedding(event_text),
                    emo_vec=_emo_embed_from_tag(emotion),
                    source={
                        "kind": "interview",
                        "session_id": session.id,
                        "turn_index": index * 2 + 1,
                    },
                )

            reflection = reflect_empathic_style(conversation)
            measured = measure_style(item["content"] for item in conversation if item["role"] == "user")
            reflected_style = reflection.setdefault("empathic_style", {})
            reflected_style["measured"] = measured
            # Deterministic measurements take precedence for fields that can be
            # computed directly rather than guessed by a model.
            reflected_style.update(measured)
            session_dir = agent_dir / "sessions" / session.id
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "conversation.json").write_text(
                json.dumps(conversation, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (session_dir / "reflection.json").write_text(
                json.dumps(reflection, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            meta_path = agent_dir / "meta.json"
            meta = load_or_init_meta(str(meta_path), session.persona_id)
            save_meta(
                meta_path=str(meta_path),
                meta=meta,
                session_id=session.id,
                style=reflection.get("empathic_style", {}),
                seed=reflection.get("personality_seed", {}),
                model_chat=MODEL_CHAT,
                model_emb=MODEL_EMB,
            )
            self.compress_memories(session.persona_id)

    def reply(self, session: SessionState, content: str) -> str:
        with self._lock:
            agent_dir = create_persona(session.persona_id)
            meta = self._require_consent(agent_dir, session.persona_id)
            reply = mirror_reply(
                session.persona_id,
                str(agent_dir),
                content,
                session.interlocutor,
                session.id,
                win_ctx=2,
                perspective=session.perspective,
                persist_memory=not bool(meta.get("memory_paused")),
            )
            if not bool(meta.get("memory_paused")):
                self.compress_memories(session.persona_id)
            return reply

    def list_memories(self, persona_id: str, *, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        agent_dir = create_persona(persona_id)
        return PersonaMemoryStore(agent_dir).list(limit=limit, offset=offset)

    def revise_memory(self, persona_id: str, memory_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            agent_dir = create_persona(persona_id)
            revised = PersonaMemoryStore(agent_dir).revise(memory_id, changes, event_embedder=get_embedding)
            memory_cache[:] = [item for item in memory_cache if str(item.get("id")) != memory_id]
            return revised

    def delete_memory(self, persona_id: str, memory_id: str) -> None:
        with self._lock:
            agent_dir = create_persona(persona_id)
            PersonaMemoryStore(agent_dir).delete(memory_id)
            memory_cache[:] = [item for item in memory_cache if str(item.get("id")) != memory_id]

    def delete_persona(self, persona_id: str) -> None:
        with self._lock:
            agent_dir = create_persona(persona_id)
            PersonaMemoryStore(agent_dir).delete_all()
            scope = str(agent_dir.resolve())
            memory_cache[:] = [item for item in memory_cache if str(item.get("_agent_dir", "")) != scope]

    def export_persona(self, persona_id: str) -> bytes:
        agent_dir = create_persona(persona_id)
        return PersonaMemoryStore(agent_dir).export_zip()

    def ingest_daily_narrative(self, persona_id: str, text: str, narrative_date: str | None = None) -> Dict[str, Any]:
        with self._lock:
            agent_dir = create_persona(persona_id)
            meta = self._require_consent(agent_dir, persona_id)
            if meta.get("memory_paused"):
                raise ValueError("Long-term memory is paused")
            prompt = (
                "Parse this daily narrative. Return JSON with arrays: events, feelings, choices, values, recurring_patterns. "
                "Do not add facts.\nNarrative: " + text
            )
            try:
                raw = json.loads(call_gpt(prompt, sys="Return grounded narrative JSON only.", temperature=0.1, json_only=True))
            except Exception:
                raw = {"events": [text], "feelings": [], "choices": [], "values": [], "recurring_patterns": []}
            narrative = normalize_narrative(raw, text, narrative_date)
            path = save_narrative(agent_dir, narrative)
            for index, event in enumerate(narrative["events"]):
                emotion = extract_emotion_tag(event)
                save_memory_node_dual(
                    agent_dir=str(agent_dir),
                    text=event,
                    summary=summarize_answer(event),
                    mtype="daily_narrative_event",
                    importance=assess_importance(event),
                    emotion_tag=emotion,
                    evt_vec=get_embedding(event),
                    emo_vec=_emo_embed_from_tag(emotion),
                    source={"kind": "daily_narrative", "narrative_id": narrative["id"], "turn_index": index},
                    extra={"narrative_date": narrative["date"]},
                )
            compression = self.compress_memories(persona_id)
            return {**narrative, "path": str(path.relative_to(agent_dir)), "compression": compression}

    def get_daily_narratives(self, persona_id: str) -> list[Dict[str, Any]]:
        agent_dir = create_persona(persona_id)
        return list_narratives(agent_dir)

    def compress_memories(self, persona_id: str) -> Dict[str, Any] | None:
        agent_dir = create_persona(persona_id)
        self._require_consent(agent_dir, persona_id)

        def summarize(nodes: list[Dict[str, Any]]) -> Dict[str, Any]:
            prompt = (
                "Compress these grounded memories without losing uncertainty. Return JSON with summary, patterns, values, open_questions.\n"
                + json.dumps([{"id": n.get("id"), "content": n.get("content"), "emotion": n.get("emotion_tag")} for n in nodes], ensure_ascii=False)
            )
            try:
                return json.loads(call_gpt(prompt, sys="Return valid memory-compression JSON only.", temperature=0.1, json_only=True))
            except Exception:
                return {"summary": " | ".join(str(n.get("summary") or n.get("content", "")) for n in nodes), "patterns": [], "values": [], "open_questions": []}

        compression = compress_memory_stream(agent_dir, summarize)
        if compression and compression.get("summary"):
            emotion = {"emotion": "reflective", "tone": ["compressed", "grounded"]}
            node = save_memory_node_dual(
                agent_dir=str(agent_dir),
                text=str(compression["summary"]),
                summary=str(compression["summary"])[:240],
                mtype="memory_compression",
                importance=75,
                emotion_tag=emotion,
                evt_vec=get_embedding(str(compression["summary"])),
                emo_vec=_emo_embed_from_tag(emotion),
                source={"kind": "compression", "compression_id": compression["id"]},
                extra={"source_ids": compression.get("source_ids", [])},
                enforce_salience_gate=False,
            )
            compression["memory_node_id"] = node["id"]
            compression_path = agent_dir / "memory_stream" / "compressions.ndjson"
            groups = read_ndjson(compression_path)
            for group in groups:
                if group.get("id") == compression.get("id"):
                    group["memory_node_id"] = node["id"]
            write_ndjson(compression_path, groups)
        return compression

    def reflect_event(self, session: SessionState, event: str) -> Dict[str, str]:
        mirror_text = self.reply(session, event)
        prompt = (
            "Create a grounded event reflection from the mirror response below. "
            "Return only a JSON object with keys first_person_recall, reflection, "
            "what_could_be_better, supportive_self_talk. Do not diagnose or invent facts.\n\n"
            f"Event: {event}\nMirror response: {mirror_text}"
        )
        try:
            raw = json.loads(call_gpt(
                prompt,
                sys="You structure Alter Emo reflections. Return valid JSON only.",
                temperature=0.2,
                json_only=True,
            ))
        except Exception:
            raw = {}
        result = {key: str(raw.get(key, "")).strip() for key in REFLECTION_KEYS}
        result["first_person_recall"] = result["first_person_recall"] or mirror_text
        result["reflection"] = result["reflection"] or mirror_text
        result["what_could_be_better"] = result["what_could_be_better"] or "I can pause and notice the pattern before choosing my next step."
        result["supportive_self_talk"] = result["supportive_self_talk"] or "I can stay curious without forcing certainty."
        result["generated_at"] = str(time.time())
        return result
