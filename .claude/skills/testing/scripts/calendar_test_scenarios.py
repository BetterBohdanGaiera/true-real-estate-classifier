"""
Calendar Test Scenarios - Specialized scenarios for calendar integration testing.

Tests the full flow: agent proposes slots -> client selects -> meeting created.
Includes timezone variations, conflict detection, and email collection scenarios.

6 Scenarios:
1. Zoom Scheduler Happy Path - Simple successful flow
2. Timezone Mismatch - Kyiv (UTC+2/+3)
3. Timezone Mismatch - EST (UTC-5)
4. Slot Conflict - Selected slot already booked
5. Email Collection Before Slots - Verify email asked first
6. DST Edge Case - Ukraine during DST transition
"""

from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field


def get_dynamic_conflict_time() -> str:
    """
    Generate a dynamic conflict slot time for testing.

    Returns tomorrow at 2pm Bali time (UTC+8) as ISO string.
    This ensures the conflict test always uses a future date.
    """
    tomorrow = datetime.now() + timedelta(days=1)
    conflict_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    return conflict_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")

# Support both package import and direct execution
try:
    from .conversation_simulator import (
        PersonaDefinition,
        ConversationScenario,
        ConversationOutcome,
    )
except ImportError:
    from conversation_simulator import (
        PersonaDefinition,
        ConversationScenario,
        ConversationOutcome,
    )


# =============================================================================
# CALENDAR TEST SCENARIO MODEL
# =============================================================================

class CalendarTestScenario(BaseModel):
    """Extended scenario with calendar-specific parameters."""

    # Base conversation scenario fields
    name: str
    persona: PersonaDefinition
    initial_context: str
    agent_initiates: bool = True
    expected_outcome: Optional[ConversationOutcome] = None

    # Calendar-specific fields
    client_timezone: str = Field(
        description="Client's timezone (e.g., 'Europe/Kyiv', 'America/New_York')"
    )
    client_email: str = Field(
        description="Client's email for meeting invite"
    )
    preferred_slot_index: int = Field(
        default=0,
        description="Which proposed slot the client will select (0-indexed)"
    )
    test_conflict: bool = Field(
        default=False,
        description="Whether to test conflict detection by pre-creating blocking event"
    )
    conflict_slot_time: Optional[str] = Field(
        default=None,
        description="ISO datetime for conflict event (only if test_conflict=True)"
    )


# =============================================================================
# SCENARIO 1: Zoom Scheduler Happy Path
# =============================================================================

ZOOM_HAPPY_PATH = CalendarTestScenario(
    name="Zoom Scheduler Happy Path",
    persona=PersonaDefinition(
        name="Анна Готовая",
        description="""Клиент полностью готов к Zoom звонку. Предоставляет email сразу,
        выбирает первый предложенный слот без возражений. Простейший сценарий для
        верификации полного flow создания встречи в календаре.""",
        difficulty="easy",
        traits=[
            "Быстро соглашается на Zoom",
            "Сразу дает email без вопросов",
            "Выбирает первый предложенный слот",
            "Не задает лишних вопросов о времени",
            "Благодарит за оперативность",
        ],
        objections=[],
        goal="immediate_zoom",
        language="ru",
        multi_message_probability=0.1,
        max_messages_per_turn=2,
    ),
    initial_context="Оставила заявку на сайте, готова к разговору прямо сейчас",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="Europe/Moscow",
    client_email="test.happy.path@example.com",
    preferred_slot_index=0,
    test_conflict=False,
)


# =============================================================================
# SCENARIO 2: Timezone Mismatch Detection (Kyiv)
# =============================================================================

TIMEZONE_KYIV = CalendarTestScenario(
    name="Timezone Mismatch - Kyiv",
    persona=PersonaDefinition(
        name="Олег Київський",
        description="""Клиент из Киева (UTC+2/+3 в зависимости от летнего времени).
        Внимательно следит за временем, может уточнить часовой пояс.
        Тестирует корректную конвертацию времени между Bali и Украиной.""",
        difficulty="medium",
        traits=[
            "Живет в Киеве, Украина",
            "Обращает внимание на время встречи",
            "Может переспросить про часовой пояс",
            "Ценит когда время показывают по его часовому поясу",
            "Занятой человек, время важно",
        ],
        objections=[
            "Это по какому времени?",
            "У нас же большая разница с Бали",
            "Подождите, это по вашему или моему времени?",
        ],
        goal="zoom_with_timezone_verification",
        language="ru",
        multi_message_probability=0.3,
        max_messages_per_turn=3,
    ),
    initial_context="Инвестор из Украины, интересуется недвижимостью на Бали",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="Europe/Kyiv",
    client_email="test.kyiv.tz@example.com",
    preferred_slot_index=1,
    test_conflict=False,
)


# =============================================================================
# SCENARIO 3: Timezone Mismatch Detection (EST - USA)
# =============================================================================

TIMEZONE_EST = CalendarTestScenario(
    name="Timezone Mismatch - EST",
    persona=PersonaDefinition(
        name="John from NYC",
        description="""American investor from New York (EST, UTC-5).
        Significant timezone difference from Bali (13 hours).
        Tests handling of day-change scenarios when scheduling.
        Prefers morning meetings his time.""",
        difficulty="medium",
        traits=[
            "Based in New York, USA",
            "Prefers morning meetings (his time)",
            "Will explicitly ask about timezone",
            "Professional tone, straight to the point",
            "May suggest alternative times if slot doesn't work",
        ],
        objections=[
            "What time is that in EST?",
            "That might be too early/late for me",
            "Can we do morning my time?",
            "I'm in New York, what's the time difference?",
        ],
        goal="zoom_with_major_tz_difference",
        language="en",
        multi_message_probability=0.2,
        max_messages_per_turn=2,
    ),
    initial_context="American investor interested in Bali real estate, found via LinkedIn",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="America/New_York",
    client_email="test.nyc.investor@example.com",
    preferred_slot_index=2,
    test_conflict=False,
)


# =============================================================================
# SCENARIO 4: Slot Conflict Detection
# =============================================================================

SLOT_CONFLICT = CalendarTestScenario(
    name="Slot Conflict",
    persona=PersonaDefinition(
        name="Петр Занятый",
        description="""Клиент выбирает слот, который уже занят в календаре
        (будет создано конфликтующее событие перед тестом).
        Агент должен корректно обнаружить конфликт и предложить альтернативы.
        Тестирует обработку занятых слотов.""",
        difficulty="hard",
        traits=[
            "Настаивает на конкретном времени",
            "Может быть раздражен если слот недоступен",
            "Готов рассмотреть альтернативные варианты",
            "Занятой бизнесмен с плотным графиком",
            "Ценит когда агент быстро предлагает альтернативы",
        ],
        objections=[
            "Мне нужно именно это время",
            "Почему оно недоступно?",
            "А другие варианты есть?",
            "Ладно, давайте другое время",
        ],
        goal="handle_conflict_gracefully",
        language="ru",
        multi_message_probability=0.4,
        max_messages_per_turn=3,
    ),
    initial_context="VIP клиент с ограниченным графиком, владелец бизнеса",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="Europe/Moscow",
    client_email="test.conflict@example.com",
    preferred_slot_index=0,  # This slot will be intentionally blocked
    test_conflict=True,
    conflict_slot_time=None,  # Computed dynamically at test runtime via get_dynamic_conflict_time()
)


# =============================================================================
# SCENARIO 5: Email Collection Before Slots
# =============================================================================

EMAIL_BEFORE_SLOTS = CalendarTestScenario(
    name="Email Collection Before Slots",
    persona=PersonaDefinition(
        name="Сергей Осторожный",
        description="""Тестирует что агент запрашивает email ДО того как показывать
        доступные слоты. Клиент не дает email сразу, хочет сначала увидеть время.
        Агент должен мягко настоять на получении email первым.""",
        difficulty="medium",
        traits=[
            "Осторожен с личными данными",
            "Не сразу дает email",
            "Хочет сначала увидеть слоты",
            "В итоге соглашается дать email",
            "Ценит когда объясняют зачем нужен email",
        ],
        objections=[
            "А зачем вам мой email?",
            "Сначала покажите доступное время",
            "Можно без email?",
            "Ладно, записывайте email",
        ],
        goal="collect_email_first",
        language="ru",
        multi_message_probability=0.3,
        max_messages_per_turn=2,
    ),
    initial_context="Клиент из рекламы в Instagram, осторожен с личными данными",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="Europe/Moscow",
    client_email="test.email.first@example.com",
    preferred_slot_index=0,
    test_conflict=False,
)


# =============================================================================
# SCENARIO 6: DST Edge Case (Ukraine Summer/Winter Time)
# =============================================================================

DST_UKRAINE = CalendarTestScenario(
    name="DST Edge Case - Ukraine",
    persona=PersonaDefinition(
        name="Марія з Одеси",
        description="""Клиент из Украины во время перехода на летнее/зимнее время.
        Тестирует корректную обработку DST при конвертации времени.
        Украина переходит на летнее время в последнее воскресенье марта,
        на зимнее - в последнее воскресенье октября. Бали не имеет DST.""",
        difficulty="hard",
        traits=[
            "Живет в Одессе, Украина",
            "Внимательна к деталям времени",
            "Может уточнить про смену времени",
            "Знает про переход часов",
            "Хочет убедиться что время правильное",
        ],
        objections=[
            "А это с учетом перехода на летнее время?",
            "У нас скоро переводят часы",
            "Точно правильное время?",
        ],
        goal="dst_handling",
        language="ru",
        multi_message_probability=0.3,
        max_messages_per_turn=2,
    ),
    initial_context="Клиент из Одессы, звонок планируется близко к дате перехода DST",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    client_timezone="Europe/Kyiv",
    client_email="test.dst.ukraine@example.com",
    preferred_slot_index=1,
    test_conflict=False,
)


# =============================================================================
# ALL CALENDAR TEST SCENARIOS
# =============================================================================

CALENDAR_TEST_SCENARIOS: list[CalendarTestScenario] = [
    ZOOM_HAPPY_PATH,
    TIMEZONE_KYIV,
    TIMEZONE_EST,
    SLOT_CONFLICT,
    EMAIL_BEFORE_SLOTS,
    DST_UKRAINE,
]
"""
Complete list of 6 calendar integration test scenarios.

Scenarios cover:
- Happy path (simple successful flow)
- Timezone conversion (Kyiv UTC+2/+3, Moscow UTC+3, EST UTC-5)
- Slot conflict detection
- Email collection before showing slots
- DST edge cases (Ukraine summer/winter time)

All Russian scenarios use "ru" language, one English scenario for timezone testing.
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_calendar_scenario_by_name(name: str) -> CalendarTestScenario:
    """
    Get a calendar test scenario by its name (case-insensitive).

    Args:
        name: The name of the scenario to find.

    Returns:
        The matching CalendarTestScenario.

    Raises:
        ValueError: If no scenario with the given name is found.
    """
    for scenario in CALENDAR_TEST_SCENARIOS:
        if scenario.name.lower() == name.lower():
            return scenario
    raise ValueError(f"Calendar test scenario not found: {name}")


def get_all_calendar_scenarios() -> list[CalendarTestScenario]:
    """
    Get all calendar test scenarios.

    Returns:
        List of all CalendarTestScenario objects.
    """
    return CALENDAR_TEST_SCENARIOS.copy()


def get_calendar_scenarios_by_timezone(timezone: str) -> list[CalendarTestScenario]:
    """
    Get all scenarios that use a specific client timezone.

    Args:
        timezone: Timezone string (e.g., "Europe/Kyiv", "America/New_York")

    Returns:
        List of matching CalendarTestScenario objects.
    """
    return [s for s in CALENDAR_TEST_SCENARIOS if s.client_timezone == timezone]


def get_calendar_scenarios_by_difficulty(difficulty: str) -> list[CalendarTestScenario]:
    """
    Get all scenarios of a specified difficulty level.

    Args:
        difficulty: One of "easy", "medium", "hard", or "expert".

    Returns:
        List of CalendarTestScenario objects matching the difficulty.
    """
    return [
        s for s in CALENDAR_TEST_SCENARIOS
        if s.persona.difficulty == difficulty
    ]


def get_conflict_scenarios() -> list[CalendarTestScenario]:
    """
    Get all scenarios that test conflict detection.

    Returns:
        List of CalendarTestScenario objects with test_conflict=True.
    """
    return [s for s in CALENDAR_TEST_SCENARIOS if s.test_conflict]


def get_scenario_names() -> list[str]:
    """
    Get a list of all calendar scenario names.

    Returns:
        List of scenario name strings.
    """
    return [s.name for s in CALENDAR_TEST_SCENARIOS]


# =============================================================================
# MODULE SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Calendar Test Scenarios Module - Self-Test")
    print("=" * 60)

    print(f"\nTotal calendar scenarios: {len(CALENDAR_TEST_SCENARIOS)}")
    assert len(CALENDAR_TEST_SCENARIOS) == 6, f"Expected 6 scenarios, got {len(CALENDAR_TEST_SCENARIOS)}"

    # Check difficulty distribution
    easy = get_calendar_scenarios_by_difficulty("easy")
    medium = get_calendar_scenarios_by_difficulty("medium")
    hard = get_calendar_scenarios_by_difficulty("hard")

    print(f"\nDifficulty distribution:")
    print(f"  Easy: {len(easy)} (expected 1)")
    print(f"  Medium: {len(medium)} (expected 3)")
    print(f"  Hard: {len(hard)} (expected 2)")

    assert len(easy) == 1, f"Expected 1 easy, got {len(easy)}"
    assert len(medium) == 3, f"Expected 3 medium, got {len(medium)}"
    assert len(hard) == 2, f"Expected 2 hard, got {len(hard)}"

    # Check timezone distribution
    kyiv = get_calendar_scenarios_by_timezone("Europe/Kyiv")
    moscow = get_calendar_scenarios_by_timezone("Europe/Moscow")
    est = get_calendar_scenarios_by_timezone("America/New_York")

    print(f"\nTimezone distribution:")
    print(f"  Europe/Kyiv: {len(kyiv)} scenarios")
    print(f"  Europe/Moscow: {len(moscow)} scenarios")
    print(f"  America/New_York: {len(est)} scenarios")

    # Check conflict scenarios
    conflicts = get_conflict_scenarios()
    print(f"\nConflict test scenarios: {len(conflicts)} (expected 1)")
    assert len(conflicts) == 1, f"Expected 1 conflict scenario, got {len(conflicts)}"

    # Print all scenarios
    print(f"\nAll calendar test scenarios:")
    for i, scenario in enumerate(CALENDAR_TEST_SCENARIOS, 1):
        outcome = scenario.expected_outcome.value if scenario.expected_outcome else "N/A"
        conflict = " [CONFLICT]" if scenario.test_conflict else ""
        print(
            f"  {i}. {scenario.name} "
            f"({scenario.persona.difficulty}) "
            f"TZ: {scenario.client_timezone} "
            f"-> {outcome}{conflict}"
        )

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
