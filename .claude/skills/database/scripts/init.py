# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Database initialization and migration module.

Provides functions to verify database connectivity and ensure schema is up-to-date.
This module should be called during daemon startup before any database operations.

Usage:
    from scripts.init import init_database

    # In your daemon's initialize() method:
    await init_database()

Example:
    >>> import asyncio
    >>> from scripts.init import init_database
    >>> asyncio.run(init_database())  # Verifies DB and runs migrations
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import asyncpg
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()

# Path to migrations directory (at skill level: .claude/skills/database/migrations/)
SCRIPT_DIR = Path(__file__).parent
MIGRATIONS_DIR = SCRIPT_DIR.parent / "migrations"


async def check_database_connection() -> bool:
    """
    Test database connectivity.

    Attempts to connect to the database specified by DATABASE_URL environment
    variable and verifies the connection is working.

    Returns:
        True if connection successful, False otherwise.

    Raises:
        RuntimeError: If DATABASE_URL environment variable is not set.

    Example:
        >>> import asyncio
        >>> from scripts.init import check_database_connection
        >>> asyncio.run(check_database_connection())
        True
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Please set it in your .env file. "
            "Example: DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require"
        )

    try:
        # Test connection with a reasonable timeout
        conn = await asyncpg.connect(database_url, timeout=10)
        # Verify connection works with a simple query
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except asyncpg.InvalidCatalogNameError as e:
        console.print(
            Panel(
                "[red]Database does not exist.[/red]\n\n"
                "Please create the database first. For NeonDB, this is done automatically.\n"
                f"Error: {e}",
                title="Database Error",
                width=80,
            )
        )
        return False
    except asyncpg.InvalidPasswordError:
        console.print(
            Panel(
                "[red]Invalid database credentials.[/red]\n\n"
                "Please check your DATABASE_URL username and password.",
                title="Authentication Error",
                width=80,
            )
        )
        return False
    except asyncpg.PostgresConnectionError as e:
        console.print(
            Panel(
                "[red]Cannot connect to database server.[/red]\n\n"
                "Please check that:\n"
                "1. The database server is running\n"
                "2. The host and port in DATABASE_URL are correct\n"
                "3. Network connectivity is available\n\n"
                f"Error: {e}",
                title="Connection Error",
                width=80,
            )
        )
        return False
    except OSError as e:
        console.print(
            Panel(
                f"[red]Network error connecting to database.[/red]\n\n"
                f"Error: {e}",
                title="Network Error",
                width=80,
            )
        )
        return False
    except Exception as e:
        console.print(
            Panel(
                f"[red]Database connection failed with unexpected error.[/red]\n\n"
                f"Error type: {type(e).__name__}\n"
                f"Error: {e}",
                title="Database Error",
                width=80,
            )
        )
        return False


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    """
    Get the set of already-applied migration names from the database.

    This queries the schema_migrations table to determine which migrations
    have already been applied, preventing duplicate execution.

    Supports both legacy schema (version column) and new schema (migration_name column).

    Args:
        conn: Active database connection.

    Returns:
        Set of migration filenames that have been applied.

    Note:
        Creates the schema_migrations table if it doesn't exist.
    """
    # Check if table exists and what columns it has
    columns = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'schema_migrations'
        """
    )
    column_names = {row["column_name"] for row in columns}

    if not column_names:
        # Table doesn't exist - create it with new schema
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        return set()

    # Determine which column to use for migration names
    if "migration_name" in column_names:
        # New schema
        rows = await conn.fetch("SELECT migration_name FROM schema_migrations")
        return {row["migration_name"] for row in rows}
    elif "version" in column_names:
        # Legacy schema - version column contains migration names
        rows = await conn.fetch("SELECT version FROM schema_migrations")
        return {row["version"] for row in rows}
    else:
        # Unknown schema - log warning and return empty set
        console.print(
            "[yellow]Warning: schema_migrations table has unexpected schema. "
            "Migrations will be re-applied if needed.[/yellow]"
        )
        return set()


async def apply_migration(
    conn: asyncpg.Connection, migration_path: Path, use_legacy_schema: bool = False
) -> bool:
    """
    Apply a single migration file to the database.

    Executes the SQL in the migration file and records it in schema_migrations.
    Uses a transaction to ensure atomicity.

    Args:
        conn: Active database connection.
        migration_path: Path to the .sql migration file.
        use_legacy_schema: If True, use 'version' column instead of 'migration_name'.

    Returns:
        True if migration was applied successfully.

    Raises:
        Exception: If migration SQL fails to execute.
    """
    migration_name = migration_path.name
    sql_content = migration_path.read_text(encoding="utf-8")

    # Execute migration within a transaction
    async with conn.transaction():
        # Execute the migration SQL
        await conn.execute(sql_content)

        # Record the migration using appropriate column name
        if use_legacy_schema:
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1)",
                migration_name,
            )
        else:
            await conn.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
                migration_name,
            )

    return True


async def run_migrations() -> int:
    """
    Run all pending database migrations.

    Scans the migrations directory for .sql files and applies any that
    haven't been applied yet. Migrations are applied in alphabetical order
    by filename (so use numbered prefixes like 001_, 002_, etc.).

    Supports both legacy schema (version column) and new schema (migration_name column)
    for backward compatibility with existing databases.

    Returns:
        Number of migrations applied.

    Raises:
        RuntimeError: If DATABASE_URL is not set or migrations fail.

    Example:
        >>> import asyncio
        >>> from scripts.init import run_migrations
        >>> applied = asyncio.run(run_migrations())
        >>> print(f"Applied {applied} migration(s)")
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    if not MIGRATIONS_DIR.exists():
        console.print(f"[yellow]Migrations directory not found: {MIGRATIONS_DIR}[/yellow]")
        return 0

    # Get all migration files sorted alphabetically
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        console.print("[dim]No migration files found[/dim]")
        return 0

    conn = await asyncpg.connect(database_url, timeout=10)
    try:
        # Check schema type for backward compatibility
        columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'schema_migrations'
            """
        )
        column_names = {row["column_name"] for row in columns}
        use_legacy_schema = "version" in column_names and "migration_name" not in column_names

        # Get already applied migrations
        applied_migrations = await get_applied_migrations(conn)

        # Find pending migrations
        pending_migrations = [
            mf for mf in migration_files if mf.name not in applied_migrations
        ]

        if not pending_migrations:
            return 0

        applied_count = 0
        for migration_path in pending_migrations:
            console.print(f"    [cyan]Applying: {migration_path.name}[/cyan]")
            try:
                await apply_migration(conn, migration_path, use_legacy_schema)
                console.print(f"    [green]Applied: {migration_path.name}[/green]")
                applied_count += 1
            except Exception as e:
                console.print(
                    f"    [red]Failed to apply {migration_path.name}: {e}[/red]"
                )
                raise RuntimeError(
                    f"Migration {migration_path.name} failed: {e}"
                ) from e

        return applied_count
    finally:
        await conn.close()


def _mask_database_url(database_url: str) -> str:
    """
    Mask sensitive parts of database URL for safe display.

    Hides password and shows only host/database info.

    Args:
        database_url: Full database URL with credentials.

    Returns:
        Masked URL safe for logging.

    Example:
        >>> _mask_database_url("postgresql://user:secret@host.db.com:5432/mydb")
        'host.db.com:5432/mydb'
    """
    if "@" in database_url:
        # Extract everything after @ (host/port/database)
        return database_url.split("@")[1].split("?")[0]
    return "configured"


async def init_database() -> None:
    """
    Initialize database: verify connection and run migrations.

    This should be called during daemon startup before any database operations.
    It performs the following steps:
    1. Verifies DATABASE_URL environment variable is set
    2. Tests database connectivity with timeout
    3. Runs any pending migrations to ensure schema is up-to-date

    Raises:
        RuntimeError: If database is not accessible or migrations fail.

    Example:
        >>> import asyncio
        >>> from scripts.init import init_database
        >>> asyncio.run(init_database())  # Called in daemon.initialize()

    Note:
        This function is idempotent - it's safe to call multiple times.
        Already-applied migrations are skipped.
    """
    console.print(Panel("[bold blue]Initializing database...[/bold blue]", width=80))

    # Check DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Please add it to your .env file. "
            "Example: DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require"
        )

    masked_url = _mask_database_url(database_url)
    console.print(f"  [dim]Database: {masked_url}[/dim]")

    # Test connectivity
    console.print("  [cyan]Testing database connection...[/cyan]")
    if not await check_database_connection():
        raise RuntimeError(
            "Cannot connect to database. Please check your DATABASE_URL and ensure "
            "the database server is running."
        )
    console.print("  [green]>[/green] Database connection successful")

    # Run migrations
    console.print("  [cyan]Running migrations...[/cyan]")
    try:
        applied_count = await run_migrations()
        if applied_count > 0:
            console.print(f"  [green]>[/green] Applied {applied_count} migration(s)")
        else:
            console.print("  [green]>[/green] All migrations up-to-date")
    except Exception as e:
        raise RuntimeError(f"Migration failed: {e}") from e

    console.print(
        Panel("[bold green]Database initialized successfully[/bold green]", width=80)
    )


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


async def _main() -> None:
    """CLI entry point for running database initialization manually."""
    try:
        await init_database()
    except RuntimeError as e:
        console.print(f"\n[red bold]Error: {e}[/red bold]")
        raise SystemExit(1) from e


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
