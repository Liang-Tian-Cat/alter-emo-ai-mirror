"""Deterministic language-style measurements that complement LLM reflection."""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev
from typing import Any, Iterable


def measure_style(messages: Iterable[str]) -> dict[str, Any]:
    texts = [str(item).strip() for item in messages if str(item).strip()]
    lengths = [len(item) for item in texts]
    sentences = [part.strip() for text in texts for part in re.split(r"[。！？.!?]+", text) if part.strip()]
    sentence_lengths = [len(item) for item in sentences]
    latin_words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", " ".join(texts).lower())
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,4}", " ".join(texts))
    stop = {"because", "that", "this", "with", "have", "就是", "然后", "这个", "那个", "觉得"}
    recurring = [word for word, count in Counter(latin_words + chinese_chunks).most_common(12) if count > 1 and word not in stop][:8]
    avg_length = round(mean(lengths), 1) if lengths else 0.0
    avg_sentence = round(mean(sentence_lengths), 1) if sentence_lengths else 0.0
    variation = round(pstdev(sentence_lengths), 1) if len(sentence_lengths) > 1 else 0.0
    return {
        "message_length": {
            "average_characters": avg_length,
            "range": [min(lengths), max(lengths)] if lengths else [0, 0],
        },
        "sentence_rhythm": {
            "average_characters": avg_sentence,
            "variation": variation,
            "sentence_count": len(sentence_lengths),
        },
        "reply_cadence": {
            "messages_observed": len(texts),
            "average_sentences_per_message": round(len(sentences) / len(texts), 2) if texts else 0.0,
        },
        "recurring_vocabulary": recurring,
    }
