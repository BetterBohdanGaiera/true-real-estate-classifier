# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
"""
Scheduled Action Manager - Database operations for scheduled follow-ups and reminders.

Provides CRUD operations for the scheduled_actions table using asyncpg connection pool.
All times are stored in UTC and converted to Bali time (UTC+8) for display.

Usage:
    from scheduled_action_manager import (
        create_scheduled_action,
        get_pending_actions,
        cancel_pending_for_prospect,
        mark_executed,
        get_by_id,
        close_pool,
    )
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

import asyncpg
from dotenv import load_dotenv

from models import ScheduledAction, ScheduledActionStatus, ScheduledActionType

load_dotenv()


# =============================================================================
# CONNECTION POOL
# =============================================================================

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.

    Returns:
        asyncpg.Pool: Database connection pool.

    Raises:
        RuntimeError: If DATABASE_URL environment variable is not set.
    """
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """
    Get a database connection from the pool.

    Yields:
        asyncpg.Connection: Database connection.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _row_to_scheduled_action(row: asyncpg.Record) -> ScheduledAction:
    """
    Convert a database row to a ScheduledAction model.

    Args:
        row: Database record from asyncpg.

    Returns:
        ScheduledAction: Pydantic model instance.
    """
    result = dict(row)

    # Convert UUID to string
    if result.get("id") is not None:
        result["id"] = str(result["id"])

    # Parse JSONB payload field
    if isinstance(result.get("payload"), str):
        result["payload"] = json.loads(result["payload"])
    elif result.get("payload") is None:
        result["payload"] = {}

    # Convert action_type string to enum
    if isinstance(result.get("action_type"), str):
        result["action_type"] = ScheduledActionType(result["action_type"])

    # Convert status string to enum
    if isinstance(result.get("status"), str):
        result["status"] = ScheduledActionStatus(result["status"])

    return ScheduledAction(**result)


# =============================================================================
# CRUD OPERATIONS
# =============================================================================


async def create_scheduled_action(
    prospect_id: str,
    action_type: ScheduledActionType,
    scheduled_for: datetime,
    payload: dict,
) -> ScheduledAction:
    """
    Create a new scheduled action.

    Args:
        prospect_id: Telegram ID of prospect (as string).
        action_type: Type of action (follow_up or pre_meeting_reminder).
        scheduled_for: When to execute (datetime object, preferably with timezone).
        payload: Action-specific data (message_template, context, etc.).

    Returns:
        ScheduledAction: Created action with database-generated ID.

    Example:
        >>> from datetime import datetime, timedelta, timezone
        >>> action = await create_scheduled_action(
        ...     prospect_id="123456789",
        ...     action_type=ScheduledActionType.FOLLOW_UP,
        ...     scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2),
        ...     payload={"message_template": "Hi! Just checking in...", "reason": "Client requested follow-up"}
        ... )
        >>> print(action.id)  # UUID string
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scheduled_actions (
                prospect_id, action_type, scheduled_for, status, payload,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, NOW(), NOW()
            )
            RETURNING id, prospect_id, action_type, scheduled_for, status,
                      payload, created_at, updated_at, executed_at,
                      cancelled_at, cancel_reason
            """,
            prospect_id,
            action_type.value if isinstance(action_type, ScheduledActionType) else action_type,
            scheduled_for,
            ScheduledActionStatus.PENDING.value,
            json.dumps(payload),
        )

        return _row_to_scheduled_action(row)


async def get_pending_actions(prospect_id: Optional[str] = None) -> list[ScheduledAction]:
    """
    Get all pending scheduled actions, optionally filtered by prospect.

    Args:
        prospect_id: Optional filter by prospect telegram ID.

    Returns:
        List of pending ScheduledAction objects, ordered by scheduled_for (ascending).

    Example:
        >>> # Get all pending actions
        >>> actions = await get_pending_actions()
        >>>
        >>> # Get pending actions for a specific prospect
        >>> actions = await get_pending_actions(prospect_id="123456789")
    """
    async with get_connection() as conn:
        if prospect_id is not None:
            rows = await conn.fetch(
                """
                SELECT id, prospect_id, action_type, scheduled_for, status,
                       payload, created_at, updated_at, executed_at,
                       cancelled_at, cancel_reason
                FROM scheduled_actions
                WHERE status = $1 AND prospect_id = $2
                ORDER BY scheduled_for ASC
                """,
                ScheduledActionStatus.PENDING.value,
                prospect_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, prospect_id, action_type, scheduled_for, status,
                       payload, created_at, updated_at, executed_at,
                       cancelled_at, cancel_reason
                FROM scheduled_actions
                WHERE status = $1
                ORDER BY scheduled_for ASC
                """,
                ScheduledActionStatus.PENDING.value,
            )

        return [_row_to_scheduled_action(row) for row in rows]


async def cancel_pending_for_prospect(prospect_id: str, reason: str) -> int:
    """
    Cancel all pending actions for a prospect.

    This is typically called when a client responds to a conversation,
    making scheduled follow-ups unnecessary.

    Args:
        prospect_id: Telegram ID of prospect.
        reason: Cancellation reason (e.g., "client_responded", "human_active").

    Returns:
        Number of actions cancelled.

    Example:
        >>> cancelled = await cancel_pending_for_prospect(
        ...     prospect_id="123456789",
        ...     reason="client_responded"
        ... )
        >>> print(f"Cancelled {cancelled} pending follow-ups")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE scheduled_actions
            SET status = $1,
                cancelled_at = NOW(),
                cancel_reason = $2,
                updated_at = NOW()
            WHERE prospect_id = $3 AND status = $4
            """,
            ScheduledActionStatus.CANCELLED.value,
            reason,
            prospect_id,
            ScheduledActionStatus.PENDING.value,
        )

        # Parse "UPDATE N" result string to get count
        if result:
            parts = result.split()
            if len(parts) >= 2:
                return int(parts[1])
        return 0


async def mark_executed(action_id: str) -> bool:
    """
    Mark an action as executed.

    Called after successfully executing a scheduled action.

    Args:
        action_id: UUID of the action (as string).

    Returns:
        True if marked successfully, False if not found.

    Example:
        >>> success = await mark_executed("550e8400-e29b-41d4-a716-446655440000")
        >>> if success:
        ...     print("Action marked as executed")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE scheduled_actions
            SET status = $1,
                executed_at = NOW(),
                updated_at = NOW()
            WHERE id = $2 AND status = $3
            """,
            ScheduledActionStatus.EXECUTED.value,
            uuid.UUID(action_id),
            ScheduledActionStatus.PENDING.value,
        )

        return result == "UPDATE 1"


async def get_by_id(action_id: str) -> Optional[ScheduledAction]:
    """
    Get a scheduled action by ID.

    Args:
        action_id: UUID of the action (as string).

    Returns:
        ScheduledAction if found, None otherwise.

    Example:
        >>> action = await get_by_id("550e8400-e29b-41d4-a716-446655440000")
        >>> if action:
        ...     print(f"Found action: {action.action_type} for {action.prospect_id}")
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, prospect_id, action_type, scheduled_for, status,
                   payload, created_at, updated_at, executed_at,
                   cancelled_at, cancel_reason
            FROM scheduled_actions
            WHERE id = $1
            """,
            uuid.UUID(action_id),
        )

        if row:
            return _row_to_scheduled_action(row)
        return None


async def get_due_actions(before: Optional[datetime] = None) -> list[ScheduledAction]:
    """
    Get pending actions that are due for execution.

    This is useful for startup recovery to find actions that should have
    been executed but weren't (e.g., due to daemon restart).

    Args:
        before: Get actions scheduled before this time. Defaults to current time.

    Returns:
        List of ScheduledAction objects that are due for execution.

    Example:
        >>> # Get all overdue actions
        >>> overdue = await get_due_actions()
        >>> for action in overdue:
        ...     await execute_action(action)
    """
    if before is None:
        before = datetime.utcnow()

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, prospect_id, action_type, scheduled_for, status,
                   payload, created_at, updated_at, executed_at,
                   cancelled_at, cancel_reason
            FROM scheduled_actions
            WHERE status = $1 AND scheduled_for <= $2
            ORDER BY scheduled_for ASC
            """,
            ScheduledActionStatus.PENDING.value,
            before,
        )

        return [_row_to_scheduled_action(row) for row in rows]


async def get_actions_for_prospect(
    prospect_id: str,
    status: Optional[ScheduledActionStatus] = None,
    limit: int = 100,
) -> list[ScheduledAction]:
    """
    Get all scheduled actions for a prospect, optionally filtered by status.

    Args:
        prospect_id: Telegram ID of prospect.
        status: Optional filter by status.
        limit: Maximum number of actions to return.

    Returns:
        List of ScheduledAction objects, ordered by scheduled_for (descending).

    Example:
        >>> # Get all actions for a prospect
        >>> actions = await get_actions_for_prospect("123456789")
        >>>
        >>> # Get only executed actions
        >>> executed = await get_actions_for_prospect(
        ...     "123456789",
        ...     status=ScheduledActionStatus.EXECUTED
        ... )
    """
    async with get_connection() as conn:
        if status is not None:
            rows = await conn.fetch(
                """
                SELECT id, prospect_id, action_type, scheduled_for, status,
                       payload, created_at, updated_at, executed_at,
                       cancelled_at, cancel_reason
                FROM scheduled_actions
                WHERE prospect_id = $1 AND status = $2
                ORDER BY scheduled_for DESC
                LIMIT $3
                """,
                prospect_id,
                status.value if isinstance(status, ScheduledActionStatus) else status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, prospect_id, action_type, scheduled_for, status,
                       payload, created_at, updated_at, executed_at,
                       cancelled_at, cancel_reason
                FROM scheduled_actions
                WHERE prospect_id = $1
                ORDER BY scheduled_for DESC
                LIMIT $2
                """,
                prospect_id,
                limit,
            )

        return [_row_to_scheduled_action(row) for row in rows]


async def delete_old_actions(days: int = 30) -> int:
    """
    Delete old executed and cancelled actions for cleanup.

    Args:
        days: Delete actions older than this many days.

    Returns:
        Number of actions deleted.

    Example:
        >>> # Clean up actions older than 30 days
        >>> deleted = await delete_old_actions(days=30)
        >>> print(f"Deleted {deleted} old actions")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM scheduled_actions
            WHERE status IN ($1, $2)
              AND updated_at < NOW() - INTERVAL '%s days'
            """ % days,
            ScheduledActionStatus.EXECUTED.value,
            ScheduledActionStatus.CANCELLED.value,
        )

        # Parse "DELETE N" result string to get count
        if result:
            parts = result.split()
            if len(parts) >= 2:
                return int(parts[1])
        return 0


async def update_payload(action_id: str, payload: dict) -> bool:
    """
    Update the payload of a scheduled action.

    Args:
        action_id: UUID of the action (as string).
        payload: New payload data.

    Returns:
        True if updated successfully, False if not found.

    Example:
        >>> success = await update_payload(
        ...     "550e8400-e29b-41d4-a716-446655440000",
        ...     {"message_template": "Updated message", "reason": "Updated reason"}
        ... )
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE scheduled_actions
            SET payload = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            json.dumps(payload),
            uuid.UUID(action_id),
        )

        return result == "UPDATE 1"


async def reschedule_action(action_id: str, new_scheduled_for: datetime) -> bool:
    """
    Reschedule a pending action to a new time.

    Args:
        action_id: UUID of the action (as string).
        new_scheduled_for: New scheduled execution time.

    Returns:
        True if rescheduled successfully, False if not found or not pending.

    Example:
        >>> from datetime import datetime, timedelta, timezone
        >>> new_time = datetime.now(timezone.utc) + timedelta(hours=4)
        >>> success = await reschedule_action(
        ...     "550e8400-e29b-41d4-a716-446655440000",
        ...     new_time
        ... )
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE scheduled_actions
            SET scheduled_for = $1,
                updated_at = NOW()
            WHERE id = $2 AND status = $3
            """,
            new_scheduled_for,
            uuid.UUID(action_id),
            ScheduledActionStatus.PENDING.value,
        )

        return result == "UPDATE 1"
