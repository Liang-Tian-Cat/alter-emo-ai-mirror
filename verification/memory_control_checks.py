import json
import os
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from memory_store import PersonaMemoryStore, write_ndjson
from narrative_memory import compress_memory_stream, normalize_narrative, save_narrative


class MemoryControlTests(unittest.TestCase):
    def test_view_revise_delete_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / "persona"
            stream = agent / "memory_stream"
            rows = [{"id": "m1", "content": "old", "summary": "old", "importance": 60}]
            write_ndjson(stream / "nodes.ndjson", rows)
            write_ndjson(stream / "embeddings_event.ndjson", [{"id": "m1", "vec": [1.0]}])
            write_ndjson(stream / "embeddings_emotion.ndjson", [{"id": "m1", "vec": [0.0]}])
            write_ndjson(stream / "compressions.ndjson", [{
                "id": "c1", "source_ids": ["m1"], "memory_node_id": "derived-1"
            }])
            rows.append({"id": "derived-1", "content": "derived", "summary": "derived", "importance": 70})
            write_ndjson(stream / "nodes.ndjson", rows)
            write_ndjson(stream / "embeddings_event.ndjson", [
                {"id": "m1", "vec": [1.0]}, {"id": "derived-1", "vec": [0.2]}
            ])
            store = PersonaMemoryStore(agent)

            self.assertEqual(store.list()["total"], 2)
            revised = store.revise("m1", {"content": "revised"}, event_embedder=lambda _text: [0.5])
            self.assertTrue(revised["user_revised"])
            self.assertEqual(store.list()["total"], 1)
            archive = zipfile.ZipFile(BytesIO(store.export_zip()))
            self.assertIn("memory_stream/nodes.ndjson", archive.namelist())
            store.delete("m1")
            self.assertEqual(store.list()["total"], 0)

    def test_daily_narrative_and_compression_are_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / "persona"
            narrative = normalize_narrative(
                {"events": ["meeting"], "feelings": ["tense"], "choices": ["paused"]},
                "I paused in a tense meeting.",
                "2026-08-25",
            )
            self.assertTrue(save_narrative(agent, narrative).exists())
            nodes = [{"id": f"m{i}", "content": f"memory {i}"} for i in range(12)]
            write_ndjson(agent / "memory_stream" / "nodes.ndjson", nodes)
            result = compress_memory_stream(
                agent,
                lambda items: {"summary": f"{len(items)} grounded memories", "patterns": [], "values": [], "open_questions": []},
            )
            self.assertEqual(result["summary"], "12 grounded memories")
            self.assertEqual(len(result["source_ids"]), 12)


if __name__ == "__main__":
    unittest.main()
