"""Inspectable and user-controllable persistent persona storage."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_ndjson(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


class PersonaMemoryStore:
    def __init__(self, agent_dir: Path):
        self.agent_dir = agent_dir.resolve()
        self.stream = self.agent_dir / "memory_stream"

    @property
    def nodes_path(self) -> Path:
        return self.stream / "nodes.ndjson"

    def list(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        rows = read_ndjson(self.nodes_path)
        page = rows[max(0, offset):max(0, offset) + max(1, min(limit, 500))]
        return {"items": page, "total": len(rows), "offset": max(0, offset), "limit": max(1, min(limit, 500))}

    def revise(
        self,
        memory_id: str,
        changes: dict[str, Any],
        *,
        event_embedder: Callable[[str], list[float]] | None = None,
    ) -> dict[str, Any]:
        self._invalidate_compressions(memory_id)
        rows = read_ndjson(self.nodes_path)
        found: dict[str, Any] | None = None
        allowed = {"content", "summary", "importance", "emotion_tag"}
        for row in rows:
            if str(row.get("id")) != memory_id:
                continue
            for key in allowed:
                if key in changes:
                    row[key] = changes[key]
            row["user_revised"] = True
            found = row
            break
        if found is None:
            raise KeyError(f"Unknown memory: {memory_id}")
        write_ndjson(self.nodes_path, rows)
        if event_embedder is not None and "content" in changes:
            vectors = read_ndjson(self.stream / "embeddings_event.ndjson")
            replacement = event_embedder(str(found.get("content", "")))
            for item in vectors:
                if str(item.get("id")) == memory_id:
                    item["vec"] = replacement
                    break
            write_ndjson(self.stream / "embeddings_event.ndjson", vectors)
        self._sync_legacy(rows)
        return found

    def delete(self, memory_id: str) -> None:
        self._invalidate_compressions(memory_id)
        rows = read_ndjson(self.nodes_path)
        kept = [row for row in rows if str(row.get("id")) != memory_id]
        if len(kept) == len(rows):
            raise KeyError(f"Unknown memory: {memory_id}")
        write_ndjson(self.nodes_path, kept)
        for filename in ("embeddings_event.ndjson", "embeddings_emotion.ndjson"):
            path = self.stream / filename
            write_ndjson(path, [row for row in read_ndjson(path) if str(row.get("id")) != memory_id])
        self._sync_legacy(kept)

    def delete_all(self) -> None:
        if self.agent_dir.exists():
            shutil.rmtree(self.agent_dir)

    def export_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            if self.agent_dir.exists():
                for path in self.agent_dir.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(self.agent_dir).as_posix())
        return buffer.getvalue()

    def _sync_legacy(self, rows: list[dict[str, Any]]) -> None:
        self.stream.mkdir(parents=True, exist_ok=True)
        legacy_nodes = [{k: v for k, v in row.items() if k != "emotion_tag"} for row in rows]
        (self.stream / "nodes.json").write_text(
            json.dumps(legacy_nodes, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        event_vectors = {str(row.get("id")): row.get("vec") for row in read_ndjson(self.stream / "embeddings_event.ndjson")}
        (self.stream / "embeddings.json").write_text(
            json.dumps([event_vectors.get(str(row.get("id"))) for row in rows], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _invalidate_compressions(self, memory_id: str) -> None:
        """Remove summaries derived from a memory before it is changed/deleted."""
        path = self.stream / "compressions.ndjson"
        groups = read_ndjson(path)
        affected = [group for group in groups if memory_id in {str(item) for item in group.get("source_ids", [])}]
        if not affected:
            return
        derived_ids = {str(group.get("memory_node_id")) for group in affected if group.get("memory_node_id")}
        write_ndjson(path, [group for group in groups if group not in affected])
        if derived_ids:
            nodes = [row for row in read_ndjson(self.nodes_path) if str(row.get("id")) not in derived_ids]
            write_ndjson(self.nodes_path, nodes)
            for filename in ("embeddings_event.ndjson", "embeddings_emotion.ndjson"):
                vector_path = self.stream / filename
                write_ndjson(vector_path, [row for row in read_ndjson(vector_path) if str(row.get("id")) not in derived_ids])
