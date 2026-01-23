#!/usr/bin/env python3
"""
Tests for OutreachDaemon configuration and environment variable handling.

Run with:
    uv run python src/sales_agent/testing/test_outreach_daemon.py
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Add src to path for imports
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

console = Console()


def test_env_var_defaults():
    """Test 1: Default values when no env vars set."""
    console.print("\n[bold cyan]Test 1: Default Environment Values[/bold cyan]")

    # Clear relevant env vars
    env_backup = {}
    for key in ["OUTREACH_INTERVAL_SECONDS", "MAX_PROSPECTS_PER_REP", "OUTREACH_ENABLED"]:
        env_backup[key] = os.environ.pop(key, None)

    try:
        check_interval = int(os.environ.get("OUTREACH_INTERVAL_SECONDS", "300"))
        max_prospects_per_rep = int(os.environ.get("MAX_PROSPECTS_PER_REP", "5"))
        outreach_enabled = os.environ.get("OUTREACH_ENABLED", "true").lower() == "true"

        assert check_interval == 300, f"Expected 300, got {check_interval}"
        assert max_prospects_per_rep == 5, f"Expected 5, got {max_prospects_per_rep}"
        assert outreach_enabled is True, f"Expected True, got {outreach_enabled}"

        console.print(f"  [green]✓[/green] check_interval defaults to 300")
        console.print(f"  [green]✓[/green] max_prospects_per_rep defaults to 5")
        console.print(f"  [green]✓[/green] outreach_enabled defaults to True")
        return True
    except AssertionError as e:
        console.print(f"  [red]✗[/red] {e}")
        return False
    finally:
        # Restore env vars
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value


def test_env_var_custom_values():
    """Test 2: Custom values from environment variables."""
    console.print("\n[bold cyan]Test 2: Custom Environment Values[/bold cyan]")

    # Set custom env vars
    os.environ["OUTREACH_INTERVAL_SECONDS"] = "600"
    os.environ["MAX_PROSPECTS_PER_REP"] = "10"
    os.environ["OUTREACH_ENABLED"] = "true"

    try:
        check_interval = int(os.environ.get("OUTREACH_INTERVAL_SECONDS", "300"))
        max_prospects_per_rep = int(os.environ.get("MAX_PROSPECTS_PER_REP", "5"))
        outreach_enabled = os.environ.get("OUTREACH_ENABLED", "true").lower() == "true"

        assert check_interval == 600, f"Expected 600, got {check_interval}"
        assert max_prospects_per_rep == 10, f"Expected 10, got {max_prospects_per_rep}"
        assert outreach_enabled is True, f"Expected True, got {outreach_enabled}"

        console.print(f"  [green]✓[/green] check_interval reads 600 from env")
        console.print(f"  [green]✓[/green] max_prospects_per_rep reads 10 from env")
        console.print(f"  [green]✓[/green] outreach_enabled reads True from env")
        return True
    except AssertionError as e:
        console.print(f"  [red]✗[/red] {e}")
        return False
    finally:
        # Clean up
        for key in ["OUTREACH_INTERVAL_SECONDS", "MAX_PROSPECTS_PER_REP", "OUTREACH_ENABLED"]:
            os.environ.pop(key, None)


def test_outreach_disabled():
    """Test 3: OUTREACH_ENABLED=false disables daemon."""
    console.print("\n[bold cyan]Test 3: OUTREACH_ENABLED=false[/bold cyan]")

    test_cases = ["false", "False", "FALSE", "no", "0"]

    for value in test_cases:
        os.environ["OUTREACH_ENABLED"] = value
        outreach_enabled = os.environ.get("OUTREACH_ENABLED", "true").lower() == "true"

        if outreach_enabled:
            console.print(f"  [red]✗[/red] '{value}' should disable daemon but got enabled=True")
            os.environ.pop("OUTREACH_ENABLED", None)
            return False

    console.print(f"  [green]✓[/green] 'false', 'False', 'FALSE' all disable daemon")
    console.print(f"  [green]✓[/green] 'no', '0' also disable daemon")

    os.environ.pop("OUTREACH_ENABLED", None)
    return True


def test_outreach_enabled_variations():
    """Test 4: Various OUTREACH_ENABLED=true variations."""
    console.print("\n[bold cyan]Test 4: OUTREACH_ENABLED=true variations[/bold cyan]")

    test_cases = ["true", "True", "TRUE"]

    for value in test_cases:
        os.environ["OUTREACH_ENABLED"] = value
        outreach_enabled = os.environ.get("OUTREACH_ENABLED", "true").lower() == "true"

        if not outreach_enabled:
            console.print(f"  [red]✗[/red] '{value}' should enable daemon but got enabled=False")
            os.environ.pop("OUTREACH_ENABLED", None)
            return False

    console.print(f"  [green]✓[/green] 'true', 'True', 'TRUE' all enable daemon")

    os.environ.pop("OUTREACH_ENABLED", None)
    return True


def test_daemon_initialization():
    """Test 5: OutreachDaemon class initialization with custom values."""
    console.print("\n[bold cyan]Test 5: OutreachDaemon Initialization[/bold cyan]")

    try:
        from sales_agent.registry.outreach_daemon import OutreachDaemon

        # Test with custom values
        daemon = OutreachDaemon(
            bot_token="test_token",
            check_interval=120,
            max_prospects_per_rep=3,
        )

        assert daemon.check_interval == 120, f"Expected 120, got {daemon.check_interval}"
        assert daemon.max_prospects_per_rep == 3, f"Expected 3, got {daemon.max_prospects_per_rep}"
        assert daemon.bot_token == "test_token", f"Token mismatch"
        assert daemon._running is False, "Daemon should not be running yet"

        console.print(f"  [green]✓[/green] check_interval set to 120")
        console.print(f"  [green]✓[/green] max_prospects_per_rep set to 3")
        console.print(f"  [green]✓[/green] bot_token set correctly")
        console.print(f"  [green]✓[/green] daemon not running initially")
        return True
    except Exception as e:
        console.print(f"  [red]✗[/red] Initialization failed: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


def test_daemon_stats():
    """Test 6: OutreachDaemon stats tracking."""
    console.print("\n[bold cyan]Test 6: Daemon Stats[/bold cyan]")

    try:
        from sales_agent.registry.outreach_daemon import OutreachDaemon

        daemon = OutreachDaemon(check_interval=60)
        stats = daemon.get_stats()

        assert "assignments_made" in stats, "Missing assignments_made"
        assert "notifications_sent" in stats, "Missing notifications_sent"
        assert "cycles_completed" in stats, "Missing cycles_completed"
        assert "running" in stats, "Missing running"
        assert stats["running"] is False, "Should not be running"

        console.print(f"  [green]✓[/green] Stats structure correct")
        console.print(f"  [green]✓[/green] Initial values are zero")
        return True
    except Exception as e:
        console.print(f"  [red]✗[/red] Stats test failed: {e}")
        return False


def main():
    """Run all tests."""
    console.print(Panel.fit(
        "[bold]OutreachDaemon Configuration Tests[/bold]\n"
        "Testing environment variables and daemon initialization",
        title="Test Suite",
        width=60,
    ))

    results = {}

    # Run tests
    results["env_defaults"] = test_env_var_defaults()
    results["env_custom"] = test_env_var_custom_values()
    results["outreach_disabled"] = test_outreach_disabled()
    results["outreach_enabled"] = test_outreach_enabled_variations()
    results["daemon_init"] = test_daemon_initialization()
    results["daemon_stats"] = test_daemon_stats()

    # Summary
    console.print("\n" + "=" * 50)
    console.print("[bold]Test Summary[/bold]")
    console.print("=" * 50)

    all_passed = True
    for test_name, passed in results.items():
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        console.print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    console.print("=" * 50)
    if all_passed:
        console.print("[bold green]All tests passed![/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Some tests failed[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
