"""
Behavior Verifiers for Telegram Agent Tests.

Provides verification logic for three key agent behaviors:
1. BatchingVerifier - verifies message batching (3 messages -> 1 response)
2. WaitHandlingVerifier - verifies agent waits when asked, resumes later
3. ZoomSchedulingVerifier - verifies meeting booking with email collection

Each verifier returns a typed result with pass/fail status and details.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent.parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

if TYPE_CHECKING:
    from ..mock_telegram_daemon import MockTelegramDaemon
    from ..conversation_simulator import ConversationTurn, ConversationResult, ConversationOutcome


# =============================================================================
# BATCHING VERIFIER
# Verifies: 3 client messages -> 1 agent response (batched)
# =============================================================================

class BatchingVerificationResult(BaseModel):
    """Result of batching behavior verification."""
    passed: bool
    client_messages_sent: int
    agent_responses_received: int
    batches_processed: int
    expected_batches: int = 1
    expected_responses: int = 1
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        """Human-readable summary of the result."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Batching Test: {status}\n"
            f"  Client messages: {self.client_messages_sent}\n"
            f"  Agent responses: {self.agent_responses_received} (expected: {self.expected_responses})\n"
            f"  Batches processed: {self.batches_processed} (expected: {self.expected_batches})"
        )


class BatchingVerifier:
    """
    Verifies message batching behavior.

    Checks that when a client sends multiple messages rapidly,
    the agent processes them as a single batch and sends one response.
    """

    def __init__(self, expected_client_messages: int = 3):
        """
        Initialize the verifier.

        Args:
            expected_client_messages: Number of rapid client messages to expect
        """
        self.expected_client_messages = expected_client_messages

    def verify(
        self,
        turns: list["ConversationTurn"],
        daemon_stats: dict,
    ) -> BatchingVerificationResult:
        """
        Verify batching behavior from conversation turns and daemon stats.

        Args:
            turns: List of conversation turns
            daemon_stats: Stats from MockTelegramDaemon (batches_processed, etc.)

        Returns:
            BatchingVerificationResult with pass/fail and details
        """
        # Count client messages before first agent response
        client_messages_before_response = 0
        agent_responses = 0

        for turn in turns:
            if turn.speaker == "persona":
                if agent_responses == 0:
                    # Still counting messages before first response
                    client_messages_before_response += 1
            elif turn.speaker == "agent":
                agent_responses += 1

        batches_processed = daemon_stats.get("batches_processed", 0)

        # Verification logic:
        # - Client sends N messages
        # - System batches them (batches_processed == 1)
        # - Agent sends 1 response (not N separate ones)
        passed = (
            client_messages_before_response >= self.expected_client_messages
            and batches_processed == 1
            and agent_responses == 1
        )

        error_message = None
        if not passed:
            issues = []
            if client_messages_before_response < self.expected_client_messages:
                issues.append(
                    f"Expected {self.expected_client_messages} client messages, "
                    f"got {client_messages_before_response}"
                )
            if batches_processed != 1:
                issues.append(f"Expected 1 batch, got {batches_processed}")
            if agent_responses != 1:
                issues.append(f"Expected 1 response, got {agent_responses}")
            error_message = "; ".join(issues)

        return BatchingVerificationResult(
            passed=passed,
            client_messages_sent=client_messages_before_response,
            agent_responses_received=agent_responses,
            batches_processed=batches_processed,
            error_message=error_message,
        )


# =============================================================================
# WAIT HANDLING VERIFIER
# Verifies: Client asks to wait -> Agent pauses -> Resumes on signal
# =============================================================================

class WaitHandlingVerificationResult(BaseModel):
    """Result of wait handling behavior verification."""
    passed: bool
    wait_phrase_sent: str
    agent_responded_immediately: bool  # Should be False
    wait_duration_seconds: float
    resume_phrase_sent: str
    agent_responded_after_resume: bool  # Should be True
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        """Human-readable summary of the result."""
        status = "PASSED" if self.passed else "FAILED"
        immediate = "Yes (BAD)" if self.agent_responded_immediately else "No (GOOD)"
        resumed = "Yes (GOOD)" if self.agent_responded_after_resume else "No (BAD)"
        return (
            f"Wait Handling Test: {status}\n"
            f"  Wait phrase: \"{self.wait_phrase_sent}\"\n"
            f"  Agent responded immediately: {immediate}\n"
            f"  Wait duration: {self.wait_duration_seconds:.1f}s\n"
            f"  Resume phrase: \"{self.resume_phrase_sent}\"\n"
            f"  Agent responded after resume: {resumed}"
        )


class WaitHandlingVerifier:
    """
    Verifies wait handling behavior.

    Tests that the agent recognizes "wait" requests and pauses
    until the client signals they're ready to continue.
    """

    def __init__(
        self,
        immediate_response_timeout: float = 30.0,
        minimum_wait_duration: float = 60.0,
    ):
        """
        Initialize the verifier.

        Args:
            immediate_response_timeout: How long to wait to confirm no immediate response
            minimum_wait_duration: Minimum pause duration before resume (seconds)
        """
        self.immediate_response_timeout = immediate_response_timeout
        self.minimum_wait_duration = minimum_wait_duration

    async def verify_with_timing(
        self,
        daemon: "MockTelegramDaemon",
        wait_phrase: str,
        resume_phrase: str,
    ) -> WaitHandlingVerificationResult:
        """
        Verify wait handling with real timing.

        This method actively tests the daemon's behavior:
        1. Sends wait phrase
        2. Verifies NO response within timeout
        3. Waits the specified duration
        4. Sends resume phrase
        5. Verifies agent responds after resume

        Args:
            daemon: Initialized MockTelegramDaemon
            wait_phrase: Message asking agent to wait
            resume_phrase: Message signaling client is back

        Returns:
            WaitHandlingVerificationResult with pass/fail and timing details
        """
        # Track initial response count
        initial_responses = len(daemon.get_all_responses())

        # Step 1: Send wait phrase
        await daemon.simulate_incoming_message(wait_phrase)

        # Step 2: Try to get response with short timeout (should fail/timeout)
        response_before_resume = await daemon.wait_for_response(
            timeout=self.immediate_response_timeout
        )
        agent_responded_immediately = response_before_resume is not None

        # Step 3: Wait the minimum duration
        wait_start = datetime.now(timezone.utc)
        await asyncio.sleep(self.minimum_wait_duration)
        wait_duration = (datetime.now(timezone.utc) - wait_start).total_seconds()

        # Step 4: Send resume phrase
        await daemon.simulate_incoming_message(resume_phrase)

        # Step 5: Wait for agent response (should succeed now)
        response_after_resume = await daemon.wait_for_response(timeout=60.0)
        agent_responded_after_resume = response_after_resume is not None

        # Verification: Agent should NOT respond immediately, but SHOULD after resume
        passed = (
            not agent_responded_immediately
            and agent_responded_after_resume
        )

        error_message = None
        if not passed:
            issues = []
            if agent_responded_immediately:
                issues.append("Agent responded immediately instead of waiting")
            if not agent_responded_after_resume:
                issues.append("Agent did not respond after resume signal")
            error_message = "; ".join(issues)

        return WaitHandlingVerificationResult(
            passed=passed,
            wait_phrase_sent=wait_phrase,
            agent_responded_immediately=agent_responded_immediately,
            wait_duration_seconds=wait_duration,
            resume_phrase_sent=resume_phrase,
            agent_responded_after_resume=agent_responded_after_resume,
            error_message=error_message,
        )

    def verify_from_turns(
        self,
        turns: list["ConversationTurn"],
        wait_phrase: str,
        resume_phrase: str,
    ) -> WaitHandlingVerificationResult:
        """
        Verify wait handling from pre-recorded conversation turns.

        This is a simplified verification based on turn sequence,
        without real-time timing validation.

        Args:
            turns: List of conversation turns
            wait_phrase: The wait request message
            resume_phrase: The resume message

        Returns:
            WaitHandlingVerificationResult
        """
        # Find wait phrase turn
        wait_turn_idx = None
        resume_turn_idx = None

        for idx, turn in enumerate(turns):
            if turn.speaker == "persona":
                if wait_phrase in turn.message and wait_turn_idx is None:
                    wait_turn_idx = idx
                elif resume_phrase in turn.message and wait_turn_idx is not None:
                    resume_turn_idx = idx

        if wait_turn_idx is None or resume_turn_idx is None:
            return WaitHandlingVerificationResult(
                passed=False,
                wait_phrase_sent=wait_phrase,
                agent_responded_immediately=False,
                wait_duration_seconds=0.0,
                resume_phrase_sent=resume_phrase,
                agent_responded_after_resume=False,
                error_message="Could not find wait/resume phrases in turns",
            )

        # Check for agent response between wait and resume
        agent_response_between = False
        for turn in turns[wait_turn_idx + 1:resume_turn_idx]:
            if turn.speaker == "agent":
                agent_response_between = True
                break

        # Check for agent response after resume
        agent_response_after = False
        for turn in turns[resume_turn_idx + 1:]:
            if turn.speaker == "agent":
                agent_response_after = True
                break

        passed = not agent_response_between and agent_response_after

        # Calculate approximate wait duration from timestamps
        wait_time = turns[wait_turn_idx].timestamp
        resume_time = turns[resume_turn_idx].timestamp
        wait_duration = (resume_time - wait_time).total_seconds()

        return WaitHandlingVerificationResult(
            passed=passed,
            wait_phrase_sent=wait_phrase,
            agent_responded_immediately=agent_response_between,
            wait_duration_seconds=wait_duration,
            resume_phrase_sent=resume_phrase,
            agent_responded_after_resume=agent_response_after,
            error_message=None if passed else "Agent responded during wait period",
        )


# =============================================================================
# ZOOM SCHEDULING VERIFIER
# Verifies: Email collected -> Slots shown -> Meeting booked
# =============================================================================

class ZoomSchedulingVerificationResult(BaseModel):
    """Result of Zoom scheduling behavior verification."""
    passed: bool
    email_collected: bool
    email_value: Optional[str] = None
    slots_shown: bool
    meeting_booked: bool
    outcome: Optional[str] = None  # ConversationOutcome value
    confirmation_message: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        """Human-readable summary of the result."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Zoom Scheduling Test: {status}\n"
            f"  Email collected: {'Yes' if self.email_collected else 'No'} "
            f"({self.email_value or 'N/A'})\n"
            f"  Time slots shown: {'Yes' if self.slots_shown else 'No'}\n"
            f"  Meeting booked: {'Yes' if self.meeting_booked else 'No'}\n"
            f"  Outcome: {self.outcome or 'N/A'}"
        )


class ZoomSchedulingVerifier:
    """
    Verifies Zoom scheduling behavior.

    Checks that the agent properly:
    1. Collects client email
    2. Shows available time slots
    3. Books a meeting with confirmation
    """

    # Patterns for detecting scheduling-related content
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    SLOT_INDICATORS = [
        "слот", "slot", "время", "time", "доступ", "available",
        "утром", "вечером", "morning", "afternoon", "вторник",
        "среда", "четверг", "пятница", "monday", "tuesday",
    ]
    BOOKING_INDICATORS = [
        "забронирован", "booked", "scheduled", "подтвержд",
        "confirmed", "отправлен", "sent", "invite", "приглашен",
        "zoom", "встреча", "meeting",
    ]

    def __init__(self, expected_email: Optional[str] = None):
        """
        Initialize the verifier.

        Args:
            expected_email: Email address expected to be collected (for validation)
        """
        self.expected_email = expected_email

    def verify(
        self,
        turns: list["ConversationTurn"],
        result: Optional["ConversationResult"] = None,
    ) -> ZoomSchedulingVerificationResult:
        """
        Verify Zoom scheduling from conversation turns.

        Args:
            turns: List of conversation turns
            result: Optional ConversationResult for outcome checking

        Returns:
            ZoomSchedulingVerificationResult with pass/fail and details
        """
        email_collected = False
        email_value = None
        slots_shown = False
        meeting_booked = False
        confirmation_message = None

        # Scan all turns for scheduling indicators
        all_text = ""
        for turn in turns:
            all_text += f" {turn.message.lower()}"

            # Check for email in client messages
            if turn.speaker == "persona":
                emails = self.EMAIL_PATTERN.findall(turn.message)
                if emails:
                    email_collected = True
                    email_value = emails[0]

            # Check agent messages for slots and booking confirmation
            if turn.speaker == "agent":
                msg_lower = turn.message.lower()

                # Check for time slot display
                slot_match = any(ind in msg_lower for ind in self.SLOT_INDICATORS)
                if slot_match:
                    slots_shown = True

                # Check for booking confirmation
                booking_match = any(ind in msg_lower for ind in self.BOOKING_INDICATORS)
                if booking_match:
                    meeting_booked = True
                    confirmation_message = turn.message

        # Determine outcome
        outcome = None
        if result is not None:
            outcome = result.outcome.value if hasattr(result.outcome, "value") else str(result.outcome)
        elif meeting_booked:
            outcome = "zoom_scheduled"

        # Validate email if expected
        if self.expected_email and email_value:
            if email_value.lower() != self.expected_email.lower():
                email_collected = False  # Wrong email doesn't count

        # Overall pass: email + slots + booking + correct outcome
        passed = (
            email_collected
            and slots_shown
            and meeting_booked
            and (outcome == "zoom_scheduled" if outcome else meeting_booked)
        )

        error_message = None
        if not passed:
            issues = []
            if not email_collected:
                issues.append("Email not collected")
            if not slots_shown:
                issues.append("Time slots not shown")
            if not meeting_booked:
                issues.append("Meeting not booked")
            if outcome and outcome != "zoom_scheduled":
                issues.append(f"Wrong outcome: {outcome}")
            error_message = "; ".join(issues)

        return ZoomSchedulingVerificationResult(
            passed=passed,
            email_collected=email_collected,
            email_value=email_value,
            slots_shown=slots_shown,
            meeting_booked=meeting_booked,
            outcome=outcome,
            confirmation_message=confirmation_message,
            error_message=error_message,
        )

    def verify_from_daemon(
        self,
        daemon: "MockTelegramDaemon",
        turns: list["ConversationTurn"],
    ) -> ZoomSchedulingVerificationResult:
        """
        Verify using daemon state in addition to turns.

        Uses daemon.prospect.status for authoritative outcome.

        Args:
            daemon: MockTelegramDaemon with prospect state
            turns: List of conversation turns

        Returns:
            ZoomSchedulingVerificationResult
        """
        # First do basic verification from turns
        base_result = self.verify(turns)

        # Override outcome from daemon prospect status
        if daemon.prospect:
            status = daemon.prospect.status
            if hasattr(status, "value"):
                outcome = status.value
            else:
                outcome = str(status)

            # Update passed based on authoritative status
            meeting_booked = outcome == "zoom_scheduled"
            passed = (
                base_result.email_collected
                and base_result.slots_shown
                and meeting_booked
            )

            return ZoomSchedulingVerificationResult(
                passed=passed,
                email_collected=base_result.email_collected,
                email_value=base_result.email_value,
                slots_shown=base_result.slots_shown,
                meeting_booked=meeting_booked,
                outcome=outcome,
                confirmation_message=base_result.confirmation_message,
                error_message=base_result.error_message if not passed else None,
            )

        return base_result
