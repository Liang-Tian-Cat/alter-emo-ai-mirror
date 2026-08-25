"""Adapter that connects the HTTP bridge to the existing Alter Emo core."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Dict


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
from mirror_agent import call_gpt, mirror_reply  # noqa: E402
from server.bridge import SessionState  # noqa: E402


REFLECTION_KEYS = (
    "first_person_recall",
    "reflection",
    "what_could_be_better",
    "supportive_self_talk",
)


class AlterEmoCoreAdapter:
    """Serialize core calls because the prototype memory cache is process-local."""

    def __init__(self):
        self._lock = threading.RLock()

    def ingest_interview(self, session: SessionState) -> None:
        with self._lock:
            agent_dir = create_persona(session.persona_id)
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

    def reply(self, session: SessionState, content: str) -> str:
        with self._lock:
            agent_dir = create_persona(session.persona_id)
            return mirror_reply(
                session.persona_id,
                str(agent_dir),
                content,
                session.interlocutor,
                session.id,
                win_ctx=2,
            )

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
