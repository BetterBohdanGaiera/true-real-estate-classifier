#!/usr/bin/env python3
"""
Telegram Authentication Setup Script.
Run this once to authenticate your Telegram account.
"""
import asyncio
import json
from pathlib import Path

from telethon import TelegramClient
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt

console = Console()

CONFIG_DIR = Path.home() / '.telegram_dl'
CONFIG_FILE = CONFIG_DIR / 'config.json'
SESSION_FILE = CONFIG_DIR / 'user.session'


async def setup():
    console.print(Panel.fit(
        "[bold blue]Telegram Agent Setup[/bold blue]\n\n"
        "This will authenticate your Telegram account.\n"
        "You'll need API credentials from https://my.telegram.org/auth",
        title="Setup"
    ))

    # Check if already configured
    if CONFIG_FILE.exists() and SESSION_FILE.exists():
        console.print("\n[green]Telegram is already configured![/green]")
        reconfigure = Prompt.ask("Do you want to reconfigure?", choices=["y", "n"], default="n")
        if reconfigure == "n":
            return

    # Get API credentials
    console.print("\n[bold]Step 1: API Credentials[/bold]")
    console.print("Get these from: [link]https://my.telegram.org/auth[/link]")
    console.print("  1. Log in with your phone number")
    console.print("  2. Click 'API development tools'")
    console.print("  3. Create application (any name)")
    console.print("")

    api_id = IntPrompt.ask("Enter your API ID")
    api_hash = Prompt.ask("Enter your API Hash")

    # Save config
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        "api_id": api_id,
        "api_hash": api_hash
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    console.print(f"[green]Config saved to {CONFIG_FILE}[/green]")

    # Authenticate
    console.print("\n[bold]Step 2: Authentication[/bold]")
    console.print("You'll receive an SMS code from Telegram.")

    client = TelegramClient(str(SESSION_FILE), api_id, api_hash)

    await client.start()

    me = await client.get_me()
    console.print(f"\n[green]Successfully authenticated as:[/green]")
    console.print(f"  Name: {me.first_name} {me.last_name or ''}")
    console.print(f"  Username: @{me.username}" if me.username else "  Username: Not set")
    console.print(f"  ID: {me.id}")

    await client.disconnect()

    console.print(Panel.fit(
        "[bold green]Setup Complete![/bold green]\n\n"
        f"Session saved to: {SESSION_FILE}\n"
        f"Config saved to: {CONFIG_FILE}\n\n"
        "You can now run the agent with:\n"
        "[cyan]uv run python run_daemon.py[/cyan]",
        title="Success"
    ))


if __name__ == "__main__":
    asyncio.run(setup())
