# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
#   "telethon>=1.28.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Stress Test Runner - Main orchestration engine for E2E stress tests.

Runs end-to-end conversations with real Telegram integration, applying stress conditions
(timing, batching, urgency), scoring results, and validating call scheduling outcomes.

This module coordinates:
- Real Telegram communication via E2ETelegramPlayer
- Stress timing application based on StressScenario parameters
- Call scheduling validation via scheduled_actions database
- Conversation quality scoring via ConversationEvaluator
- Result persistence via TestResultManager

Usage:
    >>> from stress_test_runner import StressTestRunner
    >>> from stress_scenarios import get_stress_scenario_by_name
    >>>
    >>> runner = StressTestRunner()
    >>> scenario = get_stress_scenario_by_name("Rapid Fire Burst")
    >>> result = await runner.run_stress_test(scenario, verbose=True)
    >>> print(f"Score: {result.assessment['overall_score']}/100")
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from rich.console import Console

# Setup paths for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
SKILLS_BASE = Path(__file__).parent.parent.parent
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Add telegram skill scripts to path for models
TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram/scripts"
if str(TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_SCRIPTS))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Support both package import and direct execution
try:
    from .stress_scenarios import StressScenario, StressConfig
    from .e2e_telegram_player import E2ETelegramPlayer
    from .conversation_simulator import (
        ConversationTurn,
        ConversationResult,
        ConversationOutcome,
        PersonaDefinition,
        PersonaPlayer,
    )
    from .conversation_evaluator import ConversationEvaluator
    from .test_result_manager import save_test_result
    from .manual_test import reset_test_prospect
except ImportError:
    from stress_scenarios import StressScenario, StressConfig
    from e2e_telegram_player import E2ETelegramPlayer
    from conversation_simulator import (
        ConversationTurn,
        ConversationResult,
        ConversationOutcome,
        PersonaDefinition,
        PersonaPlayer,
    )
    from conversation_evaluator import ConversationEvaluator
    from test_result_manager import save_test_result
    from manual_test import reset_test_prospect

# Add scheduling skill scripts to path
SCHEDULING_SCRIPTS = SKILLS_BASE / "scheduling/scripts"
if str(SCHEDULING_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_SCRIPTS))

# Import from telegram skill for models
from models import ScheduledActionType, ScheduledActionStatus

# Import from scheduling skill
from scheduled_action_manager import (
    get_actions_for_prospect,
    cancel_pending_for_prospect,
    close_pool as close_scheduler_pool,
)


# =============================================================================
# DATA MODELS
# =============================================================================


class CallSchedulingResult(BaseModel):
    """
    Result of call scheduling validation.

    Captures whether a meeting was successfully scheduled in the database,
    along with relevant details like scheduled time and Zoom URL.

    Attributes:
        scheduled: True if a meeting was scheduled in the database
        scheduled_time: When the meeting is scheduled for (if scheduled)
        zoom_url: Zoom meeting URL extracted from payload (if available)
        action_id: UUID of the scheduled action record
    """
    scheduled: bool
    scheduled_time: Optional[datetime] = None
    zoom_url: Optional[str] = None
    action_id: Optional[str] = None


class TimingMetrics(BaseModel):
    """
    Timing metrics collected during stress test execution.

    Tracks response times, batch handling, and urgency detection
    for analyzing agent performance under stress conditions.

    Attributes:
        response_times: List of agent response times in seconds
        avg_response_time: Average response time in seconds
        max_response_time: Maximum observed response time
        min_response_time: Minimum observed response time
        batch_sizes: Sizes of message batches sent during test
        urgency_detected: Whether agent acknowledged urgency cues
        total_duration: Total test duration in seconds
    """
    response_times: list[float] = Field(default_factory=list)
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = 0.0
    batch_sizes: list[int] = Field(default_factory=list)
    urgency_detected: bool = False
    total_duration: float = 0.0


class StressTestResult(BaseModel):
    """
    Complete result of a stress test run.

    Contains all information about a stress test execution including
    the conversation, assessment scores, call scheduling outcome,
    timing metrics, and database record ID.

    Attributes:
        scenario_name: Name of the stress scenario executed
        conversation_result: Full ConversationResult with turns and outcome
        assessment: ConversationAssessment as dict (or None if evaluation failed)
        call_scheduling: Result of call scheduling validation
        timing_metrics: Detailed timing measurements from test execution
        test_id: UUID of database record (if saved)
        timestamp: When the test was executed (UTC)
    """
    scenario_name: str
    conversation_result: ConversationResult
    assessment: Optional[dict] = None  # ConversationAssessment as dict
    call_scheduling: CallSchedulingResult
    timing_metrics: TimingMetrics
    test_id: Optional[str] = None  # UUID from database
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# TEST PATTERN ITERATOR
# =============================================================================


class TestPatternIterator:
    """
    Iterates through test orchestration pattern.

    This controls WHEN the test sends messages, NOT how the system
    detects message completion (that's timing-based via MessageBuffer).

    Pattern format: list[tuple[str, int]] where each tuple is (speaker, count):
    - 'C' = client sends messages
    - 'A' = wait for agent response(s)

    Example: [('C', 3), ('A', 1), ('C', 2)] means:
    - Test sends 3 client messages (with inter_message_delays between them)
    - Test waits for 1 agent response (system uses timing to batch)
    - Test sends 2 more client messages

    Attributes:
        pattern: List of (speaker, count) tuples
        index: Current position in pattern (0-based)
        remaining: Remaining messages in current step
    """

    def __init__(self, pattern: list[tuple[str, int]] | None):
        """Initialize iterator with pattern (None = default alternating)."""
        self.pattern = pattern or [("C", 1), ("A", 1)]  # Default alternating
        self.index = 0
        self.remaining = self.pattern[0][1] if self.pattern else 1

    def current(self) -> tuple[str, int]:
        """Get current speaker and message count for this step."""
        if self.index >= len(self.pattern):
            # Cycle back to beginning
            self.index = 0
        return self.pattern[self.index]

    def advance(self):
        """Move to next step in pattern."""
        self.remaining -= 1
        if self.remaining <= 0:
            # Move to next pattern step
            self.index += 1
            if self.index >= len(self.pattern):
                self.index = 0  # Cycle
            self.remaining = self.pattern[self.index][1]

    def reset(self):
        """Reset iterator to beginning of pattern."""
        self.index = 0
        self.remaining = self.pattern[0][1] if self.pattern else 1


# =============================================================================
# STRESS TEST RUNNER
# =============================================================================


class StressTestRunner:
    """
    Main orchestration engine for E2E stress tests.

    Coordinates real Telegram communication, stress timing application,
    conversation tracking, call scheduling validation, quality scoring,
    and result persistence.

    The runner supports two modes:
    - In-process agent (default): Agent responds within the same process
    - Daemon mode: Agent runs as a separate subprocess

    Example:
        >>> runner = StressTestRunner()
        >>> scenario = get_stress_scenario_by_name("Rapid Fire Burst")
        >>> result = await runner.run_stress_test(scenario, verbose=True)
        >>> print(f"Outcome: {result.conversation_result.outcome}")
        >>> print(f"Score: {result.assessment['overall_score']}/100")

    Attributes:
        agent_telegram_id: The agent's Telegram handle
        test_prospect_telegram_id: Test prospect's Telegram handle
        max_turns: Maximum conversation turns before timeout
        use_daemon: Whether to run daemon in subprocess vs in-process
        console: Rich console for verbose output
    """

    def __init__(
        self,
        agent_telegram_id: str = "@BetterBohdan",
        test_prospect_telegram_id: str = "@buddah_lucid",
        max_turns: int = 20,
        use_daemon: bool = False,
    ):
        """
        Initialize stress test runner.

        Args:
            agent_telegram_id: The agent's telegram ID (default: @BetterBohdan).
                               This is the account the sales agent operates as.
            test_prospect_telegram_id: Test prospect's telegram ID (default: @buddah_lucid).
                                       The test messages will be sent FROM this account.
            max_turns: Maximum conversation turns before timeout (default: 20).
                      A "turn" is a single message from either party.
            use_daemon: Whether to run daemon in subprocess vs in-process (default: False).
                       When False, responses are generated in-process for faster testing.
        """
        self.agent_telegram_id = agent_telegram_id
        self.test_prospect_telegram_id = test_prospect_telegram_id
        self.max_turns = max_turns
        self.use_daemon = use_daemon
        self.console = Console()

    async def run_stress_test(
        self,
        scenario: StressScenario,
        verbose: bool = False,
    ) -> StressTestResult:
        """
        Run a complete stress test scenario.

        This is the main entry point that orchestrates the full stress test workflow:
        1. Pre-test setup (reset prospect status, cancel pending scheduled actions)
        2. Initialize E2E Telegram player for real message sending/receiving
        3. Run conversation loop with stress timing from scenario configuration
        4. Validate call scheduling by checking scheduled_actions database
        5. Score conversation quality with ConversationEvaluator
        6. Save results to database via TestResultManager
        7. Return complete StressTestResult with all metrics

        Args:
            scenario: StressScenario to execute, containing persona definition
                     and stress configuration (timing, batching, urgency).
            verbose: If True, print conversation in real-time to console.
                    Useful for debugging and manual observation.

        Returns:
            StressTestResult with full metrics and assessment.
        """
        start_time = datetime.now(timezone.utc)

        if verbose:
            self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
            self.console.print(f"[bold]STRESS TEST: {scenario.name}[/bold]")
            self.console.print(f"Persona: {scenario.persona.name} ({scenario.persona.difficulty})")
            self.console.print(f"Timeout multiplier: {scenario.stress_config.timeout_multiplier}x")
            self.console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

        # Step 1: Pre-test setup
        if verbose:
            self.console.print("[yellow]Step 1: Pre-test setup...[/yellow]")

        await self._pre_test_setup(verbose)

        # Step 2: Initialize E2E player
        if verbose:
            self.console.print("[yellow]Step 2: Initializing Telegram player...[/yellow]")

        player = E2ETelegramPlayer(session_name="test_prospect")

        try:
            await player.connect()

            if verbose:
                me = await player.get_me()
                self.console.print(f"  Connected as: {me['first_name']} (@{me['username']})")

            # Step 3: Run conversation with stress timing
            if verbose:
                self.console.print("[yellow]Step 3: Running conversation...[/yellow]\n")

            turns, outcome, timing_metrics = await self._run_conversation(
                scenario,
                player,
                verbose,
            )

            # Calculate timing stats
            if timing_metrics.response_times:
                timing_metrics.avg_response_time = sum(timing_metrics.response_times) / len(timing_metrics.response_times)
                timing_metrics.max_response_time = max(timing_metrics.response_times)
                timing_metrics.min_response_time = min(timing_metrics.response_times)

            timing_metrics.total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        finally:
            await player.disconnect()

        # Build ConversationResult
        conversation_result = ConversationResult(
            scenario_name=scenario.name,
            persona=scenario.persona,
            turns=turns,
            outcome=outcome,
            total_turns=len(turns),
            duration_seconds=timing_metrics.total_duration,
            agent_actions_used=self._count_agent_actions(turns),
            email_collected=self._check_email_collected(turns),
            escalation_triggered=outcome == ConversationOutcome.ESCALATED,
        )

        # Step 4: Validate call scheduling
        if verbose:
            self.console.print("\n[yellow]Step 4: Validating call scheduling...[/yellow]")

        call_scheduling = await self._validate_call_scheduled(
            self.test_prospect_telegram_id,
            verbose,
        )

        # Step 5: Score with evaluator
        if verbose:
            self.console.print("[yellow]Step 5: Scoring conversation...[/yellow]")

        assessment_dict = None
        try:
            evaluator = ConversationEvaluator()
            assessment = await evaluator.evaluate(conversation_result)
            assessment_dict = assessment.model_dump()

            if verbose:
                self.console.print(f"  Overall score: [bold]{assessment.overall_score}/100[/bold]")
        except Exception as e:
            if verbose:
                self.console.print(f"  [red]Evaluation failed: {e}[/red]")

        # Step 6: Save to database
        test_id = None
        if verbose:
            self.console.print("[yellow]Step 6: Saving results...[/yellow]")

        try:
            if assessment_dict is not None:
                # Recreate assessment object for save_test_result
                from .conversation_evaluator import ConversationAssessment
                assessment_obj = ConversationAssessment(**assessment_dict)
                test_id = await save_test_result(conversation_result, assessment_obj)

                if verbose:
                    self.console.print(f"  Saved as: {test_id}")
        except Exception as e:
            if verbose:
                self.console.print(f"  [yellow]Could not save to database: {e}[/yellow]")

        # Step 7: Build and return result
        result = StressTestResult(
            scenario_name=scenario.name,
            conversation_result=conversation_result,
            assessment=assessment_dict,
            call_scheduling=call_scheduling,
            timing_metrics=timing_metrics,
            test_id=test_id,
            timestamp=start_time,
        )

        if verbose:
            self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
            self.console.print(f"[bold]RESULT: {outcome.value}[/bold]")
            self.console.print(f"Turns: {len(turns)}")
            self.console.print(f"Duration: {timing_metrics.total_duration:.1f}s")
            self.console.print(f"Call scheduled: {call_scheduling.scheduled}")
            if assessment_dict:
                self.console.print(f"Score: {assessment_dict['overall_score']}/100")
            self.console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

        return result

    async def run_mock_stress_test(
        self,
        scenario: StressScenario,
        verbose: bool = False,
    ) -> StressTestResult:
        """
        Run a PRODUCTION SIMULATION stress test without real Telegram.

        This mode tests REAL production behavior including:
        - REAL MessageBuffer debouncing (actual waiting for message batches)
        - REAL TelegramAgent response generation
        - REAL follow-up scheduling (writes to actual database)
        - REAL timing delays (reading delays, typing simulation)
        - AI-powered PersonaPlayer for intelligent client responses

        The ONLY thing mocked is the Telegram network layer.

        Args:
            scenario: StressScenario to execute.
            verbose: If True, print conversation in real-time to console.

        Returns:
            StressTestResult with full metrics and assessment.
        """
        from .mock_telegram_daemon import MockTelegramDaemon

        start_time = datetime.now(timezone.utc)

        if verbose:
            self.console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
            self.console.print(f"[bold]PRODUCTION SIMULATION: {scenario.name}[/bold]")
            self.console.print("[dim](Real batching, timing, follow-ups - no Telegram network)[/dim]")
            self.console.print(f"Persona: {scenario.persona.name} ({scenario.persona.difficulty})")
            self.console.print(f"Timeout multiplier: {scenario.stress_config.timeout_multiplier}x")
            self.console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")

        # Initialize MockTelegramDaemon with REAL production components
        daemon = MockTelegramDaemon(
            prospect_telegram_id=f"@mock_{scenario.persona.name.lower().replace(' ', '_').replace('/', '_')}",
            prospect_name=scenario.persona.name.split()[0],
            prospect_context=scenario.initial_context,
            verbose=verbose,
        )

        try:
            await daemon.initialize()

            # Initialize PersonaPlayer for AI-powered client responses
            persona_player = PersonaPlayer(scenario.persona)

            # Track conversation turns
            turns: list[ConversationTurn] = []
            timing_metrics = TimingMetrics()
            turn_counter = 0
            stress_config = scenario.stress_config
            response_times: list[float] = []

            # Determine who starts
            if scenario.agent_initiates:
                if verbose:
                    self.console.print("[dim]Waiting for agent initial message...[/dim]")

                await daemon.simulate_incoming_message("Здравствуйте")

                response = await daemon.wait_for_response(
                    timeout=60.0 * stress_config.timeout_multiplier
                )

                if response:
                    turn_counter += 1
                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="agent",
                        message=response,
                        action="initial_outreach",
                    ))
            else:
                turn_counter += 1
                first_msg = scenario.persona.initial_message or "Здравствуйте, интересуюсь недвижимостью на Бали"
                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="persona",
                    message=first_msg,
                ))
                await daemon.simulate_incoming_message(first_msg)

            # Main conversation loop with pattern-driven orchestration
            outcome: Optional[ConversationOutcome] = None
            pattern = TestPatternIterator(stress_config.message_pattern)

            while turn_counter < self.max_turns * 2:
                outcome = self._check_termination(turns, scenario)
                if outcome:
                    break

                current_speaker, message_count = pattern.current()

                if current_speaker == "C":
                    last_agent_msg = ""
                    for turn in reversed(turns):
                        if turn.speaker == "agent":
                            last_agent_msg = turn.message
                            break

                    messages = await persona_player.generate_multi_response(
                        agent_message=last_agent_msg,
                        conversation_history=turns,
                        force_multi=True
                    )
                    messages = messages[:message_count]
                    timing_metrics.batch_sizes.append(len(messages))

                    if verbose:
                        self.console.print(f"[dim]Sending {len(messages)} client message(s)...[/dim]")

                    refusal_detected = False
                    for i, msg in enumerate(messages):
                        turn_counter += 1
                        turns.append(ConversationTurn(
                            turn_number=turn_counter,
                            speaker="persona",
                            message=msg,
                        ))

                        if verbose:
                            self.console.print(f"[blue][{scenario.persona.name}][/blue]: {msg}")

                        await daemon.simulate_incoming_message(msg)

                        if i < len(messages) - 1:
                            inter_delays = stress_config.inter_message_delays
                            delay_range = inter_delays[i % len(inter_delays)]
                            delay = random.uniform(*delay_range)
                            if verbose and delay > 5.0:
                                self.console.print(f"[dim]Pausing {delay:.1f}s between messages...[/dim]")
                            await asyncio.sleep(delay)

                        if persona_player.check_refusal(msg):
                            refusal_detected = True

                    if verbose:
                        self.console.print()

                    if refusal_detected:
                        outcome = ConversationOutcome.CLIENT_REFUSED
                        break

                    pattern.advance()

                elif current_speaker == "A":
                    send_time = datetime.now(timezone.utc)

                    response = await daemon.wait_for_response(
                        timeout=60.0 * stress_config.timeout_multiplier
                    )

                    response_time = (datetime.now(timezone.utc) - send_time).total_seconds()
                    response_times.append(response_time)

                    if response is None:
                        if verbose:
                            self.console.print(f"[yellow]Agent did not respond in time[/yellow]")
                        outcome = ConversationOutcome.INCONCLUSIVE
                        break

                    turn_counter += 1

                    action_type = "reply"
                    if self._check_scheduling_success(response):
                        action_type = "schedule"
                    elif self._check_escalation(response):
                        action_type = "escalate"

                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="agent",
                        message=response,
                        action=action_type,
                    ))

                    if verbose:
                        self.console.print(f"[green][Agent][/green] ({response_time:.1f}s): {response}\n")

                    if self._check_scheduling_success(response):
                        outcome = ConversationOutcome.ZOOM_SCHEDULED
                        break

                    if self._check_escalation(response):
                        outcome = ConversationOutcome.ESCALATED
                        break

                    pattern.advance()

            if outcome is None:
                outcome = self._classify_final_outcome(turns)

            timing_metrics.response_times = response_times
            if response_times:
                timing_metrics.avg_response_time = sum(response_times) / len(response_times)
                timing_metrics.max_response_time = max(response_times)
                timing_metrics.min_response_time = min(response_times)
            timing_metrics.total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            conversation_result = ConversationResult(
                scenario_name=scenario.name,
                persona=scenario.persona,
                turns=turns,
                outcome=outcome,
                total_turns=len(turns),
                duration_seconds=timing_metrics.total_duration,
                agent_actions_used=self._count_agent_actions(turns),
                email_collected=self._check_email_collected(turns),
                escalation_triggered=outcome == ConversationOutcome.ESCALATED,
            )

            if verbose:
                self.console.print("\n[yellow]Scoring conversation...[/yellow]")

            assessment_dict = None
            try:
                evaluator = ConversationEvaluator()
                assessment = await evaluator.evaluate(conversation_result)
                assessment_dict = assessment.model_dump()

                if verbose:
                    self.console.print(f"  Overall score: [bold]{assessment.overall_score}/100[/bold]")
            except Exception as e:
                if verbose:
                    self.console.print(f"  [red]Evaluation failed: {e}[/red]")

            call_scheduling = CallSchedulingResult(
                scheduled=outcome == ConversationOutcome.ZOOM_SCHEDULED or daemon.stats["scheduled_followups"] > 0,
                scheduled_time=datetime.now(timezone.utc) if outcome == ConversationOutcome.ZOOM_SCHEDULED else None,
            )

            test_id = None
            try:
                if assessment_dict is not None:
                    from .conversation_evaluator import ConversationAssessment
                    assessment_obj = ConversationAssessment(**assessment_dict)
                    test_id = await save_test_result(conversation_result, assessment_obj)
                    if verbose:
                        self.console.print(f"  Saved to database: {test_id}")
            except Exception as e:
                if verbose:
                    self.console.print(f"  [dim]Could not save to database: {e}[/dim]")

            result = StressTestResult(
                scenario_name=scenario.name,
                conversation_result=conversation_result,
                assessment=assessment_dict,
                call_scheduling=call_scheduling,
                timing_metrics=timing_metrics,
                test_id=test_id,
                timestamp=start_time,
            )

            if verbose:
                self.console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
                self.console.print(f"[bold]RESULT: {outcome.value}[/bold]")
                self.console.print(f"Turns: {len(turns)}")
                self.console.print(f"Duration: {timing_metrics.total_duration:.1f}s")
                self.console.print(f"Batches processed: {daemon.stats['batches_processed']}")
                self.console.print(f"Follow-ups scheduled: {daemon.stats['scheduled_followups']}")
                if assessment_dict:
                    self.console.print(f"Score: {assessment_dict['overall_score']}/100")
                self.console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")

            return result

        finally:
            await daemon.cleanup()

    async def _pre_test_setup(self, verbose: bool = False) -> None:
        """Perform pre-test setup: reset prospect and cancel pending actions."""
        try:
            reset_result = await reset_test_prospect(clean_chat=False)

            if verbose:
                if reset_result.get("error"):
                    self.console.print(f"  [yellow]Reset warning: {reset_result['error']}[/yellow]")
                else:
                    self.console.print(f"  Reset {reset_result['name']} to NEW status")
        except Exception as e:
            if verbose:
                self.console.print(f"  [yellow]Could not reset prospect: {e}[/yellow]")

        try:
            prospect_id = self.test_prospect_telegram_id.lstrip("@")
            cancelled = await cancel_pending_for_prospect(
                prospect_id,
                reason="stress_test_reset"
            )

            if verbose:
                if cancelled > 0:
                    self.console.print(f"  Cancelled {cancelled} pending scheduled action(s)")
                else:
                    self.console.print("  No pending actions to cancel")
        except Exception as e:
            if verbose:
                self.console.print(f"  [dim]Could not cancel actions: {e}[/dim]")

    async def _run_conversation(
        self,
        scenario: StressScenario,
        player: E2ETelegramPlayer,
        verbose: bool,
    ) -> tuple[list[ConversationTurn], ConversationOutcome, TimingMetrics]:
        """Run the conversation loop with stress timing applied."""
        turns: list[ConversationTurn] = []
        timing_metrics = TimingMetrics()
        stress_config = scenario.stress_config

        turn_counter = 0
        persona = scenario.persona
        base_timeout = 60.0 * stress_config.timeout_multiplier

        if scenario.agent_initiates:
            if verbose:
                self.console.print("[dim]Waiting for agent initial message...[/dim]")

            initial_response = await player.wait_for_response(
                self.agent_telegram_id,
                timeout=base_timeout,
            )

            if initial_response:
                turn_counter += 1
                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="agent",
                    message=initial_response,
                    action="initial_outreach",
                ))

                if verbose:
                    self.console.print(f"[green][Agent][/green]: {initial_response}\n")
        else:
            turn_counter += 1
            first_msg = persona.initial_message or "Здравствуйте, интересуюсь недвижимостью на Бали"
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="persona",
                message=first_msg,
            ))

            await player.send_message(self.agent_telegram_id, first_msg)

            if verbose:
                self.console.print(f"[blue][{persona.name}][/blue]: {first_msg}\n")

        outcome: Optional[ConversationOutcome] = None
        pattern = TestPatternIterator(stress_config.message_pattern)
        objection_index = 0

        while turn_counter < self.max_turns * 2:
            outcome = self._check_termination(turns, scenario)
            if outcome:
                break

            current_speaker, message_count = pattern.current()

            if current_speaker == "C":
                messages_to_send: list[str] = []
                for _ in range(message_count):
                    msg = self._generate_persona_response(
                        persona, turns, stress_config, objection_index
                    )
                    messages_to_send.append(msg)
                    objection_index += 1

                timing_metrics.batch_sizes.append(len(messages_to_send))

                inter_delays = stress_config.inter_message_delays
                delays: list[float] = []
                for i in range(len(messages_to_send)):
                    delay_range = inter_delays[i % len(inter_delays)]
                    delays.append(random.uniform(*delay_range))

                if verbose:
                    self.console.print(f"[dim]Sending {len(messages_to_send)} client message(s)...[/dim]")

                await player.send_batch(self.agent_telegram_id, messages_to_send, delays)

                refusal_detected = False
                for msg in messages_to_send:
                    turn_counter += 1
                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="persona",
                        message=msg,
                    ))

                    if verbose:
                        self.console.print(f"[blue][{persona.name}][/blue]: {msg}")

                    if self._check_refusal(msg, persona.language):
                        refusal_detected = True

                if verbose:
                    self.console.print()

                if refusal_detected:
                    outcome = ConversationOutcome.CLIENT_REFUSED
                    break

                pattern.advance()

            elif current_speaker == "A":
                send_time = datetime.now(timezone.utc)

                response = await player.wait_for_response(
                    self.agent_telegram_id,
                    timeout=base_timeout,
                )

                response_time = (datetime.now(timezone.utc) - send_time).total_seconds()
                timing_metrics.response_times.append(response_time)

                if response is None:
                    if verbose:
                        self.console.print(f"[yellow]Agent did not respond within {base_timeout:.0f}s[/yellow]\n")
                    outcome = ConversationOutcome.INCONCLUSIVE
                    break

                turn_counter += 1

                action_type = "respond"
                if self._check_scheduling_success(response):
                    action_type = "schedule"
                elif self._check_escalation(response):
                    action_type = "escalate"

                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="agent",
                    message=response,
                    action=action_type,
                ))

                if verbose:
                    self.console.print(f"[green][Agent][/green] ({response_time:.1f}s): {response}\n")

                if self._check_scheduling_success(response):
                    outcome = ConversationOutcome.ZOOM_SCHEDULED
                    break

                if self._check_escalation(response):
                    outcome = ConversationOutcome.ESCALATED
                    break

                pattern.advance()

        if outcome is None:
            outcome = self._classify_final_outcome(turns)

        return turns, outcome, timing_metrics

    def _generate_persona_response(
        self,
        persona: PersonaDefinition,
        turns: list[ConversationTurn],
        stress_config: StressConfig,
        delay_index: int,
    ) -> str:
        """Generate a simple persona response based on objections list."""
        objections = persona.objections
        if not objections:
            objections = ["Интересно, расскажите подробнее"]

        base_response = objections[delay_index % len(objections)]

        if stress_config.urgency_requests:
            if delay_index > 0 and delay_index % 3 == 0:
                urgency = stress_config.urgency_requests[
                    (delay_index // 3) % len(stress_config.urgency_requests)
                ]
                base_response = f"{urgency} {base_response}"

        return base_response

    def _check_termination(
        self,
        turns: list[ConversationTurn],
        scenario: StressScenario,
    ) -> Optional[ConversationOutcome]:
        """Check if conversation should terminate based on current state."""
        if len(turns) >= self.max_turns:
            return ConversationOutcome.INCONCLUSIVE

        agent_messages = [t.message for t in turns[-3:] if t.speaker == "agent"]
        for msg in agent_messages:
            if self._check_scheduling_success(msg):
                return ConversationOutcome.ZOOM_SCHEDULED

        return None

    def _check_refusal(self, message: str, language: str = "ru") -> bool:
        """Check if message contains refusal markers."""
        refusal_markers_ru = [
            "нет, спасибо", "не интересно", "не интересует",
            "не нужно", "не надо", "отстаньте", "прекратите",
            "не пишите", "не звоните", "удалите мой номер",
            "мне не подходит", "точно нет"
        ]
        refusal_markers_en = [
            "not interested", "no thanks", "no thank you",
            "please stop", "don't contact", "remove my number",
            "definitely not", "not for me"
        ]

        lower_msg = message.lower()
        markers = refusal_markers_ru if language == "ru" else refusal_markers_en

        return any(marker in lower_msg for marker in markers)

    def _check_scheduling_success(self, message: str) -> bool:
        """Check if message indicates successful meeting scheduling."""
        scheduling_markers_ru = [
            "встреча запланирована", "записал вас", "zoom",
            "ссылка на встречу", "подтверждаю встречу",
            "до встречи в", "приглашение отправлено"
        ]
        scheduling_markers_en = [
            "meeting scheduled", "booked you", "zoom",
            "meeting link", "confirmed meeting",
            "see you at", "invitation sent"
        ]

        lower_msg = message.lower()
        markers = scheduling_markers_ru + scheduling_markers_en

        return any(marker in lower_msg for marker in markers)

    def _check_escalation(self, message: str) -> bool:
        """Check if message indicates escalation to human."""
        escalation_markers = [
            "передам коллеге", "свяжется с вами",
            "перезвоню", "позвоню вам",
            "human will contact", "colleague will reach"
        ]

        lower_msg = message.lower()
        return any(marker in lower_msg for marker in escalation_markers)

    def _classify_final_outcome(
        self,
        turns: list[ConversationTurn],
    ) -> ConversationOutcome:
        """Classify the final outcome of the conversation."""
        for turn in turns:
            if turn.speaker == "agent" and self._check_scheduling_success(turn.message):
                return ConversationOutcome.ZOOM_SCHEDULED

        for turn in turns:
            if turn.speaker == "agent" and self._check_escalation(turn.message):
                return ConversationOutcome.ESCALATED

        follow_up_markers = ["напишу позже", "свяжусь", "follow up", "get back to you"]
        for turn in turns[-5:]:
            if turn.speaker == "agent":
                lower_msg = turn.message.lower()
                if any(marker in lower_msg for marker in follow_up_markers):
                    return ConversationOutcome.FOLLOW_UP_PROPOSED

        return ConversationOutcome.INCONCLUSIVE

    def _count_agent_actions(self, turns: list[ConversationTurn]) -> dict[str, int]:
        """Count actions used by agent in conversation."""
        actions_used: dict[str, int] = {}
        for turn in turns:
            if turn.speaker == "agent" and turn.action:
                actions_used[turn.action] = actions_used.get(turn.action, 0) + 1
        return actions_used

    def _check_email_collected(self, turns: list[ConversationTurn]) -> bool:
        """Check if email was collected during conversation."""
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        for turn in turns:
            if turn.speaker == "persona":
                if re.search(email_pattern, turn.message):
                    return True

        return False

    async def _validate_call_scheduled(
        self,
        prospect_id: str,
        verbose: bool = False,
    ) -> CallSchedulingResult:
        """Validate if a call was scheduled in the database."""
        clean_prospect_id = prospect_id.lstrip("@")

        try:
            actions = await get_actions_for_prospect(clean_prospect_id)

            for action in actions:
                if action.action_type == ScheduledActionType.PRE_MEETING_REMINDER:
                    zoom_url = action.payload.get("zoom_url") if action.payload else None

                    if verbose:
                        self.console.print(f"  Found scheduled meeting at {action.scheduled_for}")
                        if zoom_url:
                            self.console.print(f"  Zoom URL: {zoom_url}")

                    return CallSchedulingResult(
                        scheduled=True,
                        scheduled_time=action.scheduled_for,
                        zoom_url=zoom_url,
                        action_id=action.id,
                    )

            if verbose:
                self.console.print("  No scheduled meeting found in database")

            return CallSchedulingResult(scheduled=False)

        except Exception as e:
            if verbose:
                self.console.print(f"  [yellow]Could not query scheduled actions: {e}[/yellow]")

            return CallSchedulingResult(scheduled=False)

    async def validate_call_scheduled(
        self,
        prospect_id: str,
    ) -> CallSchedulingResult:
        """Public method to validate if a call was scheduled in the database."""
        return await self._validate_call_scheduled(prospect_id, verbose=False)


# =============================================================================
# MODULE SELF-TEST
# =============================================================================

if __name__ == "__main__":
    async def test_runner():
        """Quick test of stress test runner initialization."""
        print("=" * 60)
        print("Stress Test Runner - Self-Test")
        print("=" * 60)

        runner = StressTestRunner()
        print(f"\nInitialized runner:")
        print(f"  Agent: {runner.agent_telegram_id}")
        print(f"  Test Prospect: {runner.test_prospect_telegram_id}")
        print(f"  Max Turns: {runner.max_turns}")
        print(f"  Use Daemon: {runner.use_daemon}")

        call_result = CallSchedulingResult(scheduled=False)
        print(f"\nCallSchedulingResult model: OK")

        timing = TimingMetrics(
            response_times=[1.5, 2.0, 1.8],
            avg_response_time=1.77,
        )
        print(f"TimingMetrics model: OK (avg: {timing.avg_response_time}s)")

        from .stress_scenarios import get_stress_scenario_by_name

        scenario = get_stress_scenario_by_name("Rapid Fire Burst")
        print(f"\nLoaded scenario: {scenario.name}")
        print(f"  Timeout multiplier: {scenario.stress_config.timeout_multiplier}x")
        print(f"  Batch sizes: {scenario.stress_config.batch_sizes}")

        print("\n" + "=" * 60)
        print("Self-test passed!")
        print("=" * 60)

    asyncio.run(test_runner())
