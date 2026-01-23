# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
"""
Sales Representative Manager - Database operations for sales rep registration.

Provides CRUD operations for the sales_representatives table using asyncpg connection pool.
Follows the same patterns as scheduled_action_manager.py.

Usage:
    from sales_agent.registry.sales_rep_manager import (
        create_sales_rep,
        get_by_telegram_id,
        list_all,
        list_active,
        approve_rep,
        suspend_rep,
        remove_rep,
        close_pool,
    )
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import asyncpg
from dotenv import load_dotenv

from sales_agent.registry.models import SalesRepresentative, SalesRepStatus

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


def _row_to_sales_rep(row: asyncpg.Record) -> SalesRepresentative:
    """
    Convert a database row to a SalesRepresentative model.

    Args:
        row: Database record from asyncpg.

    Returns:
        SalesRepresentative: Pydantic model instance.
    """
    result = dict(row)

    # Convert UUID to string
    if result.get("id") is not None:
        result["id"] = str(result["id"])

    if result.get("approved_by") is not None:
        result["approved_by"] = str(result["approved_by"])

    # Convert status string to enum
    if isinstance(result.get("status"), str):
        result["status"] = SalesRepStatus(result["status"])

    return SalesRepresentative(**result)


# =============================================================================
# CRUD OPERATIONS
# =============================================================================


async def create_sales_rep(
    telegram_id: int,
    name: str,
    email: str,
    telegram_username: Optional[str] = None,
    auto_approve: bool = True,
) -> SalesRepresentative:
    """
    Create a new sales representative.

    Args:
        telegram_id: Telegram user ID.
        name: Full name of the rep.
        email: Corporate email address.
        telegram_username: Optional @username (without @).
        auto_approve: If True, immediately set status to ACTIVE.

    Returns:
        SalesRepresentative: Created rep with database-generated ID.

    Example:
        >>> rep = await create_sales_rep(
        ...     telegram_id=123456789,
        ...     name="Иван Петров",
        ...     email="ivan@truerealestate.bali",
        ...     telegram_username="ivanpetrov"
        ... )
        >>> print(rep.id)  # UUID string
    """
    now = datetime.utcnow()
    status = SalesRepStatus.ACTIVE if auto_approve else SalesRepStatus.PENDING

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sales_representatives (
                telegram_id, telegram_username, name, email, status,
                registered_at, approved_at, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, NOW(), NOW()
            )
            RETURNING id, telegram_id, telegram_username, name, email, status,
                      calendar_account_name, is_admin, registered_at, approved_at,
                      approved_by, created_at, updated_at
            """,
            telegram_id,
            telegram_username,
            name,
            email,
            status.value,
            now,
            now if auto_approve else None,
        )

        return _row_to_sales_rep(row)


async def get_by_telegram_id(telegram_id: int) -> Optional[SalesRepresentative]:
    """
    Get a sales rep by their Telegram ID.

    Args:
        telegram_id: Telegram user ID.

    Returns:
        SalesRepresentative if found, None otherwise.

    Example:
        >>> rep = await get_by_telegram_id(123456789)
        >>> if rep:
        ...     print(f"Found: {rep.name}")
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, telegram_username, name, email, status,
                   calendar_account_name, is_admin, registered_at, approved_at,
                   approved_by, created_at, updated_at
            FROM sales_representatives
            WHERE telegram_id = $1
            """,
            telegram_id,
        )

        if row:
            return _row_to_sales_rep(row)
        return None


async def get_by_id(rep_id: str) -> Optional[SalesRepresentative]:
    """
    Get a sales rep by their UUID.

    Args:
        rep_id: UUID of the sales rep (as string).

    Returns:
        SalesRepresentative if found, None otherwise.
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, telegram_username, name, email, status,
                   calendar_account_name, is_admin, registered_at, approved_at,
                   approved_by, created_at, updated_at
            FROM sales_representatives
            WHERE id = $1
            """,
            uuid.UUID(rep_id),
        )

        if row:
            return _row_to_sales_rep(row)
        return None


async def list_all() -> list[SalesRepresentative]:
    """
    Get all sales representatives.

    Returns:
        List of all SalesRepresentative objects, ordered by created_at descending.

    Example:
        >>> all_reps = await list_all()
        >>> print(f"Total reps: {len(all_reps)}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, telegram_username, name, email, status,
                   calendar_account_name, is_admin, registered_at, approved_at,
                   approved_by, created_at, updated_at
            FROM sales_representatives
            ORDER BY created_at DESC
            """
        )

        return [_row_to_sales_rep(row) for row in rows]


async def list_active() -> list[SalesRepresentative]:
    """
    Get all active sales representatives.

    Returns:
        List of active SalesRepresentative objects, ordered by name.

    Example:
        >>> active_reps = await list_active()
        >>> for rep in active_reps:
        ...     print(f"{rep.name} - {rep.email}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, telegram_username, name, email, status,
                   calendar_account_name, is_admin, registered_at, approved_at,
                   approved_by, created_at, updated_at
            FROM sales_representatives
            WHERE status = $1
            ORDER BY name ASC
            """,
            SalesRepStatus.ACTIVE.value,
        )

        return [_row_to_sales_rep(row) for row in rows]


async def list_pending() -> list[SalesRepresentative]:
    """
    Get all pending sales representatives (awaiting approval).

    Returns:
        List of pending SalesRepresentative objects.
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, telegram_username, name, email, status,
                   calendar_account_name, is_admin, registered_at, approved_at,
                   approved_by, created_at, updated_at
            FROM sales_representatives
            WHERE status = $1
            ORDER BY registered_at ASC
            """,
            SalesRepStatus.PENDING.value,
        )

        return [_row_to_sales_rep(row) for row in rows]


async def approve_rep(rep_id: str, approved_by: Optional[str] = None) -> bool:
    """
    Approve a pending sales rep.

    Args:
        rep_id: UUID of the rep to approve.
        approved_by: UUID of the admin who approved (optional).

    Returns:
        True if approved successfully, False if not found or already approved.

    Example:
        >>> success = await approve_rep("550e8400-e29b-41d4-a716-446655440000")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET status = $1,
                approved_at = NOW(),
                approved_by = $2,
                updated_at = NOW()
            WHERE id = $3 AND status = $4
            """,
            SalesRepStatus.ACTIVE.value,
            uuid.UUID(approved_by) if approved_by else None,
            uuid.UUID(rep_id),
            SalesRepStatus.PENDING.value,
        )

        return result == "UPDATE 1"


async def suspend_rep(rep_id: str) -> bool:
    """
    Suspend an active sales rep.

    Args:
        rep_id: UUID of the rep to suspend.

    Returns:
        True if suspended successfully, False if not found or not active.

    Example:
        >>> success = await suspend_rep("550e8400-e29b-41d4-a716-446655440000")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET status = $1,
                updated_at = NOW()
            WHERE id = $2 AND status = $3
            """,
            SalesRepStatus.SUSPENDED.value,
            uuid.UUID(rep_id),
            SalesRepStatus.ACTIVE.value,
        )

        return result == "UPDATE 1"


async def remove_rep(telegram_id: int) -> bool:
    """
    Remove a sales rep (mark as removed).

    Args:
        telegram_id: Telegram ID of the rep to remove.

    Returns:
        True if removed successfully, False if not found.

    Example:
        >>> success = await remove_rep(123456789)
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET status = $1,
                updated_at = NOW()
            WHERE telegram_id = $2 AND status != $1
            """,
            SalesRepStatus.REMOVED.value,
            telegram_id,
        )

        return result == "UPDATE 1"


async def reactivate_rep(telegram_id: int) -> bool:
    """
    Reactivate a suspended or removed sales rep.

    Args:
        telegram_id: Telegram ID of the rep to reactivate.

    Returns:
        True if reactivated successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET status = $1,
                updated_at = NOW()
            WHERE telegram_id = $2 AND status IN ($3, $4)
            """,
            SalesRepStatus.ACTIVE.value,
            telegram_id,
            SalesRepStatus.SUSPENDED.value,
            SalesRepStatus.REMOVED.value,
        )

        return result == "UPDATE 1"


async def update_calendar_account(telegram_id: int, calendar_account: str) -> bool:
    """
    Update the calendar account name for a sales rep.

    Args:
        telegram_id: Telegram ID of the rep.
        calendar_account: Google Calendar account email/name.

    Returns:
        True if updated successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET calendar_account_name = $1,
                updated_at = NOW()
            WHERE telegram_id = $2
            """,
            calendar_account,
            telegram_id,
        )

        return result == "UPDATE 1"


async def set_admin(telegram_id: int, is_admin: bool = True) -> bool:
    """
    Set or unset admin status for a sales rep.

    Args:
        telegram_id: Telegram ID of the rep.
        is_admin: Whether to grant or revoke admin status.

    Returns:
        True if updated successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE sales_representatives
            SET is_admin = $1,
                updated_at = NOW()
            WHERE telegram_id = $2
            """,
            is_admin,
            telegram_id,
        )

        return result == "UPDATE 1"


async def is_registered(telegram_id: int) -> bool:
    """
    Check if a user is registered (any status except removed).

    Args:
        telegram_id: Telegram ID to check.

    Returns:
        True if registered, False otherwise.
    """
    rep = await get_by_telegram_id(telegram_id)
    return rep is not None and rep.status != SalesRepStatus.REMOVED


async def is_active(telegram_id: int) -> bool:
    """
    Check if a user is an active sales rep.

    Args:
        telegram_id: Telegram ID to check.

    Returns:
        True if active, False otherwise.
    """
    rep = await get_by_telegram_id(telegram_id)
    return rep is not None and rep.status == SalesRepStatus.ACTIVE
