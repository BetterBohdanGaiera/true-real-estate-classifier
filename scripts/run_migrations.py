#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Database Migration Runner.

Automatically applies pending SQL migrations from src/sales_agent/migrations/
directory. Tracks applied migrations in schema_migrations table.

Features:
- Creates schema_migrations table to track applied migrations
- Reads all .sql files from migrations directory
- Executes migrations in sorted order (001_, 002_, etc.)
- Skips already-applied migrations (idempotent)
- Tracks applied migrations with version and timestamp
- Safe to run multiple times

Usage:
    # Programmatic (from init.py or daemon.py):
    from scripts.run_migrations import run_migrations
    applied = await run_migrations()

    # Standalone:
    uv run python scripts/run_migrations.py

Example:
    >>> import asyncio
    >>> from scripts.run_migrations import run_migrations
    >>> count = asyncio.run(run_migrations())
    >>> print(f"Applied {count} migrations")
"""

from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Tuple

import asyncpg
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()

# Path to migrations directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "src" / "sales_agent" / "migrations"


async def create_schema_migrations_table(conn: asyncpg.Connection) -> None:
    """
    Create schema_migrations table if it doesn't exist.

    This table tracks which migrations have been applied.
    It is safe to call multiple times - uses IF NOT EXISTS.

    Args:
        conn: Database connection.

    Example:
        >>> conn = await asyncpg.connect(DATABASE_URL)
        >>> await create_schema_migrations_table(conn)
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Add comment for documentation
    await conn.execute("""
        COMMENT ON TABLE schema_migrations IS
        'Tracks which database migrations have been applied'
    """)


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    """
    Get set of migration versions that have already been applied.

    Args:
        conn: Database connection.

    Returns:
        Set of version strings (e.g., {"001", "002"}).

    Example:
        >>> applied = await get_applied_migrations(conn)
        >>> print(applied)  # {'001', '002'}
    """
    rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    return {row["version"] for row in rows}


async def get_pending_migrations(applied: set[str]) -> List[Tuple[str, Path]]:
    """
    Get list of pending migration files.

    Scans the migrations directory for .sql files and filters out
    those already in the applied set.

    Args:
        applied: Set of already applied migration versions.

    Returns:
        List of (version, file_path) tuples for pending migrations,
        sorted by version number.

    Example:
        >>> applied = {"001"}
        >>> pending = await get_pending_migrations(applied)
        >>> print(pending)  # [("002", Path("002_new_table.sql"))]
    """
    if not MIGRATIONS_DIR.exists():
        console.print(f"[yellow]Migrations directory not found: {MIGRATIONS_DIR}[/yellow]")
        return []

    pending: List[Tuple[str, Path]] = []

    # Get all .sql files
    for file_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Extract version from filename (e.g., "001" from "001_scheduled_actions.sql")
        filename_parts = file_path.stem.split("_")
        if not filename_parts:
            console.print(f"[yellow]Skipping invalid migration filename: {file_path.name}[/yellow]")
            continue

        version = filename_parts[0]

        # Validate version is numeric
        if not version.isdigit():
            console.print(f"[yellow]Skipping non-numeric version: {file_path.name}[/yellow]")
            continue

        if version not in applied:
            pending.append((version, file_path))

    return sorted(pending, key=lambda x: x[0])


async def apply_migration(
    conn: asyncpg.Connection,
    version: str,
    file_path: Path
) -> None:
    """
    Apply a single migration file.

    Executes the SQL in a transaction and records the migration
    as applied in the schema_migrations table.

    Args:
        conn: Database connection.
        version: Migration version string (e.g., "001").
        file_path: Path to SQL migration file.

    Raises:
        Exception: If migration fails (transaction is rolled back).

    Example:
        >>> await apply_migration(conn, "001", Path("001_create_users.sql"))
    """
    console.print(f"  [cyan]Applying migration {version}: {file_path.name}[/cyan]")

    # Read SQL file
    try:
        sql = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to read migration file {file_path}: {e}")

    if not sql.strip():
        raise RuntimeError(f"Migration file is empty: {file_path}")

    # Execute in a transaction
    async with conn.transaction():
        # Execute migration SQL
        await conn.execute(sql)

        # Record migration as applied
        await conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES ($1, NOW())",
            version
        )

    console.print(f"  [green]✓[/green] Migration {version} applied successfully")


async def run_migrations() -> int:
    """
    Run all pending database migrations.

    Connects to the database using DATABASE_URL from environment,
    creates the schema_migrations tracking table if needed, and
    applies any pending migrations in sorted order.

    This function is idempotent - safe to run multiple times.
    Already-applied migrations will be skipped.

    Returns:
        Number of migrations applied.

    Raises:
        RuntimeError: If DATABASE_URL is not set or connection fails.

    Example:
        >>> count = await run_migrations()
        >>> print(f"Applied {count} migrations")
        Applied 2 migrations
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Please set it in your .env file."
        )

    # Connect to database
    try:
        conn = await asyncpg.connect(database_url, timeout=10)
    except asyncpg.PostgresError as e:
        raise RuntimeError(f"Failed to connect to database: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error connecting to database: {e}")

    try:
        # Create schema_migrations table
        await create_schema_migrations_table(conn)

        # Get applied migrations
        applied = await get_applied_migrations(conn)

        # Get pending migrations
        pending = await get_pending_migrations(applied)

        if not pending:
            console.print("[dim]No pending migrations[/dim]")
            return 0

        console.print(f"[bold]Found {len(pending)} pending migration(s)[/bold]")

        # Apply each migration
        for version, file_path in pending:
            await apply_migration(conn, version, file_path)

        return len(pending)

    finally:
        await conn.close()


async def main() -> None:
    """Main entry point for standalone execution."""
    console.print(
        Panel(
            "[bold blue]Database Migration Runner[/bold blue]",
            width=console.width
        )
    )

    try:
        applied_count = await run_migrations()
        console.print(
            f"\n[bold green]Success![/bold green] Applied {applied_count} migration(s)"
        )
        sys.exit(0)
    except RuntimeError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
