#!/usr/bin/env python3
"""
Card Manager — Extract business card details using vision LLM and save to Google Sheets.

Usage:
    python -m streamlit run main.py -- --ui
"""

import argparse
import logging
import sys
from pathlib import Path
import re

from config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_SHEET_ID,
    GOOGLE_OAUTH_ENABLED,
    GOOGLE_OAUTH_SCOPES,
    OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_CLIENT_SECRET,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_BASE_URL,
)
from info_extractor import extract_info_from_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("card_manager")


def process_card(image_path: str, api_key: str = None) -> dict:
    """Send image to vision LLM and extract card fields."""
    path = Path(image_path)
    if not path.exists():
        logger.error(f"File not found: {image_path}")
        return dict(name="null", company="null", position="null",
                    phone="null", email="null")

    logger.info(f"\n{'='*50}")
    logger.info(f"Processing: {path.name}")
    logger.info(f"{'='*50}")

    card_info = extract_info_from_image(
        image_path,
        api_key=api_key or LLM_API_KEY,
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
    )

    logger.info(f"\n  ┌─ Extracted ────────────────────────────────────────────┐")
    logger.info(f"  │ Name     : {card_info['name']:<40}│")
    logger.info(f"  │ Company  : {card_info['company']:<40}│")
    logger.info(f"  │ Position : {card_info['position']:<40}│")
    logger.info(f"  │ Phone    : {card_info['phone']:<40}│")
    logger.info(f"  │ Email    : {card_info['email']:<40}│")
    logger.info(f"  │ Domain   : {card_info.get('domain', 'null'):<40}│")
    logger.info(f"  └──────────────────────────────────────────────────────────┘")

    return card_info


def cli_main():
    parser = argparse.ArgumentParser(
        description="Card Manager — Extract business card data to Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--image", "-i", nargs="+", help="Path(s) to business card image(s)")
    parser.add_argument("--sheet", "-s", action="store_true", help="Write results to Google Sheet")
    parser.add_argument("--init-sheet", action="store_true", help="Initialize the Google Sheet with headers")
    parser.add_argument("--list", action="store_true", help="List all cards from the Google Sheet")
    parser.add_argument("--ui", action="store_true", help="Launch the Streamlit web interface")

    args, _ = parser.parse_known_args()

    if args.ui:
        _launch_streamlit()
        return

    if args.init_sheet:
        _run_init_sheet()
        return

    if args.list:
        _run_list_cards()
        return

    for img_path in (args.image or []):
        card_info = process_card(img_path)
        if args.sheet:
            _write_to_sheet(card_info)

    if not args.image:
        parser.print_help()


def _run_init_sheet():
    from sheets_writer import initialize_sheet
    logger.info("Initializing Google Sheet...")
    success = initialize_sheet(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
    logger.info("Done!" if success else "Failed.")


def _run_list_cards():
    from sheets_writer import get_all_cards
    records = get_all_cards(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
    if not records:
        logger.info("No cards found.")
        return
    print(f"\nTotal cards: {len(records)}")
    for i, card in enumerate(records, 1):
        print(f"  {i}. {card.get('Card Holder Name', '?')} | {card.get('Company Name', '?')} | {card.get('Position', '?')}")
        print(f"     {card.get('Phone Number', '?')}  {card.get('Email Address', '?')}")


def _write_to_sheet(card_info: dict) -> bool:
    from sheets_writer import append_card, initialize_sheet
    try:
        initialize_sheet(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID)
        return append_card(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, card_info)
    except Exception as e:
        logger.error(f"Sheet write failed: {e}")
        return False


def _launch_streamlit():
    import streamlit as st
    import tempfile
    from PIL import Image
    import time
    import pandas as pd
    from sheets_writer import (
        initialize_sheet, append_card, get_all_cards,
        get_oauth_client, save_oauth_token, clear_oauth_token,
        save_sheet_id, get_saved_sheet_id, find_or_create_sheet,
        save_llm_api_key, get_saved_llm_api_key, clear_llm_api_key,
    )
    from config import (
        GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID,
        GOOGLE_OAUTH_ENABLED, LLM_API_KEY as DEFAULT_LLM_API_KEY,
    )

    st.set_page_config(page_title="Card Manager", page_icon="💳", layout="centered")

    # Session state
    for key in ("sheet_id", "auth_method", "oauth_authd", "oauth_active"):
        if key not in st.session_state:
            st.session_state[key] = "service_account" if key == "auth_method" else (False if key != "sheet_id" else None)

    if GOOGLE_OAUTH_ENABLED and get_oauth_client() and not st.session_state.oauth_authd:
        st.session_state.oauth_authd = True
        st.session_state.auth_method = "oauth"
        # Auto-load the saved sheet ID and LLM key if they exist, so a
        # returning login never has to redo either.
        saved_id = get_saved_sheet_id()
        if saved_id:
            st.session_state.sheet_id = saved_id
        saved_key = get_saved_llm_api_key()
        if saved_key and "llm_api_key" not in st.session_state:
            st.session_state.llm_api_key = saved_key

    # Handle OAuth callback
    if GOOGLE_OAUTH_ENABLED and not st.session_state.oauth_authd and st.query_params.get("code"):
        _handle_oauth_callback(st)
        return

    # LANDING
    if GOOGLE_OAUTH_ENABLED and not st.session_state.oauth_authd and not st.session_state.oauth_active:
        st.title("💳 Card Manager")
        st.write("Upload a business card. We extract the details and save them to your Google Sheet.")

        c1, c2, c3 = st.columns(3)
        c1.metric("📸", "Upload", "Snap a photo")
        c2.metric("⚡", "Extract", "AI reads it")
        c3.metric("📊", "Save", "To your sheet")

        st.divider()
        st.subheader("Sign in with Google")
        st.write("Connect your account to save cards to your own spreadsheet.")
        if st.button("Continue with Google", type="primary"):
            st.session_state.oauth_active = True
            st.rerun()
        st.caption("Your data goes to your Google account.")
        return

    # OAUTH FLOW
    if GOOGLE_OAUTH_ENABLED and st.session_state.oauth_active and not st.session_state.oauth_authd:
        _render_oauth(st)
        return

    # AUTHENTICATED
    is_oauth = (st.session_state.auth_method == "oauth" and st.session_state.oauth_authd)

    with st.sidebar:
        st.header("Card Manager")
        if is_oauth:
            st.success("Google account connected")
            if not st.session_state.sheet_id:
                # No manual "create sheet" step — always reuse the one sheet
                # tied to this account, creating it only if it's truly missing.
                _ensure_sheet(st)
            if st.session_state.sheet_id:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{st.session_state.sheet_id}/edit"
                st.markdown(f"📊 **[Open Sheet]({sheet_url})**")

            st.divider()
            st.caption("🔑 LLM API Key")
            if st.session_state.get("llm_api_key") and not st.session_state.get("editing_llm_key"):
                st.text(f"Saved: ••••{st.session_state.llm_api_key[-4:]}")
                if st.button("Change key"):
                    st.session_state.editing_llm_key = True
                    st.rerun()
            else:
                key_input = st.text_input(
                    "Your LLM API key (e.g. OpenRouter)", type="password", key="llm_key_input",
                )
                if st.button("Save key", type="primary") and key_input.strip():
                    st.session_state.llm_api_key = key_input.strip()
                    save_llm_api_key(key_input.strip())
                    st.session_state.pop("editing_llm_key", None)
                    st.rerun()

            if st.button("Disconnect"):
                clear_oauth_token()
                clear_llm_api_key()
                for _k in ("oauth_authd", "sheet_id", "oauth_active", "oauth_creds", "llm_api_key", "editing_llm_key"):
                    st.session_state.pop(_k, None)
                st.rerun()

    st.subheader("Scan a Card")
    st.write("Upload a business card photo.")

    uf = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "webp", "bmp"])

    if uf is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uf.name).suffix or ".jpg") as tmp:
            tmp.write(uf.getvalue())
            img_path = tmp.name

        c1, c2 = st.columns(2)
        with c1:
            st.image(Image.open(uf), use_container_width=True)
        with c2:
            if st.button("Extract & Save", type="primary", use_container_width=True):
                if not st.session_state.sheet_id:
                    st.error("Set a sheet ID in the sidebar first.")
                else:
                    bar = st.progress(0)
                    status = st.empty()

                    effective_llm_key = st.session_state.get("llm_api_key") or DEFAULT_LLM_API_KEY
                    if not effective_llm_key:
                        st.error("No LLM API key set. Add one in the sidebar.")
                    else:
                        status.info("Analyzing card with vision AI...")
                        bar.progress(30)

                        info = process_card(img_path, api_key=effective_llm_key)

                        bar.progress(60)
                        status.info("Setting up sheet headers...")
                        initialize_sheet(
                            credentials_path=GOOGLE_CREDENTIALS_PATH, sheet_id=GOOGLE_SHEET_ID,
                            oauth=is_oauth, oauth_sheet_id=st.session_state.sheet_id,
                        )

                        status.info("Saving to Google Sheets...")
                        bar.progress(85)

                        ok = append_card(
                            credentials_path=GOOGLE_CREDENTIALS_PATH, sheet_id=GOOGLE_SHEET_ID,
                            card_data=info, oauth=is_oauth, oauth_sheet_id=st.session_state.sheet_id,
                        )

                        if ok:
                            bar.progress(100)
                            status.success("Saved to Google Sheet!")
                            st.json(info)
                        else:
                            st.error("Failed to save.")

                    time.sleep(1.5)
                    status.empty()
                    bar.empty()

    if st.session_state.sheet_id and st.button("Refresh entries"):
        recs = get_all_cards(
            credentials_path=GOOGLE_CREDENTIALS_PATH, sheet_id=GOOGLE_SHEET_ID,
            oauth=is_oauth, oauth_sheet_id=st.session_state.sheet_id,
        )
        if recs:
            st.dataframe(pd.DataFrame(recs).tail(10), use_container_width=True, hide_index=True)


def _get_oauth_flow(redirect_uri: str | None = None):
    """
    Create a Google OAuth Flow object.

    Works both locally (reads oauth_client_secret.json from disk)
    and on Streamlit Cloud (reads individual secret fields).
    """
    from google_auth_oauthlib.flow import Flow
    import json, os
    from pathlib import Path

    if redirect_uri is None:
        redirect_uri = OAUTH_REDIRECT_URI

    # Option 1: Individual OAuth fields from Streamlit secrets / env vars
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        try:
            import streamlit as st
            client_id = client_id or st.secrets.get("GOOGLE_CLIENT_ID")
            client_secret = client_secret or st.secrets.get("GOOGLE_CLIENT_SECRET")
        except (ImportError, RuntimeError):
            pass

    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "project_id": os.environ.get("GOOGLE_PROJECT_ID", "card-manager-project-123"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri,
        )

    # Option 2: Full OAuth config JSON (legacy)
    client_config_json = os.environ.get("GOOGLE_OAUTH_CLIENT_CONFIG")
    if not client_config_json:
        try:
            import streamlit as st
            client_config_json = st.secrets.get("GOOGLE_OAUTH_CLIENT_CONFIG")
        except (ImportError, RuntimeError):
            pass

    if client_config_json:
        client_config = json.loads(client_config_json.strip())
        return Flow.from_client_config(
            client_config,
            scopes=GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri,
        )

    # Option 3: Local file (development)
    secret_path = Path(__file__).parent / GOOGLE_OAUTH_CLIENT_SECRET
    if secret_path.exists():
        return Flow.from_client_secrets_file(
            str(secret_path),
            scopes=GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri,
        )

    raise FileNotFoundError(
        "No OAuth client config found. "
        "Set the GOOGLE_OAUTH_CLIENT_CONFIG env var/secret, "
        "or place oauth_client_secret.json in the project root."
    )


def _handle_oauth_callback(st):
    import json, os

    state_path = os.path.expanduser("~/.claude/card-auth-state.json")

    if not os.path.exists(state_path):
        st.error("Session expired. Go back and try again.")
        return

    try:
        with open(state_path) as f:
            saved = json.load(f)
        os.remove(state_path)

        flow = _get_oauth_flow()
        flow.code_verifier = saved["cv"]

        flow.fetch_token(code=st.query_params.get("code"))
        # Store in browser session only — never in a shared server file
        st.session_state["oauth_creds"] = flow.credentials

        # Find or create the user's sheet (one user = one sheet for life)
        try:
            client = get_oauth_client()
            if client:
                sheet = find_or_create_sheet(client)
                st.session_state.sheet_id = sheet.id
        except Exception as e:
            import logging
            logging.getLogger("card_manager").warning(f"Sheet setup failed (will retry on first save): {e}")

        # Load a previously saved LLM key, if any, so it doesn't need re-entry
        from sheets_writer import get_saved_llm_api_key
        saved_key = get_saved_llm_api_key()
        if saved_key:
            st.session_state["llm_api_key"] = saved_key

        st.session_state.oauth_authd = True
        st.session_state.auth_method = "oauth"
        st.session_state.oauth_active = False
        st.query_params.clear()
        st.success("Connected!")
        st.rerun()
    except Exception as e:
        st.error(f"Connection failed: {e}")


def _render_oauth(st):
    import json, os
    from pathlib import Path

    # Validate we have OAuth config somewhere (file, env var, or individual fields)
    secret_path = Path(__file__).parent / "oauth_client_secret.json"
    has_config = secret_path.exists()

    # Check for OAuth config in env vars or Streamlit secrets
    for check_key in ("GOOGLE_OAUTH_CLIENT_CONFIG", "GOOGLE_CLIENT_ID"):
        if os.environ.get(check_key):
            has_config = True
            break
        try:
            if st.secrets.get(check_key):
                has_config = True
                break
        except (ImportError, RuntimeError):
            pass

    if not has_config:
        st.error("OAuth config missing. Set GOOGLE_OAUTH_CLIENT_CONFIG or add oauth_client_secret.json")
        st.session_state.oauth_active = False
        return

    state_path = os.path.expanduser("~/.claude/card-auth-state.json")

    flow = _get_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",  # get a refresh token so Google remembers you
    )

    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump({"cv": flow.code_verifier}, f)

    st.title("Connect Google Sheets")
    st.write("Click below to sign in with Google.")
    st.link_button("Open Google Sign-in", auth_url, use_container_width=True)

    if st.button("Back", use_container_width=True):
        st.session_state.oauth_active = False
        st.rerun()


def _ensure_sheet(st):
    """
    Load the account's one-and-only sheet into session state, creating it
    only the very first time. Called silently — never exposed as a manual
    "create new sheet" action, so returning users always land on the same
    sheet their earlier cards were saved to.
    """
    from sheets_writer import get_oauth_client, find_or_create_sheet

    client = get_oauth_client()
    if not client:
        st.error("Not authenticated.")
        return
    try:
        sheet = find_or_create_sheet(client)
        st.session_state.sheet_id = sheet.id
        st.rerun()
    except Exception as e:
        st.error(f"Failed to set up sheet: {e}")


if __name__ == "__main__":
    # Auto-launch Streamlit UI when running under `streamlit run` (Streamlit Cloud)
    try:
        import streamlit.runtime.scriptrunner as _sr
        _is_streamlit = _sr.get_script_run_ctx() is not None
    except Exception:
        _is_streamlit = False

    if _is_streamlit:
        _launch_streamlit()
    else:
        cli_main()
