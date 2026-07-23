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

# ─── LLM (Vision) Settings ────────────────────────────────────────────────────
# Sends the card image directly to a vision LLM (no OCR needed).
LLM_ENABLED = True
LLM_PROVIDER = "openrouter"
LLM_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
# LLM_MODEL = "openai/gpt-4o-mini"  # Faster, ~$0.0001/card
LLM_API_KEY = ""  # ← Paste your OpenRouter API key here

# ─── Google Account ───────────────────────────────────────────────────────────
# The Google account that OWNS the sheet (for sharing info)
GOOGLE_ACCOUNT_EMAIL = "sanchitawork31@gmail.com"

# ─── Google OAuth (for user sign-in) ──────────────────────────────────────────
# Set this to True to use OAuth (user signs in with Google) instead of service account
# For OAuth: Go to Google Cloud Console → APIs & Services → Credentials
#   → Create OAuth client ID → "Web application" or "Desktop app"
#   → Set redirect URI to http://localhost:8501 for local testing
#   → Download JSON and save as "oauth_client_secret.json"
GOOGLE_OAUTH_ENABLED = True
GOOGLE_OAUTH_CLIENT_SECRET = "oauth_client_secret.json"
# Scopes the app requests
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
