"""Settings, loaded from .env (if present) and environment variables."""

import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Tiny .env loader so the project needs no extra dependency."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _secret_key() -> str:
    """APP_SECRET from the environment, or a random key persisted to .secret."""
    env = os.getenv("APP_SECRET", "").strip()
    if env:
        return env
    path = ROOT / ".secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


DB_PATH = ROOT / "chatbox.db"
WEB_DIR = ROOT / "web"

SECRET_KEY = _secret_key()
SESSION_COOKIE = "chatbox_session"
SESSION_TTL_HOURS = 24 * 7

# Any OpenAI-compatible endpoint works. No key means mock mode.
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# Shown in the UI so it is obvious which endpoint is answering.
LLM_PROVIDER = urlparse(LLM_BASE_URL).hostname or "custom"

MOCK_MODE = not LLM_API_KEY
