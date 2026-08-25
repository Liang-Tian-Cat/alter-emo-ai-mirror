"""Pure scoring helpers for Alter Emo's four-signal memory retrieval."""

from __future__ import annotations

import math
import time
from typing import Any, Dict, Mapping


DEFAULT_WEIGHTS: Dict[str, float] = {
    "semantic": 0.55,
    "emotion": 0.20,
    "salience": 0.15,
    "recency": 0.10,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def normalized_weights(weights: Mapping[str, float] | None = None) -> Dict[str, float]:
    """Return a complete, normalized set of non-negative retrieval weights."""
    supplied = dict(DEFAULT_WEIGHTS if weights is None else weights)
    values = {name: max(0.0, float(supplied.get(name, 0.0))) for name in DEFAULT_WEIGHTS}
    total = sum(values.values())
    if total <= 0.0:
        return dict(DEFAULT_WEIGHTS)
    return {name: value / total for name, value in values.items()}


def salience_score(importance: Any) -> float:
    """Convert the stored 0-100 importance value into a safe 0-1 signal."""
    try:
        return _clamp(float(importance) / 100.0)
    except (TypeError, ValueError):
        return 0.5


def recency_score(
    timestamp: Any,
    *,
    now: float | None = None,
    half_life_days: float = 45.0,
) -> float:
    """Apply exponential decay while keeping undated memories at a neutral score."""
    try:
        created_at = float(timestamp)
    except (TypeError, ValueError):
        return 0.5

    current = time.time() if now is None else float(now)
    age_days = max(0.0, (current - created_at) / 86400.0)
    half_life = max(1.0, float(half_life_days))
    return math.pow(0.5, age_days / half_life)


def score_candidate(
    *,
    semantic: float,
    emotion: float,
    importance: Any,
    timestamp: Any,
    now: float | None = None,
    weights: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    """Score one memory and expose every signal for inspection and logging."""
    signals = {
        "semantic": _clamp(semantic),
        "emotion": _clamp(emotion),
        "salience": salience_score(importance),
        "recency": recency_score(timestamp, now=now),
    }
    resolved_weights = normalized_weights(weights)
    weighted = {
        name: signals[name] * resolved_weights[name]
        for name in DEFAULT_WEIGHTS
    }
    return {
        "score": sum(weighted.values()),
        "signals": signals,
        "weights": resolved_weights,
        "weighted": weighted,
    }
