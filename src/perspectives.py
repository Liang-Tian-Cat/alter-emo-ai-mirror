"""Selectable reflection perspectives for the AI mirror."""

from __future__ import annotations

from typing import Any


PERSPECTIVES: dict[str, dict[str, Any]] = {
    "balanced": {
        "name": "Balanced mirror",
        "description": "Balances feelings, evidence, relationships, and action.",
        "priorities": ["clarity", "empathy", "agency"],
        "instruction": "Balance emotional acknowledgement with one grounded observation.",
    },
    "efficiency": {
        "name": "Efficiency-focused",
        "description": "Surfaces constraints, trade-offs, and the smallest reversible next step.",
        "priorities": ["constraints", "trade-offs", "next action"],
        "instruction": "Be concise; identify the key constraint and one reversible next action.",
    },
    "relationship": {
        "name": "Relationship-focused",
        "description": "Examines needs, boundaries, repair, and the other person's perspective.",
        "priorities": ["needs", "boundaries", "repair"],
        "instruction": "Notice relational needs and boundaries without mind-reading the other person.",
    },
    "clarity": {
        "name": "Clarity-seeking",
        "description": "Separates observations, interpretations, feelings, and unknowns.",
        "priorities": ["evidence", "assumptions", "unknowns"],
        "instruction": "Separate observable facts from interpretation and ask when evidence is missing.",
    },
    "tone": {
        "name": "Tone-sensitive",
        "description": "Pays close attention to emotional intensity, pacing, and wording.",
        "priorities": ["emotional intensity", "cadence", "language"],
        "instruction": "Match the user's emotional pace and wording while preserving healthy distance.",
    },
}


def resolve_perspective(value: str | None) -> tuple[str, dict[str, Any]]:
    key = (value or "balanced").strip().lower()
    if key not in PERSPECTIVES:
        raise ValueError(f"Unknown perspective: {value}")
    return key, dict(PERSPECTIVES[key])


def list_perspectives() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in PERSPECTIVES.items()]
