"""Create a clean persona workspace for interviews and mirror sessions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from agent_io import load_or_init_meta
from runtime_config import PROJECT_ROOT


def safe_persona_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    if not cleaned:
        raise ValueError("Persona id must contain at least one letter or number.")
    return cleaned


def create_persona(pseudonym: str, agents_dir: Path | None = None) -> Path:
    persona_id = safe_persona_id(pseudonym)
    base = agents_dir or (PROJECT_ROOT / "agents")
    agent_dir = base / persona_id
    (agent_dir / "memory_stream").mkdir(parents=True, exist_ok=True)

    meta_path = agent_dir / "meta.json"
    meta = load_or_init_meta(str(meta_path), persona_id)
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    return agent_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Alter Emo persona workspace")
    parser.add_argument("--id", required=True, help="Persona id, for example demo-persona")
    args = parser.parse_args()
    created = create_persona(args.id)
    print(f"✅ Persona workspace ready: {created}")


if __name__ == "__main__":
    main()
