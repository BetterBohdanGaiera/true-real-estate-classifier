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
Mock Telegram Daemon for Production Simulation Testing.

This module provides a MockTelegramDaemon that replicates the REAL production behavior
but without actual Telegram network calls. It's designed for stress testing with:

- REAL MessageBuffer debouncing (actual waiting for message batches)
- REAL TelegramAgent response generation
- REAL follow-up scheduling (writes to actual database)
- REAL timing delays (reading, typing simulation)
- MOCK Telegram transport (captures messages instead of sending)

The only thing mocked is the network layer - all business logic runs as in production.

Usage:
    >>> daemon = MockTelegramDaemon()
    >>> await daemon.initialize()
    >>>
    >>> # Simulate incoming messages
    >>> await daemon.simulate_incoming_message("Hello!")
    >>> await asyncio.sleep(0.5)  # Rapid second message
    >>> await daemon.simulate_incoming_message("I have questions")
    >>>
    >>> # Wait for batch processing (real debounce timing)
    >>> await daemon.wait_for_response(timeout=30.0)
    >>> response = daemon.get_last_agent_response()
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable

from pydantic import BaseModel, Field
from rich.console import Console

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent
TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram/scripts"
SCHEDULING_SCRIPTS = SKILLS_BASE / "scheduling/scripts"
DATABASE_SCRIPTS = SKILLS_BASE / "database/scripts"
ADW_MODULES = PROJECT_ROOT / "adws"

# Add paths for module imports
for path in [TELEGRAM_SCRIPTS, SCHEDULING_SCRIPTS, DATABASE_SCRIPTS, ADW_MODULES]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

# Import from telegram skill scripts (actual module location)
from telegram_agent import TelegramAgent
from knowledge_loader import KnowledgeLoader
from prospect_manager import ProspectManager
from models import AgentConfig, ProspectStatus, ScheduledActionType, Prospect
from message_buffer import MessageBuffer, BufferedMessage
from sales_calendar import SalesCalendar
from scheduling_tool import SchedulingTool
from scheduler_service import SchedulerService
from scheduled_action_manager import (
    create_scheduled_action,
    cancel_pending_for_prospect,
    get_pending_actions,
    close_pool,
)

# Import from database skill
from init import init_database

console = Console()

# Configuration paths - in telegram skill config directory
CONFIG_DIR = SKILLS_BASE / "telegram" / "config"
PROSPECTS_FILE = CONFIG_DIR / "prospects.json"
AGENT_CONFIG_FILE = CONFIG_DIR / "agent_config.json"
TONE_OF_VOICE_DIR = SKILLS_BASE / "tone-of-voice"
HOW_TO_COMMUNICATE_DIR = SKILLS_BASE / "how-to-communicate"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base_final"
SALES_CALENDAR_CONFIG = CONFIG_DIR / "sales_slots.json"


class CapturedMessage(BaseModel):
    """A message captured from the mock daemon (would have been sent to Telegram)."""
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: Optional[str] = None  # Agent action type (reply, schedule, etc.)
    message_id: int = Field(default_factory=lambda: random.randint(100000, 999999))


class MockTelegramService:
    """
    Mock TelegramService that captures messages instead of sending to Telegram.

    Provides the same interface as TelegramService but stores messages
    in memory for test verification.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.captured_messages: list[CapturedMessage] = []
        self._message_id_counter = 100000
        self._response_event = asyncio.Event()

    async def send_message(
        self,
        telegram_id: int | str,
        text: str,
        incoming_message: str = "",
        reply_to: Optional[int] = None
    ) -> dict:
        """Capture message instead of sending to Telegram."""

        # Simulate typing delay (REAL production behavior)
        if self.config.typing_simulation:
            typing_duration = min(len(text) / 20, 5.0)  # ~20 chars/sec, max 5s
            typing_duration = max(1.0, typing_duration)
            await asyncio.sleep(typing_duration)

        # Simulate response delay based on message length
        text_length = len(text)
        if text_length < 50:
            delay_range = self.config.delay_short
        elif text_length <= 200:
            delay_range = self.config.delay_medium
        else:
            delay_range = self.config.delay_long

        delay = random.uniform(*delay_range)
        await asyncio.sleep(delay)

        # Capture the message
        self._message_id_counter += 1
        captured = CapturedMessage(
            text=text,
            message_id=self._message_id_counter,
        )
        self.captured_messages.append(captured)

        # Signal that a response is available
        self._response_event.set()

        return {
            "sent": True,
            "chat": str(telegram_id),
            "message_id": self._message_id_counter,
            "timestamp": datetime.now().isoformat()
        }

    def get_last_message(self) -> Optional[CapturedMessage]:
        """Get the last captured message."""
        return self.captured_messages[-1] if self.captured_messages else None

    def get_all_messages(self) -> list[CapturedMessage]:
        """Get all captured messages."""
        return self.captured_messages.copy()

    def clear_messages(self) -> None:
        """Clear all captured messages."""
        self.captured_messages.clear()
        self._response_event.clear()

    async def wait_for_response(self, timeout: float = 60.0) -> bool:
        """Wait for the next response to be captured."""
        self._response_event.clear()
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


class MockTelegramDaemon:
    """
    Production-like daemon for testing without real Telegram.

    This class replicates the TelegramDaemon behavior but:
    - Uses MockTelegramService instead of real Telegram
    - Provides methods to simulate incoming messages
    - Keeps all other production logic intact (batching, scheduling, timing)

    Attributes:
        mock_service: MockTelegramService capturing outgoing messages
        message_buffer: REAL MessageBuffer with production debouncing
        agent: REAL TelegramAgent generating responses
        scheduler_service: REAL SchedulerService for follow-ups
        prospect: Test prospect being used for simulation
    """

    def __init__(
        self,
        prospect_telegram_id: str = "@mock_test_prospect",
        prospect_name: str = "Mock Test Client",
        prospect_context: str = "Interested in Bali real estate (test client)",
        verbose: bool = False,
    ):
        """
        Initialize mock daemon.

        Args:
            prospect_telegram_id: Telegram ID for test prospect
            prospect_name: Name for test prospect
            prospect_context: Context/description for test prospect
            verbose: Print detailed logs
        """
        self.prospect_telegram_id = prospect_telegram_id
        self.prospect_name = prospect_name
        self.prospect_context = prospect_context
        self.verbose = verbose

        # Will be initialized in initialize()
        self.mock_service: Optional[MockTelegramService] = None
        self.agent: Optional[TelegramAgent] = None
        self.config: Optional[AgentConfig] = None
        self.prospect_manager: Optional[ProspectManager] = None
        self.message_buffer: Optional[MessageBuffer] = None
        self.sales_calendar: Optional[SalesCalendar] = None
        self.scheduling_tool: Optional[SchedulingTool] = None
        self.scheduler_service: Optional[SchedulerService] = None

        # Test prospect
        self.prospect: Optional[Prospect] = None
        self._mock_prospect_id = random.randint(1000000000, 9999999999)

        # Stats
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "batches_processed": 0,
            "scheduled_followups": 0,
        }

        # Internal state
        self._initialized = False
        self._message_counter = 0

    async def initialize(self) -> None:
        """Initialize all components (mirrors TelegramDaemon.initialize)."""
        if self._initialized:
            return

        if self.verbose:
            console.print("[bold blue]Initializing Mock Telegram Daemon...[/bold blue]")

        # Initialize database (REAL - needed for scheduled actions)
        try:
            await init_database()
            if self.verbose:
                console.print(f"  [green]>[/green] Database initialized")
        except RuntimeError as e:
            console.print(f"[yellow]Database not available: {e}[/yellow]")

        # Load config (REAL)
        self.config = self._load_config()
        if self.verbose:
            console.print(f"  [green]>[/green] Config loaded")

        # Initialize mock Telegram service
        self.mock_service = MockTelegramService(self.config)
        if self.verbose:
            console.print(f"  [green]>[/green] Mock Telegram service ready")

        # Initialize ProspectManager with in-memory prospect
        self.prospect_manager = ProspectManager(PROSPECTS_FILE)
        if self.verbose:
            console.print(f"  [green]>[/green] Prospect manager ready")

        # Create test prospect
        self.prospect = Prospect(
            telegram_id=self._mock_prospect_id,
            name=self.prospect_name,
            context=self.prospect_context,
            status=ProspectStatus.NEW,
        )

        # Register prospect in manager (use the normalized key as string)
        normalized_key = str(self._mock_prospect_id)
        self.prospect_manager._prospects[normalized_key] = self.prospect
        if self.verbose:
            console.print(f"  [green]>[/green] Test prospect created: {self.prospect_name} (ID: {normalized_key})")

        # Initialize sales calendar (REAL)
        self.sales_calendar = SalesCalendar(SALES_CALENDAR_CONFIG)
        if self.verbose:
            console.print(f"  [green]>[/green] Sales calendar loaded")

        # Initialize scheduling tool (REAL)
        self.scheduling_tool = SchedulingTool(self.sales_calendar)
        if self.verbose:
            console.print(f"  [green]>[/green] Scheduling tool ready")

        # Initialize scheduler service (REAL - for follow-ups)
        self.scheduler_service = SchedulerService(
            execute_callback=self._execute_scheduled_action
        )
        if self.verbose:
            console.print(f"  [green]>[/green] Scheduler service ready")

        # Initialize TelegramAgent (REAL)
        self.agent = TelegramAgent(
            tone_of_voice_path=TONE_OF_VOICE_DIR,
            how_to_communicate_path=HOW_TO_COMMUNICATE_DIR,
            knowledge_base_path=KNOWLEDGE_BASE_DIR,
            config=self.config,
        )
        if self.verbose:
            console.print(f"  [green]>[/green] TelegramAgent ready")

        # Initialize MessageBuffer (REAL - with actual timeouts)
        self.message_buffer = MessageBuffer(
            timeout_range=self.config.batch_timeout_medium,
            flush_callback=self._process_message_batch,
            max_messages=self.config.batch_max_messages,
            max_wait_seconds=self.config.batch_max_wait_seconds
        )
        if self.verbose:
            console.print(f"  [green]>[/green] MessageBuffer ready (timeout: {self.config.batch_timeout_medium})")

        self._initialized = True
        if self.verbose:
            console.print("[bold green]Mock daemon initialized![/bold green]\n")

    def _load_config(self) -> AgentConfig:
        """Load agent configuration."""
        if AGENT_CONFIG_FILE.exists():
            with open(AGENT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return AgentConfig(**data)
        return AgentConfig()

    async def simulate_incoming_message(self, text: str) -> int:
        """
        Simulate an incoming message from the test prospect.

        This feeds the message into the REAL MessageBuffer which will
        debounce and batch messages according to production timing.

        Args:
            text: Message text from the "client"

        Returns:
            Message ID assigned to this message
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() first")

        self._message_counter += 1
        message_id = self._message_counter

        # Create buffered message
        buffered_msg = BufferedMessage(
            message_id=message_id,
            text=text,
            timestamp=datetime.now(),
        )

        # Record in prospect history (record_response is for prospect messages)
        self.prospect_manager.record_response(
            self._mock_prospect_id,
            message_id,
            text
        )

        self.stats["messages_received"] += 1

        if self.verbose:
            console.print(f"[blue][Client][/blue]: {text}")

        # Add to REAL MessageBuffer (this starts debounce timer)
        await self.message_buffer.add_message(
            str(self._mock_prospect_id),
            buffered_msg
        )

        return message_id

    async def _process_message_batch(
        self,
        prospect_id: str,
        messages: list[BufferedMessage]
    ) -> None:
        """
        Process a batch of messages (callback from MessageBuffer).

        This mirrors TelegramDaemon._process_message_batch with production logic.
        """
        if self.verbose:
            console.print(f"\n[cyan]Processing batch of {len(messages)} message(s)[/cyan]")

        self.stats["batches_processed"] += 1

        # Cancel pending follow-ups (REAL database operation)
        try:
            pending_actions = await get_pending_actions(prospect_id)
            if pending_actions:
                cancelled = await cancel_pending_for_prospect(
                    prospect_id,
                    reason="client_responded"
                )
                if cancelled > 0 and self.verbose:
                    console.print(f"[dim]Cancelled {cancelled} pending follow-up(s)[/dim]")
        except Exception as e:
            if self.verbose:
                console.print(f"[yellow]Could not cancel actions: {e}[/yellow]")

        # Aggregate messages
        if len(messages) == 1:
            combined_text = messages[0].text
        else:
            lines = []
            for msg in messages:
                time_str = msg.timestamp.strftime("%H:%M")
                lines.append(f"[{time_str}] {msg.text}")
            combined_text = "\n".join(lines)

        # Calculate reading delay (REAL timing)
        total_length = sum(len(m.text) for m in messages)
        if total_length < 50:
            delay_range = self.config.reading_delay_short
        elif total_length <= 200:
            delay_range = self.config.reading_delay_medium
        else:
            delay_range = self.config.reading_delay_long

        reading_delay = random.uniform(*delay_range)
        if self.verbose:
            console.print(f"[dim]Reading delay: {reading_delay:.1f}s for {total_length} chars[/dim]")
        await asyncio.sleep(reading_delay)

        # Get conversation context
        context = self.prospect_manager.get_conversation_context(self._mock_prospect_id)

        # Generate response (REAL TelegramAgent)
        try:
            action = await self.agent.generate_response(
                self.prospect,
                combined_text,
                context
            )

            if self.verbose:
                console.print(f"[dim]Agent decision: {action.action} - {action.reason}[/dim]")

            # Handle actions (mirrors production logic)
            await self._handle_agent_action(action, context)

        except Exception as e:
            console.print(f"[red]Agent error: {e}[/red]")
            import traceback
            traceback.print_exc()

    async def _handle_agent_action(self, action, context: str) -> None:
        """Handle agent action (mirrors TelegramDaemon logic)."""

        # Handle schedule_followup action (REAL database write)
        if action.action == "schedule_followup" and action.scheduling_data:
            try:
                follow_up_time_str = action.scheduling_data.get("follow_up_time")
                scheduled_for = datetime.fromisoformat(follow_up_time_str)

                # Create scheduled action in database (REAL)
                scheduled_action = await create_scheduled_action(
                    prospect_id=str(self._mock_prospect_id),
                    action_type=ScheduledActionType.FOLLOW_UP,
                    scheduled_for=scheduled_for,
                    payload={
                        "follow_up_intent": action.scheduling_data.get("follow_up_intent"),
                        "reason": action.scheduling_data.get("reason"),
                        "original_context_snapshot": context[:1000]
                    }
                )

                # Schedule with service (REAL)
                await self.scheduler_service.schedule_action(scheduled_action)

                self.stats["scheduled_followups"] += 1

                if self.verbose:
                    console.print(f"[cyan]Scheduled follow-up at {scheduled_for.strftime('%Y-%m-%d %H:%M')}[/cyan]")

                # Send confirmation
                confirmation = action.message or f"OK, I'll write later!"
                await self._send_response(confirmation, action.action)

            except Exception as e:
                console.print(f"[red]Failed to schedule follow-up: {e}[/red]")

        # Handle check_availability
        elif action.action == "check_availability":
            availability_text = self.scheduling_tool.get_available_times(days=7)
            await self._send_response(availability_text, action.action)

        # Handle schedule
        elif action.action == "schedule" and action.scheduling_data:
            slot_id = action.scheduling_data.get("slot_id")
            client_email = action.scheduling_data.get("email", "")

            if not client_email:
                error_msg = "To schedule a meeting I need your email. What address should I send the invite to?"
                await self._send_response(error_msg, action.action)
            else:
                # Mock booking success
                confirm_msg = action.message or f"Great! Meeting scheduled. Invite sent to {client_email}"
                await self._send_response(confirm_msg, action.action)
                self.prospect.status = ProspectStatus.ZOOM_SCHEDULED

        # Handle escalate
        elif action.action == "escalate":
            if action.message:
                await self._send_response(action.message, action.action)

        # Handle wait
        elif action.action == "wait":
            if self.verbose:
                console.print(f"[dim]Agent decided to wait: {action.reason}[/dim]")

        # Handle reply
        elif action.action == "reply" and action.message:
            await self._send_response(action.message, action.action)

    async def _send_response(self, text: str, action: str = "reply") -> None:
        """Send response via mock service."""
        result = await self.mock_service.send_message(
            self._mock_prospect_id,
            text
        )

        if result.get("sent"):
            self.stats["messages_sent"] += 1
            self.prospect_manager.record_agent_message(
                self._mock_prospect_id,
                result["message_id"],
                text
            )

            if self.verbose:
                console.print(f"[green][Agent][/green]: {text}\n")

    async def _execute_scheduled_action(self, action) -> None:
        """Execute a scheduled action (follow-up callback)."""
        if self.verbose:
            console.print(f"[cyan]Executing scheduled follow-up...[/cyan]")

        # Generate follow-up message
        context = self.prospect_manager.get_conversation_context(self._mock_prospect_id)

        try:
            response = await self.agent.generate_response(
                self.prospect,
                "[FOLLOW-UP: This is an automatic follow-up from previous conversation]",
                context
            )

            if response.message:
                await self._send_response(response.message, "follow_up")
        except Exception as e:
            console.print(f"[red]Follow-up execution failed: {e}[/red]")

    async def wait_for_response(self, timeout: float = 60.0) -> Optional[str]:
        """
        Wait for the agent to respond.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Agent's response text, or None if timeout
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() first")

        initial_count = len(self.mock_service.captured_messages)

        success = await self.mock_service.wait_for_response(timeout=timeout)

        if success and len(self.mock_service.captured_messages) > initial_count:
            return self.mock_service.captured_messages[-1].text

        return None

    async def wait_for_responses(
        self,
        expected_count: int = 1,
        timeout: float = 60.0,
        collection_window: float = 10.0
    ) -> list[str]:
        """
        Wait for agent responses, collecting multiple if they arrive.

        The agent naturally decides when to send multiple messages
        (e.g., long answer split into parts, follow-up clarification).
        This is NOT pattern-driven - agent decides based on content.

        Args:
            expected_count: Hint for how many to expect (test orchestration)
            timeout: Max wait for first response in seconds
            collection_window: After first response, wait this long for more responses

        Returns:
            List of response strings (1 or more)

        Example:
            >>> responses = await daemon.wait_for_responses(expected_count=2, timeout=30.0)
            >>> print(f"Collected {len(responses)} responses")
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() first")

        responses = []

        # Wait for first response with full timeout
        first_response = await self.wait_for_response(timeout=timeout)
        if first_response is None:
            return []  # No response within timeout

        responses.append(first_response)

        # Collect additional responses within collection window
        start_collect = datetime.now()
        while len(responses) < expected_count:
            elapsed = (datetime.now() - start_collect).total_seconds()
            remaining = collection_window - elapsed

            if remaining <= 0:
                break  # Collection window expired

            # Try to get another response with remaining time
            additional = await self.wait_for_response(timeout=remaining)
            if additional is None:
                break  # No more responses

            responses.append(additional)

        return responses

    def get_last_response(self) -> Optional[CapturedMessage]:
        """Get the last agent response."""
        return self.mock_service.get_last_message() if self.mock_service else None

    def get_all_responses(self) -> list[CapturedMessage]:
        """Get all agent responses."""
        return self.mock_service.get_all_messages() if self.mock_service else []

    def get_conversation_history(self) -> list[dict]:
        """Get full conversation history (both sides)."""
        if not self.prospect_manager:
            return []
        return self.prospect_manager._history.get(self._mock_prospect_id, [])

    async def reset(self) -> None:
        """Reset the daemon state for a new test."""
        if self.mock_service:
            self.mock_service.clear_messages()

        self._message_counter = 0
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "batches_processed": 0,
            "scheduled_followups": 0,
        }

        # Reset prospect
        if self.prospect:
            self.prospect.status = ProspectStatus.NEW
            self.prospect.message_count = 0
            # Clear conversation history
            self.prospect.conversation_history = []

        # Cancel pending actions
        try:
            await cancel_pending_for_prospect(
                str(self._mock_prospect_id),
                reason="test_reset"
            )
        except Exception:
            pass

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.scheduler_service:
            # Stop scheduler
            pass

        try:
            await close_pool()
        except Exception:
            pass


# =============================================================================
# MODULE SELF-TEST
# =============================================================================

if __name__ == "__main__":
    async def test_mock_daemon():
        """Quick test of the mock daemon."""
        console.print("=" * 60)
        console.print("Mock Telegram Daemon - Self-Test")
        console.print("=" * 60)

        daemon = MockTelegramDaemon(verbose=True)

        try:
            await daemon.initialize()

            # Test 1: Single message
            console.print("\n[bold]Test 1: Single message[/bold]")
            await daemon.simulate_incoming_message("Hello! I'm interested in Bali real estate")

            response = await daemon.wait_for_response(timeout=30.0)
            if response:
                console.print(f"[green]> Got response[/green]")
            else:
                console.print(f"[red]x No response[/red]")

            # Test 2: Rapid messages (test batching)
            console.print("\n[bold]Test 2: Rapid messages (batching test)[/bold]")
            await daemon.reset()

            await daemon.simulate_incoming_message("Question 1: What are the prices?")
            await asyncio.sleep(0.3)  # Rapid
            await daemon.simulate_incoming_message("Question 2: What's the yield?")
            await asyncio.sleep(0.3)  # Rapid
            await daemon.simulate_incoming_message("Question 3: Is there financing?")

            # Wait for batch to process (debounce + processing)
            response = await daemon.wait_for_response(timeout=30.0)
            if response:
                console.print(f"[green]> Got batched response[/green]")
                console.print(f"  Batches processed: {daemon.stats['batches_processed']}")
            else:
                console.print(f"[red]x No response[/red]")

            console.print("\n" + "=" * 60)
            console.print("Self-test complete!")
            console.print("=" * 60)

        finally:
            await daemon.cleanup()

    asyncio.run(test_mock_daemon())
