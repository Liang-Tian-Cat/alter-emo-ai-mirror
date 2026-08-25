"""Constrained planning helpers used before Alter Emo writes a reply."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


ALLOWED_ACTIONS = (
    "question",
    "reframe",
    "guide",
    "reflect",
    "ground",
    "validate",
    "challenge",
    "pause",
    # Backward-compatible names used by earlier saved plans.
    "ask",
    "nudge",
    "mirror",
)


def fallback_response_plan(user_text: str, has_context: bool) -> Dict[str, Any]:
    """Choose a safe local plan when model-based planning is unavailable."""
    text = (user_text or "").strip()
    lowered = text.lower()

    if not text:
        action = "pause"
        reflection = "There is not enough material to interpret yet."
    elif not has_context:
        action = "question"
        reflection = "No grounded personal memory is available for this moment."
    elif any(token in lowered for token in ("崩溃", "喘不过气", "overwhelmed", "too much")):
        action = "pause"
        reflection = "The message carries more intensity than a quick interpretation should flatten."
    elif any(token in lowered for token in ("怎么办", "怎么做", "建议", "should i", "what should")):
        action = "guide"
        reflection = "The user is asking for a next step, so one bounded option is more useful than a verdict."
    elif any(token in lowered for token in ("为什么", "总是", "又一次", "why do i", "always")):
        action = "reframe"
        reflection = "The wording suggests a recurring pattern that can be viewed from another angle."
    else:
        action = "reflect"
        reflection = "The safest useful response is to reflect the grounded pattern already present."

    return {
        "reflection": reflection,
        "action": action,
        "confidence": 0.45,
        "grounding_ids": [],
    }


def normalize_response_plan(
    raw: Mapping[str, Any] | None,
    *,
    user_text: str,
    retrieved_ids: Iterable[str],
) -> Dict[str, Any]:
    """Validate a model-produced plan and constrain it to retrieved evidence."""
    allowed_ids = [str(value) for value in retrieved_ids if value]
    fallback = fallback_response_plan(user_text, bool(allowed_ids))
    candidate = dict(raw or {})

    action = str(candidate.get("action") or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        action = fallback["action"]

    reflection = str(candidate.get("reflection") or "").strip()
    if not reflection:
        reflection = fallback["reflection"]

    try:
        confidence = max(0.0, min(1.0, float(candidate.get("confidence", fallback["confidence"]))))
    except (TypeError, ValueError):
        confidence = fallback["confidence"]

    requested_ids = candidate.get("grounding_ids")
    if not isinstance(requested_ids, list):
        requested_ids = []
    grounding_ids = [value for value in allowed_ids if value in {str(item) for item in requested_ids}]
    if allowed_ids and not grounding_ids:
        grounding_ids = allowed_ids[:2]

    return {
        "reflection": reflection[:500],
        "action": action,
        "confidence": confidence,
        "grounding_ids": grounding_ids,
    }


def response_instruction(plan: Mapping[str, Any]) -> str:
    """Translate a constrained action into a generation instruction."""
    action = plan.get("action", "mirror")
    instructions = {
        "question": "Ask one brief, open clarification instead of filling the gap with an assumption.",
        "ask": "Ask one brief, open clarification instead of filling the gap with an assumption.",
        "reframe": "Offer one grounded alternative framing without dismissing the user's feeling.",
        "guide": "Offer one small, reversible next step; do not prescribe a complete solution.",
        "nudge": "Offer one small, reversible next step; do not prescribe a complete solution.",
        "reflect": "Reflect one grounded pattern or tension in the user's characteristic language.",
        "mirror": "Reflect one grounded pattern or tension in the user's characteristic language.",
        "ground": "Slow the pace and anchor the response in present, observable details.",
        "validate": "Name why the feeling makes sense without confirming unsupported assumptions.",
        "challenge": "Gently test one assumption using retrieved evidence and an open question.",
        "pause": "Acknowledge the intensity and leave space; do not force an interpretation or solution.",
    }
    return instructions.get(str(action), instructions["mirror"])
