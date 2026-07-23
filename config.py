"""
Configuration for Card Manager.

Edit the values below to match your setup.
"""

# ─── Google Sheets ───────────────────────────────────────────────────────────
# 1. Go to https://console.cloud.google.com/
# 2. Create a project → Enable "Google Sheets API"
# 3. Go to "Credentials" → "Create Credentials" → "Service Account"
# 4. Download the JSON key file and save it somewhere safe
# 5. Share your Google Sheet with the service account email (from the JSON key)
# 6. Put the path to the JSON key below and the Sheet ID from your sheet URL

GOOGLE_CREDENTIALS_PATH = "credentials.json"
GOOGLE_SHEET_ID = "1IA8IpheEntBOsgHV67DZ4kC56B1Y9LOtN0P3IUWmk0c"

# ─── OCR Settings ─────────────────────────────────────────────────────────────
# Language for OCR: 'en' for English
OCR_LANGUAGE = "en"

# ─── Image Processing ─────────────────────────────────────────────────────────
# Target DPI for preprocessing
TARGET_DPI = 300

# ─── Google Account ───────────────────────────────────────────────────────────
# The Google account that OWNS the sheet (for sharing info)
GOOGLE_ACCOUNT_EMAIL = "sanchitawork31@gmail.com"

# ─── LLM (Hybrid Extraction) ──────────────────────────────────────────────────
# Name, position, and company are extracted via LLM (OpenRouter API).
# Email and phone still use regex (near-perfect).
# The scoring system in info_extractor.py acts as fallback if the API is down.

LLM_ENABLED = True                  # Set False to fallback to pure heuristics
LLM_PROVIDER = "openrouter"         # openrouter
LLM_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"   # Cheap & fast (~$0.15/M tokens input)
# LLM_MODEL = "anthropic/claude-3-5-haiku"  # Alternative if you prefer Claude
# LLM_MODEL = "google/gemini-2.0-flash-lite-001"  # Cheapest option
LLM_API_KEY = ""                    # ← Paste your OpenRouter API key here
