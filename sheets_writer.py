"""
Google Sheets integration — supports two auth modes:
  1. Service account (server-to-server, no user interaction)
  2. OAuth 2.0 (user signs in with their own Google account)
"""

import logging
import os
import pickle
import json
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = [
    "Card Holder Name",
    "Company Name",
    "Position",
    "Phone Number",
    "Email Address",
    "Domain",
]

# ─── Service Account Auth ─────────────────────────────────────────────────


def _get_service_account_client(credentials_path: str):
    """Authenticate with Google Sheets using a service account."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    return gspread.authorize(creds)


# ─── OAuth 2.0 Auth (user signs in with Google) ──────────────────────────


def get_oauth_client():
    """
    Create a gspread client from stored OAuth credentials.

    Priority:
      1. Current browser session (st.session_state) — Streamlit Cloud
      2. Pickle file on disk — local development only
    """
    import gspread
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None

    # 1. Check browser session first (per-user, never shared across devices)
    try:
        import streamlit as st
        creds = st.session_state.get("oauth_creds")
    except (ImportError, RuntimeError, AttributeError):
        pass

    # 2. Fallback to pickle file (local dev only — never on Streamlit Cloud)
    if not creds:
        token_path = os.path.expanduser("~/.claude/card-manager-oauth-token.pickle")
        if os.path.exists(token_path):
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

    if not creds:
        return None

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        try:
            import streamlit as st
            st.session_state["oauth_creds"] = creds
        except (ImportError, RuntimeError):
            pass

    if not creds or not creds.valid:
        return None

    return gspread.authorize(creds)


def save_oauth_token(creds):
    """Persist OAuth credentials for reuse."""
    import pickle

    path = os.path.expanduser("~/.claude")
    os.makedirs(path, exist_ok=True)
    token_path = os.path.join(path, "card-manager-oauth-token.pickle")
    with open(token_path, "wb") as f:
        pickle.dump(creds, f)
    logger.info("OAuth token saved.")


def clear_oauth_token():
    """Remove stored OAuth token and saved sheet ID (sign out)."""
    token_path = os.path.expanduser("~/.claude/card-manager-oauth-token.pickle")
    if os.path.exists(token_path):
        os.remove(token_path)
        logger.info("OAuth token cleared.")
    sheet_path = os.path.expanduser("~/.claude/card-manager-sheet-id.json")
    if os.path.exists(sheet_path):
        os.remove(sheet_path)
        logger.info("Saved sheet ID cleared.")


# ─── Sheet ID Persistence (auto-created sheet) ─────────────────────────────


def save_sheet_id(sheet_id: str):
    """Remember the auto-created sheet ID for next time."""
    path = os.path.expanduser("~/.claude")
    os.makedirs(path, exist_ok=True)
    sheet_path = os.path.join(path, "card-manager-sheet-id.json")
    with open(sheet_path, "w") as f:
        json.dump({"sheet_id": sheet_id}, f)
    logger.info("Sheet ID saved.")


def get_saved_sheet_id() -> Optional[str]:
    """Load the previously saved sheet ID, if any."""
    sheet_path = os.path.expanduser("~/.claude/card-manager-sheet-id.json")
    try:
        with open(sheet_path) as f:
            return json.load(f)["sheet_id"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


# ─── Sheet Operations ────────────────────────────────────────────────────


def _get_client(credentials_path: str = None, oauth: bool = False):
    """Get a gspread client using the preferred auth method."""
    if oauth:
        client = get_oauth_client()
        if client:
            return client
        raise PermissionError("Not authenticated with Google. Sign in first.")
    if credentials_path:
        return _get_service_account_client(credentials_path)
    raise ValueError("No authentication method available.")


def initialize_sheet(credentials_path: str = None, sheet_id: str = None,
                     oauth: bool = False, oauth_sheet_id: str = None) -> bool:
    """
    Ensure the target sheet exists and has the correct headers.

    Args:
        credentials_path: Path to service account JSON key (service acct mode)
        sheet_id: Sheet ID (service acct mode)
        oauth: Use OAuth authentication
        oauth_sheet_id: Sheet ID (OAuth mode)

    Returns:
        True if successful, False otherwise
    """
    try:
        sid = oauth_sheet_id if oauth else sheet_id
        client = _get_client(credentials_path, oauth)
        sheet = client.open_by_key(sid).sheet1

        existing = sheet.row_values(1)
        if not existing or existing[0] != HEADERS[0]:
            sheet.clear()
            sheet.append_row(HEADERS)
            sheet.format("1:1", {"textFormat": {"bold": True}})
            logger.info("Sheet initialized with headers.")
        else:
            logger.info("Sheet already has headers.")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize Google Sheet: {e}")
        return False


def append_card(credentials_path: str = None, sheet_id: str = None,
                card_data: Dict[str, str] = None,
                oauth: bool = False, oauth_sheet_id: str = None) -> bool:
    """
    Append a card entry to the Google Sheet.

    Args:
        credentials_path: Path to service account JSON key (service acct mode)
        sheet_id: Sheet ID (service acct mode)
        card_data: Dict with keys: company, name, position, phone, email
        oauth: Use OAuth authentication
        oauth_sheet_id: Sheet ID (OAuth mode)

    Returns:
        True if successful, False otherwise
    """
    try:
        sid = oauth_sheet_id if oauth else sheet_id
        client = _get_client(credentials_path, oauth)
        sheet = client.open_by_key(sid).sheet1

        row = [
            card_data.get("name", "null"),
            card_data.get("company", "null"),
            card_data.get("position", "null"),
            card_data.get("phone", "null"),
            card_data.get("email", "null"),
            card_data.get("domain", "null"),
        ]

        sheet.append_row(row, value_input_option="RAW")
        logger.info(f"Card data written to sheet: {card_data.get('name')}")
        return True

    except Exception as e:
        logger.error(f"Failed to write to Google Sheet: {e}")
        return False


def get_all_cards(credentials_path: str = None, sheet_id: str = None,
                  oauth: bool = False, oauth_sheet_id: str = None) -> Optional[List[Dict[str, str]]]:
    """
    Retrieve all card entries from the sheet.
    """
    try:
        sid = oauth_sheet_id if oauth else sheet_id
        client = _get_client(credentials_path, oauth)
        sheet = client.open_by_key(sid).sheet1
        return sheet.get_all_records()

    except Exception as e:
        logger.error(f"Failed to read from Google Sheet: {e}")
        return None


def list_user_sheets(client) -> List[dict]:
    """
    List sheets the authenticated user has access to.
    Only used in OAuth mode.
    """
    try:
        sheet_list = client.openall()
        return [
            {"id": s.id, "title": s.title, "url": f"https://docs.google.com/spreadsheets/d/{s.id}/edit"}
            for s in sheet_list[:20]
        ]
    except Exception as e:
        logger.error(f"Failed to list sheets: {e}")
        return []
