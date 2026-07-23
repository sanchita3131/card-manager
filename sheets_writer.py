"""
Google Sheets integration for card data.

Writes extracted card information to a Google Sheet.
Uses a service account for authentication (no OAuth popup needed).
"""

import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Column headers matching the user's specification
HEADERS = [
    "Company Name",
    "Card Holder Name",
    "Position",
    "Contact Number",
    "Email Address",
    "Timestamp",
]


def _get_google_sheets_client(credentials_path: str):
    """
    Authenticate with Google Sheets using a service account.

    Args:
        credentials_path: Path to the service account JSON key file

    Returns:
        gspread client object
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)
    return client


def initialize_sheet(credentials_path: str, sheet_id: str) -> bool:
    """
    Ensure the target sheet exists and has the correct headers.

    Creates the sheet if it doesn't exist, and writes headers if the
    first row is empty.

    Args:
        credentials_path: Path to service account JSON key
        sheet_id: Google Sheet ID from the sheet URL

    Returns:
        True if successful, False otherwise
    """
    try:
        client = _get_google_sheets_client(credentials_path)
        sheet = client.open_by_key(sheet_id).sheet1

        # Check if headers already exist
        existing = sheet.row_values(1)
        if not existing or existing[0] != HEADERS[0]:
            # Use the worksheet title as the sheet name
            sheet.clear()
            sheet.append_row(HEADERS)
            # Bold headers
            sheet.format("1:1", {"textFormat": {"bold": True}})
            logger.info("Sheet initialized with headers.")
        else:
            logger.info("Sheet already has headers.")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize Google Sheet: {e}")
        return False


def append_card(credentials_path: str, sheet_id: str, card_data: Dict[str, str]) -> bool:
    """
    Append a card entry to the Google Sheet.

    Args:
        credentials_path: Path to service account JSON key
        sheet_id: Google Sheet ID
        card_data: Dict with keys: company, name, position, phone, email

    Returns:
        True if successful, False otherwise
    """
    from datetime import datetime

    try:
        client = _get_google_sheets_client(credentials_path)
        sheet = client.open_by_key(sheet_id).sheet1

        row = [
            card_data.get("company", "null"),
            card_data.get("name", "null"),
            card_data.get("position", "null"),
            card_data.get("phone", "null"),
            card_data.get("email", "null"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ]

        sheet.append_row(row, value_input_option="RAW")
        logger.info(f"Card data written to sheet: {card_data.get('name')}")
        return True

    except Exception as e:
        logger.error(f"Failed to write to Google Sheet: {e}")
        return False


def get_all_cards(credentials_path: str, sheet_id: str) -> Optional[List[Dict[str, str]]]:
    """
    Retrieve all card entries from the sheet.

    Args:
        credentials_path: Path to service account JSON key
        sheet_id: Google Sheet ID

    Returns:
        List of dicts, or None on error
    """
    try:
        client = _get_google_sheets_client(credentials_path)
        sheet = client.open_by_key(sheet_id).sheet1

        records = sheet.get_all_records()
        return records

    except Exception as e:
        logger.error(f"Failed to read from Google Sheet: {e}")
        return None
