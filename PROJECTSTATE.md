# Card Manager — Project State

## Last Updated
2026-07-24

## One-line Summary
Business card → vision LLM → Google Sheets. Hosted on Streamlit Cloud. Google OAuth sign-in, auto-creates a sheet, saves name/company/position/phone/email/domain. No warnings, no re-asking.

---

## Architecture (Current)

```
User uploads card image → Streamlit Cloud
         ↓
info_extractor.py — base64 → OpenRouter Vision LLM → JSON
         ↓
sheets_writer.py  — OAuth → Google Sheets (auto-created per user)
```

## Hosting
- **Platform**: Streamlit Community Cloud (`https://card-manager.streamlit.app`)
- **Secrets**: Set via Streamlit Cloud dashboard (no tracked secrets in repo)
- **OAuth Redirect**: `https://card-manager.streamlit.app` (registered in Google Cloud Console)
- **OAuth Status**: Published (In Production), no verification needed

## Pipeline

### 1. Vision LLM (`info_extractor.py`)
- Image → base64 → OpenRouter vision LLM (Nemotron Omni free or gpt-4o-mini)
- Returns JSON: name, company, position, phone, email, **domain**
- `phone` includes ALL numbers found (mobile, office, fax — comma separated)
- `domain` classifies industry: IT Company, Automation, Research, Healthcare, etc.
- `response_format={"type": "json_object"}`, temperature=0.0

### 2. Google Sheets (`sheets_writer.py`)
- **OAuth** (only): User signs in with Google → app creates "Card Manager - Business Cards" sheet
- Sheet ID persisted per-browser via JSON file (also used locally)
- **Token stored in browser session only** — no server-side file sharing, no cross-device leaks
- Column headers auto-created on first save

**Sheet columns**:
| Card Holder Name | Company Name | Position | Phone Number | Email Address | Domain |

### 3. Streamlit UI (`main.py`)
**Flow**:
1. Landing page → "Continue with Google"
2. Google OAuth consent (once) → redirect back
3. Auto-creates sheet → sidebar shows **Open Sheet** link
4. Upload card → Extract & Save → results displayed

**Auth Architecture**:
- PKCE flow with code_verifier saved to disk (handles Streamlit session loss on redirect)
- Token stored in `st.session_state.oauth_creds` — per-browser-session, never shared
- `get_oauth_client()` checks session state first, falls back to local pickle for dev
- `access_type="offline"` ensures Google remembers consent

## Files

| File | Status | Purpose |
|------|--------|---------|
| `main.py` | ✅ Active | Streamlit UI, OAuth flow, entry point |
| `config.py` | ✅ Active | Config with env/secret overrides |
| `info_extractor.py` | ✅ Active | Vision LLM — sends image to OpenRouter |
| `sheets_writer.py` | ✅ Active | Google Sheets API (OAuth + service account) |
| `.streamlit/secrets.toml.example` | ✅ Active | Streamlit secrets template |
| `ocr_engine.py` | ❌ Dead | PaddleOCR wrapper — not imported |
| `image_processor.py` | ❌ Dead | No-op passthrough |
| `excel_writer.py` | ❌ Dead | Excel export — replaced by Google Sheets |
| `setup_google_sheets.py` | 🟡 Legacy | Service account setup guide |
| `error.md` | 🟡 Doc | Old scoring error analysis |
| `workflow.html` | 🟡 Doc | Workflow explainer (outdated) |

## Google Cloud Console Setup
- **Project**: `card-manager-project-123`
- **OAuth consent screen**: Published (In Production), app name "Card Manager"
- **OAuth client**: Web application, authorized redirect URIs: `https://card-manager.streamlit.app` (and `http://127.0.0.1:8501` for local)
- **Scopes**: `spreadsheets` + `drive.file`
- **OAuth client secret**: `oauth_client_secret.json` (gitignored), also configurable via Streamlit secrets

## Known Issues
1. **Free Nemotron model is slow** (~7s/card). Switch to `openai/gpt-4o-mini` for production.
2. **Code verifier saved to disk** — works but hacky. Streamlit session lost on redirect, file bridges the gap.

## GitHub
- Repo: `https://github.com/sanchita3131/card-manager`
- Key gitignored files: `oauth_client_secret.json`, `credentials.json`, `.streamlit/secrets.toml`, `.env`

## Running Locally
```bash
cd /Users/sanchitapathak/Claude_Code/Projects/card_manager
source venv/bin/activate
streamlit run main.py
```
