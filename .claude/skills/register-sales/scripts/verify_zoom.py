#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Verify Zoom Server-to-Server OAuth integration.

Zoom uses shared credentials - all reps use the same Zoom account.
This script checks if credentials are configured and valid.

Usage:
    PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/verify_zoom.py
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Add src to path for imports
src_dir = Path(__file__).resolve().parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_dir))

load_dotenv()

console = Console()

ZOOM_CREDENTIALS_FILE = Path.home() / ".zoom_credentials" / "credentials.json"


def main():
    console.print(Panel(
        "[bold blue]Zoom Integration Check[/bold blue]\n"
        "Verifying Zoom Server-to-Server OAuth credentials",
        width=console.width,
    ))

    # Check credentials file
    if not ZOOM_CREDENTIALS_FILE.exists():
        console.print(Panel(
            "[red]Zoom credentials not found.[/red]\n\n"
            f"Expected file: {ZOOM_CREDENTIALS_FILE}\n\n"
            "[bold]Setup instructions:[/bold]\n"
            "1. Go to https://marketplace.zoom.us/develop/create\n"
            "2. Create a Server-to-Server OAuth app\n"
            "3. Copy your credentials\n"
            "4. Create the credentials file:\n\n"
            f"   mkdir -p {ZOOM_CREDENTIALS_FILE.parent}\n"
            f'   cat > {ZOOM_CREDENTIALS_FILE} << \'EOF\'\n'
            '   {\n'
            '     "account_id": "YOUR_ACCOUNT_ID",\n'
            '     "client_id": "YOUR_CLIENT_ID",\n'
            '     "client_secret": "YOUR_CLIENT_SECRET"\n'
            '   }\n'
            '   EOF\n\n'
            "All sales reps share the same Zoom account (Server-to-Server OAuth).",
            width=console.width,
        ))
        return

    # Validate credentials file
    try:
        with open(ZOOM_CREDENTIALS_FILE) as f:
            creds = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[red]Failed to read credentials file: {e}[/red]")
        return

    required_fields = ["account_id", "client_id", "client_secret"]
    missing = [f for f in required_fields if not creds.get(f)]

    if missing:
        console.print(f"[red]Missing fields in credentials file: {', '.join(missing)}[/red]")
        return

    # Try importing ZoomBookingService
    try:
        from sales_agent.zoom import ZoomBookingService
        zoom = ZoomBookingService()
        if zoom.enabled:
            console.print(Panel(
                "[bold green]Zoom integration is configured and enabled![/bold green]\n\n"
                f"Credentials file: {ZOOM_CREDENTIALS_FILE}\n"
                f"Account ID: {creds['account_id'][:8]}...\n"
                f"Client ID: {creds['client_id'][:8]}...\n\n"
                "All sales reps share this Zoom account for meeting creation.",
                width=console.width,
            ))
        else:
            console.print("[yellow]ZoomBookingService loaded but reports not enabled.[/yellow]")
    except ImportError:
        console.print(Panel(
            "[yellow]Zoom credentials found but ZoomBookingService module not available.[/yellow]\n\n"
            f"Credentials file: {ZOOM_CREDENTIALS_FILE}\n"
            f"Account ID: {creds['account_id'][:8]}...\n"
            f"Client ID: {creds['client_id'][:8]}...\n\n"
            "The credentials look valid. Install the zoom module if meeting creation is needed.",
            width=console.width,
        ))


if __name__ == "__main__":
    main()
