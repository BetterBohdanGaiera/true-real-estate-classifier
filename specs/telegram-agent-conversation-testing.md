# Plan: Telegram Agent Mock Conversation Testing System

## Task Description

Create an automated testing system for the Telegram communication agent that simulates challenging multi-turn conversations with different client personas. The system should run mock scenarios from the user perspective against the actual agent, track outcomes (Zoom meeting scheduled, followed-up properly, or clear rejection), and provide detailed quality assessments.

## Objective

Build a conversation simulation framework that:
1. Tests the Telegram agent with realistic, challenging user personas
2. Runs multi-turn conversations until a clear outcome is reached
3. Provides structured assessment of conversation quality (what worked, what didn't, areas for improvement)
4. Uses **Anthropic Agent SDK** (`adws/adw_modules/adw_agent_sdk.py`) for all Claude interactions (no mocking per CLAUDE.md)

## Problem Statement

Currently, the TelegramAgent has only basic inline tests in `__main__` blocks. There's no systematic way to:
- Test multi-turn conversations with realistic challenging scenarios
- Validate that the agent follows communication methodology (BANT, Zmeyka)
- Assess quality of responses against tone-of-voice guidelines
- Track success/failure rates across different persona types
- Identify patterns in what works and what doesn't

## Solution Approach

Create a `ConversationSimulator` class using the **Anthropic Agent SDK** that:
1. Orchestrates multi-turn conversations between mock personas and the TelegramAgent
2. Tracks conversation state and outcomes using SDK's session management
3. Uses Claude via `quick_prompt()` to evaluate conversation quality after completion
4. Generates detailed reports with actionable insights and token tracking

### Agent SDK Integration

The system will use the existing Agent SDK wrapper for all Claude interactions:

| Component | SDK Function | Model | Purpose |
|-----------|--------------|-------|---------|
| **PersonaPlayer** | `quick_prompt(AdhocPrompt)` | `ModelName.SONNET` | Roleplay challenging client personas |
| **ConversationEvaluator** | `quick_prompt(AdhocPrompt)` | `ModelName.SONNET` | Quality assessment |
| **Token Tracking** | `TokenUsage`, `UsageAccumulator` | N/A | Cost tracking |
| **TelegramAgent** (optional) | `query_to_completion(QueryInput)` | `ModelName.SONNET` | Migrate from direct Anthropic client |

Key SDK imports from `adws/adw_modules/adw_agent_sdk.py`:
```python
import sys
from pathlib import Path

# Add ADW modules to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "adws"))

from adw_modules.adw_agent_sdk import (
    quick_prompt,
    AdhocPrompt,
    ModelName,
    SystemPromptConfig,
    SystemPromptMode,
    TokenUsage,
    UsageAccumulator,
)
```

## Relevant Files

### Existing Files to Use

- `adws/adw_modules/adw_agent_sdk.py` (lines 1-1655)
  - **PRIMARY SDK**: Typed Pydantic wrapper for Claude Agent SDK
  - Key functions: `quick_prompt()` (lines 1555-1632), `query_to_completion()` (lines 883-1177)
  - Key models: `AdhocPrompt`, `ModelName`, `SystemPromptConfig`, `SystemPromptMode`
  - Token tracking: `TokenUsage` (lines 186-250), `UsageAccumulator`

- `.claude/skills/telegram/scripts/telegram_agent.py` (lines 25-432)
  - Core TelegramAgent class with `generate_response()` and `generate_initial_message()` methods
  - Uses direct Anthropic client - can optionally migrate to SDK

- `.claude/skills/telegram/scripts/models.py` (lines 1-104)
  - Pydantic models: Prospect, ConversationMessage, AgentAction, ProspectStatus
  - Will extend with conversation simulation models

- `.claude/skills/how-to-communicate/references/client_personas.md`
  - Existing personas: Финансист, Житель Бали, Budget-Conscious
  - Base for creating challenging test scenarios

- `.claude/skills/how-to-communicate/references/скрипты_возражения.md`
  - Objection handling scripts
  - Source for creating realistic objections in scenarios

- `.claude/skills/tone-of-voice/SKILL.md`
  - 7 communication principles for quality assessment
  - Evaluation criteria for responses

### New Files to Create

| File | Purpose |
|------|---------|
| `.claude/skills/telegram/scripts/conversation_simulator.py` | Main ConversationSimulator + PersonaPlayer classes |
| `.claude/skills/telegram/scripts/test_scenarios.py` | 10 challenging persona scenarios |
| `.claude/skills/telegram/scripts/conversation_evaluator.py` | Quality assessment using Agent SDK |
| `.claude/skills/telegram/scripts/run_conversation_tests.py` | CLI runner with Rich output |

## Implementation Phases

### Phase 1: Foundation (Data Models & Infrastructure)

1. Create Pydantic models for conversation simulation
2. Build PersonaPlayer class using Agent SDK `quick_prompt()`
3. Create ConversationSimulator orchestration class

### Phase 2: Core Implementation (Scenarios & Simulation)

1. Define 10 challenging test scenarios based on existing personas
2. Implement multi-turn conversation loop with termination conditions
3. Add conversation state tracking and outcome classification

### Phase 3: Integration & Polish (Evaluation & Reporting)

1. Build ConversationEvaluator using Agent SDK `quick_prompt()`
2. Create detailed report generation
3. Build CLI runner with parallel execution
4. Add Rich console output for visual feedback

---

## Step by Step Tasks

### 1. Create Data Models for Conversation Simulation

Create `.claude/skills/telegram/scripts/conversation_simulator.py` with Pydantic models:

```python
from enum import Enum
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PersonaDefinition(BaseModel):
    """Definition of a test persona for conversation simulation."""
    name: str  # e.g., "Skeptical Financist"
    description: str  # Full personality description
    difficulty: Literal["easy", "medium", "hard", "expert"]
    traits: list[str]  # e.g., ["скептичный", "задает много вопросов"]
    objections: list[str]  # Typical objections they raise
    goal: str  # Expected outcome: "may_zoom", "will_refuse", "needs_escalation"
    language: Literal["ru", "en"] = "ru"
    initial_message: Optional[str] = None  # If persona initiates


class ConversationTurn(BaseModel):
    """Single turn in a conversation."""
    turn_number: int
    speaker: Literal["agent", "persona"]
    message: str
    action: Optional[str] = None  # AgentAction type if agent turn
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationOutcome(str, Enum):
    """Possible outcomes of a conversation test."""
    ZOOM_SCHEDULED = "zoom_scheduled"  # Successfully scheduled with email
    FOLLOW_UP_PROPOSED = "follow_up_proposed"  # Agent proposed follow-up
    CLIENT_REFUSED = "client_refused"  # Clear "no" from client
    ESCALATED = "escalated"  # Handed off to human
    INCONCLUSIVE = "inconclusive"  # No clear outcome after max turns


class ConversationScenario(BaseModel):
    """A complete test scenario to run."""
    name: str
    persona: PersonaDefinition
    initial_context: str  # Context for Prospect creation
    agent_initiates: bool = True  # Agent sends first message
    expected_outcome: Optional[ConversationOutcome] = None


class ConversationResult(BaseModel):
    """Complete result of a conversation test."""
    scenario_name: str
    persona: PersonaDefinition
    turns: list[ConversationTurn]
    outcome: ConversationOutcome
    total_turns: int
    duration_seconds: float
    agent_actions_used: dict[str, int]  # {"reply": 5, "check_availability": 1}
    email_collected: bool
    escalation_triggered: bool
    token_usage: Optional[dict] = None  # From SDK tracking
```

---

### 2. Implement PersonaPlayer Class with Agent SDK

PersonaPlayer uses `quick_prompt()` from the Agent SDK to roleplay personas:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "adws"))

from adw_modules.adw_agent_sdk import (
    quick_prompt,
    AdhocPrompt,
    ModelName,
    SystemPromptConfig,
    SystemPromptMode,
)


class PersonaPlayer:
    """
    Uses Anthropic Agent SDK to roleplay challenging client personas.

    Each persona has specific traits, objections, and behavioral patterns
    that test different aspects of the agent's communication skills.
    """

    def __init__(self, persona: PersonaDefinition):
        self.persona = persona
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt for persona roleplay."""
        lang = "Russian" if self.persona.language == "ru" else "English"

        return f"""You are roleplaying as a potential real estate client interested in Bali property.

PERSONA: {self.persona.name}
{self.persona.description}

YOUR TRAITS:
{chr(10).join(f'- {t}' for t in self.persona.traits)}

OBJECTIONS YOU TYPICALLY RAISE:
{chr(10).join(f'- {o}' for o in self.persona.objections)}

CRITICAL RULES:
1. Stay COMPLETELY in character - never break the fourth wall
2. Be challenging but realistic - real clients are skeptical
3. Don't make it easy - push back on at least 3-4 messages before warming up
4. If agent earns trust with GOOD answers, you MAY agree to Zoom
5. If agent is pushy, gives wrong info, or ignores questions - become MORE resistant
6. You speak {lang} ONLY
7. Keep responses SHORT: 1-3 sentences (like real Telegram messages)
8. React naturally - show emotions, hesitation, interest where appropriate
9. If you decide to agree to Zoom, provide email when asked
10. If NOT interested, politely but clearly refuse

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

Respond as your persona would. Remember:
- Stay in character
- Be realistic and challenging
- Keep response short (1-3 sentences)"""

        result = await quick_prompt(AdhocPrompt(
            prompt=user_prompt,
            model=ModelName.SONNET,
            system_prompt=SystemPromptConfig(
                mode=SystemPromptMode.OVERWRITE,
                system_prompt=self.system_prompt,
            ),
        ))

        return result.strip()

    def _format_history(self, turns: list[ConversationTurn]) -> str:
        """Format conversation history for context."""
        if not turns:
            return "(Начало разговора / Start of conversation)"

        lines = []
        for turn in turns[-10:]:  # Last 10 messages
            speaker = "Agent" if turn.speaker == "agent" else "You (Client)"
            lines.append(f"{speaker}: {turn.message}")

        return "\n".join(lines)

    def check_refusal(self, message: str) -> bool:
        """Check if message indicates clear refusal."""
        refusal_ru = ["нет, спасибо", "не интересно", "не нужно", "отстаньте"]
        refusal_en = ["not interested", "no thanks", "please stop"]
        markers = refusal_ru if self.persona.language == "ru" else refusal_en
        return any(m in message.lower() for m in markers)

    def check_agreement(self, message: str) -> bool:
        """Check if message indicates agreement to Zoom."""
        agree_ru = ["давайте созвонимся", "согласен", "хорошо, давайте", "записывайте"]
        agree_en = ["let's schedule", "sounds good", "i'm available"]
        markers = agree_ru if self.persona.language == "ru" else agree_en
        return any(m in message.lower() for m in markers)
```

---

### 3. Implement ConversationSimulator Class

Orchestrates multi-turn conversations:

```python
class ConversationSimulator:
    """
    Orchestrates multi-turn conversation tests between personas and agent.

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
            verbose: Print conversation in real-time

        Returns:
            ConversationResult with full conversation and outcome
        """
        start_time = datetime.now()
        turns: list[ConversationTurn] = []
        persona_player = PersonaPlayer(scenario.persona)
        actions_used: dict[str, int] = {}
        email_collected = False
        escalation_triggered = False

        # Create test prospect
        prospect = Prospect(
            telegram_id=f"@test_{scenario.name.lower().replace(' ', '_')}",
            name=scenario.persona.name.split()[0],
            context=scenario.initial_context,
            status=ProspectStatus.NEW,
        )

        if verbose:
            print(f"\n{'='*60}")
            print(f"SCENARIO: {scenario.name}")
            print(f"PERSONA: {scenario.persona.name} ({scenario.persona.difficulty})")
            print(f"{'='*60}\n")

        # Agent initiates or persona starts
        if scenario.agent_initiates:
            action = await self.agent.generate_initial_message(prospect)
            if action.message:
                turns.append(ConversationTurn(
                    turn_number=1, speaker="agent",
                    message=action.message, action=action.action
                ))
                actions_used[action.action] = 1
                if verbose:
                    print(f"[Agent]: {action.message}\n")
        else:
            first_msg = scenario.persona.initial_message or "Здравствуйте"
            turns.append(ConversationTurn(
                turn_number=1, speaker="persona", message=first_msg
            ))
            if verbose:
                print(f"[{scenario.persona.name}]: {first_msg}\n")

        # Main conversation loop
        outcome = None
        turn_num = len(turns)

        while turn_num < self.max_turns * 2:
            outcome = self._check_termination(turns, actions_used, email_collected, escalation_triggered)
            if outcome:
                break

            last_turn = turns[-1]

            if last_turn.speaker == "agent":
                # Persona responds
                turn_num += 1
                response = await persona_player.generate_response(last_turn.message, turns)
                turns.append(ConversationTurn(
                    turn_number=turn_num, speaker="persona", message=response
                ))
                if verbose:
                    print(f"[{scenario.persona.name}]: {response}\n")

                if persona_player.check_refusal(response):
                    outcome = ConversationOutcome.CLIENT_REFUSED
                    break
            else:
                # Agent responds
                turn_num += 1
                context = self._format_context(turns)
                last_persona_msg = next(
                    (t.message for t in reversed(turns) if t.speaker == "persona"), ""
                )

                action = await self.agent.generate_response(
                    prospect, last_persona_msg, conversation_context=context
                )
                actions_used[action.action] = actions_used.get(action.action, 0) + 1

                if action.action == "escalate":
                    escalation_triggered = True
                    outcome = ConversationOutcome.ESCALATED
                    if verbose:
                        print(f"[Agent - ESCALATE]: {action.message or action.reason}\n")
                    break

                if action.action == "schedule" and action.scheduling_data:
                    if action.scheduling_data.get("email"):
                        email_collected = True
                        outcome = ConversationOutcome.ZOOM_SCHEDULED

                if action.message:
                    turns.append(ConversationTurn(
                        turn_number=turn_num, speaker="agent",
                        message=action.message, action=action.action
                    ))
                    if verbose:
                        print(f"[Agent]: {action.message}\n")

                if outcome == ConversationOutcome.ZOOM_SCHEDULED:
                    break

        # Final outcome classification
        if not outcome:
            outcome = self._classify_outcome(turns, actions_used, email_collected)

        duration = (datetime.now() - start_time).total_seconds()

        if verbose:
            print(f"\n{'='*60}")
            print(f"OUTCOME: {outcome.value}")
            print(f"TURNS: {len(turns)} | DURATION: {duration:.1f}s")
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

    def _check_termination(self, turns, actions_used, email_collected, escalated) -> Optional[ConversationOutcome]:
        """Check if conversation should terminate."""
        if escalated:
            return ConversationOutcome.ESCALATED
        if email_collected and actions_used.get("schedule", 0) > 0:
            return ConversationOutcome.ZOOM_SCHEDULED
        if len(turns) >= self.max_turns:
            return ConversationOutcome.INCONCLUSIVE
        if actions_used.get("wait", 0) >= 3:
            return ConversationOutcome.FOLLOW_UP_PROPOSED
        return None

    def _classify_outcome(self, turns, actions_used, email_collected) -> ConversationOutcome:
        """Classify final outcome."""
        if email_collected:
            return ConversationOutcome.ZOOM_SCHEDULED
        if actions_used.get("escalate", 0) > 0:
            return ConversationOutcome.ESCALATED
        # Check for refusal in last messages
        for t in turns[-3:]:
            if t.speaker == "persona" and any(
                w in t.message.lower() for w in ["нет", "не интересно", "not interested"]
            ):
                return ConversationOutcome.CLIENT_REFUSED
        return ConversationOutcome.INCONCLUSIVE

    def _format_context(self, turns: list[ConversationTurn]) -> str:
        """Format history for agent context."""
        return "\n".join(
            f"{'Agent' if t.speaker == 'agent' else 'Prospect'}: {t.message}"
            for t in turns[-15:]
        )
```

---

### 4. Define Test Scenarios

Create `.claude/skills/telegram/scripts/test_scenarios.py` with 10 challenging scenarios:

```python
from conversation_simulator import PersonaDefinition, ConversationScenario, ConversationOutcome

SCENARIOS = [
    # ==========================================================================
    # SCENARIO 1: Skeptical Financist (HARD)
    # ==========================================================================
    ConversationScenario(
        name="Skeptical Financist",
        persona=PersonaDefinition(
            name="Алексей Финансист",
            description="""Профессиональный инвестор, работает с портфелями.
            Привык к точным цифрам, ROI, IRR. Не терпит "воды" и эмоций.
            Сравнивает все с альтернативными инвестициями (акции, крипта, облигации).""",
            difficulty="hard",
            traits=[
                "Требует конкретных цифр ROI до любого разговора",
                "Сравнивает с доходностью S&P500 и депозитов",
                "Скептичен к любым обещаниям без данных",
                "Задает вопросы про риски и хеджирование",
            ],
            objections=[
                "Какой IRR? Покажите финмодель",
                "12% годовых? S&P дает столько же с меньшим риском",
                "А если рынок упадет? Какие гарантии?",
                "Это просто маркетинговые цифры",
            ],
            goal="may_zoom_after_data",
            language="ru",
        ),
        initial_context="Увидел рекламу в Instagram, профессиональный инвестор",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 2: Catalog Requester (HARD)
    # ==========================================================================
    ConversationScenario(
        name="Catalog Requester",
        persona=PersonaDefinition(
            name="Марина Каталог",
            description="""Хочет только получить материалы и изучить самостоятельно.
            Категорически не хочет звонков и встреч.
            Тестирует настойчивость агента в работе с возражением "скиньте каталог".""",
            difficulty="hard",
            traits=[
                "Сразу просит скинуть каталог/материалы",
                "Отказывается от любых звонков",
                "Говорит 'я сама разберусь'",
                "Раздражается от настойчивости",
            ],
            objections=[
                "Просто скиньте каталог, я посмотрю",
                "Не хочу звонить, отправьте материалы",
                "Я сама приму решение когда изучу",
                "Почему нельзя просто получить информацию?",
            ],
            goal="may_zoom_after_4_exchanges",
            language="ru",
        ),
        initial_context="Оставила заявку на сайте, просит каталог",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 3: "After the War" (MEDIUM)
    # ==========================================================================
    ConversationScenario(
        name="After the War Deferred",
        persona=PersonaDefinition(
            name="Андрей Украина",
            description="""Украинец, интересуется инвестициями, но говорит что
            сейчас не время из-за ситуации. Эмоциональные и практические возражения.
            Может согласиться на образовательный формат.""",
            difficulty="medium",
            traits=[
                "Ссылается на войну и неопределенность",
                "Говорит что сейчас не до инвестиций",
                "Эмоционально реагирует на тему",
                "Интересуется, но откладывает",
            ],
            objections=[
                "Куплю после войны, сейчас не время",
                "Все деньги нужны здесь",
                "Как я могу думать об этом сейчас?",
                "Может быть потом, когда всё закончится",
            ],
            goal="may_agree_educational_zoom",
            language="ru",
        ),
        initial_context="Подписчик в Telegram, украинец",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 4: Leasehold Skeptic (HARD)
    # ==========================================================================
    ConversationScenario(
        name="Leasehold Skeptic",
        persona=PersonaDefinition(
            name="Игорь Юрист",
            description="""Юридически подкован, сильно сомневается в leasehold.
            Боится что земля не его, что законы изменятся.
            Нужны многочисленные правовые аргументы.""",
            difficulty="hard",
            traits=[
                "Категорически против leasehold",
                "Спрашивает про freehold (что запрещено!)",
                "Боится изменения законов",
                "Требует юридических гарантий",
            ],
            objections=[
                "Leasehold — это не собственность, это аренда",
                "А если законы изменятся? Всё отберут",
                "Почему нельзя купить freehold?",
                "Какие гарантии что через 30 лет продлят?",
            ],
            goal="may_zoom_after_legal_reassurance",
            language="ru",
        ),
        initial_context="Интересуется виллой, юридическое образование",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 5: Price Haggler (MEDIUM)
    # ==========================================================================
    ConversationScenario(
        name="Price Haggler",
        persona=PersonaDefinition(
            name="Сергей Скидка",
            description="""Сразу спрашивает о скидках и пытается торговаться.
            Говорит что видел дешевле. Тестирует объяснение комиссии.""",
            difficulty="medium",
            traits=[
                "Первый вопрос про скидку",
                "Сравнивает с дешевыми вариантами",
                "Торгуется на всё",
                "Просит скидку за счет комиссии",
            ],
            objections=[
                "Можно скидку?",
                "Видел на Airbnb дешевле в 2 раза",
                "А скидка за счет вашей комиссии?",
                "Дорого, у конкурентов дешевле",
            ],
            goal="may_zoom_after_value_explanation",
            language="ru",
        ),
        initial_context="Нашел через поиск, сравнивает цены",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 6: Bali Insider (EXPERT)
    # ==========================================================================
    ConversationScenario(
        name="Bali Insider",
        persona=PersonaDefinition(
            name="Дмитрий Бали",
            description="""Уже живет на Бали 3 года. Знает рынок изнутри,
            называет конкретные районы и застройщиков.
            Не терпит базовых объяснений.""",
            difficulty="expert",
            traits=[
                "Знает Чангу, Убуд, Семиньяк детально",
                "Называет конкретных застройщиков",
                "Раздражается от банальностей",
                "Спрашивает про специфику (Hak Pakai vs Leasehold)",
            ],
            objections=[
                "Я живу здесь, мне не нужно объяснять что такое Бали",
                "А что насчет проекта X от застройщика Y?",
                "Hak Pakai или Leasehold - в чем разница в вашем случае?",
                "Я знаю что ParQ overselling, а у вас?",
            ],
            goal="may_zoom_for_specific_legal_help",
            language="ru",
        ),
        initial_context="Живет на Бали, ищет инвестицию для себя",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 7: Phone Request Escalation (EASY - tests escalation)
    # ==========================================================================
    ConversationScenario(
        name="Phone Request Escalation",
        persona=PersonaDefinition(
            name="Николай Звонок",
            description="""Категорически хочет только телефонный звонок.
            Не Zoom, не переписка - только живой голос по телефону.
            Использует ключевые слова для эскалации.""",
            difficulty="easy",
            traits=[
                "Требует позвонить по телефону",
                "Не принимает Zoom как альтернативу",
                "Настаивает на срочности",
            ],
            objections=[
                "Позвоните мне срочно",
                "Я хочу только по телефону говорить",
                "Перезвоните мне сейчас",
                "Не хочу Zoom, только звонок",
            ],
            goal="should_escalate",
            language="ru",
        ),
        initial_context="Срочно хочет связаться по телефону",
        expected_outcome=ConversationOutcome.ESCALATED,
    ),

    # ==========================================================================
    # SCENARIO 8: Silent Treatment (HARD)
    # ==========================================================================
    ConversationScenario(
        name="Silent Treatment",
        persona=PersonaDefinition(
            name="Анна Молчун",
            description="""Отвечает односложно, без энтузиазма.
            Минимальные ответы, сложно вытянуть информацию.
            Тестирует follow-up стратегию агента.""",
            difficulty="hard",
            traits=[
                "Односложные ответы: да, нет, возможно",
                "Не задает вопросов",
                "Не проявляет инициативы",
                "Медленно отвечает",
            ],
            objections=[
                "Ок",
                "Возможно",
                "Посмотрим",
                "Не знаю",
            ],
            goal="hard_to_engage",
            language="ru",
        ),
        initial_context="Подписалась на канал, минимальная активность",
        expected_outcome=ConversationOutcome.FOLLOW_UP_PROPOSED,
    ),

    # ==========================================================================
    # SCENARIO 9: Rapid Fire Questions (HARD)
    # ==========================================================================
    ConversationScenario(
        name="Rapid Fire Questions",
        persona=PersonaDefinition(
            name="Виктор Вопросы",
            description="""Задает 3-4 вопроса в каждом сообщении.
            Нетерпелив, хочет всю информацию сразу.
            Тестирует способность агента обрабатывать объем.""",
            difficulty="hard",
            traits=[
                "3-4 вопроса в одном сообщении",
                "Нетерпеливый",
                "Хочет все ответы сразу",
                "Перескакивает с темы на тему",
            ],
            objections=[
                "Какая доходность? Какие налоги? Сколько стоит? Есть рассрочка?",
                "А гарантии какие? А если война? А управляющая компания?",
                "Почему Бали а не Дубай? Какой минимальный вход? Можно в долларах?",
            ],
            goal="may_zoom_if_questions_answered",
            language="ru",
        ),
        initial_context="Активный инвестор, много вопросов сразу",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # ==========================================================================
    # SCENARIO 10: English Speaker (MEDIUM)
    # ==========================================================================
    ConversationScenario(
        name="English Speaker",
        persona=PersonaDefinition(
            name="John Investor",
            description="""English-speaking professional investor from Singapore.
            Looking at Bali as portfolio diversification.
            Tests agent's English communication skills.""",
            difficulty="medium",
            traits=[
                "Professional, formal English",
                "Focuses on investment fundamentals",
                "Compares to other SEA markets",
                "Asks about tax implications for foreigners",
            ],
            objections=[
                "What's the actual ROI after all fees?",
                "How does this compare to Thai property market?",
                "What are the tax implications for non-residents?",
                "Is the ownership structure secure for foreigners?",
            ],
            goal="may_zoom_for_detailed_discussion",
            language="en",
        ),
        initial_context="Singapore-based investor, found via LinkedIn",
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),
]

def get_scenario_by_name(name: str) -> ConversationScenario:
    """Get scenario by name."""
    for s in SCENARIOS:
        if s.name.lower() == name.lower():
            return s
    raise ValueError(f"Scenario not found: {name}")

def get_scenarios_by_difficulty(difficulty: str) -> list[ConversationScenario]:
    """Get all scenarios of specified difficulty."""
    return [s for s in SCENARIOS if s.persona.difficulty == difficulty]
```

---

### 5. Build Conversation Evaluator with Agent SDK

Create `.claude/skills/telegram/scripts/conversation_evaluator.py`:

```python
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "adws"))

from adw_modules.adw_agent_sdk import (
    quick_prompt,
    AdhocPrompt,
    ModelName,
    SystemPromptConfig,
    SystemPromptMode,
)

from conversation_simulator import ConversationResult, ConversationTurn


class ConversationAssessment(BaseModel):
    """Quality assessment of a conversation."""
    overall_score: int  # 0-100
    what_went_well: list[str]  # 3-5 specific positives
    areas_for_improvement: list[str]  # 3-5 specific suggestions
    critical_issues: list[str]  # Serious problems (empty if none)

    # Detailed scores
    personalization_score: int  # 0-10: Used client name
    questions_score: int  # 0-10: Ended with open questions
    value_first_score: int  # 0-10: Explained value before asking
    bant_coverage: dict  # {"budget": bool, "authority": bool, "need": bool, "timeline": bool}
    zmeyka_adherence: int  # 0-10: Followed Zmeyka methodology
    objection_handling: int  # 0-10: Addressed objections properly
    zoom_close_attempt: bool  # Attempted to schedule
    message_length_appropriate: bool  # 2-5 sentences
    formal_language: bool  # Used "Вы"
    no_forbidden_topics: bool  # Didn't mention freehold for foreigners

    recommended_actions: list[str]  # Concrete next steps


class ConversationEvaluator:
    """
    Uses Agent SDK to assess conversation quality.

    Evaluates against tone-of-voice principles and how-to-communicate methodology.
    """

    def __init__(self):
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """You are an expert sales coach evaluating conversations for a Bali real estate company.

EVALUATION CRITERIA (based on company guidelines):

1. PERSONALIZATION (0-10): Did agent use client's name? Personalize responses?

2. OPEN QUESTIONS (0-10): Did messages end with questions that advance dialogue?

3. VALUE-FIRST (0-10): Did agent explain value before asking for information?

4. BANT COVERAGE: Did agent discover Budget, Authority, Need, Timeline?

5. ZMEYKA METHODOLOGY (0-10):
   - Easy question first
   - Reflect client's answer
   - Show expertise with facts
   - Ask next question

6. OBJECTION HANDLING (0-10): How well were objections addressed?

7. ZOOM CLOSE: Did agent attempt to schedule a Zoom meeting?

8. MESSAGE LENGTH: Were messages 2-5 sentences (not too long)?

9. FORMAL LANGUAGE: Used "Вы" (formal you) in Russian?

10. FORBIDDEN TOPICS: Did NOT mention "freehold for foreigners" (legally impossible)?

SCORING GUIDE:
- 90-100: Excellent - followed all principles, achieved goal
- 70-89: Good - minor issues, mostly effective
- 50-69: Average - several areas need improvement
- 30-49: Below average - significant issues
- 0-29: Poor - fundamental problems

Return ONLY valid JSON matching the ConversationAssessment schema."""

    async def evaluate(self, result: ConversationResult) -> ConversationAssessment:
        """
        Evaluate conversation using Agent SDK quick_prompt.

        Args:
            result: Complete conversation result

        Returns:
            ConversationAssessment with detailed scoring
        """
        conversation_text = self._format_conversation(result.turns)

        user_prompt = f"""Analyze this sales conversation:

SCENARIO: {result.scenario_name}
PERSONA TYPE: {result.persona.name} ({result.persona.difficulty} difficulty)
OUTCOME: {result.outcome.value}
TOTAL TURNS: {result.total_turns}
ACTIONS USED: {result.agent_actions_used}
EMAIL COLLECTED: {result.email_collected}

CONVERSATION:
{conversation_text}

Evaluate against all criteria and return JSON with:
{{
  "overall_score": 0-100,
  "what_went_well": ["...", "...", "..."],
  "areas_for_improvement": ["...", "...", "..."],
  "critical_issues": ["..."],
  "personalization_score": 0-10,
  "questions_score": 0-10,
  "value_first_score": 0-10,
  "bant_coverage": {{"budget": bool, "authority": bool, "need": bool, "timeline": bool}},
  "zmeyka_adherence": 0-10,
  "objection_handling": 0-10,
  "zoom_close_attempt": bool,
  "message_length_appropriate": bool,
  "formal_language": bool,
  "no_forbidden_topics": bool,
  "recommended_actions": ["..."]
}}"""

        result_text = await quick_prompt(AdhocPrompt(
            prompt=user_prompt,
            model=ModelName.SONNET,
            system_prompt=SystemPromptConfig(
                mode=SystemPromptMode.OVERWRITE,
                system_prompt=self.system_prompt,
            ),
        ))

        # Parse JSON from response
        try:
            # Find JSON in response
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = result_text[start:end]
                data = json.loads(json_str)
                return ConversationAssessment(**data)
        except (json.JSONDecodeError, ValueError) as e:
            # Return default assessment on parse error
            return ConversationAssessment(
                overall_score=0,
                what_went_well=["Could not parse evaluation"],
                areas_for_improvement=["Evaluation parsing failed"],
                critical_issues=[f"Parse error: {str(e)}"],
                personalization_score=0,
                questions_score=0,
                value_first_score=0,
                bant_coverage={"budget": False, "authority": False, "need": False, "timeline": False},
                zmeyka_adherence=0,
                objection_handling=0,
                zoom_close_attempt=False,
                message_length_appropriate=False,
                formal_language=False,
                no_forbidden_topics=True,
                recommended_actions=["Re-run evaluation"],
            )

    def _format_conversation(self, turns: list[ConversationTurn]) -> str:
        """Format conversation for evaluation."""
        lines = []
        for turn in turns:
            speaker = "AGENT" if turn.speaker == "agent" else "CLIENT"
            action = f" [{turn.action}]" if turn.action else ""
            lines.append(f"{speaker}{action}: {turn.message}")
        return "\n\n".join(lines)
```

---

### 6. Create CLI Runner

Create `.claude/skills/telegram/scripts/run_conversation_tests.py`:

```python
"""
CLI to run conversation tests using Anthropic Agent SDK.

Usage:
    uv run python run_conversation_tests.py [OPTIONS]

Options:
    --scenario NAME      Run specific scenario by name
    --all               Run all scenarios
    --difficulty LEVEL  Filter by difficulty (easy/medium/hard/expert)
    --parallel N        Parallel execution (default: 1)
    --output FILE       Save results to JSON file
    --verbose           Show conversation turns in real-time
"""
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from telegram_agent import TelegramAgent
from conversation_simulator import ConversationSimulator, ConversationResult
from conversation_evaluator import ConversationEvaluator, ConversationAssessment
from test_scenarios import SCENARIOS, get_scenario_by_name, get_scenarios_by_difficulty

console = Console()
SKILLS_BASE = Path(__file__).parent.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent


async def run_single_scenario(
    simulator: ConversationSimulator,
    evaluator: ConversationEvaluator,
    scenario_name: str,
    verbose: bool = False
) -> tuple[ConversationResult, ConversationAssessment]:
    """Run a single scenario and evaluate it."""
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
    """Run all scenarios sequentially."""
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


def display_summary(results: list[tuple[ConversationResult, ConversationAssessment]]):
    """Display summary table of all results."""
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
            "✓" if result.email_collected else "✗",
        )

    console.print(table)

    # Summary stats
    avg_score = sum(a.overall_score for _, a in results) / len(results)
    zoom_count = sum(1 for r, _ in results if r.outcome.value == "zoom_scheduled")

    console.print(Panel(
        f"Average Score: {avg_score:.1f}/100\n"
        f"Zoom Scheduled: {zoom_count}/{len(results)}\n"
        f"Total Scenarios: {len(results)}",
        title="Summary",
        expand=False,
    ))


def save_results(filepath: str, results: list[tuple[ConversationResult, ConversationAssessment]]):
    """Save detailed results to JSON file."""
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
                    {"speaker": t.speaker, "message": t.message, "action": t.action}
                    for t in r.turns
                ],
            }
            for r, a in results
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]Results saved to {filepath}[/green]")


async def main():
    parser = argparse.ArgumentParser(description="Run conversation tests")
    parser.add_argument("--scenario", type=str, help="Run specific scenario")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard", "expert"])
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--verbose", action="store_true", help="Show conversations")
    args = parser.parse_args()

    # Initialize components
    agent = TelegramAgent(
        tone_of_voice_path=SKILLS_BASE / "tone-of-voice",
        how_to_communicate_path=SKILLS_BASE / "how-to-communicate",
        knowledge_base_path=PROJECT_ROOT / "knowledge_base_final",
    )
    simulator = ConversationSimulator(agent, max_turns=15)
    evaluator = ConversationEvaluator()

    # Determine which scenarios to run
    if args.scenario:
        scenarios = [get_scenario_by_name(args.scenario)]
    elif args.difficulty:
        scenarios = get_scenarios_by_difficulty(args.difficulty)
    elif args.all:
        scenarios = SCENARIOS
    else:
        console.print("[yellow]Specify --scenario NAME, --difficulty LEVEL, or --all[/yellow]")
        return

    console.print(Panel(
        f"Running {len(scenarios)} scenario(s)",
        title="Conversation Tests",
    ))

    # Run scenarios
    results = await run_all_scenarios(simulator, evaluator, scenarios, args.verbose)

    # Display results
    display_summary(results)

    # Save if requested
    if args.output:
        save_results(args.output, results)


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Integrate and Test

- Wire up all components
- Run each scenario individually to verify
- Fine-tune persona prompts for realism
- Adjust termination conditions
- Validate evaluation criteria scoring

---

## Testing Strategy

**Unit Level:**
- Test PersonaPlayer generates appropriate responses via SDK
- Test ConversationSimulator termination conditions
- Test outcome classification logic

**Integration Level:**
- Run each scenario end-to-end
- Verify conversations reach reasonable conclusions
- Check evaluation scores are sensible

**Validation:**
- Compare agent behavior to expected methodology
- Verify escalation scenarios trigger correctly
- Confirm scheduling flow works (email → availability → schedule)

---

## Acceptance Criteria

1. **Scenario Coverage**: All 10 scenarios run successfully
2. **Outcome Classification**: Each conversation reaches a classified outcome
3. **Quality Assessment**: Each conversation gets a scored evaluation
4. **Realistic Conversations**: Persona responses feel like real clients
5. **Actionable Feedback**: Assessment provides specific improvement suggestions
6. **CLI Usability**: Can run individual or all scenarios from command line
7. **Report Quality**: Summary shows patterns across scenarios

---

## Validation Commands

```bash
# Verify syntax
uv run python -m py_compile .claude/skills/telegram/scripts/conversation_simulator.py
uv run python -m py_compile .claude/skills/telegram/scripts/test_scenarios.py
uv run python -m py_compile .claude/skills/telegram/scripts/conversation_evaluator.py
uv run python -m py_compile .claude/skills/telegram/scripts/run_conversation_tests.py

# Run single scenario
uv run python .claude/skills/telegram/scripts/run_conversation_tests.py --scenario "Skeptical Financist" --verbose

# Run by difficulty
uv run python .claude/skills/telegram/scripts/run_conversation_tests.py --difficulty hard --verbose

# Run all scenarios
uv run python .claude/skills/telegram/scripts/run_conversation_tests.py --all

# Run with JSON output
uv run python .claude/skills/telegram/scripts/run_conversation_tests.py --all --output results.json
```

---

## Notes

**Agent SDK Usage:**
- Uses `adws/adw_modules/adw_agent_sdk.py` for all Claude interactions (no mocking per CLAUDE.md)
- PersonaPlayer: `quick_prompt()` with `ModelName.SONNET` and `SystemPromptMode.OVERWRITE`
- ConversationEvaluator: `quick_prompt()` for quality assessment
- TelegramAgent: Continues using direct Anthropic client (can optionally migrate to SDK)
- Token tracking via SDK's `TokenUsage` class
- Estimated cost: ~$0.50-1.00 per full scenario run (20 turns × 2 API calls)

**Dependencies:**
- No new dependencies required
- Uses existing `adws/adw_modules/adw_agent_sdk.py` wrapper
- Uses existing anthropic, pydantic, rich libraries
- All files go in existing `.claude/skills/telegram/scripts/` directory
- SDK imports via path manipulation: `sys.path.insert(0, str(PROJECT_ROOT / "adws"))`

**Language Support:**
- Primary testing in Russian (main client base)
- One English scenario for international client testing
- Evaluation criteria adapted for both languages

**Future Enhancements:**
- Save conversation histories to database for pattern analysis
- A/B test different agent prompts
- Benchmark improvements over time
- Integration with actual Telegram for live testing

**Expected Test Duration:**
- Single scenario: 30-60 seconds
- All 10 scenarios: 5-10 minutes
- Parallel execution (3 at once): 3-4 minutes total
