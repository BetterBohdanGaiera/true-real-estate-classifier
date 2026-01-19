#!/usr/bin/env python3
"""Google Calendar OAuth Authentication Setup.

Run once to store per-account refresh tokens.
After initial setup, authentication is automatic using stored tokens.

Usage:
    uv run python setup_auth.py --account work
    uv run python setup_auth.py --account personal
"""

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def setup_auth(account_name: str, base_path: Path) -> None:
    """Run OAuth authentication flow and save token.

    Args:
        account_name: Account identifier (e.g., 'work', 'personal')
        base_path: Skill root path
    """
    credentials_path = base_path / "references" / "credentials.json"
    token_path = base_path / "accounts" / f"{account_name}.json"

    if not credentials_path.exists():
        print(f"❌ OAuth Client ID file not found: {credentials_path}")
        print()
        print("Setup instructions:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create or select a project")
        print("3. Go to 'APIs & Services' > 'Credentials'")
        print("4. Create 'OAuth 2.0 Client ID' (Desktop type)")
        print("5. Download JSON → save to references/credentials.json")
        return

    # Check existing token
    if token_path.exists():
        print(f"⚠️  Token for account '{account_name}' already exists.")
        response = input("Overwrite? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled")
            return

    print(f"🔐 Starting authentication for '{account_name}' account...")
    print("When the browser opens, log in with your Google account.")
    print()

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        SCOPES,
    )

    # Receive callback via local server
    creds = flow.run_local_server(port=0)

    # Save token
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        json.dump(json.loads(creds.to_json()), f, indent=2)

    print()
    print(f"✅ Authentication complete! Token saved: {token_path}")
    print(f"   Account: {account_name}")


def list_accounts(base_path: Path) -> None:
    """Print list of registered accounts."""
    accounts_dir = base_path / "accounts"

    if not accounts_dir.exists():
        print("No registered accounts.")
        return

    accounts = [f.stem for f in accounts_dir.glob("*.json")]

    if not accounts:
        print("No registered accounts.")
        return

    print("📋 Registered accounts:")
    for account in accounts:
        print(f"   - {account}")


def main():
    parser = argparse.ArgumentParser(
        description="Google Calendar OAuth authentication setup"
    )
    parser.add_argument(
        "--account",
        "-a",
        help="Account identifier (e.g., work, personal)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List registered accounts",
    )

    args = parser.parse_args()
    base_path = Path(__file__).parent.parent

    if args.list:
        list_accounts(base_path)
        return

    if not args.account:
        parser.print_help()
        print()
        print("Examples:")
        print("  uv run python setup_auth.py --account work")
        print("  uv run python setup_auth.py --account personal")
        print("  uv run python setup_auth.py --list")
        return

    setup_auth(args.account, base_path)


if __name__ == "__main__":
    main()
