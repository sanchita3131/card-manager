# Card Manager — Project State

## Last Updated
2026-07-23

## One-line Summary
Business card OCR → Google Sheets with hybrid extraction (LLM for name/position/company, regex for phone/email). Uses PaddleOCR v5 via ONNX Runtime, OpenRouter API, Google Sheets API.

---

## Architecture

```
Card Image → [NO preprocessing] → PaddleOCR (ONNX Runtime) → Hybrid extractor → Google Sheets
                                        ↑                         ↑
                                  PP-OCRv5_server_det     OpenRouter LLM (name/pos/co)
                                  en_PP-OCRv5_mobile_rec  Regex (phone/email)
                                  engine='onnxruntime'     Scoring fallback
```

## Key Design Decisions

### 1. NO image preprocessing
- Previous versions applied binary thresholding (CLAHE + adaptive threshold) which DESTROYED text
- PaddleOCR is trained on natural images — feed it the raw photo
- `image_processor.py` now just returns the original path unchanged

### 2. Hybrid extraction: LLM + regex
- **Email & Phone**: regex (near-perfect, cheap, fast — stays as-is)
- **Name, Position, Company**: OpenRouter LLM (context-aware, handles ambiguity)
- **Fallback**: Scoring system in `info_extractor.py` kicks in if LLM is unavailable
- Uses OpenAI-compatible SDK with OpenRouter's API

### 3. PaddleOCR 3.7 + ONNX Runtime
- PaddleOCR 3.7 uses PaddleX under the hood
- `engine='onnxruntime'` kwarg eliminates PaddlePaddle dependency
- PP-OCRv5 has ONNX-packaged models (v3 and v4 don't)
- Models auto-download on first run (~30 MB total)

### 4. Google Sheets via service account
- Service account: `card-manager-sa@card-manager-project-123.iam.gserviceaccount.com`
- Key file: `credentials.json` (in project root)
- Sheet: "Card Manager - Business Cards" (ID: `1IA8IpheEntBOsgHV67DZ4kC56B1Y9LOtN0P3IUWmk0c`)
- Owner: `sanchitawork31@gmail.com`

## File Map

| File | Purpose | Key Functions |
|------|---------|---------------|
| `main.py` | Entry point — CLI + Streamlit UI | `process_card()`, `cli_main()`, `_launch_streamlit()` |
| `image_processor.py` | Image handling | `prepare()` — returns original path, no-op |
| `ocr_engine.py` | OCR via PaddleOCR + ONNX | `extract_text()` → list of (text, conf, bbox) |
| `info_extractor.py` | Field extraction (hybrid LLM + regex) | `extract_info_from_boxes()` → dict of 5 fields |
|                    |                                         | `extract_with_llm()` → OpenRouter API call       |
|                    |                                         | `score_line()` → fallback heuristics              |
| `sheets_writer.py` | Google Sheets integration | `initialize_sheet()`, `append_card()`, `get_all_cards()` |
| `config.py` | Configuration | Sheet ID, credentials path, OCR language |
| `setup_google_sheets.py` | Interactive Google setup | Step-by-step guide |

## Dependencies

```
opencv-python        # Image loading (minimal use)
paddleocr>=2.8.0     # OCR engine (uses PaddleX 3.x)
onnxruntime          # Inference backend
gspread              # Google Sheets API
google-auth          # Auth for sheets
streamlit            # Web UI
```

All in `requirements.txt`. Models auto-download: `PP-OCRv5_server_det_onnx` + `en_PP-OCRv5_mobile_rec_onnx`.

## Known Issues

1. **Phone cleanup** — OCR sometimes includes labels ("Phone:", "Tel:", "M:")
   - `PHONE_RE.search()` handles most inline cases
   - But "Phone: +1 (555) 123-4567" → "+1 (555) 123-4567" (keeps prefix if in same bbox)

2. **LLM depends on internet + API key** — if OpenRouter is unreachable or no API key set
   - Falls back to scoring system (still works, less accurate on edge cases)
   - Configure `LLM_ENABLED = False` in config.py to skip LLM entirely

3. **Streamlit UI restart needed after code changes**
   - Must kill old process: `kill $(lsof -ti:8501)`
   - Then restart: `python -m streamlit run main.py -- --ui`

## Cost per card

| Component | Cost |
|-----------|------|
| PaddleOCR (local ONNX) | **$0.00** |
| OpenRouter (gpt-4o-mini) | **~$0.0001** (~150 input tokens, ~30 output tokens) |
| Google Sheets API | **$0.00** |
| **Total** | **~$0.0001/card** ($0.01 per 100 cards) |

## Google Cloud Resources

- Project: `card-manager-project-123`
- APIs enabled: `sheets.googleapis.com`, `drive.googleapis.com`
- Service account: `card-manager-sa@card-manager-project-123.iam.gserviceaccount.com`
- Credentials file: `credentials.json` (in project root)
- User: `sanchitawork31@gmail.com`
- gcloud CLI installed via brew

## Running

```bash
cd /Users/sanchitapathak/Claude_Code/Projects/card_manager
source venv/bin/activate

# CLI
python main.py --image ~/Desktop/card.jpg --sheet

# Web UI
python -m streamlit run main.py -- --ui
```

## Testing

Test script creates synthetic cards with different layouts (standard, compact, all-caps, name-at-bottom). Run with:

```bash
source venv/bin/activate
python3 -c "
from ocr_engine import OCREngine
from info_extractor import extract_info_from_boxes
ocr = OCREngine(lang='en', use_onnx=True)
items = ocr.extract_text('/path/to/card.jpg')
info = extract_info_from_boxes(items)
print(info)
"
```

## Extraction Accuracy

Tested layouts (all pass):
- Standard (header + name + position + contact) → 5/5
- Compact (no dividers, tight spacing) → 5/5
- Simple (left-aligned, no dividers) → 5/5  
- Name at bottom (company → division → position → name) → 5/5
- All-caps company (ORACLE) → 5/5

## Fix History

1. **Removed image preprocessing** — was binary-thresholding images, destroying text
2. **Removed zone splitting** — was using fixed header/body/contact zones, too fragile
3. **Scoring system** — each line scored for company/name/position, highest wins
4. **Position before name** — position assigned first (keyword-based = reliable), name after
5. **Corporate word penalty** — "Division", "Group", "Solutions" penalized in name scoring
6. **Lowered OCR thresholds** — text_det_thresh=0.2, box_thresh=0.2, rec_score_thresh=0.1
7. **Auto-save to sheet** — UI now extracts AND saves in one click
8. **Fixed phone formula issue** — changed `USER_ENTERED` to `RAW` so `+1...` isn't treated as formula

---

## Current Extraction Flow (Hybrid LLM + Regex)

```
OCR lines → LLM (OpenRouter) tries for name/position/company     (Round 0)
         ↓
         → Regex extracts email + phone from ALL text             (Round 1)
         ↓
         → Scoring fills any fields LLM didn't get                (Rounds 2-5)
```

- **Round 0**: OpenRouter API receives OCR text lines with position hints → returns JSON
- **Round 1**: Regex extracts email/phone (always runs, near-perfect)
- **Rounds 2-5 (fallback)**: Scoring system fills any fields still null — position keywords, company suffix matching, capitalization analysis, font-size heuristics
- If LLM is unavailable (no key, network issue, API error), the scoring system runs as fallback — still works, just less accurate on edge cases

## LLM Details

- **Provider**: OpenRouter (OpenAI-compatible API)
- **SDK**: `openai` Python library with custom `base_url`
- **Default model**: `openai/gpt-4o-mini` (~$0.15/M input tokens) — ~150 tokens/card ≈ $0.0001/card
- **Alternatives**: Change `LLM_MODEL` in config.py — works with any OpenRouter model
- **Toggle**: Set `LLM_ENABLED = False` to use pure scoring (no API calls at all)

## Fix History

1. **Removed image preprocessing** — was binary-thresholding images, destroying text
2. **Removed zone splitting** — was using fixed header/body/contact zones, too fragile
3. **Scoring system** — each line scored for company/name/position, highest wins
4. **Position before name** — position assigned first (keyword-based = reliable), name after
5. **Corporate word penalty** — "Division", "Group", "Solutions" penalized in name scoring
6. **Lowered OCR thresholds** — text_det_thresh=0.2, box_thresh=0.2, rec_score_thresh=0.1
7. **Auto-save to sheet** — UI now extracts AND saves in one click
8. **Fixed phone formula issue** — changed `USER_ENTERED` to `RAW` so `+1...` isn't treated as formula
9. **Hybrid LLM extraction** — name/position/company via OpenRouter, regex for phone/email, scoring fallback
