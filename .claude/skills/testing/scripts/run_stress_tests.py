#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
# ]
# ///
"""
CLI for Running Stress Tests with Various Options.

Provides a user-friendly command-line interface to execute single or multiple
stress test scenarios, view results with rich console output, and generate
timing analysis reports.

Usage:
    # Run a single stress test
    PYTHONPATH=.claude/skills/testing/scripts:.claude/skills/telegram/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --scenario "Rapid Fire Burst" --verbose

    # Run all stress tests
    PYTHONPATH=.claude/skills/testing/scripts:.claude/skills/telegram/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --all-stress

    # Run with timing report and JSON export
    PYTHONPATH=.claude/skills/testing/scripts:.claude/skills/telegram/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --all-stress --timing-report --output results.json

    # List available scenarios
    PYTHONPATH=.claude/skills/testing/scripts:.claude/skills/telegram/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --list

Exit codes:
    0 - All tests passed (call_scheduled=True for all)
    1 - One or more tests failed or error occurred
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Support both package import and direct execution
try:
    from .stress_test_runner import StressTestRunner, StressTestResult
    from .stress_scenarios import (
        STRESS_SCENARIOS,
        StressScenario,
        get_stress_scenario_by_name,
        get_stress_scenario_names,
    )
    from .test_result_manager import (
        get_score_trends,
        get_scenario_analytics,
        close_pool,
    )
except ImportError:
    from stress_test_runner import StressTestRunner, StressTestResult
    from stress_scenarios import (
        STRESS_SCENARIOS,
        StressScenario,
        get_stress_scenario_by_name,
        get_stress_scenario_names,
    )
    from test_result_manager import (
        get_score_trends,
        get_scenario_analytics,
        close_pool,
    )


# =============================================================================
# CLI ARGUMENT PARSER
# =============================================================================

parser = argparse.ArgumentParser(
    description="Run stress tests for Telegram Agent",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  # Run a single stress test (MOCK MODE - no Telegram needed)
  PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --scenario "Rapid Fire Burst" --mock --verbose

  # Run all stress tests in mock mode
  PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --all-stress --mock

  # Run with real Telegram (requires accounts and sessions)
  PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --scenario "Rapid Fire Burst" --verbose

  # Run with timing report and JSON export
  PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --all-stress --mock --timing-report --output results.json

  # List available scenarios
  PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_stress_tests.py --list
"""
)

parser.add_argument(
    "--scenario",
    type=str,
    help="Run specific stress scenario by name"
)
parser.add_argument(
    "--all-stress",
    action="store_true",
    help="Run all stress scenarios"
)
parser.add_argument(
    "--list",
    action="store_true",
    help="List available stress scenarios and exit"
)
parser.add_argument(
    "--output",
    type=str,
    help="Export results to JSON file"
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="Print real-time conversation"
)
parser.add_argument(
    "--timing-report",
    action="store_true",
    help="Generate detailed timing analysis report"
)
parser.add_argument(
    "--mock",
    action="store_true",
    help="Run in mock mode: AI simulation without real Telegram (no accounts needed)"
)


# =============================================================================
# OUTPUT FORMATTING FUNCTIONS
# =============================================================================


def print_scenario_list(console: Console) -> None:
    """
    Print table of available stress test scenarios.

    Displays scenario name, difficulty level, and stress type
    (Batching, Delays, Urgency) in a formatted rich table.

    Args:
        console: Rich Console instance for output.
    """
    table = Table(title="Available Stress Test Scenarios", expand=True)
    table.add_column("Name", style="cyan")
    table.add_column("Difficulty", style="yellow")
    table.add_column("Stress Type", style="magenta")
    table.add_column("Timeout Mult.", justify="right", style="dim")

    for scenario in STRESS_SCENARIOS:
        # Determine stress type based on configuration
        stress_types = []
        if max(scenario.stress_config.batch_sizes) > 1:
            stress_types.append("Batching")
        if len(scenario.stress_config.message_delays) > 1:
            stress_types.append("Delays")
        if scenario.stress_config.urgency_requests:
            stress_types.append("Urgency")

        stress_type_str = ", ".join(stress_types) if stress_types else "Standard"

        table.add_row(
            scenario.name,
            scenario.persona.difficulty,
            stress_type_str,
            f"{scenario.stress_config.timeout_multiplier}x"
        )

    console.print(table)
    console.print(f"\n[dim]Total scenarios: {len(STRESS_SCENARIOS)}[/dim]")


def print_test_summary(console: Console, result: StressTestResult) -> None:
    """
    Print summary panel for a single test result.

    Displays pass/fail status, score, outcome, call scheduling status,
    turns, duration, and average response time.

    Args:
        console: Rich Console instance for output.
        result: StressTestResult from the completed test.
    """
    status_indicator = "[green]PASS[/green]" if result.call_scheduling.scheduled else "[red]FAIL[/red]"

    # Extract score from assessment or use 0
    score = result.assessment.get("overall_score", 0) if result.assessment else 0

    # Format timing info
    avg_response = result.timing_metrics.avg_response_time
    timing_info = f"Avg Response Time: {avg_response:.2f}s" if avg_response > 0 else "Avg Response Time: N/A"

    content = f"""[bold]{status_indicator} {result.scenario_name}[/bold]

Score: {score}/100
Outcome: {result.conversation_result.outcome.value}
Call Scheduled: {"Yes" if result.call_scheduling.scheduled else "No"}
Turns: {result.conversation_result.total_turns}
Duration: {result.conversation_result.duration_seconds:.1f}s
{timing_info}"""

    console.print(Panel(
        content,
        title=f"Test Result: {result.scenario_name}",
        width=60
    ))


def print_overall_summary(console: Console, results: list[StressTestResult]) -> None:
    """
    Print summary table of all test results.

    Shows scenario name, score, call scheduling status, turns,
    and duration for each test in a table format.

    Args:
        console: Rich Console instance for output.
        results: List of StressTestResult objects.
    """
    if not results:
        console.print("[yellow]No results to display[/yellow]")
        return

    table = Table(title="Stress Test Summary", expand=True)
    table.add_column("Scenario", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Call?", justify="center")
    table.add_column("Outcome", style="dim")
    table.add_column("Turns", justify="right")
    table.add_column("Duration", justify="right")

    for result in results:
        score = result.assessment.get("overall_score", 0) if result.assessment else 0
        call_status = "[green]Yes[/green]" if result.call_scheduling.scheduled else "[red]No[/red]"

        # Color outcome based on value
        outcome_value = result.conversation_result.outcome.value
        outcome_colors = {
            "zoom_scheduled": "green",
            "follow_up_proposed": "yellow",
            "client_refused": "red",
            "escalated": "blue",
            "inconclusive": "dim",
        }
        outcome_color = outcome_colors.get(outcome_value, "white")

        table.add_row(
            result.scenario_name,
            f"{score}/100",
            call_status,
            f"[{outcome_color}]{outcome_value}[/{outcome_color}]",
            str(result.conversation_result.total_turns),
            f"{result.conversation_result.duration_seconds:.1f}s"
        )

    console.print("\n")
    console.print(table)

    # Calculate overall stats
    pass_count = sum(1 for r in results if r.call_scheduling.scheduled)
    total_count = len(results)
    pass_rate = (pass_count / total_count * 100) if total_count > 0 else 0

    scores = [r.assessment.get("overall_score", 0) for r in results if r.assessment]
    avg_score = sum(scores) / len(scores) if scores else 0

    total_duration = sum(r.conversation_result.duration_seconds for r in results)

    console.print(Panel(
        f"[bold]Pass Rate:[/bold] {pass_count}/{total_count} ({pass_rate:.1f}%)\n"
        f"[bold]Average Score:[/bold] {avg_score:.1f}/100\n"
        f"[bold]Total Duration:[/bold] {total_duration:.1f}s",
        title="Overall Statistics",
        expand=True
    ))


def print_timing_report(console: Console, results: list[StressTestResult]) -> None:
    """
    Generate detailed timing analysis report.

    For each test, displays average, min, max response times
    and batch handling information.

    Args:
        console: Rich Console instance for output.
        results: List of StressTestResult objects.
    """
    console.print("\n[bold cyan]Timing Analysis Report[/bold cyan]")
    console.print("=" * 60)

    for result in results:
        metrics = result.timing_metrics
        response_times = metrics.response_times

        console.print(f"\n[bold]{result.scenario_name}[/bold]")

        if not response_times:
            console.print("  [dim]No response time data available[/dim]")
            continue

        # Calculate statistics
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)

        console.print(f"  Response Count: {len(response_times)}")
        console.print(f"  Avg Response:   {avg_time:.2f}s")
        console.print(f"  Min Response:   {min_time:.2f}s")
        console.print(f"  Max Response:   {max_time:.2f}s")
        console.print(f"  Total Duration: {metrics.total_duration:.1f}s")

        # Batch handling info
        if metrics.batch_sizes:
            console.print(f"  Batch Sizes:    {metrics.batch_sizes}")

        # Urgency detection
        if metrics.urgency_detected:
            console.print("  Urgency:        [green]Detected[/green]")

    console.print("\n" + "=" * 60)


def export_to_json(
    results: list[StressTestResult],
    filepath: str,
    console: Console
) -> None:
    """
    Export test results to JSON file.

    Creates a JSON file with timestamp, total test count,
    and detailed results for each test.

    Args:
        results: List of StressTestResult objects to export.
        filepath: Path to the output JSON file.
        console: Rich Console instance for output.
    """
    # Build exportable data structure
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tests": len(results),
        "summary": {
            "pass_count": sum(1 for r in results if r.call_scheduling.scheduled),
            "fail_count": sum(1 for r in results if not r.call_scheduling.scheduled),
            "avg_score": sum(
                r.assessment.get("overall_score", 0) for r in results if r.assessment
            ) / len(results) if results else 0,
        },
        "results": []
    }

    for result in results:
        result_data = result.model_dump(mode="json")
        data["results"].append(result_data)

    # Write to file
    output_path = Path(filepath)
    output_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    console.print(f"\n[green]Results exported to {filepath}[/green]")


async def print_historical_analytics(console: Console) -> None:
    """
    Print historical analytics from database if available.

    Shows score trends and per-scenario analytics from
    the test_results database table.

    Args:
        console: Rich Console instance for output.
    """
    console.print("\n[bold cyan]Historical Analytics[/bold cyan]")

    try:
        # Get score trends
        trends = await get_score_trends(days=7)
        if trends:
            console.print("\n[bold]Score Trends (Last 7 Days):[/bold]")
            for day in trends[:5]:  # Show last 5 days
                console.print(
                    f"  {day.date}: avg={day.avg_score:.1f}, "
                    f"tests={day.test_count}, pass_rate={day.pass_rate:.1f}%"
                )
        else:
            console.print("[dim]  No historical data available[/dim]")

        # Get per-scenario analytics for stress scenarios
        console.print("\n[bold]Per-Scenario Performance:[/bold]")
        for scenario_name in get_stress_scenario_names():
            try:
                analytics = await get_scenario_analytics(scenario_name)
                console.print(
                    f"  {scenario_name}: avg={analytics.avg_score:.1f}, "
                    f"runs={analytics.total_runs}, trend={analytics.recent_trend}"
                )
            except ValueError:
                # No data for this scenario
                console.print(f"  {scenario_name}: [dim]No data[/dim]")

    except Exception as e:
        console.print(f"[yellow]Could not fetch analytics: {e}[/yellow]")


# =============================================================================
# MAIN EXECUTION
# =============================================================================


async def main() -> int:
    """
    Main async entry point for the CLI.

    Parses arguments, runs selected stress tests, displays results,
    and returns appropriate exit code.

    Returns:
        0 if all tests passed (call_scheduled=True), 1 otherwise.
    """
    args = parser.parse_args()
    console = Console()

    # Handle --list
    if args.list:
        print_scenario_list(console)
        return 0

    # Determine which scenarios to run
    scenarios_to_run: list[StressScenario] = []

    if args.all_stress:
        scenarios_to_run = list(STRESS_SCENARIOS)
    elif args.scenario:
        try:
            scenario = get_stress_scenario_by_name(args.scenario)
            scenarios_to_run = [scenario]
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print(f"\nAvailable scenarios: {', '.join(get_stress_scenario_names())}")
            return 1
    else:
        console.print("[red]Error: Must specify --scenario NAME or --all-stress[/red]")
        console.print()
        parser.print_help()
        return 1

    # Display header
    mode_str = "[magenta](MOCK MODE - No Telegram)[/magenta]" if args.mock else "[cyan](Real Telegram)[/cyan]"
    console.print(Panel(
        f"[bold]Running {len(scenarios_to_run)} stress test(s)[/bold]\n{mode_str}",
        title="Stress Test Runner",
        expand=True
    ))

    # Initialize runner
    runner = StressTestRunner()
    results: list[StressTestResult] = []

    # Run tests with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not args.verbose,  # Keep progress visible if verbose
    ) as progress:
        task = progress.add_task("Running stress tests...", total=len(scenarios_to_run))

        for scenario in scenarios_to_run:
            progress.update(task, description=f"Running: {scenario.name}")

            try:
                # Use mock or real mode based on --mock flag
                if args.mock:
                    result = await runner.run_mock_stress_test(scenario, verbose=args.verbose)
                else:
                    result = await runner.run_stress_test(scenario, verbose=args.verbose)
                results.append(result)

                # Show individual summary if not verbose (verbose already shows details)
                if not args.verbose:
                    progress.stop()
                    print_test_summary(console, result)
                    progress.start()

            except Exception as e:
                console.print(f"\n[red]Test '{scenario.name}' failed with error:[/red]")
                console.print(f"[red]{e}[/red]")
                if args.verbose:
                    traceback.print_exc()

            progress.advance(task)

    # Print overall summary
    print_overall_summary(console, results)

    # Generate timing report if requested
    if args.timing_report:
        print_timing_report(console, results)

    # Export to JSON if requested
    if args.output:
        export_to_json(results, args.output, console)

    # Cleanup database connections
    try:
        await close_pool()
    except Exception:
        pass  # Pool may not have been initialized

    # Calculate exit code based on pass rate
    if not results:
        console.print("[yellow]No tests were completed[/yellow]")
        return 1

    pass_count = sum(1 for r in results if r.call_scheduling.scheduled)
    if pass_count == len(results):
        console.print(f"\n[bold green]All {len(results)} tests PASSED[/bold green]")
        return 0
    else:
        fail_count = len(results) - pass_count
        console.print(f"\n[bold red]{fail_count} of {len(results)} tests FAILED[/bold red]")
        return 1


def run() -> None:
    """Synchronous entry point for the CLI."""
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    run()
