# Card Manager — Project State

## Last Updated
2026-07-24

## One-line Summary
Business card → vision LLM → Google Sheets. User signs in with Google OAuth, picks a sheet, uploads a card photo, and the vision LLM extracts name/company/position/phone/email directly. No OCR, no setup for users.

---

## Architecture (Current)

```
Card Image → base64 → OpenRouter Vision LLM → JSON → Google Sheets (OAuth)
                         ↑
              Nemotron Omni (free) or gpt-4o-mini ($)
```

No PaddleOCR. No ONNX Runtime. No scoring heuristics. No regex. The model reads the image directly.

## Pipeline

### 1. Vision LLM (`info_extractor.py`)
- Image is base64-encoded and sent to OpenRouter via OpenAI-compatible SDK.
- Prompt tells it to return JSON: name, company, position, phone, email.
- `response_format={"type": "json_object"}` forces structured output.
- No OCR, no preprocessing, no heuristics.
- **Current model**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` (free, ~7s latency)
- **Alternative**: `openai/gpt-4o-mini` (~$0.003/card, ~1s latency, reliable)

### 2. Google Sheets (`sheets_writer.py`)
Two auth modes:
- **OAuth** (primary): User signs in with Google → app gets access to their Drive. Can create new sheets or use existing ones.
- **Service account** (fallback): Uses `credentials.json` and a fixed sheet ID.

Columns (no Timestamp):
| Card Holder Name | Company Name | Position | Phone Number | Email Address |
|---|---|---|---|---|

Headers are auto-created by `initialize_sheet()` before every save.

### 3. Streamlit UI (`main.py`)
Pages:
- **Landing**: Title + 3 step cards + "Continue with Google" button
- **OAuth flow**: Link to Google → user authorizes → redirects back → token saved
- **Main app**: Sidebar (account status, sheet ID input, create sheet button) + upload area + extract button + results + recent entries

OAuth callback flow:
1. User clicks "Open Google Sign-in" → auth URL generated (PKCE enabled)
2. `flow.code_verifier` saved to `~/.claude/card-auth-state.json`
3. Google redirects to `http://127.0.0.1:8501/?code=...`
4. New Streamlit session detects `?code=` → reads saved verifier → exchanges code
5. Token saved to `~/.claude/card-manager-oauth-token.pickle`
6. Session marked authenticated → reruns as main app

## OAuth Setup (Google Cloud Console)
1. Project: `card-manager-project-123`
2. OAuth consent screen: External, app name "Card Manager"
3. OAuth client: **Web application** type, name "Card Manager"
4. **Authorized redirect URIs**: `http://127.0.0.1:8501`
5. Test user: `sanchitawork31@gmail.com`
6. Client secret saved as `oauth_client_secret.json` in project root
7. Env: `GOOGLE_OAUTH_ENABLED = True` in config.py

## Files

| File | Status | Purpose |
|------|--------|---------|
| `main.py` | ✅ Active | Streamlit UI, OAuth flow, entry point |
| `config.py` | ✅ Active | API keys, OAuth settings, model config |
| `info_extractor.py` | ✅ Active | Vision LLM — sends image to OpenRouter |
| `sheets_writer.py` | ✅ Active | Google Sheets API (OAuth + service account) |
| `oc r_engine.py` | ❌ Dead | PaddleOCR wrapper — not imported anywhere |
| `image_processor.py` | ❌ Dead | No-op passthrough — not imported anywhere |
| `excel_writer.py` | ❌ Dead | Excel export — replaced by Google Sheets |
| `setup_google_sheets.py` | 🟡 Legacy | Interactive setup guide for service account |
| `oauth_client_secret.json` | ⚠️ Secret | Google OAuth credentials (gitignored) |
| `credentials.json` | ⚠️ Secret | Service account key (gitignored) |
| `error.md` | 🟡 Doc | Error analysis from session |
| `workflow.html` | 🟡 Doc | Visual workflow explainer |

## Dependencies (`requirements.txt`)
```
opencv-python       # NOT USED (kept for reference)
numpy               # NOT USED
paddleocr           # NOT USED
onnxruntime         # NOT USED
google-auth         # Service account auth
google-api-python-client
google-auth-httplib2
google-auth-oauthlib   # OAuth flow
gspread              # Google Sheets API
openai               # OpenRouter SDK (vision LLM)
streamlit            # Web UI
Pillow              # Image handling
```

## Session History (2026-07-23 — 2026-07-24)

### Phase 1: Original (Scoring + PaddleOCR)
- PaddleOCR v5 via ONNX Runtime for text detection
- Scoring-based extractor: each line scored for name/company/position
- Regex for phone/email
- Google Sheets via service account
- Tested 5/5 on synthetic cards; failed on real card2 (all-caps name, address lines)

### Phase 2: LLM added (text-based)
- Added `extract_with_llm()` sending OCR text to OpenRouter
- Scoring kept as fallback
- Free Nemotron model was unreliable — swapped name/address/company

### Phase 3: Scoring fixes attempted
- Added address detection, all-caps name boost, entity priority reorder, email-domain fallback
- User rejected as "card-specific" — all reverted

### Phase 4: Excel export
- Created `excel_writer.py` — no Google Cloud setup needed
- Streamlit UI switched to download-based Excel
- Race condition with download button (fix: always enable)
- User reverted — wanted Google Sheets

### Phase 5: OAuth sign-in (long struggle)
- **Attempt 1**: Desktop app client + `urn:ietf:wg:oauth:2.0:oob` → Google deprecated OOB, error 400
- **Attempt 2**: `run_local_server()` → blocked Streamlit thread
- **Attempt 3**: Desktop app + `http://localhost` → still error 400
- **Attempt 4**: Web application client + `http://localhost:8501` → `redirect_uri_mismatch`
- **Attempt 5**: Added redirect URI in GC Console → still mismatch (used `127.0.0.1:8501` vs `localhost:8501`)
- **Attempt 6**: Web app + `http://127.0.0.1:8501` → PKCE code verifier lost on redirect
- **Attempt 7**: Save `flow.code_verifier` to disk → callback restores it → exchange succeeds
- **Issue**: Streamlit session lost on redirect (new session, no auth state)

### Phase 6: Vision LLM (no OCR)
- Removed PaddleOCR entirely
- `info_extractor.py` rewritten: sends image directly to vision model
- Headers simplified: removed Timestamp
- Sheet columns: Name, Company, Position, Phone, Email

### Phase 7: Final fixes
- Fixed API key trailing space
- Added `initialize_sheet()` before every save (headers auto-created)
- Pushed to GitHub

## Recent Changes

### 2026-07-24 — Fixed OAuth "asks every time" issue
- Removed `prompt="consent"` from `flow.authorization_url()` — was forcing Google to re-ask for permission on every sign-in
- Replaced with `access_type="offline"`, `include_granted_scopes=True`, `prompt="auto"`
- Now Google remembers consent: user only sees the approval screen once, subsequent sign-ins are silent

## Known Issues

1. **OAuth session lost on redirect** — Google redirects back with `?code=...`, which creates a new Streamlit session without auth state. The `_handle_oauth_callback` function detects the code from URL params and exchanges it, but the flow depends on `~/.claude/card-auth-state.json` being written before the redirect.

2. **Free Nemotron model is slow** (~7s/card). Switch to `openai/gpt-4o-mini` for production.

3. **API key in config.py** — Must be pasted manually after every `git pull` (file is tracked, key is removed before commits).

4. **OAuth client redirect URI** — `http://127.0.0.1:8501` must be in authorized URIs in Google Cloud Console for the Web app client. For production deployment, update to the deployed URL.

## GitHub
- Repo: `https://github.com/sanchita3131/card-manager`
- `.gitignore` excludes: `credentials.json`, `oauth_client_secret.json`, `venv/`, `__pycache__/`
- API key removed before commits (GitHub push protection blocks secrets)

## Running
```bash
cd /Users/sanchitapathak/Claude_Code/Projects/card_manager
source venv/bin/activate
python -m streamlit run main.py -- --ui
```
