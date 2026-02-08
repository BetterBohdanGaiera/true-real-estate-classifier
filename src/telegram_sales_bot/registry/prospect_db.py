# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
"""
Test Prospect Manager - Database operations for test prospect management.

Provides CRUD operations for the test_prospects table using asyncpg connection pool.
Handles prospect assignment to sales reps and status tracking.

Note: This file was migrated from src/sales_agent/registry/prospect_manager.py
      and renamed to test_prospect_manager.py to avoid conflict with telegram skill.

Usage:
    from test_prospect_manager import (
        get_unreached_prospects,
        assign_prospect_to_rep,
        get_prospects_for_rep,
        update_prospect_status,
    )
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timezone
from typing import Optional

import asyncpg
from dotenv import load_dotenv

try:
    from .registry_models import TestProspect, ProspectStatus
except ImportError:
    from registry_models import TestProspect, ProspectStatus

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

def _row_to_prospect(row: asyncpg.Record) -> TestProspect:
    """
    Convert a database row to a TestProspect model.

    Args:
        row: Database record from asyncpg.

    Returns:
        TestProspect: Pydantic model instance.
    """
    result = dict(row)

    # Convert UUID to string
    if result.get("assigned_rep_id") is not None:
        result["assigned_rep_id"] = str(result["assigned_rep_id"])

    # Convert status string to enum
    if isinstance(result.get("status"), str):
        result["status"] = ProspectStatus(result["status"])

    return TestProspect(**result)

# =============================================================================
# CRUD OPERATIONS
# =============================================================================

async def get_all_prospects() -> list[TestProspect]:
    """
    Get all test prospects.

    Returns:
        List of all TestProspect objects.

    Example:
        >>> all_prospects = await get_all_prospects()
        >>> print(f"Total prospects: {len(all_prospects)}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            ORDER BY created_at ASC
            """
        )

        return [_row_to_prospect(row) for row in rows]

async def get_unreached_prospects() -> list[TestProspect]:
    """
    Get all unreached test prospects (not yet contacted).

    Returns:
        List of unreached TestProspect objects.

    Example:
        >>> unreached = await get_unreached_prospects()
        >>> for p in unreached:
        ...     print(f"{p.name} - {p.context}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            WHERE status = $1
            ORDER BY created_at ASC
            """,
            ProspectStatus.UNREACHED.value,
        )

        return [_row_to_prospect(row) for row in rows]

async def get_unassigned_prospects() -> list[TestProspect]:
    """
    Get all prospects that are not yet assigned to any rep.

    Returns:
        List of unassigned TestProspect objects.
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            WHERE assigned_rep_id IS NULL AND status != $1
            ORDER BY created_at ASC
            """,
            ProspectStatus.ARCHIVED.value,
        )

        return [_row_to_prospect(row) for row in rows]

async def get_prospect_by_id(prospect_id: str) -> Optional[TestProspect]:
    """
    Get a prospect by ID.

    Args:
        prospect_id: String ID of the prospect (e.g., "test_001").

    Returns:
        TestProspect if found, None otherwise.
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            WHERE id = $1
            """,
            prospect_id,
        )

        if row:
            return _row_to_prospect(row)
        return None

async def assign_prospect_to_rep(prospect_id: str, rep_id: str) -> bool:
    """
    Assign a prospect to a sales rep.

    Args:
        prospect_id: String ID of the prospect.
        rep_id: UUID of the sales rep (as string).

    Returns:
        True if assigned successfully, False if not found.

    Example:
        >>> success = await assign_prospect_to_rep("test_001", "uuid-here")
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE test_prospects
            SET assigned_rep_id = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            uuid.UUID(rep_id),
            prospect_id,
        )

        return result == "UPDATE 1"

async def unassign_prospect(prospect_id: str) -> bool:
    """
    Remove assignment from a prospect.

    Args:
        prospect_id: String ID of the prospect.

    Returns:
        True if unassigned successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE test_prospects
            SET assigned_rep_id = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            prospect_id,
        )

        return result == "UPDATE 1"

async def get_prospects_for_rep(rep_id: str) -> list[TestProspect]:
    """
    Get all prospects assigned to a specific sales rep.

    Args:
        rep_id: UUID of the sales rep (as string).

    Returns:
        List of TestProspect objects assigned to this rep.

    Example:
        >>> prospects = await get_prospects_for_rep("uuid-here")
        >>> for p in prospects:
        ...     print(f"{p.name} - {p.status}")
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            WHERE assigned_rep_id = $1
            ORDER BY last_contact_at DESC NULLS LAST
            """,
            uuid.UUID(rep_id),
        )

        return [_row_to_prospect(row) for row in rows]

async def update_prospect_status(
    prospect_id: str,
    status: ProspectStatus,
    update_contact: bool = False,
) -> bool:
    """
    Update the status of a prospect.

    Args:
        prospect_id: String ID of the prospect.
        status: New status to set.
        update_contact: If True, also update last_contact_at.

    Returns:
        True if updated successfully, False if not found.

    Example:
        >>> success = await update_prospect_status(
        ...     "test_001",
        ...     ProspectStatus.CONTACTED,
        ...     update_contact=True
        ... )
    """
    async with get_connection() as conn:
        if update_contact:
            result = await conn.execute(
                """
                UPDATE test_prospects
                SET status = $1,
                    last_contact_at = NOW(),
                    updated_at = NOW()
                WHERE id = $2
                """,
                status.value if isinstance(status, ProspectStatus) else status,
                prospect_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE test_prospects
                SET status = $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                status.value if isinstance(status, ProspectStatus) else status,
                prospect_id,
            )

        return result == "UPDATE 1"

async def update_prospect_notes(prospect_id: str, notes: str) -> bool:
    """
    Update the notes for a prospect.

    Args:
        prospect_id: String ID of the prospect.
        notes: New notes content.

    Returns:
        True if updated successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE test_prospects
            SET notes = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            notes,
            prospect_id,
        )

        return result == "UPDATE 1"

async def create_prospect(
    prospect_id: str,
    telegram_id: str,
    name: str,
    context: Optional[str] = None,
    email: Optional[str] = None,
    notes: Optional[str] = None,
) -> TestProspect:
    """
    Create a new test prospect.

    Args:
        prospect_id: String ID for the prospect (e.g., "test_004").
        telegram_id: Telegram @username.
        name: Full name of the prospect.
        context: Background context.
        email: Email address.
        notes: Additional notes.

    Returns:
        TestProspect: Created prospect.
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO test_prospects (
                id, telegram_id, name, context, status, email, notes,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, NOW(), NOW()
            )
            RETURNING id, telegram_id, name, context, status, assigned_rep_id,
                      email, notes, last_contact_at, created_at, updated_at
            """,
            prospect_id,
            telegram_id,
            name,
            context,
            ProspectStatus.UNREACHED.value,
            email,
            notes,
        )

        return _row_to_prospect(row)

async def delete_prospect(prospect_id: str) -> bool:
    """
    Delete a test prospect.

    Args:
        prospect_id: String ID of the prospect.

    Returns:
        True if deleted successfully, False if not found.
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM test_prospects
            WHERE id = $1
            """,
            prospect_id,
        )

        return result == "DELETE 1"

async def get_prospects_by_status(status: ProspectStatus) -> list[TestProspect]:
    """
    Get all prospects with a specific status.

    Args:
        status: Status to filter by.

    Returns:
        List of TestProspect objects with the given status.
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, name, context, status, assigned_rep_id,
                   email, notes, last_contact_at, created_at, updated_at
            FROM test_prospects
            WHERE status = $1
            ORDER BY created_at ASC
            """,
            status.value if isinstance(status, ProspectStatus) else status,
        )

        return [_row_to_prospect(row) for row in rows]

async def count_prospects_for_rep(rep_id: str) -> int:
    """
    Count how many prospects are assigned to a rep.

    Args:
        rep_id: UUID of the sales rep (as string).

    Returns:
        Number of prospects assigned to this rep.
    """
    async with get_connection() as conn:
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM test_prospects
            WHERE assigned_rep_id = $1
            """,
            uuid.UUID(rep_id),
        )

        return result or 0
