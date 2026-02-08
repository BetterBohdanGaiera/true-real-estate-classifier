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
Follow-Up Polling Daemon - Database-driven execution of scheduled actions.

Polls the scheduled_actions table at regular intervals and executes due actions.
Uses PostgreSQL row-level locking (FOR UPDATE SKIP LOCKED) to prevent duplicate
execution across multiple daemon instances.

This approach replaces in-memory asyncio.sleep-based scheduling with database
polling, providing:
- Persistence across Docker restarts
- Accurate timing (no drift on daemon restart)
- Multi-instance scalability (row locking prevents duplicates)
- Easy debugging (query database to see pending actions)

Usage:
    from followup_polling_daemon import FollowUpPollingDaemon
    from telegram_sales_bot.core.models import ScheduledAction, FollowUpPollingConfig

    async def execute_action(action: ScheduledAction) -> None:
        # Send follow-up message, reminder, etc.
        await send_telegram_message(action.prospect_id, action.payload["message"])

    config = FollowUpPollingConfig(poll_interval_seconds=30, batch_size=10)
    daemon = FollowUpPollingDaemon(execute_callback=execute_action, config=config)

    await daemon.start()
    # ... daemon runs in background ...
    await daemon.stop()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timezone, timezone
from pathlib import Path
from typing import Callable, Awaitable, Optional

from rich.console import Console

# Add scheduling skill scripts to path for intra-module imports

# Add telegram skill scripts to path for model imports

from telegram_sales_bot.core.models import ScheduledAction, FollowUpPollingConfig, ScheduledActionStatus
from telegram_sales_bot.scheduling.db import (
    claim_due_actions,
    mark_executed,
    get_by_id,
)

class FollowUpPollingDaemon:
    """
    Database-driven follow-up execution daemon.

    Polls the scheduled_actions table at regular intervals
    and executes due actions. Uses PostgreSQL row-level locking
    to prevent duplicate execution across multiple instances.

    The daemon works by:
    1. Polling the database every N seconds (configurable)
    2. Claiming due actions atomically with row locking
    3. Executing each claimed action via the provided callback
    4. Marking actions as executed on success

    Attributes:
        execute_callback: Async function called to execute each action.
        config: Polling configuration (intervals, batch sizes, etc.).
        _running: Whether the daemon is currently running.
        _poll_task: The asyncio task running the poll loop.
        console: Rich console for logging.
        stats: Dictionary tracking execution stats.

    Example:
        >>> async def my_executor(action: ScheduledAction) -> None:
        ...     print(f"Executing action for {action.prospect_id}")
        ...
        >>> daemon = FollowUpPollingDaemon(execute_callback=my_executor)
        >>> await daemon.start()
        >>> # ... daemon polls and executes actions in background ...
        >>> await daemon.stop()
    """

    def __init__(
        self,
        execute_callback: Callable[[ScheduledAction], Awaitable[None]],
        config: Optional[FollowUpPollingConfig] = None,
    ):
        """
        Initialize the polling daemon.

        Args:
            execute_callback: Async function to call when executing actions.
                             Must accept ScheduledAction and return None.
                             This function should handle the actual message
                             sending or other action execution logic.
            config: Optional polling configuration. Uses defaults if not provided.
                   Default: poll every 30s, batch size 10, 5s preemptive window.
        """
        self.execute_callback = execute_callback
        self.config = config or FollowUpPollingConfig()
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self.console = Console()
        self.stats = {
            "polls": 0,
            "actions_executed": 0,
            "actions_failed": 0,
            "started_at": None,
        }

    async def start(self) -> None:
        """
        Start the polling loop.

        Creates a background task that polls the database at configured intervals.
        Safe to call multiple times (no-op if already running).

        The polling loop will:
        - Check for due actions every poll_interval_seconds
        - Claim up to batch_size actions per poll
        - Execute actions via the callback function
        - Handle errors with exponential backoff

        Example:
            >>> daemon = FollowUpPollingDaemon(execute_callback=my_executor)
            >>> await daemon.start()
            >>> # Daemon now polling in background
        """
        if self._running:
            self.console.print("[yellow]Polling daemon already running[/yellow]")
            return

        self._running = True
        self.stats["started_at"] = datetime.now(timezone.utc)
        self._poll_task = asyncio.create_task(self._poll_loop())
        self.console.print(
            f"[green]Polling daemon started (interval: {self.config.poll_interval_seconds}s, "
            f"batch: {self.config.batch_size})[/green]"
        )

    async def stop(self) -> None:
        """
        Stop the polling loop gracefully.

        Waits for current poll cycle to complete before stopping.
        Cancels the background polling task and handles cleanup.

        Note: Any action currently being executed will be allowed to complete.
        Actions that were claimed but not yet executed will remain in
        'processing' status and should be recovered on next startup.

        Example:
            >>> await daemon.stop()
            >>> # Daemon stopped gracefully
        """
        if not self._running:
            self.console.print("[yellow]Polling daemon not running[/yellow]")
            return

        self._running = False

        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        self.console.print("[green]Polling daemon stopped[/green]")

    async def _poll_loop(self) -> None:
        """
        Main polling loop.

        Runs continuously while _running is True. Each iteration:
        1. Calls _poll_and_execute to claim and execute due actions
        2. Waits for poll_interval_seconds before next poll
        3. On error, applies exponential backoff (max 5 minutes)

        The loop catches all exceptions to prevent daemon crashes.
        Graceful shutdown is handled via asyncio.CancelledError.
        """
        backoff_delay = self.config.poll_interval_seconds
        consecutive_errors = 0

        while self._running:
            try:
                # Execute one poll cycle
                executed_count = await self._poll_and_execute()

                # Reset backoff on successful poll
                consecutive_errors = 0
                backoff_delay = self.config.poll_interval_seconds

                # Wait before next poll
                await asyncio.sleep(self.config.poll_interval_seconds)

            except asyncio.CancelledError:
                # Graceful shutdown requested
                break
            except Exception as e:
                consecutive_errors += 1
                # Exponential backoff on errors (max 5 minutes)
                backoff_delay = min(
                    self.config.poll_interval_seconds * (2 ** consecutive_errors),
                    300
                )
                self.console.print(
                    f"[red]Poll cycle error: {e} "
                    f"(retry in {backoff_delay}s, errors: {consecutive_errors})[/red]"
                )
                await asyncio.sleep(backoff_delay)

    async def _poll_and_execute(self) -> int:
        """
        Single poll iteration: claim due actions and execute them.

        This method:
        1. Calls claim_due_actions() to atomically claim pending actions
        2. Iterates through claimed actions
        3. Verifies each action is still valid (not cancelled during claiming)
        4. Executes via callback and marks as executed

        Individual action failures don't stop batch processing - we continue
        with the next action in the batch.

        Returns:
            Number of actions successfully executed in this cycle.
        """
        self.stats["polls"] += 1

        try:
            # Claim due actions with row locking
            # claim_due_actions atomically updates status to 'processing'
            # and returns only successfully claimed actions
            actions = await claim_due_actions(
                limit=self.config.batch_size,
                max_delay_seconds=self.config.preemptive_window_seconds,
            )

            if not actions:
                # No actions due - silent poll (no spam in logs)
                return 0

            self.console.print(
                f"[cyan]Poll cycle {self.stats['polls']}: "
                f"Found {len(actions)} due action(s)[/cyan]"
            )

            executed_count = 0
            for action in actions:
                try:
                    # Verify action is still valid (not cancelled during claiming)
                    # This handles race condition where action is cancelled
                    # between claim_due_actions and execution
                    current = await get_by_id(action.id)
                    if not current or current.status != ScheduledActionStatus.PROCESSING:
                        self.console.print(
                            f"[dim]Skipping action {action.id[:8]}... "
                            f"(status changed to {current.status if current else 'deleted'})[/dim]"
                        )
                        continue

                    # Execute via callback
                    self.console.print(
                        f"[cyan]Executing action {action.id[:8]}... "
                        f"for prospect {action.prospect_id}[/cyan]"
                    )

                    await self.execute_callback(action)

                    # Mark as executed in database
                    success = await mark_executed(action.id)
                    if success:
                        executed_count += 1
                        self.stats["actions_executed"] += 1
                        self.console.print(
                            f"[green]Action {action.id[:8]}... executed successfully[/green]"
                        )
                    else:
                        self.console.print(
                            f"[yellow]Action {action.id[:8]}... executed but "
                            f"failed to mark as executed[/yellow]"
                        )

                except Exception as e:
                    self.stats["actions_failed"] += 1
                    self.console.print(
                        f"[red]Failed to execute action {action.id[:8]}...: {e}[/red]"
                    )
                    # Continue with next action - don't let one failure stop the batch

            return executed_count

        except Exception as e:
            self.console.print(f"[red]Error in poll cycle: {e}[/red]")
            return 0

    def health_check(self) -> dict:
        """
        Get daemon health status.

        Provides metrics for monitoring and debugging. Can be used by
        Docker health checks or monitoring systems.

        Returns:
            Dictionary with health metrics:
            - running: Whether daemon is currently running
            - uptime_seconds: Time since daemon started (or None if not running)
            - polls: Total number of poll cycles executed
            - actions_executed: Total actions successfully executed
            - actions_failed: Total actions that failed execution
            - config: Current polling configuration

        Example:
            >>> health = daemon.health_check()
            >>> print(f"Running: {health['running']}, Executed: {health['actions_executed']}")
        """
        uptime = None
        if self.stats["started_at"]:
            uptime = (datetime.now(timezone.utc) - self.stats["started_at"]).total_seconds()

        return {
            "running": self._running,
            "uptime_seconds": uptime,
            "polls": self.stats["polls"],
            "actions_executed": self.stats["actions_executed"],
            "actions_failed": self.stats["actions_failed"],
            "config": {
                "poll_interval_seconds": self.config.poll_interval_seconds,
                "batch_size": self.config.batch_size,
                "preemptive_window_seconds": self.config.preemptive_window_seconds,
            }
        }

    @property
    def is_running(self) -> bool:
        """
        Check if daemon is running.

        Returns:
            True if the polling loop is active.
        """
        return self._running
