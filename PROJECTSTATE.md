# Card Manager — Project State

## Last Updated
2026-07-24

## One-line Summary
Business card OCR/vision → Google Sheets with OAuth sign-in. Currently switched to vision LLM (OpenRouter, no OCR). Google Sheets via user's own account (OAuth) or service account.

---

## Architecture (Current)

```
Card Image → Vision LLM (OpenRouter) → JSON fields → Google Sheets
                ↑                            ↑
          Nemotron Omni (free)          OAuth (user signs in)
          or gpt-4o-mini ($)            or service account
```

## Current Pipeline

### 1. Vision LLM (no OCR)
- **PaddleOCR/ONNX Runtime REMOVED** — no longer used.
- Image is base64-encoded and sent directly to OpenRouter vision model.
- Model sees the image and returns JSON: name, company, position, phone, email.
- Configured in `config.py`: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`.
- Current model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` (free tier, ~7s latency).
- Alternative (faster): `openai/gpt-4o-mini` (~$0.0001/card, ~1s latency).

### 2. Google Sheets (two auth modes)
- **OAuth** (default): User signs in with Google → picks their sheet → data saved. Set `GOOGLE_OAUTH_ENABLED = True`.
- **Service account**: Uses `credentials.json` and fixed sheet ID. Used when OAuth is disabled.

### 3. Sheet Columns (no Timestamp)
| Card Holder Name | Company Name | Position | Phone Number | Email Address |
|---|---|---|---|---|

---

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — Streamlit UI (no CLI mode used currently) |
| `config.py` | LLM settings, OAuth config, sheet ID |
| `info_extractor.py` | Vision LLM extraction — sends image to OpenRouter |
| `sheets_writer.py` | Google Sheets API (service account + OAuth) |
| `ocr_engine.py` | ❌ NOT USED (kept for reference) |
| `image_processor.py` | ❌ NOT USED (kept for reference) |
| `excel_writer.py` | ❌ NOT USED (Excel export was removed) |
| `setup_google_sheets.py` | Setup helper |
| `oauth_client_secret.json` | Google OAuth client credentials (Web app type) |
| `credentials.json` | Service account key |

---

## Session History (2026-07-23 to 2026-07-24)

### Original State
- Project used PaddleOCR v5 + ONNX Runtime for text recognition.
- Scoring-based extraction (heuristics + regex) for all fields.
- Google Sheets via service account.
- Tested 5/5 on synthetic cards. Failed on real card2.jpeg (all-caps name put as company, address put as name).

### Changes Made

#### LLM Integration (Round 1)
- Added `extract_with_llm()` in info_extractor.py — sends OCR text to OpenRouter for name/position/company extraction.
- Kept regex for phone/email.
- Used `openai` SDK with OpenRouter base URL.
- Model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`.
- **Issue**: The free Nemotron model was unreliable — confused addresses with names, swapped fields.

#### Scoring Fixes (tried, then reverted)
- Tried adding `_is_address_line()` to reject address patterns.
- Tried changing entity assignment priority (name before company).
- Tried ALL-CAPS name scoring adjustments.
- Tried email-domain company fallback.
- **All reverted** — user said "don't work card specific."

#### Google Sheets → Excel → Google Sheets
- Moved to Excel writer (`excel_writer.py`) — no Google Cloud setup needed.
- **Issue**: Excel download button wasn't updating after extraction (race condition).
- Reverted back to Google Sheets with OAuth support.

#### OAuth Flow (long struggle)
- Initially used Desktop app OAuth client with `urn:ietf:wg:oauth:2.0:oob` redirect.
- Google deprecated OOB flow — got `error 400: invalid_request`.
- Switched to Web application client with `http://localhost:8501` redirect.
- Got `redirect_uri_mismatch` — URI wasn't authorized.
- Added redirect URI in Google Cloud Console → still mismatch.
- Discovered PKCE code verifier was being auto-generated but lost on redirect.
- Fixed: save `flow.code_verifier` to disk before redirect, restore on callback.
- **Current OAuth flow**: 
  - User clicks "Continue with Google"
  - Auth URL with PKCE generated → saved to `~/.claude/card-auth-state.json`
  - User authorizes → Google redirects to `http://127.0.0.1:8501/?code=...`
  - New Streamlit session detects code in URL → reads saved verifier → exchanges code
  - Token saved to `~/.claude/card-manager-oauth-token.pickle`
- **Last known issue**: OAuth sign-in redirects but app still shows sign-in page (session state lost on redirect).

#### Vision LLM (no OCR)
- Removed PaddleOCR entirely.
- `info_extractor.py` rewritten — sends image directly to vision model.
- No OCR engine, no ONNX Runtime, no model downloads.
- Headers in sheets simplified: removed Timestamp column.
- New sheets auto-create with headers: Name, Company, Position, Phone, Email.

### Known Issues
1. **Vision LLM needs API key** — paste `LLM_API_KEY` in `config.py`.
2. **OAuth sign-in flow** — code verifier is saved/restored but Streamlit session state is lost on redirect (new session is created when Google redirects back).
3. **Web app OAuth client** needs `http://127.0.0.1:8501` as authorized redirect URI in Google Cloud Console.
4. **Free Nemotron model** is slow (~7s per request) and may be unreliable. Switch to `openai/gpt-4o-mini` for production.

### Cost
| Component | Cost |
|-----------|------|
| Vision LLM (Nemotron free) | **$0.00** |
| Vision LLM (gpt-4o-mini) | ~$0.003/card |
| Google Sheets API | **$0.00** |

### To Make the App Work Now
1. Set `LLM_API_KEY` in `config.py` to your OpenRouter API key.
2. Ensure `http://127.0.0.1:8501` is in authorized redirect URIs for the Web application OAuth client in Google Cloud Console.
3. Run: `python -m streamlit run main.py -- --ui`
