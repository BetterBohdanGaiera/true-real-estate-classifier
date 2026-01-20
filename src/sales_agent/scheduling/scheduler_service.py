# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "apscheduler>=4.0.0a5",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Scheduler Service - APScheduler wrapper for scheduling delayed actions.

Provides scheduling and execution of delayed actions (follow-ups, reminders).
Uses in-memory APScheduler for scheduling, with our scheduled_actions table
for persistence across daemon restarts.

Usage:
    from scheduler_service import SchedulerService
    from models import ScheduledAction

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

import asyncio
import os
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

from apscheduler import AsyncScheduler
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv
from rich.console import Console

from sales_agent.crm.models import ScheduledAction, ScheduledActionStatus
from .scheduled_action_manager import (
    get_by_id,
    mark_executed,
    get_due_actions,
    get_pending_actions,
)

load_dotenv()
console = Console()


class SchedulerService:
    """
    APScheduler-based service for scheduling and executing delayed actions.

    Uses in-memory APScheduler for timing, with our scheduled_actions table
    for persistence. Actions are recovered from the database on startup.

    Attributes:
        execute_callback: Async function called when an action is due.
        scheduler: APScheduler AsyncScheduler instance.

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

    def __init__(self, execute_callback: Callable[[ScheduledAction], Awaitable[None]]):
        """
        Initialize the scheduler service.

        Args:
            execute_callback: Async function to call when action is due.
                              Must accept ScheduledAction and return None.
                              This function should handle the actual message
                              sending or other action execution.
        """
        self.execute_callback = execute_callback
        self.scheduler: Optional[AsyncScheduler] = None
        self._running = False
        self._scheduled_tasks: dict[str, asyncio.Task] = {}  # action_id -> asyncio.Task

    async def start(self) -> None:
        """
        Start the scheduler and recover pending actions.

        Starts the scheduler and recovers any pending actions that may have
        been missed during downtime.

        Example:
            >>> service = SchedulerService(execute_callback=my_executor)
            >>> await service.start()  # Scheduler now running
        """
        if self._running:
            console.print("[yellow]Scheduler already running[/yellow]")
            return

        # Create AsyncScheduler (in-memory, no persistence)
        self.scheduler = AsyncScheduler()

        # Enter async context manager
        await self.scheduler.__aenter__()

        # Start scheduler in background (non-blocking)
        await self.scheduler.start_in_background()
        self._running = True
        console.print("[green]Scheduler started with PostgreSQL persistence[/green]")

        # Recover any pending actions from database
        await self._recover_pending_actions()

    async def stop(self) -> None:
        """
        Gracefully shutdown the scheduler.

        Waits for any currently running jobs to complete before stopping.
        This ensures no actions are interrupted mid-execution.

        Example:
            >>> await service.stop()  # Clean shutdown
        """
        if not self._running:
            console.print("[yellow]Scheduler not running[/yellow]")
            return

        self._running = False

        # Cancel any pending asyncio tasks
        for task_id, task in self._scheduled_tasks.items():
            if not task.done():
                task.cancel()
        self._scheduled_tasks.clear()

        if self.scheduler is not None:
            # Graceful shutdown - waits for running jobs
            await self.scheduler.stop()

            # Exit the async context manager
            try:
                await self.scheduler.__aexit__(None, None, None)
            except Exception:
                pass  # Ignore errors during cleanup

            console.print("[green]Scheduler stopped gracefully[/green]")

        self.scheduler = None

    async def schedule_action(self, action: ScheduledAction) -> str:
        """
        Schedule an action for execution at its scheduled time.

        Creates an asyncio task that will trigger _execute_action
        at the specified scheduled_for time.

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
            ...     payload={"message_template": "Just checking in!"}
            ... )
            >>> job_id = await service.schedule_action(action)
            >>> print(f"Scheduled job: {job_id}")
        """
        if not self._running:
            raise RuntimeError("Scheduler is not running. Call start() first.")

        if action.id is None:
            raise ValueError("Action must have an ID to be scheduled")

        # Calculate delay until scheduled time
        now = datetime.now(timezone.utc)
        scheduled_for = action.scheduled_for
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

        delay_seconds = (scheduled_for - now).total_seconds()
        if delay_seconds < 0:
            delay_seconds = 0  # Execute immediately if overdue

        # Create an asyncio task to execute after delay
        async def delayed_execute():
            try:
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                await self._execute_action(action.id)
            except asyncio.CancelledError:
                pass  # Task was cancelled, don't execute
            finally:
                # Remove from scheduled tasks
                self._scheduled_tasks.pop(action.id, None)

        task = asyncio.create_task(delayed_execute())
        self._scheduled_tasks[action.id] = task

        console.print(
            f"[cyan]Scheduled action {action.id[:8]}... "
            f"for {scheduled_for.strftime('%Y-%m-%d %H:%M:%S %Z')}[/cyan]"
        )

        return action.id

    async def cancel_action(self, action_id: str) -> bool:
        """
        Cancel a scheduled action.

        Removes the scheduled task so it won't execute.
        Note: This does NOT update the database status - use
        ScheduledActionManager for that.

        Args:
            action_id: UUID string of the action to cancel.

        Returns:
            True if the task was found and cancelled.
            False if the task was not found (may have already executed
            or never been scheduled).

        Example:
            >>> cancelled = await service.cancel_action("abc-123")
            >>> if cancelled:
            ...     print("Action cancelled")
            ... else:
            ...     print("Action not found")
        """
        if action_id in self._scheduled_tasks:
            task = self._scheduled_tasks.pop(action_id)
            if not task.done():
                task.cancel()
            console.print(f"[yellow]Cancelled scheduled action {action_id[:8]}...[/yellow]")
            return True
        else:
            console.print(
                f"[dim]Could not cancel action {action_id[:8]}... "
                f"(may have already executed)[/dim]"
            )
            return False

    async def _execute_action(self, action_id: str) -> None:
        """
        Job handler that executes when an action is due.

        This is called at the scheduled time. It:
        1. Fetches the action from the database
        2. Verifies the action is still PENDING
        3. Calls the execute_callback
        4. Marks the action as executed

        Args:
            action_id: UUID string of the action to execute.

        Note:
            All exceptions are caught and logged to prevent the scheduler
            from crashing. Failed actions remain in PENDING status.
        """
        try:
            # Fetch action from database to get latest status
            action = await get_by_id(action_id)

            if action is None:
                console.print(
                    f"[red]Action {action_id[:8]}... not found in database[/red]"
                )
                return

            # Check if action is still pending
            # It may have been cancelled while waiting to execute
            if action.status != ScheduledActionStatus.PENDING:
                console.print(
                    f"[dim]Skipping action {action_id[:8]}... "
                    f"(status: {action.status})[/dim]"
                )
                return

            console.print(
                f"[cyan]Executing scheduled action {action_id[:8]}... "
                f"for prospect {action.prospect_id}[/cyan]"
            )

            # Call the execution callback (e.g., send message)
            await self.execute_callback(action)

            # Mark as executed in database
            success = await mark_executed(action_id)
            if success:
                console.print(
                    f"[green]Action {action_id[:8]}... executed successfully[/green]"
                )
            else:
                console.print(
                    f"[yellow]Action {action_id[:8]}... executed but "
                    f"failed to update status[/yellow]"
                )

        except Exception as e:
            console.print(
                f"[red]Error executing action {action_id[:8]}...: {e}[/red]"
            )
            # Don't re-raise - let scheduler continue with other jobs

    async def _recover_pending_actions(self) -> None:
        """
        Recover pending actions on startup.

        Called during start() to handle actions that were scheduled but
        not executed (e.g., daemon was down when they were due).

        For each pending action:
        - If scheduled_for is in the past: execute immediately
        - If scheduled_for is in the future: reschedule with APScheduler

        This ensures no actions are lost due to daemon restarts.
        """
        try:
            # Get all pending actions from database
            pending_actions = await get_pending_actions()

            if not pending_actions:
                console.print("[dim]No pending actions to recover[/dim]")
                return

            console.print(
                f"[cyan]Recovering {len(pending_actions)} pending action(s)...[/cyan]"
            )

            now = datetime.now(timezone.utc)
            overdue_count = 0
            rescheduled_count = 0

            for action in pending_actions:
                # Make scheduled_for timezone-aware if it isn't
                scheduled_for = action.scheduled_for
                if scheduled_for.tzinfo is None:
                    scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

                if scheduled_for <= now:
                    # Action is overdue - execute immediately
                    console.print(
                        f"[yellow]Executing overdue action {action.id[:8]}... "
                        f"(was due {scheduled_for})[/yellow]"
                    )
                    await self._execute_action(action.id)
                    overdue_count += 1

                    # Rate limiting: wait between overdue executions to prevent Telegram API flooding
                    console.print("[dim]Rate limiting: waiting 5s before next overdue action...[/dim]")
                    await asyncio.sleep(5)
                else:
                    # Action is in the future - reschedule
                    try:
                        await self.schedule_action(action)
                        rescheduled_count += 1
                    except Exception as e:
                        console.print(
                            f"[red]Failed to reschedule action {action.id[:8]}...: {e}[/red]"
                        )

            console.print(
                f"[green]Recovery complete: "
                f"{overdue_count} overdue executed, "
                f"{rescheduled_count} rescheduled[/green]"
            )

        except Exception as e:
            console.print(f"[red]Error during action recovery: {e}[/red]")

    @property
    def is_running(self) -> bool:
        """
        Check if the scheduler is currently running.

        Returns:
            True if scheduler is running and processing jobs.
        """
        return self._running
