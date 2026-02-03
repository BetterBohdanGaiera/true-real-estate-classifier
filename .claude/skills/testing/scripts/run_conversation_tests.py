"""
CLI to run conversation tests using Anthropic Agent SDK.

Usage:
    PYTHONPATH=.claude/skills/testing/scripts:.claude/skills/telegram/scripts uv run python .claude/skills/testing/scripts/run_conversation_tests.py [OPTIONS]

Options:
    --scenario NAME      Run specific scenario by name
    --all               Run all scenarios
    --difficulty LEVEL  Filter by difficulty (easy/medium/hard/expert)
    --output FILE       Save results to JSON file
    --verbose           Show conversation turns in real-time

Examples:
    # Run a specific scenario
    PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_conversation_tests.py --scenario "Skeptical Financist" --verbose

    # Run all scenarios by difficulty
    PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_conversation_tests.py --difficulty hard

    # Run all scenarios and save results
    PYTHONPATH=.claude/skills/testing/scripts uv run python .claude/skills/testing/scripts/run_conversation_tests.py --all --output results.json
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent

# Add telegram scripts to path for TelegramAgent import
_TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram" / "scripts"
if str(_TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_TELEGRAM_SCRIPTS))

from telegram_agent import TelegramAgent

# Support both package import and direct execution
try:
    from .conversation_simulator import ConversationSimulator, ConversationResult
    from .conversation_evaluator import ConversationEvaluator, ConversationAssessment
    from .test_scenarios import SCENARIOS, get_scenario_by_name, get_scenarios_by_difficulty
except ImportError:
    from conversation_simulator import ConversationSimulator, ConversationResult
    from conversation_evaluator import ConversationEvaluator, ConversationAssessment
    from test_scenarios import SCENARIOS, get_scenario_by_name, get_scenarios_by_difficulty

console = Console()


async def run_single_scenario(
    simulator: ConversationSimulator,
    evaluator: ConversationEvaluator,
    scenario_name: str,
    verbose: bool = False
) -> tuple[ConversationResult, ConversationAssessment]:
    """
    Run a single scenario and evaluate it.

    Args:
        simulator: ConversationSimulator instance
        evaluator: ConversationEvaluator instance
        scenario_name: Name of the scenario to run
        verbose: Whether to print conversation in real-time

    Returns:
        Tuple of (ConversationResult, ConversationAssessment)
    """
    scenario = get_scenario_by_name(scenario_name)
    result = await simulator.run_scenario(scenario, verbose=verbose)
    assessment = await evaluator.evaluate(result)
    return result, assessment


async def run_all_scenarios(
    simulator: ConversationSimulator,
    evaluator: ConversationEvaluator,
    scenarios: list,
    verbose: bool = False
) -> list[tuple[ConversationResult, ConversationAssessment]]:
    """
    Run all scenarios sequentially with progress tracking.

    Args:
        simulator: ConversationSimulator instance
        evaluator: ConversationEvaluator instance
        scenarios: List of ConversationScenario to run
        verbose: Whether to print conversations in real-time

    Returns:
        List of (ConversationResult, ConversationAssessment) tuples
    """
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running scenarios...", total=len(scenarios))

        for scenario in scenarios:
            progress.update(task, description=f"Running: {scenario.name}")
            result = await simulator.run_scenario(scenario, verbose=verbose)
            assessment = await evaluator.evaluate(result)
            results.append((result, assessment))
            progress.advance(task)

    return results


def display_summary(results: list[tuple[ConversationResult, ConversationAssessment]]) -> None:
    """
    Display summary table of all test results.

    Args:
        results: List of (ConversationResult, ConversationAssessment) tuples
    """
    table = Table(title="Conversation Test Results", expand=True)

    table.add_column("Scenario", style="cyan")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Outcome", style="green")
    table.add_column("Turns", justify="right")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Email", justify="center")

    for result, assessment in results:
        outcome_color = {
            "zoom_scheduled": "green",
            "follow_up_proposed": "yellow",
            "client_refused": "red",
            "escalated": "blue",
            "inconclusive": "dim",
        }.get(result.outcome.value, "white")

        table.add_row(
            result.scenario_name,
            result.persona.difficulty,
            f"[{outcome_color}]{result.outcome.value}[/{outcome_color}]",
            str(result.total_turns),
            f"{assessment.overall_score}/100",
            "[green]Y[/green]" if result.email_collected else "[red]X[/red]",
        )

    console.print(table)

    # Summary statistics
    avg_score = sum(a.overall_score for _, a in results) / len(results)
    zoom_count = sum(1 for r, _ in results if r.outcome.value == "zoom_scheduled")

    console.print(Panel(
        f"[bold]Average Score:[/bold] {avg_score:.1f}/100\n"
        f"[bold]Zoom Scheduled:[/bold] {zoom_count}/{len(results)}\n"
        f"[bold]Total Scenarios:[/bold] {len(results)}",
        title="Summary",
        expand=True,
    ))


def save_results(
    filepath: str,
    results: list[tuple[ConversationResult, ConversationAssessment]]
) -> None:
    """
    Save detailed results to JSON file.

    Args:
        filepath: Path to output JSON file
        results: List of (ConversationResult, ConversationAssessment) tuples
    """
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(results),
        "results": [
            {
                "scenario": r.scenario_name,
                "outcome": r.outcome.value,
                "turns": r.total_turns,
                "duration_seconds": r.duration_seconds,
                "email_collected": r.email_collected,
                "assessment": a.model_dump(),
                "conversation": [
                    {
                        "speaker": t.speaker,
                        "message": t.message,
                        "action": t.action,
                    }
                    for t in r.turns
                ],
            }
            for r, a in results
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]Results saved to {filepath}[/green]")


async def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Run conversation tests for Telegram agent"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run specific scenario by name"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all scenarios"
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        choices=["easy", "medium", "hard", "expert"],
        help="Filter by difficulty level"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show conversation turns in real-time"
    )
    args = parser.parse_args()

    # Initialize TelegramAgent with paths
    agent = TelegramAgent(
        tone_of_voice_path=SKILLS_BASE / "tone-of-voice",
        how_to_communicate_path=SKILLS_BASE / "how-to-communicate",
        knowledge_base_path=PROJECT_ROOT / "knowledge_base_final",
    )

    # Initialize simulator and evaluator
    simulator = ConversationSimulator(agent, max_turns=15)
    evaluator = ConversationEvaluator()

    # Determine which scenarios to run based on arguments
    scenarios = []
    if args.scenario:
        scenarios = [get_scenario_by_name(args.scenario)]
    elif args.difficulty:
        scenarios = get_scenarios_by_difficulty(args.difficulty)
    elif args.all:
        scenarios = SCENARIOS
    else:
        console.print(
            "[yellow]No scenarios specified. Use --scenario NAME, "
            "--difficulty LEVEL, or --all[/yellow]"
        )
        return

    if not scenarios:
        console.print("[red]No scenarios found matching criteria[/red]")
        return

    # Display test info panel
    console.print(Panel(
        f"[bold]Running {len(scenarios)} scenario(s)[/bold]",
        title="Conversation Tests",
        expand=True,
    ))

    # Run scenarios
    results = await run_all_scenarios(simulator, evaluator, scenarios, args.verbose)

    # Display summary
    display_summary(results)

    # Save results if output path specified
    if args.output:
        save_results(args.output, results)


if __name__ == "__main__":
    asyncio.run(main())
