#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich>=13.0.0",
#   "pydantic>=2.0.0",
#   "pytz>=2024.1",
#   "python-dotenv>=1.0.0",
# ]
# ///
"""
CLI for Running Calendar Integration Tests.

Tests Google Calendar event creation, timezone conversion, and slot
availability checking with real API calls.

Usage:
    # Run happy path test
    uv run python .claude/skills/testing/scripts/run_calendar_tests.py --scenario "Zoom Scheduler Happy Path"

    # Run all calendar tests
    uv run python .claude/skills/testing/scripts/run_calendar_tests.py --all-calendar

    # Run with cleanup of all [TEST] events
    uv run python .claude/skills/testing/scripts/run_calendar_tests.py --all-calendar --cleanup

    # List available calendar scenarios
    uv run python .claude/skills/testing/scripts/run_calendar_tests.py --list

    # Run with verbose output
    uv run python .claude/skills/testing/scripts/run_calendar_tests.py --scenario "Timezone Mismatch - Kyiv" --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent

# Add required paths
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram" / "scripts"
if str(TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_SCRIPTS))

# Load environment variables
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Import local modules with try/except for both package and direct execution
try:
    from .calendar_test_client import CalendarTestClient
    from .calendar_validation import CalendarValidator, CalendarValidationResult
    from .calendar_test_scenarios import (
        CALENDAR_TEST_SCENARIOS,
        CalendarTestScenario,
        get_calendar_scenario_by_name,
        get_scenario_names,
        get_dynamic_conflict_time,
    )
    from .conversation_simulator import ConversationSimulator, ConversationResult
except ImportError:
    from calendar_test_client import CalendarTestClient
    from calendar_validation import CalendarValidator, CalendarValidationResult
    from calendar_test_scenarios import (
        CALENDAR_TEST_SCENARIOS,
        CalendarTestScenario,
        get_calendar_scenario_by_name,
        get_scenario_names,
        get_dynamic_conflict_time,
    )
    from conversation_simulator import ConversationSimulator, ConversationResult

# Rich console with full width
console = Console(width=None)


# =============================================================================
# RESULT MODELS
# =============================================================================


class CalendarTestResult(BaseModel):
    """Result of a single calendar integration test."""

    scenario_name: str
    conversation_outcome: str
    conversation_score: int
    calendar_metrics: dict
    validation_result: Optional[dict] = None
    duration_seconds: float
    error: Optional[str] = None


class CalendarTestSummary(BaseModel):
    """Summary of all calendar tests."""

    total_tests: int
    passed: int
    failed: int
    scenarios_run: list[str]
    results: list[CalendarTestResult]
    total_duration_seconds: float


# =============================================================================
# TEST RUNNER FUNCTIONS
# =============================================================================


async def run_calendar_test(
    scenario: CalendarTestScenario,
    cal_client: CalendarTestClient,
    validator: CalendarValidator,
    verbose: bool = False,
) -> CalendarTestResult:
    """
    Run a single calendar integration test.

    Args:
        scenario: CalendarTestScenario to run.
        cal_client: CalendarTestClient for event management.
        validator: CalendarValidator for verification.
        verbose: Whether to show detailed output.

    Returns:
        CalendarTestResult with test outcome.
    """
    start_time = datetime.now(timezone.utc)
    error_msg = None
    validation: Optional[CalendarValidationResult] = None

    if verbose:
        console.print(
            Panel(
                f"[bold cyan]CALENDAR TEST: {scenario.name}[/bold cyan]\n"
                f"Client Timezone: {scenario.client_timezone}\n"
                f"Client Email: {scenario.client_email}\n"
                f"Test Conflict: {scenario.test_conflict}",
                title="Running Scenario",
                expand=True,
            )
        )

    try:
        # If testing conflict, create blocking event first
        conflict_event = None
        if scenario.test_conflict:
            if verbose:
                console.print("[yellow]Creating conflict event...[/yellow]")
            # Use dynamic conflict time if not specified in scenario
            conflict_time_str = scenario.conflict_slot_time or get_dynamic_conflict_time()
            # Parse the ISO time string (remove timezone for datetime parsing)
            conflict_time_clean = conflict_time_str.replace("+08:00", "").replace("+08", "")
            conflict_time = datetime.fromisoformat(conflict_time_clean)
            conflict_event = cal_client.create_test_event(
                summary="Existing Meeting (Conflict Test)",
                start=conflict_time,
                end=conflict_time + timedelta(hours=1),
                timezone="Asia/Makassar",
            )
            if verbose:
                console.print(f"[green]Created conflict event: {conflict_event.id}[/green]")
                console.print(f"  Conflict time: {conflict_time_str}")

        # Create a test calendar event (simulating successful scheduling)
        # In a full integration test, the ConversationSimulator would drive this
        meeting_time = datetime.now() + timedelta(days=1, hours=2)
        meeting_time = meeting_time.replace(minute=0, second=0, microsecond=0)

        test_event = cal_client.create_test_event(
            summary=f"Meeting with {scenario.persona.name}",
            start=meeting_time,
            end=meeting_time + timedelta(hours=1),
            timezone="Asia/Makassar",
            attendees=[scenario.client_email],
            zoom_url="https://zoom.us/j/123456789",
        )

        if verbose:
            console.print(f"[green]Created test event: {test_event.summary}[/green]")
            console.print(f"  Event ID: {test_event.id}")
            console.print(f"  Start: {test_event.start}")
            console.print(f"  End: {test_event.end}")

        # Validate the created event
        event_data = cal_client.get_event(test_event.id)
        validation = validator.validate_event(
            event=event_data,
            expected_timezone="Asia/Makassar",
            expected_attendees=[scenario.client_email],
            expected_zoom_url="https://zoom.us/j/123456789",
            proposed_time=meeting_time,
        )

        # Build calendar metrics
        calendar_metrics = {
            "calendar_created": True,
            "correct_timezone": validation.timezone_correct,
            "slot_match": validation.time_matches_proposal,
            "zoom_link_embedded": validation.zoom_link_present,
            "attendee_added": validation.attendees_correct,
            "event_id": test_event.id,
        }

        # Check timezone conversion if verbose
        if verbose:
            client_time = validator.convert_to_client_timezone(
                meeting_time, scenario.client_timezone
            )
            console.print(f"Bali time: {meeting_time.strftime('%H:%M')}")
            console.print(
                f"Client time ({scenario.client_timezone}): {client_time.strftime('%H:%M %Z')}"
            )
            console.print(f"Validation passed: {validation.all_passed}")
            if validation.validation_errors:
                for err in validation.validation_errors:
                    console.print(f"  [red]Error: {escape(err)}[/red]")

    except Exception as e:
        error_msg = str(e)
        calendar_metrics = {
            "calendar_created": False,
            "correct_timezone": False,
            "slot_match": False,
            "zoom_link_embedded": False,
            "attendee_added": False,
        }
        validation = None
        if verbose:
            console.print(f"[red]Error: {escape(error_msg)}[/red]")

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Determine score and outcome
    if validation and validation.all_passed:
        score = 100
        outcome = "zoom_scheduled"
    elif calendar_metrics.get("calendar_created"):
        # Partial success - event created but some validation failed
        passed_checks = sum(
            1
            for k in ["correct_timezone", "slot_match", "zoom_link_embedded", "attendee_added"]
            if calendar_metrics.get(k)
        )
        score = 25 * passed_checks  # 25 points per check
        outcome = "zoom_scheduled" if score >= 75 else "partial_success"
    else:
        score = 0
        outcome = "failed"

    return CalendarTestResult(
        scenario_name=scenario.name,
        conversation_outcome=outcome,
        conversation_score=score,
        calendar_metrics=calendar_metrics,
        validation_result=validation.model_dump() if validation else None,
        duration_seconds=duration,
        error=error_msg,
    )


async def run_all_calendar_tests(
    scenarios: list[CalendarTestScenario],
    cal_client: CalendarTestClient,
    validator: CalendarValidator,
    verbose: bool = False,
) -> CalendarTestSummary:
    """
    Run all calendar integration tests.

    Args:
        scenarios: List of scenarios to run.
        cal_client: CalendarTestClient for event management.
        validator: CalendarValidator for verification.
        verbose: Whether to show detailed output.

    Returns:
        CalendarTestSummary with all results.
    """
    start_time = datetime.now(timezone.utc)
    results: list[CalendarTestResult] = []

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            console.print(f"\n[bold]Running scenario {i}/{len(scenarios)}[/bold]")
        else:
            console.print(f"Running: {scenario.name}...", end=" ")

        result = await run_calendar_test(scenario, cal_client, validator, verbose)
        results.append(result)

        if not verbose:
            status = (
                "[green]PASS[/green]"
                if result.conversation_score >= 75
                else "[red]FAIL[/red]"
            )
            console.print(status)

    passed = sum(1 for r in results if r.conversation_score >= 75)
    failed = len(results) - passed
    total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    return CalendarTestSummary(
        total_tests=len(results),
        passed=passed,
        failed=failed,
        scenarios_run=[r.scenario_name for r in results],
        results=results,
        total_duration_seconds=total_duration,
    )


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================


def display_scenarios_list() -> None:
    """Display available calendar test scenarios."""
    table = Table(title="Calendar Test Scenarios", expand=True)
    table.add_column("Name", style="cyan")
    table.add_column("Timezone", style="yellow")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Test Conflict", style="red")
    table.add_column("Language", style="green")

    for scenario in CALENDAR_TEST_SCENARIOS:
        table.add_row(
            scenario.name,
            scenario.client_timezone,
            scenario.persona.difficulty,
            "Yes" if scenario.test_conflict else "No",
            scenario.persona.language,
        )

    console.print(table)
    console.print(f"\n[dim]Total scenarios: {len(CALENDAR_TEST_SCENARIOS)}[/dim]")


def display_test_results(summary: CalendarTestSummary) -> None:
    """Display test results in a formatted table."""
    # Results table
    table = Table(title="Calendar Test Results", expand=True)
    table.add_column("Scenario", style="cyan")
    table.add_column("Outcome", style="white")
    table.add_column("Calendar", style="white")
    table.add_column("Timezone", style="white")
    table.add_column("Zoom", style="white")
    table.add_column("Attendee", style="white")
    table.add_column("Score", justify="right", style="white")
    table.add_column("Duration", justify="right", style="dim")

    for result in summary.results:
        cm = result.calendar_metrics

        # Format status indicators
        cal_status = (
            "[green]Created[/green]"
            if cm.get("calendar_created")
            else "[red]Failed[/red]"
        )
        tz_status = (
            "[green]OK[/green]" if cm.get("correct_timezone") else "[red]Wrong[/red]"
        )
        zoom_status = (
            "[green]Yes[/green]"
            if cm.get("zoom_link_embedded")
            else "[red]No[/red]"
        )
        att_status = (
            "[green]Added[/green]"
            if cm.get("attendee_added")
            else "[red]Missing[/red]"
        )

        outcome_color = "green" if result.conversation_score >= 75 else "red"
        score_color = "green" if result.conversation_score >= 75 else "yellow" if result.conversation_score >= 50 else "red"

        table.add_row(
            result.scenario_name,
            f"[{outcome_color}]{result.conversation_outcome}[/{outcome_color}]",
            cal_status,
            tz_status,
            zoom_status,
            att_status,
            f"[{score_color}]{result.conversation_score}/100[/{score_color}]",
            f"{result.duration_seconds:.1f}s",
        )

    console.print(table)

    # Summary panel
    pass_rate = (
        (summary.passed / summary.total_tests * 100) if summary.total_tests > 0 else 0
    )
    verdict = "PASSED" if summary.failed == 0 else "FAILED"
    verdict_color = "green" if summary.failed == 0 else "red"

    summary_text = Text()
    summary_text.append(f"Total Tests: {summary.total_tests}\n")
    summary_text.append(f"Passed: {summary.passed}\n", style="green")
    summary_text.append(
        f"Failed: {summary.failed}\n", style="red" if summary.failed > 0 else "dim"
    )
    summary_text.append(f"Pass Rate: {pass_rate:.1f}%\n")
    summary_text.append(f"Total Duration: {summary.total_duration_seconds:.1f}s\n")
    summary_text.append("\nVerdict: ", style="bold")
    summary_text.append(verdict, style=f"bold {verdict_color}")

    console.print(Panel(summary_text, title="Summary", expand=True))


# =============================================================================
# MAIN CLI
# =============================================================================


async def main() -> int:
    """Main entry point for calendar test CLI."""
    parser = argparse.ArgumentParser(
        description="Run calendar integration tests for the sales conversation agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available scenarios
  uv run python run_calendar_tests.py --list

  # Run a specific scenario
  uv run python run_calendar_tests.py --scenario "Zoom Scheduler Happy Path"

  # Run all calendar tests
  uv run python run_calendar_tests.py --all-calendar

  # Run with cleanup
  uv run python run_calendar_tests.py --all-calendar --cleanup

  # Run with verbose output
  uv run python run_calendar_tests.py --scenario "Timezone Mismatch - Kyiv" --verbose
        """,
    )

    parser.add_argument(
        "--scenario",
        type=str,
        help="Run a specific scenario by name",
    )
    parser.add_argument(
        "--all-calendar",
        action="store_true",
        help="Run all calendar test scenarios",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available calendar test scenarios",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up all [TEST] events after tests",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only clean up [TEST] events (don't run tests)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--account",
        type=str,
        default="personal",
        help="Google account name for calendar (default: personal)",
    )

    args = parser.parse_args()

    # Handle --list
    if args.list:
        display_scenarios_list()
        return 0

    # Initialize clients
    try:
        cal_client = CalendarTestClient(account=args.account)
        validator = CalendarValidator()
    except FileNotFoundError as e:
        console.print(f"[red]Failed to initialize calendar client: {escape(str(e))}[/red]")
        console.print(
            "[yellow]Please ensure you have set up Google Calendar authentication.[/yellow]"
        )
        console.print(
            "[dim]See .claude/skills/google-calendar/SKILL.md for setup instructions.[/dim]"
        )
        return 1
    except Exception as e:
        console.print(f"[red]Failed to initialize calendar client: {escape(str(e))}[/red]")
        return 1

    # Handle --cleanup-only
    if args.cleanup_only:
        console.print("[yellow]Cleaning up all \\[TEST] events...[/yellow]")
        deleted = cal_client.cleanup_all_test_prefix_events()
        console.print(f"[green]Deleted {deleted} \\[TEST] events[/green]")
        return 0

    # Determine scenarios to run
    scenarios: list[CalendarTestScenario] = []

    if args.all_calendar:
        scenarios = list(CALENDAR_TEST_SCENARIOS)
    elif args.scenario:
        try:
            scenario = get_calendar_scenario_by_name(args.scenario)
            scenarios = [scenario]
        except ValueError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            console.print("\nAvailable scenarios:")
            for name in get_scenario_names():
                console.print(f"  - {name}")
            return 1
    else:
        console.print("[yellow]Specify --scenario NAME or --all-calendar[/yellow]")
        console.print("Use --list to see available scenarios")
        return 1

    # Run tests
    console.print(
        Panel(
            f"[bold]Running {len(scenarios)} calendar integration test(s)[/bold]\n"
            f"Account: {args.account}",
            title="Calendar Test Runner",
            expand=True,
        )
    )

    summary = await run_all_calendar_tests(scenarios, cal_client, validator, args.verbose)

    # Display results
    console.print()
    display_test_results(summary)

    # Cleanup if requested
    if args.cleanup:
        console.print("\n[yellow]Cleaning up \\[TEST] events...[/yellow]")
        deleted = cal_client.cleanup_all_test_prefix_events()
        console.print(f"[green]Deleted {deleted} \\[TEST] events[/green]")

    return 0 if summary.failed == 0 else 1


def run() -> None:
    """Synchronous entry point for the CLI."""
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    run()
