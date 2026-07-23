# 💳 Card Manager

Extract business card details from images and save them to Google Sheets — **hybrid LLM + regex extraction**.

## How It Works

```
Card Image → PaddleOCR (ONNX Runtime) → LLM extracts name/position/company → Google Sheets
                                               │
                                         Regex extracts phone/email
                                               │
                                         Scoring system = fallback
```

### Technology Stack
| Component | Tool | Cost |
|-----------|------|------|
| Text recognition | **PaddleOCR** via **ONNX Runtime** | ✅ Free |
| Field extraction | **OpenRouter LLM** (name/position/company) + **regex** (phone/email) | ✅ ~$0.0001/card |
| Fallback | **Scoring heuristics** (no-API backup) | ✅ Free |
| Data storage | **Google Sheets API** | ✅ Free |

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

On first run, PaddleOCR will automatically download its ONNX models (~30 MB total).

### 2. Configure Google Sheets

Run the interactive setup:

```bash
python setup_google_sheets.py
```

Or follow these manual steps:

1. **Create a Google Cloud Project** → Enable **Google Sheets API**
2. **Create a Service Account** → Download JSON key → Save as `credentials.json`
3. **Create a Google Sheet** → Share it with your service account email (Editor)
4. Copy the **Sheet ID** from the URL: `https://docs.google.com/spreadsheets/d/`**`THIS_IS_THE_ID`**`/edit`
5. Update `config.py`:

```python
GOOGLE_SHEET_ID = "your-sheet-id-here"
GOOGLE_CREDENTIALS_PATH = "credentials.json"
```

6. Run once to set up headers:

```bash
python main.py --init-sheet
```

### 3. Set your OpenRouter API key

Get a key from [openrouter.ai/keys](https://openrouter.ai/keys), then set it in `config.py`:

```python
LLM_API_KEY = "sk-or-v1-your-key-here"
```

That's it — name/position/company will now be extracted via LLM. If you leave the key empty, the app falls back to the scoring system automatically.

## Usage

### CLI — Process a single card

```bash
python main.py --image path/to/card.jpg
```

### CLI — Process and save to Google Sheets

```bash
python main.py --image path/to/card.jpg --sheet
```

### CLI — Batch process multiple cards

```bash
python main.py --image card1.jpg card2.jpg card3.jpg --sheet
```

### Web UI — Streamlit interface

```bash
python -m streamlit run main.py -- --ui
```

Open the URL shown in the terminal (usually http://localhost:8501).

### View saved cards

```bash
python main.py --list
```

## Output Format

The Google Sheet has the following columns:

| Company Name | Card Holder Name | Position | Contact Number | Email Address | Timestamp |
|-------------|------------------|----------|---------------|---------------|-----------|
| Acme Corp   | John Doe         | CEO      | +1 555-0123   | john@acme.com | 2026-07-18 14:30:00 |

Missing fields are saved as `null`.

## Cost Comparison

| Approach | Cost per 100 cards |
|----------|-------------------|
| **This tool** (LLM + regex) | **~$0.01** |
| Pure regex/heuristics (this tool, no LLM) | **$0.00** |
| OpenAI GPT-4o (vision) | ~$5.00+ |
| Google Vision API | ~$1.50 |
| AWS Textract | ~$1.50 |

## Accuracy Notes

- **Excellent** for well-lit, flat card photos
- **Good** for angled cards (deskew helps)
- **Phone/Email extraction** is very reliable (strong regex patterns)
- **Name/Position/Company** greatly improved with LLM — handles ambiguity, non-standard layouts, and tricky company names
- If the OpenRouter API is down, falls back to the scoring system automatically
- For best results, photograph cards flat against a dark background with even lighting

## Project Structure

```
card_manager/
├── main.py                 # Entry point (CLI + Streamlit UI)
├── config.py               # Configuration (Sheet ID, API keys, model)
├── image_processor.py      # Image handling (pass-through — no preprocessing)
├── ocr_engine.py           # OCR via PaddleOCR + ONNX Runtime
├── info_extractor.py       # Hybrid extraction: LLM (OpenRouter) + regex + scoring fallback
├── sheets_writer.py        # Google Sheets integration
├── setup_google_sheets.py  # Interactive setup helper
├── requirements.txt        # Python dependencies
└── README.md               # This file
```
