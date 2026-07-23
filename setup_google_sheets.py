#!/usr/bin/env python3
"""
Google Sheets Setup Helper.

Guides you through creating a service account and connecting
it to your Google Sheet.
"""

import json
import webbrowser
import sys
from pathlib import Path


def print_step(step: int, title: str):
    print(f"\n{'─'*60}")
    print(f"  STEP {step}: {title}")
    print(f"{'─'*60}")


def main():
    print(f"\n{'='*60}")
    print("  Google Sheets Setup for Card Manager")
    print(f"{'='*60}")

    print_step(1, "Create a Google Cloud Project")
    print("""
  1. Go to: https://console.cloud.google.com/projectcreate
  2. Name: "Card Manager" (or anything you like)
  3. Click "Create"
    """)
    input("  Press Enter after creating the project...")

    print_step(2, "Enable the Google Sheets API")
    print("""
  1. Go to: https://console.cloud.google.com/apis/library/sheets.googleapis.com
  2. Click "Enable"
    """)
    webbrowser.open("https://console.cloud.google.com/apis/library/sheets.googleapis.com")
    input("  Press Enter after enabling the API...")

    print_step(3, "Create a Service Account")
    print("""
  1. Go to: https://console.cloud.google.com/apis/credentials
  2. Click "+ Create Credentials" → "Service Account"
  3. Name: "card-manager-sa"
  4. Click "Create and Continue" (roles are optional)
  5. Click "Done"
    """)
    webbrowser.open("https://console.cloud.google.com/apis/credentials")
    input("  Press Enter after creating the service account...")

    print_step(4, "Download the Service Account Key")
    print("""
  1. On the Credentials page, find your service account
  2. Click the pencil/edit icon next to it
  3. Go to the "Keys" tab
  4. Click "Add Key" → "Create New Key" → "JSON"
  5. The key file will download automatically
  6. Move it to this project folder as "credentials.json"
    """)
    input("  Press Enter after downloading and renaming the key file...")

    # Check if credentials file exists
    creds_path = Path("credentials.json")
    if not creds_path.exists():
        print("  ⚠️  credentials.json not found in current directory.")
        # Try to find any JSON key file
        json_files = list(Path(".").glob("*.json"))
        sa_keys = [f for f in json_files if "key" in f.name.lower() or "service" in f.name.lower() or "credential" in f.name.lower()]
        if sa_keys:
            print(f"  Did you mean: {sa_keys[0].name}?")
            rename = input(f"  Rename it to credentials.json? (y/n): ").strip().lower()
            if rename == "y":
                sa_keys[0].rename(creds_path)
                print("  ✅ Renamed to credentials.json")
            else:
                print("  Please manually rename the file to credentials.json")
        else:
            print("  Please ensure credentials.json exists before continuing.")
    else:
        print("  ✅ credentials.json found!")

    print_step(5, "Share Your Google Sheet")
    print(f"""
  1. Read the service account email from credentials.json
     or look it up in the Google Cloud Console
  2. Create a new Google Sheet at: https://sheets.new
  3. Click "Share" in the top-right
  4. Paste the service account email (xxx@xxx.iam.gserviceaccount.com)
  5. Give "Editor" access → Click "Send"
  6. Copy the Sheet ID from the URL:
     https://docs.google.com/spreadsheets/d/<THIS_IS_THE_ID>/edit
    """)

    # Try to read the service account email
    if creds_path.exists():
        try:
            with open(creds_path) as f:
                creds_data = json.load(f)
            sa_email = creds_data.get("client_email", "unknown")
            print(f"  Your service account email is: {sa_email}")
            print(f"\n  📋  Copied to clipboard (if available)")
        except Exception as e:
            print(f"  Could not read credentials.json: {e}")

    print_step(6, "Update config.py")
    print("""
  Open config.py in this project and set:
    GOOGLE_SHEET_ID = "your-sheet-id-here"
    GOOGLE_CREDENTIALS_PATH = "credentials.json"

  Then run:
    python main.py --init-sheet
    """)

    sheet_id = input("  Enter your Google Sheet ID (or press Enter to do it later): ").strip()
    if sheet_id:
        # Update config.py
        try:
            with open("config.py") as f:
                config = f.read()
            config = config.replace(
                'GOOGLE_SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"',
                f'GOOGLE_SHEET_ID = "{sheet_id}"'
            )
            with open("config.py", "w") as f:
                f.write(config)
            print("  ✅ Sheet ID saved to config.py!")
        except Exception as e:
            print(f"  ⚠️  Could not auto-update config.py: {e}")
            print(f"  Please manually set GOOGLE_SHEET_ID = \"{sheet_id}\" in config.py")

    print(f"\n{'='*60}")
    print("  Setup complete! Run the card manager:")
    print(f"\n    python main.py --image path/to/card.jpg --sheet")
    print(f"\n  Or launch the web UI:")
    print(f"\n    python -m streamlit run main.py -- --ui")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
