"""Shared runtime configuration for Alter Emo command-line entry points."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> Dict[str, str]:
    """Load the documented root .env, with src/.env as a legacy fallback."""
    root_env = PROJECT_ROOT / ".env"
    legacy_env = Path(__file__).with_name(".env")
    if root_env.exists():
        load_dotenv(root_env, override=True)
    elif legacy_env.exists():
        load_dotenv(legacy_env, override=True)
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
        "OPENAI_PROJECT": (
            os.getenv("OPENAI_PROJECT", "")
            or os.getenv("OPENAI_PROJECT_ID", "")
        ).strip(),
        "CHAT_MODEL": os.getenv("CHAT_MODEL", "gpt-4o-mini").strip(),
        "EMB_MODEL": os.getenv("EMB_MODEL", "text-embedding-3-small").strip(),
    }


def create_openai_client(settings: Dict[str, str]) -> OpenAI:
    """Create a client only when an API-backed operation is actually requested."""
    api_key = settings.get("OPENAI_API_KEY", "").strip()
    if not api_key or not api_key.startswith("sk-") or len(api_key) < 20:
        raise RuntimeError(
            "OPENAI_API_KEY is missing or malformed. Copy .env.example to .env "
            "in the repository root and add a valid key."
        )

    project = settings.get("OPENAI_PROJECT", "").strip()
    return OpenAI(api_key=api_key, project=project) if project else OpenAI(api_key=api_key)
