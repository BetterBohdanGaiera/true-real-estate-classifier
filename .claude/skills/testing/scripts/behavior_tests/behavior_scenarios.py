"""
Behavior Test Scenarios for Telegram Agent.

Defines three test scenarios to verify specific agent behaviors:
1. Batching - sends 3 messages rapidly, expects single batched response
2. Wait Handling - asks agent to wait, verifies pause then resume
3. Zoom Scheduling - cooperative buyer journey ending in meeting booking

Each scenario includes a PersonaDefinition and StressConfig optimized
for testing the specific behavior pattern.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Setup paths for imports
SCRIPTS_DIR = Path(__file__).parent.parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Support both package import and direct execution
try:
    from ..conversation_simulator import (
        PersonaDefinition,
        ConversationScenario,
        ConversationOutcome,
    )
    from ..stress_scenarios import StressScenario, StressConfig
except ImportError:
    from conversation_simulator import (
        PersonaDefinition,
        ConversationScenario,
        ConversationOutcome,
    )
    from stress_scenarios import StressScenario, StressConfig


# =============================================================================
# BATCHING TEST SCENARIO
# Tests: 3 client messages -> 1 agent response (batched)
# =============================================================================

BATCHING_PERSONA = PersonaDefinition(
    name="Быстрый Спрашиватель",
    description="""Клиент, который привык задавать вопросы очередями.
    Отправляет несколько сообщений подряд, не дожидаясь ответа.
    Имитирует типичное поведение в Telegram, когда пользователь
    пишет короткими сообщениями вместо одного длинного.""",
    difficulty="medium",
    traits=[
        "Пишет короткими сообщениями подряд",
        "Не ждёт ответа между вопросами",
        "Задаёт 3 вопроса одной очередью",
        "Ожидает один развёрнутый ответ",
        "Нетерпеливый, но не грубый",
    ],
    objections=[],  # No objections for batching test
    goal="zoom_scheduled",
    language="ru",
    initial_message=None,  # Agent initiates
    multi_message_probability=1.0,  # Always send multiple messages
    max_messages_per_turn=3,  # Exactly 3 messages in burst
)

BATCHING_SCENARIO = StressScenario(
    name="Message Batching Test",
    persona=BATCHING_PERSONA,
    initial_context="Interested in Bali villas, rapid multi-question style",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    stress_config=StressConfig(
        # Test orchestration: Client sends 3, wait for 1 agent response
        message_pattern=[("C", 3), ("A", 1)],
        # Fast bursts between messages (0.5-1.5 seconds)
        inter_message_delays=[(0.5, 1.5)],
        # Standard delays between turns
        message_delays=[(2.0, 5.0)],
        # Batch size of 3 for this test
        batch_sizes=[3],
        # Standard timeout
        timeout_multiplier=1.5,
        urgency_requests=[],
    ),
)


# =============================================================================
# WAIT HANDLING TEST SCENARIO
# Tests: Client asks to wait -> Agent pauses -> Client resumes -> Agent responds
# =============================================================================

WAIT_HANDLING_PERSONA = PersonaDefinition(
    name="Занятой Проверяющий",
    description="""Клиент, который во время разговора отвлекается.
    Просит подождать несколько минут, пока проверяет что-то.
    Затем возвращается и продолжает разговор.
    Тестирует способность агента распознавать просьбу подождать.""",
    difficulty="medium",
    traits=[
        "Занят параллельными делами",
        "Просит подождать 2-3 минуты",
        "Всегда возвращается после паузы",
        "Вежливый, ценит терпение агента",
        "После паузы продолжает с того же места",
    ],
    objections=[],  # No objections for wait test
    goal="follow_up_proposed",
    language="ru",
    initial_message=None,  # Agent initiates
    multi_message_probability=0.0,  # Single messages only
    max_messages_per_turn=1,
)

WAIT_HANDLING_SCENARIO = StressScenario(
    name="Wait Handling Test",
    persona=WAIT_HANDLING_PERSONA,
    initial_context="Busy client checking other options while chatting",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.FOLLOW_UP_PROPOSED,
    stress_config=StressConfig(
        # Pattern: initial exchange, wait request, long pause, resume
        message_pattern=[("C", 1), ("A", 1), ("C", 1), ("A", 0), ("C", 1), ("A", 1)],
        # Long pause after wait request (2-3 minutes)
        inter_message_delays=[(120.0, 180.0)],
        # Standard message delays for other turns
        message_delays=[(3.0, 8.0)],
        batch_sizes=[1],
        # Extended timeout for wait test
        timeout_multiplier=3.0,
        urgency_requests=[],
    ),
)

# Predefined wait phrases for the test
WAIT_PHRASES = [
    "Секунду, дай мне 2 минуты, нужно проверить кое-что",
    "Подожди пару минут, мне нужно посмотреть другое предложение",
    "Минуту, отвлекся на звонок",
]

RESUME_PHRASES = [
    "Хорошо, вернулся. Продолжим?",
    "Всё, я здесь. На чём остановились?",
    "Окей, можем продолжить",
]


# =============================================================================
# ZOOM SCHEDULING TEST SCENARIO
# Tests: Cooperative buyer provides email -> books Zoom meeting
# =============================================================================

ZOOM_SCHEDULING_PERSONA = PersonaDefinition(
    name="Готовый Покупатель",
    description="""Идеальный клиент, готовый к звонку.
    Отвечает кооперативно, предоставляет email когда просят,
    выбирает слот для звонка из предложенных.
    Тестирует полный цикл записи на Zoom.""",
    difficulty="easy",
    traits=[
        "Готов к звонку прямо сейчас",
        "Быстро предоставляет email",
        "Выбирает первый удобный слот",
        "Не торгуется и не возражает",
        "Вежливый и благодарный",
        "Подтверждает бронирование",
    ],
    objections=[],  # No objections - cooperative buyer
    goal="zoom_scheduled",
    language="ru",
    initial_message=None,  # Agent initiates
    multi_message_probability=0.1,  # Rarely sends multiple
    max_messages_per_turn=2,
)

# Test email for Zoom scheduling verification
TEST_EMAIL = "test@example.com"

ZOOM_SCHEDULING_SCENARIO = StressScenario(
    name="Zoom Scheduling Test",
    persona=ZOOM_SCHEDULING_PERSONA,
    initial_context="Ready buyer, wants to schedule a call immediately",
    agent_initiates=True,
    expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    stress_config=StressConfig(
        # Normal conversation flow: several exchanges leading to booking
        message_pattern=[
            ("C", 1), ("A", 1),  # Initial exchange
            ("C", 1), ("A", 1),  # Agent asks for email
            ("C", 1), ("A", 1),  # Client provides email, agent shows slots
            ("C", 1), ("A", 1),  # Client selects slot, agent confirms
        ],
        inter_message_delays=[(1.0, 3.0)],
        message_delays=[(2.0, 5.0)],
        batch_sizes=[1],
        timeout_multiplier=1.5,
        urgency_requests=[],
    ),
)


# =============================================================================
# ALL BEHAVIOR SCENARIOS
# =============================================================================

BEHAVIOR_SCENARIOS: list[StressScenario] = [
    BATCHING_SCENARIO,
    WAIT_HANDLING_SCENARIO,
    ZOOM_SCHEDULING_SCENARIO,
]


def get_behavior_scenario_by_name(name: str) -> Optional[StressScenario]:
    """
    Get a behavior scenario by name (case-insensitive partial match).

    Args:
        name: Scenario name to search for

    Returns:
        StressScenario if found, None otherwise
    """
    name_lower = name.lower()
    for scenario in BEHAVIOR_SCENARIOS:
        if name_lower in scenario.name.lower():
            return scenario
    return None


def get_behavior_scenario_names() -> list[str]:
    """Get list of all behavior scenario names."""
    return [s.name for s in BEHAVIOR_SCENARIOS]
