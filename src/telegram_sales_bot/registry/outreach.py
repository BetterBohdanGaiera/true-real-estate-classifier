# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
#   "python-telegram-bot>=21.0",
# ]
# ///
"""
Outreach Daemon - Proactive prospect assignment and notification.

Background task that:
1. Assigns unreached prospects to active sales reps (round-robin)
2. Notifies reps via Telegram when new prospects are assigned
3. Monitors prospect status and follows up

Note: This file was migrated from src/sales_agent/registry/outreach_daemon.py

Usage:
    from outreach_daemon import OutreachDaemon

    daemon = OutreachDaemon(bot_token="YOUR_TOKEN")
    await daemon.start()
    # ... later ...
    await daemon.stop()

Can also be run standalone:
    PYTHONPATH=.claude/skills/register-sales/scripts uv run python outreach_daemon.py
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Local imports - support both package and standalone usage
try:
    from .registry_models import ProspectStatus
    from . import sales_rep_manager
    from . import test_prospect_manager
except ImportError:
    from registry_models import ProspectStatus
    import sales_rep_manager
    import test_prospect_manager

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
console = Console()

class OutreachDaemon:
    """
    Background daemon for proactive prospect outreach.

    Periodically assigns unreached prospects to active sales reps
    and sends notifications.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        check_interval: int = 300,  # 5 minutes
        max_prospects_per_rep: int = 5,
    ):
        """
        Initialize the outreach daemon.

        Args:
            bot_token: Telegram bot token for sending notifications.
            check_interval: Seconds between prospect assignment checks.
            max_prospects_per_rep: Maximum prospects to assign to one rep.
        """
        self.bot_token = bot_token or os.getenv("REGISTRY_BOT_TOKEN")
        self.check_interval = check_interval
        self.max_prospects_per_rep = max_prospects_per_rep

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._round_robin_index = 0

        # Stats tracking
        self.stats = {
            "assignments_made": 0,
            "notifications_sent": 0,
            "cycles_completed": 0,
            "started_at": None,
        }

    async def start(self) -> None:
        """Start the outreach daemon."""
        if self._running:
            logger.warning("Outreach daemon already running")
            return

        self._running = True
        self.stats["started_at"] = datetime.now()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Outreach daemon started")

    async def stop(self) -> None:
        """Stop the outreach daemon."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Outreach daemon stopped")

    async def _run_loop(self) -> None:
        """Main daemon loop."""
        while self._running:
            try:
                await self._process_assignments()
                self.stats["cycles_completed"] += 1
            except Exception as e:
                logger.error(f"Error in outreach daemon: {e}")

            # Wait for next cycle
            await asyncio.sleep(self.check_interval)

    async def _process_assignments(self) -> None:
        """Process prospect assignments for this cycle."""
        # Get active reps
        active_reps = await sales_rep_manager.list_active()
        if not active_reps:
            logger.debug("No active reps available for assignment")
            return

        # Get unreached prospects that are not assigned
        unreached = await test_prospect_manager.get_unreached_prospects()
        unassigned = [p for p in unreached if not p.assigned_rep_id]

        if not unassigned:
            logger.debug("No unassigned prospects to process")
            return

        logger.info(f"Processing {len(unassigned)} unassigned prospects among {len(active_reps)} reps")

        # Assign prospects round-robin
        for prospect in unassigned:
            # Find next rep with capacity
            rep = await self._get_next_rep_with_capacity(active_reps)
            if not rep:
                logger.info("All reps at capacity, stopping assignments")
                break

            # Assign prospect
            success = await test_prospect_manager.assign_prospect_to_rep(prospect.id, rep.id)
            if success:
                self.stats["assignments_made"] += 1
                logger.info(f"Assigned {prospect.name} to {rep.name}")

                # Send notification
                await self._notify_rep(rep, prospect)

    async def _get_next_rep_with_capacity(self, active_reps: list) -> Optional[object]:
        """Get next rep with available capacity using round-robin."""
        if not active_reps:
            return None

        # Try each rep starting from current index
        for _ in range(len(active_reps)):
            rep = active_reps[self._round_robin_index % len(active_reps)]
            self._round_robin_index += 1

            # Check capacity
            current_count = await test_prospect_manager.count_prospects_for_rep(rep.id)
            if current_count < self.max_prospects_per_rep:
                return rep

        return None

    async def _notify_rep(self, rep, prospect) -> None:
        """Send notification to rep about new prospect."""
        if not self.bot_token:
            logger.debug("No bot token, skipping notification")
            return

        try:
            from telegram import Bot

            bot = Bot(token=self.bot_token)

            message = (
                f"Вам назначен новый тестовый клиент!\n\n"
                f"Имя: {prospect.name}\n"
                f"Telegram: {prospect.telegram_id}\n"
                f"Контекст: {prospect.context or 'Не указан'}\n\n"
                f"Напишите «мои клиенты» чтобы посмотреть всех клиентов."
            )

            await bot.send_message(chat_id=rep.telegram_id, text=message)
            self.stats["notifications_sent"] += 1
            logger.info(f"Notification sent to {rep.name}")

        except Exception as e:
            logger.error(f"Failed to send notification to {rep.name}: {e}")

    async def assign_all_unreached(self) -> int:
        """
        Manually trigger assignment of all unreached prospects.

        Returns:
            Number of prospects assigned.
        """
        await self._process_assignments()
        return self.stats["assignments_made"]

    def get_stats(self) -> dict:
        """Get daemon statistics."""
        stats = self.stats.copy()
        if stats["started_at"]:
            stats["uptime"] = str(datetime.now() - stats["started_at"])
        stats["running"] = self._running
        return stats

async def main() -> None:
    """Run the outreach daemon standalone."""
    console.print(Panel.fit(
        "[bold blue]Outreach Daemon[/bold blue]\n"
        "Proactive prospect assignment",
        title="Starting",
    ))

    # Check configuration
    bot_token = os.getenv("REGISTRY_BOT_TOKEN")
    if not bot_token:
        console.print("[yellow]Warning: REGISTRY_BOT_TOKEN not set, notifications disabled[/yellow]")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        console.print("[red]ERROR: DATABASE_URL not set[/red]")
        return

    # Initialize database
    try:
        # Add database skill to path
        DATABASE_SCRIPTS = Path(__file__).parent.parent.parent / "database" / "scripts"
        from init import init_database
        await init_database()
    except Exception as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        return

    # Read environment variables with defaults
    check_interval = int(os.environ.get("OUTREACH_INTERVAL_SECONDS", "300"))
    max_prospects_per_rep = int(os.environ.get("MAX_PROSPECTS_PER_REP", "5"))
    outreach_enabled = os.environ.get("OUTREACH_ENABLED", "true").lower() == "true"

    if not outreach_enabled:
        console.print("[yellow]Outreach daemon disabled via OUTREACH_ENABLED=false[/yellow]")
        logger.info("Outreach daemon disabled via OUTREACH_ENABLED=false")
        return

    # Start daemon
    daemon = OutreachDaemon(
        bot_token=bot_token,
        check_interval=check_interval,
        max_prospects_per_rep=max_prospects_per_rep,
    )

    console.print(Panel.fit(
        "[bold green]Outreach Daemon Running[/bold green]\n\n"
        f"Check interval: {daemon.check_interval}s\n"
        f"Max prospects per rep: {daemon.max_prospects_per_rep}\n"
        f"Notifications: {'Enabled' if daemon.bot_token else 'Disabled'}\n\n"
        "Press Ctrl+C to stop.",
        title="Running",
    ))

    await daemon.start()

    # Run until interrupted
    try:
        while True:
            await asyncio.sleep(60)
            stats = daemon.get_stats()
            console.print(
                f"[dim]Cycle {stats['cycles_completed']}: "
                f"{stats['assignments_made']} assigned, "
                f"{stats['notifications_sent']} notified[/dim]"
            )
    except asyncio.CancelledError:
        pass
    finally:
        await daemon.stop()
        console.print("[green]Outreach daemon stopped[/green]")

if __name__ == "__main__":
    import signal

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    main_task = loop.create_task(main())

    def signal_handler():
        main_task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
