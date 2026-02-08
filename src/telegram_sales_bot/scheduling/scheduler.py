# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Scheduler Service - Database-driven wrapper for scheduling delayed actions.

Provides scheduling and execution of delayed actions (follow-ups, reminders).
Uses FollowUpPollingDaemon for database polling, with our scheduled_actions table
as the single source of truth. This design is resilient to Docker restarts.

Usage:
    from telegram_sales_bot.scheduling.scheduler import SchedulerService
    from telegram_sales_bot.core.models import ScheduledAction

    async def execute_action(action: ScheduledAction) -> None:
        # Your execution logic here
        pass

    scheduler = SchedulerService(execute_callback=execute_action)
    await scheduler.start()

    # Schedule an action
    job_id = await scheduler.schedule_action(action)

    # Cancel an action
    await scheduler.cancel_action(action.id)

    # Shutdown
    await scheduler.stop()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timezone, timezone
from pathlib import Path
from typing import Callable, Awaitable, Optional

from dotenv import load_dotenv
from rich.console import Console

# Add scheduling skill scripts to path for intra-module imports

from telegram_sales_bot.core.models import (
    ScheduledAction,
    ScheduledActionStatus,
    FollowUpPollingConfig,
)
from telegram_sales_bot.scheduling.polling_daemon import FollowUpPollingDaemon
from telegram_sales_bot.scheduling.db import (
    get_by_id,
    get_pool,
)

load_dotenv()
console = Console()

class SchedulerService:
    """
    Database-driven service for scheduling and executing delayed actions.

    Uses FollowUpPollingDaemon for timing, with our scheduled_actions table
    as the single source of truth. Actions are recovered automatically by the
    polling daemon on startup - no in-memory state to lose.

    Key differences from APScheduler-based approach:
    - No in-memory task tracking (_scheduled_tasks removed)
    - No asyncio.sleep-based scheduling (polling daemon handles timing)
    - Docker restart safe (database is source of truth)
    - Stateless service (can scale horizontally with row locking)

    Attributes:
        execute_callback: Async function called when an action is due.
        polling_daemon: FollowUpPollingDaemon instance for execution.
        _running: Whether the service is currently running.

    Example:
        >>> async def my_executor(action: ScheduledAction) -> None:
        ...     print(f"Executing action {action.id} for {action.prospect_id}")
        ...
        >>> service = SchedulerService(execute_callback=my_executor)
        >>> await service.start()
        >>> await service.schedule_action(some_action)
        >>> # ... later ...
        >>> await service.stop()
    """

    def __init__(
        self,
        execute_callback: Callable[[ScheduledAction], Awaitable[None]],
        config: Optional[FollowUpPollingConfig] = None,
    ):
        """
        Initialize the scheduler service.

        Args:
            execute_callback: Async function to call when action is due.
                              Must accept ScheduledAction and return None.
                              This function should handle the actual message
                              sending or other action execution.
            config: Optional polling configuration. Uses defaults if not provided.
                   Default: poll every 30s, batch size 10, 5s preemptive window.
        """
        self.execute_callback = execute_callback
        self.polling_daemon = FollowUpPollingDaemon(
            execute_callback=self._execute_action_wrapper,
            config=config,
        )
        self._running = False

    async def start(self) -> None:
        """
        Start the scheduler and polling daemon.

        Starts the database polling daemon which will automatically
        execute actions when they become due. Also resets any stale
        processing actions from previous crashes.

        Example:
            >>> service = SchedulerService(execute_callback=my_executor)
            >>> await service.start()  # Polling daemon now running
        """
        if self._running:
            console.print("[yellow]Scheduler already running[/yellow]")
            return

        self._running = True

        # Reset any stale processing actions from previous crashes
        try:
            reset_count = await self._reset_stale_processing(stale_after_seconds=600)
            if reset_count > 0:
                console.print(
                    f"[yellow]Reset {reset_count} stale action(s) from previous run[/yellow]"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not reset stale actions: {e}[/yellow]")

        # Start polling daemon
        await self.polling_daemon.start()
        console.print("[green]Scheduler started with database polling (Docker-safe)[/green]")

    async def stop(self) -> None:
        """
        Gracefully shutdown the scheduler.

        Stops the polling daemon and waits for any in-flight actions to complete.
        Actions that were claimed but not yet executed will remain in
        'processing' status and should be recovered on next startup.

        Example:
            >>> await service.stop()  # Clean shutdown
        """
        if not self._running:
            console.print("[yellow]Scheduler not running[/yellow]")
            return

        self._running = False

        # Stop polling daemon
        await self.polling_daemon.stop()
        console.print("[green]Scheduler stopped gracefully[/green]")

    async def schedule_action(self, action: ScheduledAction) -> str:
        """
        Schedule an action for execution at its scheduled time.

        Note: With the polling daemon, this method just logs confirmation.
        The action should already be in the database (created by the agent),
        and the polling daemon will automatically execute it when due.

        Args:
            action: The ScheduledAction to schedule. Must have:
                    - id: UUID string identifying the action
                    - scheduled_for: datetime when to execute

        Returns:
            Schedule ID (same as action.id).

        Raises:
            RuntimeError: If scheduler is not running.
            ValueError: If action.id is None.

        Example:
            >>> action = ScheduledAction(
            ...     id="abc-123",
            ...     prospect_id="456",
            ...     action_type=ScheduledActionType.FOLLOW_UP,
            ...     scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2),
            ...     payload={"follow_up_intent": "Check in about property viewing"}
            ... )
            >>> job_id = await service.schedule_action(action)
            >>> print(f"Scheduled: {job_id}")
        """
        if not self._running:
            raise RuntimeError("Scheduler is not running. Call start() first.")

        if action.id is None:
            raise ValueError("Action must have an ID to be scheduled")

        # Ensure scheduled_for is timezone-aware for display
        scheduled_for = action.scheduled_for
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

        # Action is already in database with status='pending'
        # Polling daemon will execute it automatically when scheduled_for arrives
        console.print(
            f"[cyan]Action {action.id[:8]}... scheduled for "
            f"{scheduled_for.strftime('%Y-%m-%d %H:%M:%S %Z')} "
            f"(polling daemon will execute)[/cyan]"
        )

        return action.id

    async def cancel_action(self, action_id: str) -> bool:
        """
        Cancel a scheduled action.

        Updates the database to mark action as cancelled.
        The polling daemon will skip cancelled actions.

        Args:
            action_id: UUID string of the action to cancel.

        Returns:
            True if the action was found and cancelled in database.
            False if the action was not found or already processed.

        Example:
            >>> cancelled = await service.cancel_action("abc-123")
            >>> if cancelled:
            ...     print("Action cancelled")
        """
        action = await get_by_id(action_id)
        if not action:
            console.print(
                f"[dim]Action {action_id[:8]}... not found in database[/dim]"
            )
            return False

        if action.status != ScheduledActionStatus.PENDING:
            console.print(
                f"[dim]Action {action_id[:8]}... already {action.status}[/dim]"
            )
            return False

        # Cancel in database
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE scheduled_actions
                    SET status = $1,
                        cancelled_at = NOW(),
                        cancel_reason = $2,
                        updated_at = NOW()
                    WHERE id = $3 AND status = $4
                    """,
                    ScheduledActionStatus.CANCELLED.value,
                    "manual_cancellation",
                    uuid.UUID(action_id),
                    ScheduledActionStatus.PENDING.value,
                )
                success = result == "UPDATE 1"

            if success:
                console.print(
                    f"[yellow]Cancelled action {action_id[:8]}... in database[/yellow]"
                )

            return success

        except Exception as e:
            console.print(f"[red]Error cancelling action {action_id[:8]}...: {e}[/red]")
            return False

    async def _execute_action_wrapper(self, action: ScheduledAction) -> None:
        """
        Wrapper for execute_callback that adds logging.

        This is called by the polling daemon when an action is due.
        The polling daemon handles:
        - Claiming the action (status -> processing)
        - Marking as executed on success
        - Error tracking

        This wrapper just delegates to the user-provided callback.

        Args:
            action: The action to execute (already fetched from database).
        """
        try:
            console.print(
                f"[cyan]Executing action {action.id[:8]}... "
                f"for prospect {action.prospect_id}[/cyan]"
            )

            # Call the user-provided callback
            await self.execute_callback(action)

            console.print(
                f"[green]Action {action.id[:8]}... executed successfully[/green]"
            )

        except Exception as e:
            console.print(
                f"[red]Error executing action {action.id[:8]}...: {e}[/red]"
            )
            raise  # Re-raise so polling daemon can track failures

    async def _reset_stale_processing(self, stale_after_seconds: int = 600) -> int:
        """
        Reset stale processing actions from previous crashes.

        When the daemon crashes while an action is in 'processing' status,
        it will remain stuck. This method resets such actions back to 'pending'
        so they can be retried.

        Args:
            stale_after_seconds: Actions in 'processing' status for longer than
                                this duration are considered stale (default: 10 min).

        Returns:
            Number of actions reset.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE scheduled_actions
                    SET status = $1,
                        updated_at = NOW()
                    WHERE status = $2
                      AND updated_at < NOW() - INTERVAL '%s seconds'
                    """ % stale_after_seconds,
                    ScheduledActionStatus.PENDING.value,
                    ScheduledActionStatus.PROCESSING.value,
                )

                # Parse "UPDATE N" result string to get count
                if result:
                    parts = result.split()
                    if len(parts) >= 2:
                        return int(parts[1])
                return 0

        except Exception as e:
            console.print(f"[red]Error resetting stale actions: {e}[/red]")
            return 0

    @property
    def is_running(self) -> bool:
        """
        Check if the scheduler is currently running.

        Returns:
            True if scheduler is running and processing jobs.
        """
        return self._running

    def health_check(self) -> dict:
        """
        Get scheduler health status.

        Combines scheduler status with polling daemon health metrics.
        Useful for monitoring and debugging.

        Returns:
            Dictionary with health metrics:
            - running: Whether scheduler is running
            - daemon_health: Health metrics from polling daemon

        Example:
            >>> health = scheduler.health_check()
            >>> print(f"Running: {health['running']}")
        """
        return {
            "running": self._running,
            "daemon_health": self.polling_daemon.health_check(),
        }
