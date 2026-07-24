"""
Configuration for Card Manager.

Secrets are read in this priority order:
  1. Streamlit secrets (st.secrets) — for Streamlit Cloud
  2. Environment variables — for CLI or testing
  3. .env file — local development
  4. Hardcoded defaults below — last resort
"""

import os
from pathlib import Path

# ── Load .env file if it exists (lightweight, no dependency) ────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


def _get(key: str, default: str = "") -> str:
    """Read a config value: Streamlit secrets > env var > .env > default."""
    if _HAS_STREAMLIT:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except RuntimeError:
            pass  # not running in a Streamlit context
    return os.environ.get(key, default)


# ─── Google Sheets ───────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_PATH = "credentials.json"
GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID", "1IA8IpheEntBOsgHV67DZ4kC56B1Y9LOtN0P3IUWmk0c")

# ─── LLM (Vision) Settings ────────────────────────────────────────────────────
LLM_ENABLED = True
LLM_PROVIDER = "openrouter"
LLM_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
# LLM_MODEL = "openai/gpt-4o-mini"  # Faster, ~$0.0001/card
LLM_API_KEY = _get("LLM_API_KEY", "")

# ─── Google Account ───────────────────────────────────────────────────────────
GOOGLE_ACCOUNT_EMAIL = "sanchitawork31@gmail.com"

# ─── Google OAuth (for user sign-in) ──────────────────────────────────────────
GOOGLE_OAUTH_ENABLED = True
GOOGLE_OAUTH_CLIENT_SECRET = "oauth_client_secret.json"
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Redirect URI — override for Streamlit Cloud (set via secrets or env var)
OAUTH_REDIRECT_URI = _get("OAUTH_REDIRECT_URI", "http://127.0.0.1:8501")
