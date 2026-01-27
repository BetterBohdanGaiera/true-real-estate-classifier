#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
List all registered sales representatives with their status.

Shows a Rich table with session readiness, calendar connection, etc.

Usage:
    PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/list_reps.py
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to path for imports
src_dir = Path(__file__).resolve().parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_dir))

load_dotenv()

console = Console()


async def main():
    # Initialize database
    from sales_agent.database import init_database

    try:
        await init_database()
    except RuntimeError as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        return

    from sales_agent.registry.sales_rep_manager import list_all, close_pool

    reps = await list_all()

    if not reps:
        console.print(Panel(
            "[yellow]No sales representatives registered yet.[/yellow]\n\n"
            "Run the registration script to add a rep:\n"
            "  PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py",
            width=console.width,
        ))
        await close_pool()
        return

    table = Table(title="Registered Sales Representatives", width=console.width)
    table.add_column("Name", style="cyan")
    table.add_column("Telegram", style="white")
    table.add_column("Telegram ID", style="dim")
    table.add_column("Status", style="white")
    table.add_column("Session", style="white")
    table.add_column("Calendar", style="white")
    table.add_column("Agent Name", style="white")
    table.add_column("Registered", style="dim")

    for rep in reps:
        # Status styling
        status_style = {
            "active": "[green]active[/green]",
            "pending": "[yellow]pending[/yellow]",
            "suspended": "[red]suspended[/red]",
            "removed": "[dim]removed[/dim]",
        }
        status = status_style.get(rep.status, rep.status)

        # Session status
        if rep.telegram_session_ready:
            session = "[green]ready[/green]"
        elif rep.telegram_session_name:
            session = "[yellow]not ready[/yellow]"
        else:
            session = "[dim]none[/dim]"

        # Calendar status
        calendar = "[green]connected[/green]" if rep.calendar_connected else "[dim]not connected[/dim]"

        # Registered date
        registered = rep.registered_at.strftime("%Y-%m-%d") if rep.registered_at else "-"

        table.add_row(
            rep.name,
            f"@{rep.telegram_username}" if rep.telegram_username else "-",
            str(rep.telegram_id),
            status,
            session,
            calendar,
            rep.agent_name or "-",
            registered,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(reps)} rep(s)[/dim]")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
