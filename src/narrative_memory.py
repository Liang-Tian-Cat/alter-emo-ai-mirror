"""Daily narrative persistence and inspectable memory compression."""

from __future__ import annotations

import json
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable

from memory_store import read_ndjson, write_ndjson


NARRATIVE_FIELDS = ("events", "feelings", "choices", "values", "recurring_patterns")


def normalize_narrative(raw: dict[str, Any], original: str, narrative_date: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "date": narrative_date or date.today().isoformat(),
        "created_at": time.time(),
        "original": original.strip(),
    }
    for field in NARRATIVE_FIELDS:
        value = raw.get(field, [])
        if isinstance(value, str):
            value = [value]
        result[field] = [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
    if not result["events"] and original.strip():
        result["events"] = [original.strip()]
    return result


def save_narrative(agent_dir: Path, narrative: dict[str, Any]) -> Path:
    folder = agent_dir / "daily_narratives"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{narrative['date']}-{narrative['id'][:8]}.json"
    target.write_text(json.dumps(narrative, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def list_narratives(agent_dir: Path) -> list[dict[str, Any]]:
    folder = agent_dir / "daily_narratives"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            items.append(value)
    return items


def compress_memory_stream(
    agent_dir: Path,
    summarizer: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    chunk_size: int = 12,
) -> dict[str, Any] | None:
    """Compress a stable chunk once, retaining source nodes for user inspection."""
    stream = agent_dir / "memory_stream"
    nodes = read_ndjson(stream / "nodes.ndjson")
    compressions_path = stream / "compressions.ndjson"
    compressions = read_ndjson(compressions_path)
    already = {str(item) for group in compressions for item in group.get("source_ids", [])}
    candidates = [node for node in nodes if str(node.get("id")) not in already and node.get("type") != "memory_compression"]
    if len(candidates) < chunk_size:
        return None
    chunk = candidates[:chunk_size]
    payload = summarizer(chunk)
    compression = {
        "id": uuid.uuid4().hex,
        "created_at": time.time(),
        "source_ids": [str(node.get("id")) for node in chunk],
        "summary": str(payload.get("summary", "")).strip(),
        "patterns": payload.get("patterns", []),
        "values": payload.get("values", []),
        "open_questions": payload.get("open_questions", []),
    }
    write_ndjson(compressions_path, [*compressions, compression])
    return compression
