#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
#   "telethon>=1.34.0",
# ]
# ///
"""
Interactive CLI to register a new sales representative.

Steps:
1. Prompt for: name, email, telegram_username, phone, agent_display_name
2. Create Telegram session via interactive phone auth
3. Verify session via get_me()
4. Save to database via create_sales_rep() + update_session_info()
5. Print success + next steps

Usage:
    PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py
"""

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
    console.print(Panel(
        "[bold blue]Sales Rep Registration[/bold blue]\n"
        "Register a new sales representative with Telegram session",
        width=console.width,
    ))

    # Collect info
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

    console.print(f"\n[bold]Creating Telegram session for @{telegram_username}...[/bold]")
    console.print("[dim]Telethon will send a verification code to the phone. Enter it when prompted.[/dim]\n")

    # Create Telegram session
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

    # Initialize database
    console.print("\n[bold]Saving to database...[/bold]")
    from sales_agent.database import init_database

    try:
        await init_database()
    except RuntimeError as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        return

    # Check if rep already exists
    from sales_agent.registry.sales_rep_manager import (
        create_sales_rep,
        get_by_telegram_id,
        update_session_info,
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

    await close_pool()

    # Success
    console.print(Panel(
        f"[bold green]Registration complete![/bold green]\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Telegram: @{telegram_username} (ID: {telegram_id})\n"
        f"Session: {session_name}\n"
        f"Agent name: {agent_display_name}\n\n"
        f"[bold]Next steps:[/bold]\n"
        f"1. Set up Google Calendar:\n"
        f"   PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/setup_calendar.py --telegram-id {telegram_id}\n\n"
        f"2. Verify Zoom:\n"
        f"   PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/verify_zoom.py\n\n"
        f"3. Run daemon as this rep:\n"
        f"   PYTHONPATH=src uv run python src/sales_agent/daemon.py --rep-telegram-id {telegram_id}",
        width=console.width,
    ))


if __name__ == "__main__":
    asyncio.run(main())
