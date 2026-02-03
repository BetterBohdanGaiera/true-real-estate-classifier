#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
#   "telethon>=1.34.0",
#   "httpx>=0.25.0",
# ]
# ///
"""
Interactive CLI to register a new sales representative.

Steps:
1. Prompt for: name, email, telegram_username, phone, agent_display_name
2. Create Telegram session via interactive phone auth
3. Google Calendar OAuth setup
4. Zoom integration verification
5. Save to database (only after all steps pass)

Usage:
    PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py
"""

import asyncio
import json
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

ZOOM_CREDENTIALS_FILE = Path.home() / ".zoom_credentials" / "credentials.json"


async def main():
    console.print(Panel(
        "[bold blue]Sales Rep Registration[/bold blue]\n"
        "Register a new sales representative with Telegram, Google Calendar, and Zoom",
        width=console.width,
    ))

    # =========================================================================
    # Step 1: Collect rep info
    # =========================================================================
    console.print("\n[bold]Step 1/5: Collect rep info[/bold]\n")

    name = Prompt.ask("[cyan]Full name[/cyan]")
    email = Prompt.ask("[cyan]Email[/cyan]")
    telegram_username = Prompt.ask("[cyan]Telegram username[/cyan] (without @)")
    phone = Prompt.ask("[cyan]Phone number[/cyan] (with country code, e.g. +628123456789)")
    agent_display_name = Prompt.ask(
        "[cyan]Agent display name[/cyan] (name shown in messages)",
        default=name,
    )

    # Validate
    if not all([name, email, telegram_username, phone]):
        console.print("[red]All fields are required.[/red]")
        return

    # Clean up username
    telegram_username = telegram_username.lstrip("@")
    session_name = f"rep_{telegram_username}"

    # =========================================================================
    # Step 2: Create & verify Telegram session
    # =========================================================================
    console.print(f"\n[bold]Step 2/5: Create Telegram session for @{telegram_username}[/bold]")
    console.print("[dim]Telethon will send a verification code to the phone. Enter it when prompted.[/dim]\n")

    from sales_agent.telegram.telegram_fetch import create_session

    try:
        account_info = await create_session(session_name, phone)
    except Exception as e:
        console.print(f"[red]Failed to create Telegram session: {e}[/red]")
        return

    telegram_id = account_info["id"]
    console.print(f"[green]Session created for {account_info['first_name']} (ID: {telegram_id})[/green]")

    # Verify session
    console.print("\n[bold]Verifying session...[/bold]")
    from sales_agent.telegram.telegram_fetch import get_client_for_rep

    try:
        client = await get_client_for_rep(session_name)
        me = await client.get_me()
        console.print(f"[green]Session verified: {me.first_name} (@{me.username})[/green]")
        await client.disconnect()
    except Exception as e:
        console.print(f"[red]Session verification failed: {e}[/red]")
        return

    # =========================================================================
    # Step 3: Google Calendar OAuth
    # =========================================================================
    console.print(f"\n[bold]Step 3/5: Google Calendar setup[/bold]\n")

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
        console.print("[red]Registration aborted. Configure Google Calendar and re-run.[/red]")
        return

    calendar_already_connected = connector.is_connected(telegram_id)
    if calendar_already_connected:
        console.print(f"[green]Calendar already connected for Telegram ID {telegram_id}.[/green]")
    else:
        # Generate OAuth URL
        try:
            auth_url = connector.get_auth_url(telegram_id)
        except RuntimeError as e:
            console.print(f"[red]{e}[/red]")
            return

        console.print(Panel(
            "[bold]Open this URL in your browser:[/bold]\n\n"
            f"{auth_url}\n\n"
            "[bold]Authorize access and copy the code.[/bold]",
            width=console.width,
        ))

        code = Prompt.ask("\n[cyan]Paste the authorization code here[/cyan]")
        if not code.strip():
            console.print("[red]No code provided. Registration aborted.[/red]")
            return

        console.print("[bold]Completing OAuth flow...[/bold]")
        success = await connector.complete_auth(telegram_id, code.strip())

        if success:
            console.print("[green]Google Calendar connected successfully.[/green]")
        else:
            console.print("[red]OAuth flow failed. Check the code and re-run registration.[/red]")
            return

    # =========================================================================
    # Step 4: Zoom verification
    # =========================================================================
    console.print(f"\n[bold]Step 4/5: Zoom integration check[/bold]\n")

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
            '   EOF',
            width=console.width,
        ))
        console.print("[red]Registration aborted. Configure Zoom and re-run.[/red]")
        return

    # Validate credentials file
    try:
        with open(ZOOM_CREDENTIALS_FILE) as f:
            zoom_creds = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[red]Failed to read Zoom credentials file: {e}[/red]")
        return

    required_fields = ["account_id", "client_id", "client_secret"]
    missing = [f for f in required_fields if not zoom_creds.get(f)]

    if missing:
        console.print(f"[red]Missing fields in Zoom credentials: {', '.join(missing)}[/red]")
        console.print("[red]Registration aborted. Fix Zoom credentials and re-run.[/red]")
        return

    # Try importing ZoomBookingService
    try:
        from sales_agent.zoom import ZoomBookingService
        zoom = ZoomBookingService()
        if zoom.enabled:
            console.print(
                f"[green]Zoom integration verified.[/green] "
                f"Account: {zoom_creds['account_id'][:8]}..."
            )
        else:
            console.print("[yellow]ZoomBookingService loaded but reports not enabled.[/yellow]")
            console.print("[red]Registration aborted. Ensure Zoom is properly configured.[/red]")
            return
    except ImportError:
        # Credentials exist and are valid, module just not available
        console.print(
            f"[yellow]Zoom credentials found but ZoomBookingService module not available.[/yellow]\n"
            f"Credentials look valid (Account: {zoom_creds['account_id'][:8]}...). "
            f"Proceeding without module check."
        )

    # =========================================================================
    # Step 5: Save to database
    # =========================================================================
    console.print(f"\n[bold]Step 5/5: Saving to database[/bold]\n")

    from sales_agent.database import init_database

    try:
        await init_database()
    except RuntimeError as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        return

    from sales_agent.registry.sales_rep_manager import (
        create_sales_rep,
        get_by_telegram_id,
        update_session_info,
        update_calendar_connected,
        close_pool,
    )

    existing = await get_by_telegram_id(telegram_id)
    if existing:
        console.print(f"[yellow]Rep already exists: {existing.name} (updating session info)[/yellow]")
        await update_session_info(
            telegram_id=telegram_id,
            session_name=session_name,
            phone=phone,
            agent_name=agent_display_name,
            session_ready=True,
        )
    else:
        rep = await create_sales_rep(
            telegram_id=telegram_id,
            name=name,
            email=email,
            telegram_username=telegram_username,
        )
        console.print(f"[green]Rep created: {rep.name} (ID: {rep.id})[/green]")

        await update_session_info(
            telegram_id=telegram_id,
            session_name=session_name,
            phone=phone,
            agent_name=agent_display_name,
            session_ready=True,
        )

    # Mark calendar as connected
    await update_calendar_connected(telegram_id, True)

    await close_pool()

    # Success
    console.print(Panel(
        f"[bold green]Registration complete![/bold green]\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Telegram: @{telegram_username} (ID: {telegram_id})\n"
        f"Session: {session_name}\n"
        f"Agent name: {agent_display_name}\n"
        f"Google Calendar: Connected\n"
        f"Zoom: Verified\n\n"
        f"[bold]Next steps:[/bold]\n"
        f"1. Run daemon as this rep:\n"
        f"   PYTHONPATH=src uv run python src/sales_agent/daemon.py --rep-telegram-id {telegram_id}\n\n"
        f"2. [bold yellow]IMPORTANT: Calendar sharing required![/bold yellow]\n"
        f"   The new rep must share their Google Calendar with bohdan.p@trueagency.online\n"
        f"   Instructions to send to the rep:\n"
        f"   - Open Google Calendar > Settings (gear icon)\n"
        f"   - Click on their calendar under 'Settings for my calendars'\n"
        f"   - Scroll to 'Share with specific people' > Click 'Add people'\n"
        f"   - Add: bohdan.p@trueagency.online\n"
        f"   - Permission: 'See all event details'\n"
        f"   - Click Send",
        width=console.width,
    ))


if __name__ == "__main__":
    asyncio.run(main())
