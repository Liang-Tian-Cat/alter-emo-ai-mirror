"""Five-signal salience gate for long-term Alter Emo memories.

The project page defines S=.30E+.25I+.20R+.15D+.10N.  This module makes
that formula executable and inspectable instead of treating "importance" as
an opaque model score.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


DEFAULT_THRESHOLD = 0.42
WEIGHTS = {
    "emotion": 0.30,
    "identity": 0.25,
    "recurrence": 0.20,
    "decision": 0.15,
    "novelty": 0.10,
}

_IDENTITY_MARKERS = (
    "我", "我的", "对我", "价值", "在乎", "相信", "边界", "习惯",
    "i ", "my ", "value", "believe", "boundary", "usually",
)
_DECISION_MARKERS = (
    "决定", "选择", "打算", "以后", "下一步", "改变", "拒绝", "答应",
    "decide", "choose", "plan", "next", "change", "refuse", "commit",
)
_HIGH_EMOTIONS = {"anger", "fear", "grief", "sadness", "joy", "shame", "愤怒", "恐惧", "悲伤", "羞耻", "兴奋"}


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _tokens(text: str) -> set[str]:
    lowered = (text or "").lower()
    latin = re.findall(r"[a-z0-9']+", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]", lowered)
    return set(latin + chinese)


def _overlap(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _emotion_signal(emotion_tag: Mapping[str, Any] | None, importance: Any) -> float:
    tag = dict(emotion_tag or {})
    for key in ("intensity", "score", "strength"):
        if key in tag:
            value = float(tag[key])
            return _clamp(value / 100.0 if value > 1.0 else value)
    label = str(tag.get("emotion", "neutral")).lower()
    tones = {str(item).lower() for item in tag.get("tone", []) if item}
    base = 0.78 if label in _HIGH_EMOTIONS or tones & _HIGH_EMOTIONS else 0.35
    try:
        model_importance = _clamp(float(importance) / 100.0)
    except (TypeError, ValueError):
        model_importance = 0.5
    return _clamp(base * 0.6 + model_importance * 0.4)


@dataclass(frozen=True)
class SalienceDecision:
    score: float
    threshold: float
    store: bool
    components: dict[str, float]
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_salience(
    text: str,
    *,
    emotion_tag: Mapping[str, Any] | None = None,
    importance: Any = 50,
    existing_memories: Iterable[Mapping[str, Any]] = (),
    threshold: float = DEFAULT_THRESHOLD,
) -> SalienceDecision:
    """Calculate E/I/R/D/N and decide whether text enters long-term memory."""
    normalized = (text or "").strip()
    lowered = normalized.lower()
    comparisons = [
        str(item.get("content") or item.get("summary") or "")
        for item in existing_memories
    ]
    max_overlap = max((_overlap(normalized, item) for item in comparisons), default=0.0)

    identity_hits = sum(1 for marker in _IDENTITY_MARKERS if marker in lowered)
    decision_hits = sum(1 for marker in _DECISION_MARKERS if marker in lowered)
    components = {
        "emotion": _emotion_signal(emotion_tag, importance),
        "identity": _clamp(0.25 + identity_hits * 0.22),
        "recurrence": _clamp(max_overlap * 2.2),
        "decision": _clamp(decision_hits * 0.38),
        "novelty": _clamp(1.0 - max_overlap),
    }
    score = sum(components[name] * WEIGHTS[name] for name in WEIGHTS)
    resolved_threshold = _clamp(threshold)
    return SalienceDecision(
        score=round(score, 6),
        threshold=resolved_threshold,
        store=bool(normalized) and score >= resolved_threshold,
        components={name: round(value, 6) for name, value in components.items()},
        weights=dict(WEIGHTS),
    )
