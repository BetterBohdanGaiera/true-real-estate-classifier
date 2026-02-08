#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-telegram-bot>=21.0",
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Sales Representative Registry Bot - Entry Point.

This script initializes the database and starts the registry bot.

Note: This file was migrated from src/sales_agent/registry/run_registry_bot.py

Usage:
    PYTHONPATH=.claude/skills/register-sales/scripts:.claude/skills/database/scripts uv run python run_registry_bot.py

Prerequisites:
    1. Create a bot on Telegram via @BotFather
    2. Add REGISTRY_BOT_TOKEN to your .env file
    3. Ensure DATABASE_URL is set in .env

The bot will:
    - Initialize database and run migrations
    - Start polling for messages
    - Handle registration conversations
"""

import asyncio
import os
import signal
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment variables
load_dotenv()

console = Console()

async def main() -> None:
    """Main entry point for the registry bot."""
    console.print(Panel.fit(
        "[bold blue]Sales Representative Registry Bot[/bold blue]\n"
        "Initializing...",
        title="Registry Bot",
    ))

    # Check required environment variables
    token = os.getenv("REGISTRY_BOT_TOKEN")
    if not token:
        console.print(
            Panel(
                "[red bold]REGISTRY_BOT_TOKEN not set![/red bold]\n\n"
                "To get a bot token:\n"
                "1. Message @BotFather on Telegram\n"
                "2. Send /newbot and follow instructions\n"
                "3. Add the token to your .env file:\n"
                "   REGISTRY_BOT_TOKEN=your_token_here",
                title="Configuration Error",
                width=80,
            )
        )
        sys.exit(1)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        console.print(
            Panel(
                "[red bold]DATABASE_URL not set![/red bold]\n\n"
                "Please add DATABASE_URL to your .env file.",
                title="Configuration Error",
                width=80,
            )
        )
        sys.exit(1)

    # Initialize database
    console.print("  [cyan]Initializing database...[/cyan]")
    try:
        # Add database skill to path
        DATABASE_SCRIPTS = Path(__file__).parent.parent.parent / "database" / "scripts"
        from init import init_database
        await init_database()
        console.print("  [green]>[/green] Database initialized")
    except Exception as e:
        console.print(f"  [red]Database initialization failed: {e}[/red]")
        sys.exit(1)

    # Import and create bot after database is initialized
    try:
        from .registry_bot import RegistryBot
    except ImportError:
        from registry_bot import RegistryBot

    corporate_domain = os.getenv("CORPORATE_EMAIL_DOMAIN", "truerealestate.bali")
    bot = RegistryBot(token=token, corporate_email_domain=corporate_domain)

    console.print("  [green]>[/green] Bot configured")
    console.print(f"  [dim]Corporate email domain: {corporate_domain}[/dim]")

    # Build application
    app = bot.build_application()
    await app.initialize()
    await app.start()

    console.print(Panel.fit(
        "[bold green]Registry Bot Started![/bold green]\n\n"
        "The bot is now listening for messages.\n"
        "Press Ctrl+C to stop.",
        title="Running",
    ))

    # Setup signal handlers
    stop_event = asyncio.Event()

    def signal_handler(sig):
        console.print("\n[yellow]Shutdown requested...[/yellow]")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    # Start polling
    await app.updater.start_polling(
        drop_pending_updates=True,
    )

    # Wait for stop signal
    await stop_event.wait()

    # Graceful shutdown
    console.print("[cyan]Stopping bot...[/cyan]")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()

    # Close database connections
    try:
        try:
            from . import sales_rep_manager, test_prospect_manager
        except ImportError:
            import sales_rep_manager
            import test_prospect_manager
        await sales_rep_manager.close_pool()
        await test_prospect_manager.close_pool()
        console.print("  [green]>[/green] Database connections closed")
    except Exception as e:
        console.print(f"  [yellow]Warning: {e}[/yellow]")

    console.print(Panel.fit(
        "[bold green]Registry Bot Stopped[/bold green]",
        title="Shutdown Complete",
    ))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red bold]Fatal error: {e}[/red bold]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
