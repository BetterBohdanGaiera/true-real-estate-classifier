#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "anthropic>=0.40.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Configuration Validation Script.

Validates all required environment variables, credentials, and API connectivity
before starting the Telegram agent daemon.

Usage:
    uv run python scripts/validate_config.py

Exit codes:
    0: All validations passed
    1: One or more validations failed
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

import asyncpg
from dotenv import load_dotenv

# Anthropic import is optional (may fail on Python 3.14)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    Anthropic = None
    ANTHROPIC_AVAILABLE = False
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables from .env file
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()  # Also load from current directory if exists

# Initialize console with full width
console = Console(width=120)

# Type alias for validation results
# (success, check_name, message)
ValidationResult = Tuple[bool, str, str]


# =============================================================================
# ENVIRONMENT VARIABLE CHECKS
# =============================================================================


def check_env_var(var_name: str, required: bool = True) -> ValidationResult:
    """
    Check if an environment variable is set.

    Args:
        var_name: Name of the environment variable to check.
        required: Whether the variable is required for daemon operation.

    Returns:
        ValidationResult tuple with (success, check_name, message).
    """
    value = os.getenv(var_name)
    if value:
        # Mask sensitive values for display
        sensitive_keywords = ["KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIALS"]
        is_sensitive = any(keyword in var_name.upper() for keyword in sensitive_keywords)

        if is_sensitive:
            if len(value) > 14:
                display = f"{value[:8]}...{value[-4:]}"
            else:
                display = "***"
        else:
            # Truncate long values
            display = value[:50] + "..." if len(value) > 50 else value

        return (True, var_name, f"Set: {display}")
    elif required:
        return (False, var_name, "NOT SET - Required!")
    else:
        return (True, var_name, "Not set (optional)")


# =============================================================================
# DATABASE CHECK
# =============================================================================


async def check_database() -> ValidationResult:
    """
    Test database connectivity.

    Attempts to connect to the PostgreSQL database specified by DATABASE_URL
    and run a simple query to verify the connection works.

    Returns:
        ValidationResult tuple with connection status.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return (False, "Database Connection", "DATABASE_URL not set")

    try:
        conn = await asyncpg.connect(database_url, timeout=10)
        # Test a simple query
        version = await conn.fetchval("SELECT version()")

        # Extract just the PostgreSQL version number for display
        if version:
            version_short = version.split(",")[0] if "," in version else version[:50]
        else:
            version_short = "Connected"

        await conn.close()
        return (True, "Database Connection", f"OK - {version_short}")
    except asyncpg.InvalidPasswordError:
        return (False, "Database Connection", "Invalid password")
    except asyncpg.InvalidCatalogNameError:
        return (False, "Database Connection", "Database does not exist")
    except OSError as e:
        return (False, "Database Connection", f"Cannot connect: {str(e)[:40]}")
    except Exception as e:
        return (False, "Database Connection", f"Failed: {str(e)[:40]}")


# =============================================================================
# ANTHROPIC API CHECK
# =============================================================================


async def check_anthropic_api() -> ValidationResult:
    """
    Test Anthropic API key validity.

    Makes a minimal API call to verify the API key works.
    Uses the fastest/cheapest model for the test.

    Returns:
        ValidationResult tuple with API status.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return (False, "Anthropic API", "ANTHROPIC_API_KEY not set")

    if not ANTHROPIC_AVAILABLE:
        # Can't test API but key is set
        return (True, "Anthropic API", f"Key set (library unavailable on Python {sys.version_info.major}.{sys.version_info.minor})")

    try:
        client = Anthropic(api_key=api_key)
        # Make a minimal API call to verify key using the haiku model
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return (True, "Anthropic API", "Valid API key - connection verified")
    except Exception as e:
        error_msg = str(e).lower()
        if "authentication" in error_msg or "api_key" in error_msg or "invalid x-api-key" in error_msg:
            return (False, "Anthropic API", "Invalid API key")
        elif "rate" in error_msg:
            return (True, "Anthropic API", "Valid key (rate limited)")
        elif "404" in str(e) or "not_found" in error_msg:
            # Model not found but API key worked - consider this a pass
            return (True, "Anthropic API", "Valid API key (model check skipped)")
        return (False, "Anthropic API", f"Error: {str(e)[:40]}")


# =============================================================================
# TELEGRAM CREDENTIALS CHECK
# =============================================================================


def check_telegram_credentials() -> ValidationResult:
    """
    Check if Telegram credentials exist.

    Verifies that the ~/.telegram_dl/ directory contains the required
    config.json and user.session files for Telethon authentication.

    Returns:
        ValidationResult tuple with credentials status.
    """
    telegram_dir = Path.home() / ".telegram_dl"
    config_file = telegram_dir / "config.json"
    session_file = telegram_dir / "user.session"

    if not telegram_dir.exists():
        return (
            False,
            "Telegram Credentials",
            f"Directory not found: ~/.telegram_dl/\n"
            "  Create it and add config.json with api_id and api_hash",
        )

    if not config_file.exists():
        return (
            False,
            "Telegram Credentials",
            "config.json not found in ~/.telegram_dl/",
        )

    # Validate config.json content
    try:
        with open(config_file) as f:
            config = json.load(f)
        if "api_id" not in config or "api_hash" not in config:
            return (
                False,
                "Telegram Credentials",
                "config.json missing api_id or api_hash",
            )
    except json.JSONDecodeError:
        return (False, "Telegram Credentials", "config.json is not valid JSON")

    if not session_file.exists():
        return (
            False,
            "Telegram Credentials",
            "user.session not found - run telegram_fetch.py to authenticate",
        )

    return (True, "Telegram Credentials", "Found config.json and user.session")


# =============================================================================
# ZOOM CREDENTIALS CHECK (OPTIONAL)
# =============================================================================


def check_zoom_credentials() -> ValidationResult:
    """
    Check if Zoom credentials exist (optional).

    Verifies that the ~/.zoom_credentials/credentials.json file exists
    and contains the required OAuth fields.

    Returns:
        ValidationResult tuple with credentials status.
    """
    zoom_dir = Path.home() / ".zoom_credentials"
    credentials_file = zoom_dir / "credentials.json"

    if not credentials_file.exists():
        return (True, "Zoom Credentials", "Not configured (optional)")

    try:
        with open(credentials_file) as f:
            creds = json.load(f)
        required = ["account_id", "client_id", "client_secret"]
        missing = [k for k in required if k not in creds]
        if missing:
            return (
                False,
                "Zoom Credentials",
                f"Missing required fields: {', '.join(missing)}",
            )
        return (True, "Zoom Credentials", "Found and valid")
    except json.JSONDecodeError:
        return (False, "Zoom Credentials", "credentials.json is not valid JSON")
    except Exception as e:
        return (False, "Zoom Credentials", f"Error reading file: {str(e)[:30]}")


# =============================================================================
# GOOGLE CALENDAR CREDENTIALS CHECK (OPTIONAL)
# =============================================================================


def check_google_calendar_credentials() -> ValidationResult:
    """
    Check if Google Calendar credentials exist (optional).

    Looks for credential files in the .claude/skills/google-calendar/accounts directory.

    Returns:
        ValidationResult tuple with credentials status.
    """
    calendar_dir = PROJECT_ROOT / ".claude/skills/google-calendar/accounts"

    if not calendar_dir.exists():
        return (True, "Google Calendar", "Not configured (optional)")

    # Check for any .json files
    json_files = list(calendar_dir.glob("*.json"))
    if json_files:
        return (True, "Google Calendar", f"Found {len(json_files)} account(s)")
    else:
        return (True, "Google Calendar", "No accounts found (optional)")


# =============================================================================
# KNOWLEDGE BASE CHECK (OPTIONAL)
# =============================================================================


def check_knowledge_base() -> ValidationResult:
    """
    Check if knowledge base directory exists (optional).

    The knowledge base provides context for the agent but is not strictly required.

    Returns:
        ValidationResult tuple with knowledge base status.
    """
    # Check both possible locations
    kb_dir_1 = PROJECT_ROOT / "knowledge_base_final"
    kb_dir_2 = PROJECT_ROOT / "knowledge_base" / "Final"

    if kb_dir_1.exists():
        # Count files
        files = list(kb_dir_1.rglob("*.md")) + list(kb_dir_1.rglob("*.txt"))
        return (True, "Knowledge Base", f"Found at knowledge_base_final/ ({len(files)} files)")
    elif kb_dir_2.exists():
        files = list(kb_dir_2.rglob("*.md")) + list(kb_dir_2.rglob("*.txt"))
        return (True, "Knowledge Base", f"Found at knowledge_base/Final/ ({len(files)} files)")
    else:
        return (True, "Knowledge Base", "Not found (optional, agent will work without it)")


# =============================================================================
# SKILLS DIRECTORIES CHECK (OPTIONAL)
# =============================================================================


def check_skills_directories() -> ValidationResult:
    """
    Check if required skills directories exist.

    The daemon uses tone-of-voice and how-to-communicate skills.

    Returns:
        ValidationResult tuple with skills status.
    """
    skills_dir = PROJECT_ROOT / ".claude/skills"
    tone_of_voice_dir = skills_dir / "tone-of-voice"
    how_to_communicate_dir = skills_dir / "how-to-communicate"

    if not skills_dir.exists():
        return (True, "Skills Directories", "Not found (optional)")

    found = []
    if tone_of_voice_dir.exists():
        found.append("tone-of-voice")
    if how_to_communicate_dir.exists():
        found.append("how-to-communicate")

    if found:
        return (True, "Skills Directories", f"Found: {', '.join(found)}")
    else:
        return (True, "Skills Directories", "No skill directories found (optional)")


# =============================================================================
# MAIN VALIDATION RUNNER
# =============================================================================


async def run_validations() -> bool:
    """
    Run all validation checks.

    Executes all configuration checks and displays results in a formatted table.

    Returns:
        True if all required validations passed, False otherwise.
    """
    results: List[ValidationResult] = []

    console.print("\n")
    console.print(
        Panel.fit(
            "[bold blue]Telegram Agent Configuration Validation[/bold blue]\n\n"
            "Checking environment variables, credentials, and API connectivity...",
            title="Configuration Validator",
            border_style="blue",
        )
    )
    console.print("\n")

    # -------------------------------------------------------------------------
    # Required Environment Variables
    # -------------------------------------------------------------------------
    console.print("[cyan]Checking required environment variables...[/cyan]")
    results.append(check_env_var("ANTHROPIC_API_KEY", required=True))
    results.append(check_env_var("DATABASE_URL", required=True))

    # -------------------------------------------------------------------------
    # Optional Environment Variables
    # -------------------------------------------------------------------------
    console.print("[cyan]Checking optional environment variables...[/cyan]")
    results.append(check_env_var("ZOOM_ACCOUNT_ID", required=False))
    results.append(check_env_var("ZOOM_CLIENT_ID", required=False))
    results.append(check_env_var("ZOOM_CLIENT_SECRET", required=False))
    results.append(check_env_var("LOG_LEVEL", required=False))
    results.append(check_env_var("ORCHESTRATOR_MODEL", required=False))

    # -------------------------------------------------------------------------
    # Credentials
    # -------------------------------------------------------------------------
    console.print("[cyan]Checking credentials...[/cyan]")
    results.append(check_telegram_credentials())
    results.append(check_zoom_credentials())
    results.append(check_google_calendar_credentials())

    # -------------------------------------------------------------------------
    # Optional Resources
    # -------------------------------------------------------------------------
    console.print("[cyan]Checking optional resources...[/cyan]")
    results.append(check_knowledge_base())
    results.append(check_skills_directories())

    # -------------------------------------------------------------------------
    # API Connectivity (async checks)
    # -------------------------------------------------------------------------
    console.print("[cyan]Testing API connectivity (this may take a few seconds)...[/cyan]")

    # Run database and Anthropic API checks concurrently
    db_result, anthropic_result = await asyncio.gather(
        check_database(),
        check_anthropic_api(),
    )
    results.append(db_result)
    results.append(anthropic_result)

    # -------------------------------------------------------------------------
    # Display Results
    # -------------------------------------------------------------------------
    table = Table(title="Validation Results", width=120)
    table.add_column("Check", style="cyan", width=30)
    table.add_column("Status", style="bold", width=12)
    table.add_column("Details", width=70)

    all_passed = True
    required_checks = {
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "Database Connection",
        "Anthropic API",
        "Telegram Credentials",
    }

    for success, check_name, message in results:
        is_required = check_name in required_checks
        if success:
            status = "[green]PASS[/green]"
        else:
            if is_required:
                status = "[red]FAIL[/red]"
                all_passed = False
            else:
                status = "[yellow]WARN[/yellow]"

        # Truncate long messages for table display
        display_message = message if len(message) <= 70 else message[:67] + "..."
        table.add_row(check_name, status, display_message)

    console.print("\n")
    console.print(table)
    console.print("\n")

    # -------------------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------------------
    if all_passed:
        console.print(
            Panel.fit(
                "[bold green]All required validations passed![/bold green]\n\n"
                "You can now start the Telegram agent daemon:\n"
                "  [dim]uv run python -m sales_agent.daemon[/dim]",
                title="Success",
                border_style="green",
            )
        )
        return True
    else:
        # Collect failures for specific guidance
        failures = [(name, msg) for success, name, msg in results if not success and name in required_checks]

        guidance_lines = []
        for name, msg in failures:
            if name == "ANTHROPIC_API_KEY":
                guidance_lines.append(
                    "  - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/\n"
                    "    Add to your .env file: ANTHROPIC_API_KEY=sk-ant-..."
                )
            elif name == "DATABASE_URL":
                guidance_lines.append(
                    "  - DATABASE_URL: Set your PostgreSQL connection string\n"
                    "    Add to your .env file: DATABASE_URL=postgresql://user:pass@host:5432/db"
                )
            elif name == "Database Connection":
                guidance_lines.append(
                    "  - Database: Verify your DATABASE_URL is correct and the database is running\n"
                    "    Check: psql $DATABASE_URL -c 'SELECT 1'"
                )
            elif name == "Anthropic API":
                guidance_lines.append(
                    "  - Anthropic API: Your API key appears to be invalid\n"
                    "    Get a new key from https://console.anthropic.com/"
                )
            elif name == "Telegram Credentials":
                guidance_lines.append(
                    "  - Telegram: Create ~/.telegram_dl/config.json with api_id and api_hash\n"
                    "    Then run telegram_fetch.py to create user.session"
                )

        guidance_text = "\n".join(guidance_lines) if guidance_lines else "  Check the error messages above"

        console.print(
            Panel.fit(
                "[bold red]Some required validations failed![/bold red]\n\n"
                "Please fix the following issues before starting the daemon:\n\n"
                f"{guidance_text}\n\n"
                "[dim]After fixing issues, run this script again to verify.[/dim]",
                title="Failed",
                border_style="red",
            )
        )
        return False


# =============================================================================
# ENTRY POINT
# =============================================================================


async def main() -> None:
    """Main entry point for the validation script."""
    try:
        all_passed = await run_validations()
        sys.exit(0 if all_passed else 1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Validation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error during validation:[/bold red] {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
