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
CLI for Running Behavior Tests.

Tests specific agent behaviors:
1. Message Batching - 3 client messages → 1 agent response
2. Wait Handling - client asks to wait → agent pauses
3. Zoom Scheduling - conversation ends with meeting booking

Usage:
    # Run all behavior tests
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --all --verbose

    # Run individual tests
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test batching --verbose
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test wait --verbose
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test zoom --verbose

    # Save results to JSON
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --all --output behavior_results.json

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Setup paths for imports
BEHAVIOR_TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = BEHAVIOR_TESTS_DIR.parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent
_SRC_DIR = PROJECT_ROOT / "src"
TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram/scripts"
ADW_MODULES = PROJECT_ROOT / "adws"

# Add paths in correct order - must add src first for sales_agent imports
for path in [_SRC_DIR, ADW_MODULES, TELEGRAM_SCRIPTS, SCRIPTS_DIR, BEHAVIOR_TESTS_DIR]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Local imports - these don't need lazy loading
from behavior_scenarios import (
    BEHAVIOR_SCENARIOS,
    BATCHING_SCENARIO,
    WAIT_HANDLING_SCENARIO,
    ZOOM_SCHEDULING_SCENARIO,
    WAIT_PHRASES,
    RESUME_PHRASES,
    TEST_EMAIL,
    get_behavior_scenario_by_name,
)
from behavior_verifiers import (
    BatchingVerifier,
    BatchingVerificationResult,
    WaitHandlingVerifier,
    WaitHandlingVerificationResult,
    ZoomSchedulingVerifier,
    ZoomSchedulingVerificationResult,
)

# Heavy imports are done lazily in functions to avoid import errors at startup
# mock_telegram_daemon, conversation_simulator are imported when tests actually run

# Type checking imports (not executed at runtime)
if TYPE_CHECKING:
    from mock_telegram_daemon import MockTelegramDaemon
    from conversation_simulator import ConversationTurn, ConversationResult, ConversationOutcome, PersonaPlayer

console = Console()


# =============================================================================
# CLI ARGUMENT PARSER
# =============================================================================

parser = argparse.ArgumentParser(
    description="Run behavior tests for Telegram Agent",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  # Run all behavior tests
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --all --verbose

  # Run specific test
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test batching --verbose
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test wait --verbose
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --test zoom --verbose

  # Export results to JSON
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --all --output results.json

  # List available tests
  PYTHONPATH=src uv run python .claude/skills/testing/scripts/behavior_tests/run_behavior_tests.py --list
"""
)

parser.add_argument(
    "--test",
    type=str,
    choices=["batching", "wait", "zoom"],
    help="Run specific behavior test"
)
parser.add_argument(
    "--all",
    action="store_true",
    help="Run all behavior tests"
)
parser.add_argument(
    "--list",
    action="store_true",
    help="List available behavior tests and exit"
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


# =============================================================================
# BEHAVIOR TEST RESULT
# =============================================================================

class BehaviorTestResult:
    """Container for a single behavior test result."""

    def __init__(
        self,
        test_name: str,
        passed: bool,
        verification_result: BatchingVerificationResult | WaitHandlingVerificationResult | ZoomSchedulingVerificationResult,
        turns: list[Any],  # ConversationTurn - lazy loaded
        daemon_stats: dict,
        duration_seconds: float,
    ):
        self.test_name = test_name
        self.passed = passed
        self.verification_result = verification_result
        self.turns = turns
        self.daemon_stats = daemon_stats
        self.duration_seconds = duration_seconds

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "verification": self.verification_result.model_dump(),
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "speaker": t.speaker,
                    "message": t.message,
                    "action": t.action,
                    "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, 'isoformat') else str(t.timestamp),
                }
                for t in self.turns
            ],
            "daemon_stats": self.daemon_stats,
            "duration_seconds": self.duration_seconds,
        }


# =============================================================================
# TEST RUNNERS
# =============================================================================

async def run_batching_test(verbose: bool = False) -> BehaviorTestResult:
    """
    Run message batching behavior test.

    Tests that 3 rapid client messages result in 1 batched agent response.
    """
    # Lazy imports to avoid import errors at startup
    from mock_telegram_daemon import MockTelegramDaemon
    from conversation_simulator import ConversationTurn

    scenario = BATCHING_SCENARIO
    start_time = datetime.now(timezone.utc)

    if verbose:
        console.print(Panel(
            f"[bold]Batching Test: {scenario.name}[/bold]\n"
            f"Persona: {scenario.persona.name}\n"
            f"Tests: 3 client messages → 1 agent response",
            title="BATCHING TEST",
            expand=True,
        ))

    # Initialize daemon
    daemon = MockTelegramDaemon(
        prospect_telegram_id=f"@batching_test_{random.randint(1000, 9999)}",
        prospect_name="Batching Test Client",
        prospect_context=scenario.initial_context,
        verbose=verbose,
    )

    turns: list[ConversationTurn] = []
    turn_counter = 0

    try:
        await daemon.initialize()

        # Step 1: Agent initiates
        if verbose:
            console.print("\n[cyan]Step 1: Triggering agent initial message...[/cyan]")

        await daemon.simulate_incoming_message("Здравствуйте")
        response = await daemon.wait_for_response(timeout=60.0)

        if response:
            turn_counter += 1
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="agent",
                message=response,
            ))
            if verbose:
                console.print(f"[green][Agent][/green]: {response}")

        # Step 2: Client sends 3 rapid messages (the key test)
        if verbose:
            console.print("\n[cyan]Step 2: Sending 3 rapid client messages...[/cyan]")

        # Clear captured messages and reset stats to count just the batch
        daemon.mock_service.clear_messages()
        daemon.stats["batches_processed"] = 0
        daemon.stats["messages_sent"] = 0

        # Clear turns list for accurate verification of the batch test
        turns = []
        turn_counter = 0

        test_messages = [
            "Какие есть виллы на продажу?",
            "Сколько стоит?",
            "Есть ли возможность рассрочки?",
        ]

        for i, msg in enumerate(test_messages):
            turn_counter += 1
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="persona",
                message=msg,
            ))
            if verbose:
                console.print(f"[blue][Client][/blue]: {msg}")

            await daemon.simulate_incoming_message(msg)

            # Short delay between messages (simulating rapid typing)
            if i < len(test_messages) - 1:
                delay = random.uniform(0.5, 1.5)
                await asyncio.sleep(delay)

        # Step 3: Wait for single batched response
        if verbose:
            console.print("\n[cyan]Step 3: Waiting for batched response...[/cyan]")

        response = await daemon.wait_for_response(timeout=90.0)

        if response:
            turn_counter += 1
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="agent",
                message=response,
            ))
            if verbose:
                console.print(f"[green][Agent][/green]: {response}")

        # Verify batching
        verifier = BatchingVerifier(expected_client_messages=3)
        verification = verifier.verify(turns, daemon.stats)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        if verbose:
            console.print(f"\n[{'green' if verification.passed else 'red'}]{verification.summary()}[/]")

        return BehaviorTestResult(
            test_name="batching",
            passed=verification.passed,
            verification_result=verification,
            turns=turns,
            daemon_stats=daemon.stats.copy(),
            duration_seconds=duration,
        )

    finally:
        await daemon.cleanup()


async def run_wait_handling_test(verbose: bool = False) -> BehaviorTestResult:
    """
    Run wait handling behavior test.

    Tests that agent pauses when client asks to wait, then resumes.
    """
    # Lazy imports to avoid import errors at startup
    from mock_telegram_daemon import MockTelegramDaemon
    from conversation_simulator import ConversationTurn

    scenario = WAIT_HANDLING_SCENARIO
    start_time = datetime.now(timezone.utc)

    wait_phrase = random.choice(WAIT_PHRASES)
    resume_phrase = random.choice(RESUME_PHRASES)

    if verbose:
        console.print(Panel(
            f"[bold]Wait Handling Test: {scenario.name}[/bold]\n"
            f"Persona: {scenario.persona.name}\n"
            f"Wait phrase: \"{wait_phrase}\"\n"
            f"Resume phrase: \"{resume_phrase}\"",
            title="WAIT HANDLING TEST",
            expand=True,
        ))

    # Initialize daemon
    daemon = MockTelegramDaemon(
        prospect_telegram_id=f"@wait_test_{random.randint(1000, 9999)}",
        prospect_name="Wait Test Client",
        prospect_context=scenario.initial_context,
        verbose=verbose,
    )

    turns: list[ConversationTurn] = []
    turn_counter = 0

    try:
        await daemon.initialize()

        # Step 1: Initial exchange
        if verbose:
            console.print("\n[cyan]Step 1: Initial conversation...[/cyan]")

        await daemon.simulate_incoming_message("Здравствуйте, интересуюсь недвижимостью")
        response = await daemon.wait_for_response(timeout=60.0)

        if response:
            turn_counter += 1
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="agent",
                message=response,
            ))
            if verbose:
                console.print(f"[green][Agent][/green]: {response}")

        # Step 2: Use verifier for wait handling test
        if verbose:
            console.print("\n[cyan]Step 2: Testing wait handling...[/cyan]")
            console.print(f"[blue][Client][/blue]: {wait_phrase}")

        verifier = WaitHandlingVerifier(
            immediate_response_timeout=30.0,
            minimum_wait_duration=120.0,  # 2 minutes
        )

        verification = await verifier.verify_with_timing(
            daemon=daemon,
            wait_phrase=wait_phrase,
            resume_phrase=resume_phrase,
        )

        # Add turns from the wait test
        turn_counter += 1
        turns.append(ConversationTurn(
            turn_number=turn_counter,
            speaker="persona",
            message=wait_phrase,
        ))

        turn_counter += 1
        turns.append(ConversationTurn(
            turn_number=turn_counter,
            speaker="persona",
            message=resume_phrase,
        ))

        if verification.agent_responded_after_resume:
            # Get the actual response
            last_response = daemon.get_last_response()
            if last_response:
                turn_counter += 1
                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="agent",
                    message=last_response.text,
                ))
                if verbose:
                    console.print(f"[green][Agent][/green]: {last_response.text}")

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        if verbose:
            console.print(f"\n[{'green' if verification.passed else 'red'}]{verification.summary()}[/]")

        return BehaviorTestResult(
            test_name="wait_handling",
            passed=verification.passed,
            verification_result=verification,
            turns=turns,
            daemon_stats=daemon.stats.copy(),
            duration_seconds=duration,
        )

    finally:
        await daemon.cleanup()


async def run_zoom_scheduling_test(verbose: bool = False) -> BehaviorTestResult:
    """
    Run Zoom scheduling behavior test.

    Tests full booking flow: email collection → slots → confirmation.
    """
    # Lazy imports to avoid import errors at startup
    from mock_telegram_daemon import MockTelegramDaemon
    from conversation_simulator import ConversationTurn, PersonaPlayer

    scenario = ZOOM_SCHEDULING_SCENARIO
    start_time = datetime.now(timezone.utc)

    if verbose:
        console.print(Panel(
            f"[bold]Zoom Scheduling Test: {scenario.name}[/bold]\n"
            f"Persona: {scenario.persona.name}\n"
            f"Test email: {TEST_EMAIL}",
            title="ZOOM SCHEDULING TEST",
            expand=True,
        ))

    # Initialize daemon
    daemon = MockTelegramDaemon(
        prospect_telegram_id=f"@zoom_test_{random.randint(1000, 9999)}",
        prospect_name="Zoom Test Client",
        prospect_context=scenario.initial_context,
        verbose=verbose,
    )

    turns: list[ConversationTurn] = []
    turn_counter = 0

    try:
        await daemon.initialize()

        # Initialize persona player for intelligent responses
        persona_player = PersonaPlayer(scenario.persona)

        # Conversation flow for Zoom scheduling
        messages_sequence = [
            # Initial greeting
            "Здравствуйте! Ищу виллу на Бали для покупки.",
            # Express interest in call
            "Да, хотел бы созвониться и обсудить варианты подробнее.",
            # Provide email when asked
            f"Конечно, мой email: {TEST_EMAIL}",
            # Select time slot
            "Отлично, давайте завтра утром, первый слот подойдёт.",
            # Confirm
            "Да, подтверждаю. Спасибо!",
        ]

        max_exchanges = 10  # Safety limit

        for exchange_num in range(max_exchanges):
            if verbose:
                console.print(f"\n[cyan]Exchange {exchange_num + 1}...[/cyan]")

            # Client message
            if exchange_num < len(messages_sequence):
                client_msg = messages_sequence[exchange_num]
            else:
                # Generate response using persona player
                last_agent_msg = ""
                for turn in reversed(turns):
                    if turn.speaker == "agent":
                        last_agent_msg = turn.message
                        break
                client_msg = await persona_player.generate_response(
                    agent_message=last_agent_msg,
                    conversation_history=turns,
                )

            turn_counter += 1
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="persona",
                message=client_msg,
            ))

            if verbose:
                console.print(f"[blue][Client][/blue]: {client_msg}")

            await daemon.simulate_incoming_message(client_msg)

            # Wait for agent response
            response = await daemon.wait_for_response(timeout=90.0)

            if response:
                turn_counter += 1
                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="agent",
                    message=response,
                ))

                if verbose:
                    console.print(f"[green][Agent][/green]: {response}")

                # Check if meeting was booked
                if daemon.prospect and daemon.prospect.status.value == "zoom_scheduled":
                    if verbose:
                        console.print("\n[green]Meeting scheduled![/green]")
                    break

            # Small delay between exchanges
            await asyncio.sleep(random.uniform(1.0, 2.0))

        # Verify Zoom scheduling
        verifier = ZoomSchedulingVerifier(expected_email=TEST_EMAIL)
        verification = verifier.verify_from_daemon(daemon, turns)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        if verbose:
            console.print(f"\n[{'green' if verification.passed else 'red'}]{verification.summary()}[/]")

        return BehaviorTestResult(
            test_name="zoom_scheduling",
            passed=verification.passed,
            verification_result=verification,
            turns=turns,
            daemon_stats=daemon.stats.copy(),
            duration_seconds=duration,
        )

    finally:
        await daemon.cleanup()


# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

def print_test_list():
    """Print available behavior tests."""
    table = Table(title="Available Behavior Tests", expand=True)
    table.add_column("Test", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Key Verification", style="yellow")

    table.add_row(
        "batching",
        "Message Batching Test",
        "3 client messages → 1 agent response"
    )
    table.add_row(
        "wait",
        "Wait Handling Test",
        "Agent pauses when asked, resumes on signal"
    )
    table.add_row(
        "zoom",
        "Zoom Scheduling Test",
        "Email → slots → meeting booked"
    )

    console.print(table)


def print_results_summary(results: list[BehaviorTestResult]):
    """Print summary table of all test results."""
    table = Table(title="Behavior Test Results", expand=True)
    table.add_column("Test", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Details", style="white")

    for result in results:
        status = "[green]PASSED[/green]" if result.passed else "[red]FAILED[/red]"

        # Get brief details from verification
        details = ""
        if hasattr(result.verification_result, "error_message") and result.verification_result.error_message:
            details = result.verification_result.error_message
        elif result.passed:
            details = "All checks passed"

        table.add_row(
            result.test_name,
            status,
            f"{result.duration_seconds:.1f}s",
            details[:50] + "..." if len(details) > 50 else details,
        )

    console.print(table)

    # Overall summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    status_color = "green" if passed == total else "red"
    console.print(f"\n[{status_color}]Overall: {passed}/{total} tests passed[/{status_color}]")


def save_results_to_json(results: list[BehaviorTestResult], output_path: str):
    """Save test results to JSON file."""
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tests": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [r.to_dict() for r in results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    console.print(f"\n[green]Results saved to: {output_path}[/green]")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    args = parser.parse_args()

    # List tests and exit
    if args.list:
        print_test_list()
        return 0

    # Validate arguments
    if not args.all and not args.test:
        console.print("[red]Error: Specify --all or --test <name>[/red]")
        parser.print_help()
        return 1

    results: list[BehaviorTestResult] = []

    # Run tests
    if args.all:
        console.print("[bold]Running all behavior tests...[/bold]\n")

        # Batching test
        console.print("[cyan]1/3: Batching Test[/cyan]")
        result = await run_batching_test(verbose=args.verbose)
        results.append(result)

        # Wait handling test
        console.print("\n[cyan]2/3: Wait Handling Test[/cyan]")
        result = await run_wait_handling_test(verbose=args.verbose)
        results.append(result)

        # Zoom scheduling test
        console.print("\n[cyan]3/3: Zoom Scheduling Test[/cyan]")
        result = await run_zoom_scheduling_test(verbose=args.verbose)
        results.append(result)

    elif args.test == "batching":
        result = await run_batching_test(verbose=args.verbose)
        results.append(result)

    elif args.test == "wait":
        result = await run_wait_handling_test(verbose=args.verbose)
        results.append(result)

    elif args.test == "zoom":
        result = await run_zoom_scheduling_test(verbose=args.verbose)
        results.append(result)

    # Print summary
    console.print("\n")
    print_results_summary(results)

    # Save to JSON if requested
    if args.output:
        save_results_to_json(results, args.output)

    # Return exit code
    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
