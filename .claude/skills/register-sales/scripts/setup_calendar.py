#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
#   "httpx>=0.25.0",
# ]
# ///
"""
Google Calendar OAuth setup for a sales representative.

Uses the existing CalendarConnector to generate an OAuth URL,
then completes the auth flow with the user's code.

Usage:
    PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/setup_calendar.py --telegram-id <ID>
"""

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Add src to path for imports
src_dir = Path(__file__).resolve().parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_dir))

load_dotenv()

console = Console()


async def main():
    parser = argparse.ArgumentParser(description="Set up Google Calendar for a sales rep")
    parser.add_argument("--telegram-id", type=int, required=True, help="Telegram ID of the rep")
    args = parser.parse_args()

    telegram_id = args.telegram_id

    console.print(Panel(
        f"[bold blue]Google Calendar Setup[/bold blue]\n"
        f"Setting up calendar for rep with Telegram ID: {telegram_id}",
        width=console.width,
    ))

    # Initialize database
    from sales_agent.database import init_database

    try:
        await init_database()
    except RuntimeError as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        return

    # Verify rep exists
    from sales_agent.registry.sales_rep_manager import get_by_telegram_id, update_calendar_connected, close_pool

    rep = await get_by_telegram_id(telegram_id)
    if not rep:
        console.print(f"[red]No sales rep found with Telegram ID: {telegram_id}[/red]")
        await close_pool()
        return

    console.print(f"[green]Found rep: {rep.name} (@{rep.telegram_username})[/green]")

    # Initialize calendar connector
    from sales_agent.registry.calendar_connector import CalendarConnector

    connector = CalendarConnector()
    if not connector.enabled:
        console.print(Panel(
            "[red]Google Calendar integration not configured.[/red]\n\n"
            "Set these environment variables in .env:\n"
            "  GOOGLE_CLIENT_ID=your_client_id\n"
            "  GOOGLE_CLIENT_SECRET=your_client_secret\n\n"
            "Get OAuth credentials at:\n"
            "  https://console.cloud.google.com/apis/credentials",
            width=console.width,
        ))
        await close_pool()
        return

    # Check if already connected
    if connector.is_connected(telegram_id):
        console.print(f"[yellow]Calendar already connected for {rep.name}.[/yellow]")
        reconnect = Prompt.ask("Reconnect?", choices=["yes", "no"], default="no")
        if reconnect != "yes":
            await close_pool()
            return

    # Generate OAuth URL
    try:
        auth_url = connector.get_auth_url(telegram_id)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        await close_pool()
        return

    console.print(Panel(
        "[bold]Step 1: Open this URL in your browser:[/bold]\n\n"
        f"{auth_url}\n\n"
        "[bold]Step 2: Authorize access and copy the code.[/bold]",
        width=console.width,
    ))

    # Get the authorization code
    code = Prompt.ask("\n[cyan]Paste the authorization code here[/cyan]")
    if not code.strip():
        console.print("[red]No code provided.[/red]")
        await close_pool()
        return

    # Complete auth
    console.print("[bold]Completing OAuth flow...[/bold]")
    success = await connector.complete_auth(telegram_id, code.strip())

    if success:
        await update_calendar_connected(telegram_id, True)
        console.print(Panel(
            f"[bold green]Calendar connected for {rep.name}![/bold green]\n\n"
            "Google Calendar events will now be available for scheduling.",
            width=console.width,
        ))
    else:
        console.print("[red]OAuth flow failed. Please check the code and try again.[/red]")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
