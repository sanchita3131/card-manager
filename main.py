#!/usr/bin/env python3
"""
Card Manager — Extract details from business card images and save to Google Sheets.

Uses OpenCV for image processing + PaddleOCR (ONNX Runtime) for OCR.
Hybrid extraction: regex for email/phone, LLM (OpenRouter) for name/position/company.

Usage:
    # Process a single card
    python main.py --image path/to/card.jpg

    # Process and write to Google Sheets (after setup)
    python main.py --image path/to/card.jpg --sheet

    # Initialize Google Sheet headers
    python main.py --init-sheet

    # Process multiple cards
    python main.py --image path/to/card1.jpg path/to/card2.jpg --sheet

    # Interactive web UI (Streamlit)
    python -m streamlit run main.py -- --ui
"""

import argparse
import logging
import sys
from pathlib import Path

from config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_SHEET_ID,
    OCR_LANGUAGE,
    LLM_ENABLED,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_BASE_URL,
)
from image_processor import prepare
from ocr_engine import OCREngine
from info_extractor import extract_info_from_boxes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("card_manager")


def process_card(
    image_path: str,
    ocr_engine: OCREngine,
    use_llm: bool = LLM_ENABLED,
    llm_api_key: str = LLM_API_KEY,
    llm_model: str = LLM_MODEL,
    llm_base_url: str = LLM_BASE_URL,
) -> dict:
    """
    Process a single business card image end-to-end.

    Steps:
      1. Preprocess image (OpenCV: deskew, denoise, enhance contrast)
      2. Run OCR (PaddleOCR via ONNX Runtime)
      3. Extract fields (LLM + regex for name/pos/co; regex for phone/email)

    Args:
        image_path: Path to the card image file
        ocr_engine: Initialized OCR engine
        use_llm: Try LLM extraction for name/position/company
        llm_api_key: OpenRouter API key
        llm_model: Model name (e.g. "openai/gpt-4o-mini")
        llm_base_url: OpenRouter API base URL

    Returns:
        Dict with keys: company, name, position, phone, email
    """
    path = Path(image_path)
    if not path.exists():
        logger.error(f"File not found: {image_path}")
        return {"company": "null", "name": "null", "position": "null",
                "phone": "null", "email": "null"}

    logger.info(f"\n{'='*50}")
    logger.info(f"Processing: {path.name}")
    logger.info(f"{'='*50}")

    # Step 1: Lightly prepare image (resize + mild deskew, keep color)
    logger.info("  [1/3] Preparing image...")
    ocr_image_path = prepare(image_path)
    logger.info(f"  -> Prepared image: {Path(ocr_image_path).name}")

    # Step 2: OCR with bounding boxes
    logger.info("  [2/3] Running OCR (ONNX Runtime + PaddleOCR)...")
    items = ocr_engine.extract_text(ocr_image_path)  # (text, conf, bbox) tuples

    # Display raw OCR output
    if items:
        logger.info("  -> Text detected (top→bottom):")
        for text, conf, bbox in items:
            logger.info(f"     [{conf:.2f}] {text}")
    else:
        logger.warning("  -> No text detected!")
        Path(ocr_image_path).unlink(missing_ok=True)
        return {"company": "null", "name": "null", "position": "null",
                "phone": "null", "email": "null"}

    # Clean up temp file
    Path(ocr_image_path).unlink(missing_ok=True)

    # Step 3: Extract information (hybrid — LLM + regex)
    mode = "LLM + regex" if use_llm and llm_api_key else "scoring + regex"
    logger.info(f"  [3/3] Extracting fields ({mode})...")
    card_info = extract_info_from_boxes(
        items,
        use_llm=use_llm,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
    )

    logger.info(f"\n  ┌─ Extracted Card Info ─────────────────────────────┐")
    logger.info(f"  │ Company    : {card_info['company']:<40}│")
    logger.info(f"  │ Name       : {card_info['name']:<40}│")
    logger.info(f"  │ Position   : {card_info['position']:<40}│")
    logger.info(f"  │ Phone      : {card_info['phone']:<40}│")
    logger.info(f"  │ Email      : {card_info['email']:<40}│")
    logger.info(f"  └─────────────────────────────────────────────────────┘")

    return card_info


def cli_main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Card Manager — Extract business card data to Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --image card.jpg
  python main.py --image card1.jpg card2.jpg --sheet
  python main.py --init-sheet
  python main.py --list
        """,
    )
    parser.add_argument(
        "--image", "-i",
        nargs="+",
        help="Path(s) to business card image(s)",
    )
    parser.add_argument(
        "--sheet", "-s",
        action="store_true",
        help="Write results to Google Sheet",
    )
    parser.add_argument(
        "--init-sheet",
        action="store_true",
        help="Initialize the Google Sheet with headers (run once)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all cards from the Google Sheet",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the Streamlit web interface",
    )

    args, _ = parser.parse_known_args()

    if args.ui:
        _launch_streamlit()
        return

    # Sheet operations
    if args.init_sheet:
        _run_init_sheet()
        return

    if args.list:
        _run_list_cards()
        return

    if not args.image:
        parser.print_help()
        logger.error("\nPlease provide at least one image path with --image")
        sys.exit(1)

    # Initialize OCR engine (once, reused across multiple cards)
    ocr_engine = OCREngine(lang=OCR_LANGUAGE, use_onnx=True)

    for img_path in args.image:
        card_info = process_card(img_path, ocr_engine)

        if args.sheet:
            _write_to_sheet(card_info)

        print()  # spacing between cards

    logger.info("Done.")


def _run_init_sheet():
    """Initialize the Google Sheet with headers."""
    from sheets_writer import initialize_sheet

    logger.info("Initializing Google Sheet...")

    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        logger.error(
            "Please set GOOGLE_SHEET_ID in config.py first.\n"
            "1. Create a Google Sheet\n"
            "2. Copy the Sheet ID from the URL\n"
            "3. Set it in config.py"
        )
        sys.exit(1)

    success = initialize_sheet(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
    if success:
        logger.info("✅ Sheet initialized successfully!")
    else:
        logger.error("❌ Failed to initialize sheet. Check credentials.")


def _run_list_cards():
    """List all cards from the Google Sheet."""
    from sheets_writer import get_all_cards

    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        logger.error("Please set GOOGLE_SHEET_ID in config.py first.")
        sys.exit(1)

    records = get_all_cards(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
    if records is None:
        logger.error("Failed to read sheet.")
        return

    if not records:
        logger.info("No cards found in the sheet.")
        return

    print(f"\n{'─'*70}")
    print(f"Total cards: {len(records)}")
    print(f"{'─'*70}")
    for i, card in enumerate(records, 1):
        print(f"  {i}. {card.get('Card Holder Name', '?')} | {card.get('Company Name', '?')} | {card.get('Position', '?')}")
        print(f"     📞 {card.get('Contact Number', '?')}  ✉️ {card.get('Email Address', '?')}")
        print()


def _write_to_sheet(card_info: dict) -> bool:
    """Write card info to Google Sheet. Returns True on success."""
    from sheets_writer import append_card, initialize_sheet

    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        logger.error("Sheet ID not configured.")
        return False

    try:
        initialize_sheet(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
        return append_card(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, card_info)
    except Exception as e:
        logger.error(f"Sheet write failed: {e}")
        return False


def _launch_streamlit():
    """Launch Streamlit web UI."""
    import streamlit as st
    import tempfile
    from PIL import Image
    import time

    st.set_page_config(
        page_title="Card Manager",
        page_icon="💳",
        layout="centered",
    )

    # ─── Custom CSS for cleaner look ────────────────────────────────────────
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .stButton > button { width: 100%; }
        .card-result { padding: 0.75rem; }
        </style>
    """, unsafe_allow_html=True)

    st.title("💳 Card Manager")
    st.caption("Upload a business card — extracts details and saves to Google Sheets.")

    # Initialize OCR engine once
    if "ocr" not in st.session_state:
        with st.spinner("Loading OCR engine (ONNX models)..."):
            st.session_state.ocr = OCREngine(lang=OCR_LANGUAGE, use_onnx=True)

    # ─── Upload ──────────────────────────────────────────────────────────────
    uploaded_file = st.file_uploader(
        "Choose a business card image",
        type=["jpg", "jpeg", "png", "webp", "bmp"],
        label_visibility="collapsed",
    )

    # ─── Main area (only shows after upload) ────────────────────────────────
    if uploaded_file is not None:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        # Image column + action column
        img_col, result_col = st.columns([1, 1], gap="medium")

        with img_col:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Card", use_container_width=True)

        with result_col:
            extract_btn = st.button("🔍 Extract & Save", type="primary")

        if extract_btn:
            # Progress indicators (full width, below the columns)
            progress_bar = st.progress(0)
            status = st.empty()

            status.info("🔎 Running OCR (ONNX Runtime)...")
            progress_bar.progress(30)

            card_info = process_card(tmp_path, st.session_state.ocr)

            status.info("📋 Extracting fields...")
            progress_bar.progress(60)

            # Display results in a clean card
            with st.container(border=True):
                st.markdown("### 📇 Extracted Info")
                for label, value, icon in [
                    ("Company", card_info["company"], "🏢"),
                    ("Name", card_info["name"], "👤"),
                    ("Position", card_info["position"], "💼"),
                    ("Phone", card_info["phone"], "📞"),
                    ("Email", card_info["email"], "✉️"),
                ]:
                    st.markdown(
                        f"<div style='display:flex; gap:8px; margin-bottom:6px;'>"
                        f"<span style='min-width:80px; color:#888;'>{icon} {label}</span>"
                        f"<span>{value}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            # Auto-save to Google Sheet
            status.info("💾 Saving to Google Sheet...")
            progress_bar.progress(85)
            saved = _write_to_sheet(card_info)
            if saved:
                result_col.success("✅ Saved to Google Sheet!")
            else:
                result_col.error("❌ Failed to save to sheet. Check console.")

            progress_bar.progress(100)
            status.success("✅ Done!")
            time.sleep(2)
            status.empty()
            progress_bar.empty()

    # ─── Recent entries footer ──────────────────────────────────────────────
    with st.expander("📋 View recent entries"):
        if st.button("Refresh", type="secondary"):
            from sheets_writer import get_all_cards
            records = get_all_cards(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
            if records:
                st.dataframe(records.tail(20), use_container_width=True)
            else:
                st.info("No entries found or sheet not configured.")


if __name__ == "__main__":
    cli_main()
