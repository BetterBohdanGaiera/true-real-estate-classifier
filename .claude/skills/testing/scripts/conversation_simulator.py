"""
Conversation Simulator for testing Telegram Agent with mock personas.

Uses Anthropic Agent SDK for persona simulation and orchestrates
multi-turn conversations to test agent behavior.
"""
import json
import random
import sys
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

# Add required paths for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "adws"))

# Add telegram skill scripts to path
SKILLS_BASE = Path(__file__).parent.parent.parent
TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram/scripts"
if str(TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_SCRIPTS))

from adw_modules.adw_agent_sdk import (
    quick_prompt,
    AdhocPrompt,
    ModelName,
    SystemPromptConfig,
    SystemPromptMode,
)

from models import Prospect, AgentAction, ProspectStatus
from telegram_agent import TelegramAgent


# =============================================================================
# Data Models
# =============================================================================

class PersonaDefinition(BaseModel):
    """Definition of a test persona for conversation simulation."""
    name: str
    description: str
    difficulty: Literal["easy", "medium", "hard", "expert"]
    traits: list[str]
    objections: list[str]
    goal: str  # Expected outcome type
    language: Literal["ru", "en"] = "ru"
    initial_message: Optional[str] = None  # First message from persona (if they initiate)
    multi_message_probability: float = 0.3  # Probability of sending multiple messages (0.0-1.0)
    max_messages_per_turn: int = 5  # Maximum messages when sending burst (up to 5)


class ConversationTurn(BaseModel):
    """Single turn in a conversation."""
    turn_number: int
    speaker: Literal["agent", "persona"]
    message: str
    action: Optional[str] = None  # AgentAction type if agent turn
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationOutcome(str, Enum):
    """Possible outcomes of a conversation test."""
    ZOOM_SCHEDULED = "zoom_scheduled"  # Successfully scheduled meeting with email
    FOLLOW_UP_PROPOSED = "follow_up_proposed"  # Agent proposed to follow up later
    CLIENT_REFUSED = "client_refused"  # Clear "no" from client
    ESCALATED = "escalated"  # Handed off to human
    INCONCLUSIVE = "inconclusive"  # No clear outcome after max turns


class ConversationScenario(BaseModel):
    """A complete test scenario to run."""
    name: str
    persona: PersonaDefinition
    initial_context: str  # Context for creating the Prospect
    agent_initiates: bool = True  # Whether agent sends first message
    expected_outcome: Optional[ConversationOutcome] = None


class ConversationResult(BaseModel):
    """Complete result of a conversation test."""
    scenario_name: str
    persona: PersonaDefinition
    turns: list[ConversationTurn]
    outcome: ConversationOutcome
    total_turns: int
    duration_seconds: float
    agent_actions_used: dict[str, int]
    email_collected: bool
    escalation_triggered: bool
    token_usage: Optional[dict] = None


class CalendarTestMetrics(BaseModel):
    """
    Metrics specific to calendar integration testing.

    Tracks the results of calendar event creation, timezone conversion,
    and other scheduling-related validations during E2E tests.

    Attributes:
        calendar_created: Whether a Google Calendar event was created.
        correct_timezone: Whether the event has correct timezone (Bali UTC+8).
        slot_match: Whether the event time matches the proposed slot.
        zoom_link_embedded: Whether Zoom link is in event description.
        attendee_added: Whether client email was added as attendee.
        conflict_detected: Whether a slot conflict was detected (None if not tested).
        client_timezone: Client timezone used for conversion testing.
        displayed_time_correct: Whether time shown to client was correct.
        event_id: Google Calendar event ID for reference.
        event_start: Event start datetime.
        event_end: Event end datetime.
    """
    calendar_created: bool = False
    correct_timezone: bool = False
    slot_match: bool = False
    zoom_link_embedded: bool = False
    attendee_added: bool = False
    conflict_detected: Optional[bool] = None  # None if not tested
    client_timezone: Optional[str] = None
    displayed_time_correct: bool = False
    event_id: Optional[str] = None
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None


# =============================================================================
# PersonaPlayer - Uses Agent SDK for Persona Roleplay
# =============================================================================

class PersonaPlayer:
    """
    Uses Anthropic Agent SDK to roleplay challenging client personas.

    Generates realistic, challenging responses based on persona traits
    using quick_prompt() with SystemPromptMode.OVERWRITE.
    """

    def __init__(self, persona: PersonaDefinition):
        self.persona = persona
        self._build_system_prompt()

    def _build_system_prompt(self) -> None:
        """Build the system prompt for persona roleplay."""
        lang_instruction = "Russian" if self.persona.language == "ru" else "English"

        self.system_prompt = f"""You are roleplaying as a potential real estate client interested in Bali property.

PERSONA: {self.persona.name}
{self.persona.description}

YOUR TRAITS:
{chr(10).join(f'- {trait}' for trait in self.persona.traits)}

OBJECTIONS YOU TYPICALLY RAISE:
{chr(10).join(f'- {obj}' for obj in self.persona.objections)}

CRITICAL RULES:
1. Stay COMPLETELY in character - never break the fourth wall
2. Be challenging but realistic - real clients are skeptical
3. Don't make it easy - push back on at least 3-4 messages before warming up
4. If the agent earns your trust with GOOD answers, you MAY agree to Zoom
5. If the agent is pushy, gives wrong info, or ignores your questions - become MORE resistant
6. You speak {lang_instruction} ONLY
7. Keep responses SHORT: 1-3 sentences, like real Telegram messages
8. React naturally - show emotions, hesitation, interest where appropriate
9. If you decide to agree to Zoom, naturally provide your email when asked
10. If you're NOT interested, politely but clearly refuse

PERSONA GOAL: {self.persona.goal}

Remember: You are testing the sales agent's skills. Be a realistic, challenging prospect."""

    async def generate_response(
        self,
        agent_message: str,
        conversation_history: list[ConversationTurn]
    ) -> str:
        """
        Generate persona response using Agent SDK quick_prompt.

        Args:
            agent_message: The last message from the agent
            conversation_history: Full conversation history

        Returns:
            Persona's response as a string
        """
        history_text = self._format_history(conversation_history)

        user_prompt = f"""Conversation so far:
{history_text}

The sales agent just said:
"{agent_message}"

Respond as your persona would. Remember to stay in character and be realistic."""

        result = await quick_prompt(AdhocPrompt(
            prompt=user_prompt,
            model=ModelName.SONNET,
            system_prompt=SystemPromptConfig(
                mode=SystemPromptMode.OVERWRITE,
                system_prompt=self.system_prompt,
            ),
        ))

        return result.strip()

    async def generate_multi_response(
        self,
        agent_message: str,
        conversation_history: list[ConversationTurn],
        force_multi: bool = False
    ) -> list[str]:
        """
        Generate one or more persona responses as separate messages.

        Simulates realistic user behavior where people often send multiple
        short messages instead of one long message (like rapid Telegram messages).

        The method uses `multi_message_probability` from the persona definition
        to randomly decide whether to generate multiple messages. When triggered,
        it instructs the LLM to return a JSON array of short messages.

        Args:
            agent_message: The last message from the agent
            conversation_history: Full conversation history
            force_multi: If True, always generate multiple messages (for testing).
                         Bypasses the probability check.

        Returns:
            List of 1-5 message strings to be sent with pauses between them.
            Returns exactly 1 message if multi-message mode was not triggered.
            Returns up to `max_messages_per_turn` messages otherwise.

        Examples:
            # Normal usage (probabilistic)
            messages = await player.generate_multi_response(
                "Какой бюджет вас интересует?",
                history
            )
            # Could return: ["Ну примерно 200-300к"] (single)
            # Or: ["Хм", "Думаю около 250к", "Но могу немного больше"] (multi)

            # Forced multi-message (for testing)
            messages = await player.generate_multi_response(
                "Расскажите о себе",
                history,
                force_multi=True
            )
            # Always returns: ["Привет!", "Меня зовут Иван", "Интересуюсь инвестициями"]
        """
        # Check if we should generate multiple messages
        if not force_multi and random.random() >= self.persona.multi_message_probability:
            # Single message path - use existing generate_response
            single = await self.generate_response(agent_message, conversation_history)
            return [single]

        # Multi-message path
        history_text = self._format_history(conversation_history)

        # Determine how many messages to request (2 to max_messages_per_turn)
        # Cap at 5 as an absolute maximum for realistic behavior
        max_msgs = min(self.persona.max_messages_per_turn, 5)

        # Modify system prompt to request JSON array
        multi_system_prompt = self.system_prompt + f"""

IMPORTANT: For this response, split your reply into multiple short messages like rapid Telegram/WhatsApp messages.
Respond with a JSON array of {max_msgs} or fewer short messages.
Format: ["Message 1", "Message 2", "Message 3"]
Each message should be 1-3 sentences maximum, like real chat behavior.
People often send:
- A greeting or reaction first
- Then the main point
- Then additional thoughts or questions
Output ONLY the JSON array, no other text."""

        user_prompt = f"""Conversation so far:
{history_text}

The sales agent just said:
"{agent_message}"

Respond as your persona would, but split your response into multiple short messages (like real Telegram behavior).
Return a JSON array of strings. Output ONLY the JSON array."""

        result = await quick_prompt(AdhocPrompt(
            prompt=user_prompt,
            model=ModelName.SONNET,
            system_prompt=SystemPromptConfig(
                mode=SystemPromptMode.OVERWRITE,
                system_prompt=multi_system_prompt,
            ),
        ))

        # Parse JSON array with fallback
        try:
            # Try to extract JSON array from response (handle potential text around it)
            result_stripped = result.strip()

            # Find JSON array bounds if there's extra text
            start_idx = result_stripped.find('[')
            end_idx = result_stripped.rfind(']')

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = result_stripped[start_idx:end_idx + 1]
                messages = json.loads(json_str)

                if isinstance(messages, list) and all(isinstance(m, str) for m in messages):
                    # Filter out empty messages and cap at max_messages_per_turn
                    non_empty = [m.strip() for m in messages if m.strip()]
                    if non_empty:
                        return non_empty[:max_msgs]

        except (json.JSONDecodeError, TypeError, ValueError):
            # JSON parsing failed
            pass

        # Fallback to single message using standard generate_response
        single = await self.generate_response(agent_message, conversation_history)
        return [single]

    def _format_history(self, turns: list[ConversationTurn]) -> str:
        """Format conversation history for context."""
        if not turns:
            return "(Начало разговора / Start of conversation)"

        lines = []
        for turn in turns[-10:]:  # Last 10 messages for context
            speaker = "Agent" if turn.speaker == "agent" else "You (Client)"
            lines.append(f"{speaker}: {turn.message}")

        return "\n".join(lines)

    def check_refusal(self, message: str) -> bool:
        """Check if persona's message indicates clear refusal."""
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
        markers = refusal_markers_ru if self.persona.language == "ru" else refusal_markers_en

        return any(marker in lower_msg for marker in markers)

    def check_agreement(self, message: str) -> bool:
        """Check if persona's message indicates agreement to Zoom."""
        agreement_markers_ru = [
            "давайте созвонимся", "согласен на zoom", "хорошо, давайте",
            "готов созвониться", "записывайте", "подходит",
            "да, давайте", "можно в", "удобно в"
        ]
        agreement_markers_en = [
            "let's schedule", "okay let's", "sounds good",
            "i'm available", "book me", "let's do it",
            "yes, let's", "that works"
        ]

        lower_msg = message.lower()
        markers = agreement_markers_ru if self.persona.language == "ru" else agreement_markers_en

        return any(marker in lower_msg for marker in markers)


# =============================================================================
# ConversationSimulator - Orchestrates Multi-turn Conversations
# =============================================================================

class ConversationSimulator:
    """
    Orchestrates multi-turn conversation tests between personas and the TelegramAgent.

    Manages conversation flow, tracks state, and determines outcomes.
    """

    def __init__(
        self,
        agent: TelegramAgent,
        max_turns: int = 20,
        timeout_seconds: float = 300,
    ):
        self.agent = agent
        self.max_turns = max_turns
        self.timeout = timeout_seconds

    async def run_scenario(
        self,
        scenario: ConversationScenario,
        verbose: bool = False
    ) -> ConversationResult:
        """
        Run a complete conversation scenario.

        Args:
            scenario: The scenario to run
            verbose: Whether to print conversation in real-time

        Returns:
            ConversationResult with full conversation and outcome
        """
        start_time = datetime.now()
        turns: list[ConversationTurn] = []
        persona_player = PersonaPlayer(scenario.persona)
        actions_used: dict[str, int] = {}
        email_collected = False
        escalation_triggered = False
        turn_counter = 0

        # Create test prospect
        prospect = Prospect(
            telegram_id=f"@test_{scenario.persona.name.lower().replace(' ', '_').replace('/', '_')}",
            name=scenario.persona.name.split()[0],  # First name only
            context=scenario.initial_context,
            status=ProspectStatus.NEW,
        )

        if verbose:
            print(f"\n{'='*60}")
            print(f"SCENARIO: {scenario.name}")
            print(f"PERSONA: {scenario.persona.name} ({scenario.persona.difficulty})")
            print(f"{'='*60}\n")

        # Determine who starts
        if scenario.agent_initiates:
            # Agent sends first message
            turn_counter += 1
            initial_action = await self.agent.generate_initial_message(prospect)

            if initial_action.message:
                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="agent",
                    message=initial_action.message,
                    action=initial_action.action,
                ))
                actions_used[initial_action.action] = actions_used.get(initial_action.action, 0) + 1

                if verbose:
                    print(f"[Agent]: {initial_action.message}\n")
        else:
            # Persona sends first message
            turn_counter += 1
            first_msg = scenario.persona.initial_message or "Здравствуйте, интересуюсь недвижимостью на Бали"
            turns.append(ConversationTurn(
                turn_number=turn_counter,
                speaker="persona",
                message=first_msg,
            ))

            if verbose:
                print(f"[{scenario.persona.name}]: {first_msg}\n")

        # Main conversation loop
        outcome: Optional[ConversationOutcome] = None

        while turn_counter < self.max_turns * 2:  # *2 because each exchange is 2 turns
            # Check if we should terminate
            outcome = self._check_termination(turns, actions_used, email_collected, escalation_triggered)
            if outcome:
                break

            last_turn = turns[-1] if turns else None

            if last_turn and last_turn.speaker == "agent":
                # Persona's turn to respond
                turn_counter += 1
                persona_response = await persona_player.generate_response(
                    last_turn.message,
                    turns
                )

                turns.append(ConversationTurn(
                    turn_number=turn_counter,
                    speaker="persona",
                    message=persona_response,
                ))

                if verbose:
                    print(f"[{scenario.persona.name}]: {persona_response}\n")

                # Check for clear refusal
                if persona_player.check_refusal(persona_response):
                    outcome = ConversationOutcome.CLIENT_REFUSED
                    break

                # Update prospect with conversation context
                prospect.message_count += 1
                prospect.last_response = datetime.now()
                prospect.status = ProspectStatus.IN_CONVERSATION

            else:
                # Agent's turn to respond
                turn_counter += 1
                conversation_context = self._format_context(turns)

                # Get the last persona message
                last_persona_msg = ""
                for turn in reversed(turns):
                    if turn.speaker == "persona":
                        last_persona_msg = turn.message
                        break

                action = await self.agent.generate_response(
                    prospect,
                    last_persona_msg,
                    conversation_context=conversation_context,
                )

                # Track actions
                actions_used[action.action] = actions_used.get(action.action, 0) + 1

                if action.action == "escalate":
                    escalation_triggered = True
                    outcome = ConversationOutcome.ESCALATED
                    if action.message:
                        turns.append(ConversationTurn(
                            turn_number=turn_counter,
                            speaker="agent",
                            message=action.message,
                            action=action.action,
                        ))
                        if verbose:
                            print(f"[Agent - ESCALATE]: {action.message}\n")
                    break

                if action.action == "wait":
                    # Agent decided not to respond
                    if verbose:
                        print(f"[Agent]: (decided to wait - {action.reason})\n")
                    continue

                if action.action == "check_availability":
                    # Agent showing available slots
                    msg = action.message or "Вот доступные слоты для встречи..."
                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="agent",
                        message=msg,
                        action=action.action,
                    ))
                    if verbose:
                        print(f"[Agent - CHECK_AVAILABILITY]: {msg}\n")

                elif action.action == "schedule":
                    # Agent attempting to schedule
                    if action.scheduling_data and action.scheduling_data.get("email"):
                        email_collected = True
                        outcome = ConversationOutcome.ZOOM_SCHEDULED
                    msg = action.message or "Отлично, встреча запланирована!"
                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="agent",
                        message=msg,
                        action=action.action,
                    ))
                    if verbose:
                        print(f"[Agent - SCHEDULE]: {msg}\n")
                    if email_collected:
                        break

                elif action.message:
                    turns.append(ConversationTurn(
                        turn_number=turn_counter,
                        speaker="agent",
                        message=action.message,
                        action=action.action,
                    ))
                    if verbose:
                        print(f"[Agent]: {action.message}\n")

        # Determine final outcome if not already set
        if not outcome:
            outcome = self._classify_outcome(turns, actions_used, email_collected)

        duration = (datetime.now() - start_time).total_seconds()

        if verbose:
            print(f"\n{'='*60}")
            print(f"OUTCOME: {outcome.value}")
            print(f"TURNS: {len(turns)}")
            print(f"DURATION: {duration:.1f}s")
            print(f"{'='*60}\n")

        return ConversationResult(
            scenario_name=scenario.name,
            persona=scenario.persona,
            turns=turns,
            outcome=outcome,
            total_turns=len(turns),
            duration_seconds=duration,
            agent_actions_used=actions_used,
            email_collected=email_collected,
            escalation_triggered=escalation_triggered,
        )

    def _check_termination(
        self,
        turns: list[ConversationTurn],
        actions_used: dict[str, int],
        email_collected: bool,
        escalation_triggered: bool,
    ) -> Optional[ConversationOutcome]:
        """Check if conversation should terminate."""

        # Escalation already triggered
        if escalation_triggered:
            return ConversationOutcome.ESCALATED

        # Email collected and schedule action used
        if email_collected and actions_used.get("schedule", 0) > 0:
            return ConversationOutcome.ZOOM_SCHEDULED

        # Too many turns without progress
        if len(turns) >= self.max_turns:
            return ConversationOutcome.INCONCLUSIVE

        # Multiple follow-up attempts without response
        wait_count = actions_used.get("wait", 0)
        if wait_count >= 3:
            return ConversationOutcome.FOLLOW_UP_PROPOSED

        return None

    def _classify_outcome(
        self,
        turns: list[ConversationTurn],
        actions_used: dict[str, int],
        email_collected: bool,
    ) -> ConversationOutcome:
        """Classify the final outcome of the conversation."""

        if email_collected and actions_used.get("schedule", 0) > 0:
            return ConversationOutcome.ZOOM_SCHEDULED

        if actions_used.get("escalate", 0) > 0:
            return ConversationOutcome.ESCALATED

        # Check last few persona messages for refusal
        persona_messages = [t.message.lower() for t in turns if t.speaker == "persona"][-3:]
        refusal_markers = ["нет", "не интересно", "не нужно", "not interested", "no thanks"]

        for msg in persona_messages:
            if any(marker in msg for marker in refusal_markers):
                return ConversationOutcome.CLIENT_REFUSED

        # Check if agent proposed follow-up
        agent_messages = [t.message.lower() for t in turns if t.speaker == "agent"][-3:]
        follow_up_markers = ["напишу позже", "свяжусь", "follow up", "get back to you"]

        for msg in agent_messages:
            if any(marker in msg for marker in follow_up_markers):
                return ConversationOutcome.FOLLOW_UP_PROPOSED

        return ConversationOutcome.INCONCLUSIVE

    def _format_context(self, turns: list[ConversationTurn]) -> str:
        """Format conversation history for agent context."""
        if not turns:
            return ""

        lines = []
        for turn in turns[-15:]:  # Last 15 messages
            speaker = "Agent" if turn.speaker == "agent" else "Prospect"
            lines.append(f"{speaker}: {turn.message}")

        return "\n".join(lines)


# =============================================================================
# Test Entry Point
# =============================================================================

if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    async def test_simulator():
        """Quick test of the conversation simulator."""
        skills_base = Path(__file__).parent.parent.parent
        project_root = skills_base.parent.parent

        # Initialize agent
        agent = TelegramAgent(
            tone_of_voice_path=skills_base / "tone-of-voice",
            how_to_communicate_path=skills_base / "how-to-communicate",
            knowledge_base_path=project_root / "knowledge_base_final",
        )

        # Create a test scenario
        test_persona = PersonaDefinition(
            name="Тестовый Скептик",
            description="Скептичный инвестор, который сомневается во всем",
            difficulty="medium",
            traits=["скептичный", "задает много вопросов", "сравнивает с другими инвестициями"],
            objections=["А какая гарантия?", "Почему я должен вам верить?"],
            goal="После хороших ответов может согласиться на Zoom",
            language="ru",
        )

        scenario = ConversationScenario(
            name="Test Skeptic Scenario",
            persona=test_persona,
            initial_context="Увидел рекламу в Instagram, интересуется недвижимостью на Бали",
            agent_initiates=True,
        )

        # Run simulation
        simulator = ConversationSimulator(agent, max_turns=10)
        result = await simulator.run_scenario(scenario, verbose=True)

        print(f"\nFinal Result:")
        print(f"  Outcome: {result.outcome}")
        print(f"  Turns: {result.total_turns}")
        print(f"  Actions: {result.agent_actions_used}")
        print(f"  Email Collected: {result.email_collected}")

    asyncio.run(test_simulator())
