"""
Stress Test Scenarios for Telegram Agent Communication Simulation.

This module defines 7 stress test scenarios that test the agent's behavior under
various challenging timing conditions: rapid messages, delayed responses, urgency
demands, mixed timing patterns, long messages, interruption patterns, and realistic
multi-message conversations.

Each scenario includes:
- A challenging Russian-speaking persona
- Stress configuration parameters (delays, batching, urgency phrases)
- Expected outcomes based on agent behavior

Stress Scenario Distribution:
- Timing Stress: 2 scenarios (Rapid Fire, Slow Responder)
- Content Stress: 2 scenarios (Urgency Demand, Long Messages)
- Pattern Stress: 3 scenarios (Mixed Timing, Interruption Pattern, Realistic Multi-Message)

All scenarios are in Russian to maintain consistency with the main test_scenarios.py.
"""

from typing import Optional

from pydantic import BaseModel, Field

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
# Stress Configuration Model
# =============================================================================

class StressConfig(BaseModel):
    """
    Configuration for stress testing parameters.

    Controls timing, batching, and urgency injection for stress test scenarios.
    These parameters are used by the stress test runner to control message timing
    and simulate various client communication patterns.

    Attributes:
        message_delays: List of (min, max) delay ranges in seconds between messages.
                       The runner picks randomly within each range.
        batch_sizes: How many messages to send at once before waiting for response.
                    [1] means normal single messages, [3, 2] means send 3, then 2.
        urgency_requests: Specific urgency phrases to inject into conversation.
                         Empty list means no urgency injection.
        timeout_multiplier: Multiply standard timeouts by this factor.
                           Values < 1.0 expect faster responses, > 1.0 allows slower.
        conversation_pattern: Defines the sequence of turns in the conversation.
                            'C' = client message, 'A' = wait for agent response.
                            Example: ["C", "C", "C", "A", "C", "A", "A"] means:
                            - Client sends 3 messages rapidly
                            - Wait for agent response
                            - Client sends 1 message
                            - Wait for 2 agent responses
                            If None, uses default alternating C-A-C-A pattern.
    """
    message_delays: list[tuple[float, float]] = Field(
        default=[(0.5, 2.0)],
        description="List of (min, max) delay ranges between messages in seconds"
    )
    inter_message_delays: list[tuple[float, float]] = Field(
        default=[(0.5, 3.0)],
        description="Delay ranges between messages in a burst (seconds). Can be up to 1-2 minutes for realistic pauses."
    )
    batch_sizes: list[int] = Field(
        default=[1],
        description="How many messages to send at once (1 = no batching)"
    )
    urgency_requests: list[str] = Field(
        default=[],
        description="Specific urgency phrases to inject into conversation"
    )
    timeout_multiplier: float = Field(
        default=1.0,
        description="Multiply standard timeouts by this factor"
    )
    conversation_pattern: list[str] | None = Field(
        default=None,
        description="Sequence of turns: 'C'=client, 'A'=agent. None=default alternating."
    )
    message_pattern: list[tuple[str, int]] | None = Field(
        default=None,
        description="""
        TEST ORCHESTRATION pattern as list of (speaker, count) tuples.
        Example: [('C', 3), ('A', 1), ('C', 2)] means:
        - Test sends 3 client messages (with inter_message_delays between them)
        - Test waits for agent response (system uses timing to batch)
        - Test sends 2 more client messages

        Note: This controls TEST behavior. The SYSTEM still uses timing-based
        detection (MessageBuffer debounce) to determine when client is done.
        """
    )


# =============================================================================
# Stress Scenario Model
# =============================================================================

class StressScenario(ConversationScenario):
    """
    A conversation scenario with additional stress testing configuration.

    Extends ConversationScenario to include timing and batching parameters
    that control how the test runner sends messages to stress test the agent.

    Attributes:
        stress_config: Configuration for timing, batching, and urgency parameters.
    """
    stress_config: StressConfig = Field(
        default_factory=StressConfig,
        description="Stress testing configuration for this scenario"
    )


# =============================================================================
# STRESS SCENARIOS - 7 Challenging Timing/Pattern Test Personas
# =============================================================================

STRESS_SCENARIOS: list[StressScenario] = [
    # =========================================================================
    # Scenario 1: Rapid Fire Burst (HARD)
    # Tests message batching - sends 5 messages within 2 seconds
    # =========================================================================
    StressScenario(
        name="Rapid Fire Burst",
        persona=PersonaDefinition(
            name="Быстрый Инвестор",
            description="""Очень нетерпеливый клиент, который задает вопросы очередями.
            Привык к мгновенным ответам, как в современных чатах.
            Если агент медлит - раздражается и может уйти.""",
            difficulty="hard",
            traits=[
                "Нетерпеливый, хочет ответов прямо сейчас",
                "Отправляет несколько сообщений подряд не дожидаясь ответа",
                "Раздражается если агент медлит с ответом",
                "Пишет короткими сообщениями, по одной мысли на сообщение",
                "Ожидает что агент ответит на ВСЕ вопросы сразу",
            ],
            objections=[
                "Почему так долго отвечаете?",
                "Это же простой вопрос!",
                "Вы вообще читаете что я пишу?",
                "Ответьте уже наконец",
                "Я жду",
            ],
            goal="zoom_if_fast_response",
            language="ru",
            multi_message_probability=0.8,
            max_messages_per_turn=5,
        ),
        initial_context="Увидел рекламу, хочет быстрых ответов, нет времени ждать",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_pattern=[("C", 3), ("A", 1), ("C", 2), ("A", 1)],
            inter_message_delays=[(0.5, 2.0), (1.0, 5.0)],
            message_delays=[(0.2, 0.5), (0.3, 0.6), (0.1, 0.4)],  # Very fast bursts
            batch_sizes=[3, 2],  # Send 3 messages, then 2 more
            urgency_requests=[],  # No explicit urgency, just fast messages
            timeout_multiplier=0.5,  # Expect faster agent responses
        ),
    ),

    # =========================================================================
    # Scenario 2: Slow Responder (MEDIUM)
    # Tests agent patience - 30-60 second delays between responses
    # =========================================================================
    StressScenario(
        name="Slow Responder",
        persona=PersonaDefinition(
            name="Занятой Бизнесмен",
            description="""Очень занятой человек, который отвечает урывками.
            Между ответами могут быть большие паузы - он на встречах, за рулем.
            Ценит агента который не давит и терпеливо ждет.""",
            difficulty="medium",
            traits=[
                "Отвечает с большими задержками (минуты, иногда десятки минут)",
                "Часто пишет 'извините, был занят'",
                "Не любит когда торопят или давят",
                "Ценит терпение и профессионализм",
                "Может внезапно стать очень активным",
            ],
            objections=[
                "Извините, был на встрече",
                "Сейчас за рулем, позже отвечу подробнее",
                "Много работы, пишите коротко",
                "Не могу сейчас разговаривать, потом",
                "Вернусь к вам через час",
            ],
            goal="zoom_if_patient",
            language="ru",
            multi_message_probability=0.2,
            max_messages_per_turn=2,
        ),
        initial_context="VIP клиент, владелец бизнеса, очень занят",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_delays=[(30.0, 60.0), (20.0, 45.0), (40.0, 90.0)],  # Long delays
            batch_sizes=[1],  # Single messages
            urgency_requests=[],  # No urgency from this persona
            timeout_multiplier=3.0,  # Allow much longer agent wait times
        ),
    ),

    # =========================================================================
    # Scenario 3: Urgency Demand (HARD)
    # Tests urgency handling - includes "respond in X minutes" phrases
    # =========================================================================
    StressScenario(
        name="Urgency Demand",
        persona=PersonaDefinition(
            name="Срочный Покупатель",
            description="""Клиент который уезжает завтра и ему нужно решить вопрос СЕЙЧАС.
            Постоянно подчеркивает срочность, ставит дедлайны.
            Если агент не реагирует на срочность - уходит к конкурентам.""",
            difficulty="hard",
            traits=[
                "Постоянно подчеркивает срочность ситуации",
                "Ставит конкретные дедлайны для ответа",
                "Угрожает уйти к конкурентам если не успеют",
                "Нервничает и торопит агента",
                "Готов принять решение быстро если получит нужную информацию",
            ],
            objections=[
                "Мне нужен ответ в течение 2 минут",
                "У меня самолет завтра утром!",
                "Если не ответите сейчас - позвоню другому агентству",
                "Это срочно!!! Когда ответите?",
                "Нет времени ждать, решайте быстрее",
            ],
            goal="zoom_if_urgent_response",
            language="ru",
            multi_message_probability=0.5,
            max_messages_per_turn=3,
        ),
        initial_context="Оставил заявку с пометкой СРОЧНО, уезжает завтра",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_delays=[(1.0, 3.0)],  # Moderate delays but with urgency
            batch_sizes=[1, 2],  # Occasional double messages
            urgency_requests=[
                "Ответьте в течение 2 минут пожалуйста",
                "Это ОЧЕНЬ срочно",
                "У меня только 5 минут на разговор",
                "Нужен ответ СЕЙЧАС",
            ],
            timeout_multiplier=0.3,  # Expect very fast responses
        ),
    ),

    # =========================================================================
    # Scenario 4: Mixed Timing (HARD)
    # Alternates between fast and slow responses unpredictably
    # =========================================================================
    StressScenario(
        name="Mixed Timing",
        persona=PersonaDefinition(
            name="Непредсказуемый Клиент",
            description="""Клиент с хаотичным расписанием. Иногда отвечает мгновенно,
            иногда пропадает на полчаса. Агент должен адаптироваться к ритму.
            Не любит шаблонных ответов.""",
            difficulty="hard",
            traits=[
                "Непредсказуемое время ответа - то мгновенно, то через час",
                "Меняет темы разговора без предупреждения",
                "Иногда отвечает очень подробно, иногда односложно",
                "Ценит когда агент подстраивается под его ритм",
                "Не терпит когда чувствует давление",
            ],
            objections=[
                "Секунду, отвлекся",
                "Так, на чем мы остановились?",
                "Подождите, мне звонят",
                "Ок... продолжайте",
                "Хм, интересно, а что насчет...",
            ],
            goal="zoom_if_adaptive",
            language="ru",
            multi_message_probability=0.6,
            max_messages_per_turn=4,
        ),
        initial_context="Пришел по рекомендации, интересуется но пока не определился",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_delays=[
                (0.5, 1.5),   # Fast
                (25.0, 40.0),  # Slow
                (1.0, 2.0),   # Fast again
                (30.0, 60.0),  # Very slow
                (0.3, 0.8),   # Very fast burst
            ],
            batch_sizes=[1, 1, 2, 1, 3],  # Mix of single and batch
            urgency_requests=[],
            timeout_multiplier=1.5,  # Moderate tolerance
        ),
    ),

    # =========================================================================
    # Scenario 5: Long Messages (MEDIUM)
    # Sends multi-paragraph messages testing reading delay calculation
    # =========================================================================
    StressScenario(
        name="Long Messages",
        persona=PersonaDefinition(
            name="Подробный Аналитик",
            description="""Человек который привык излагать мысли подробно и структурированно.
            Пишет длинные сообщения с множеством вопросов. Ожидает такого же уровня
            детализации в ответах. Работает в аналитике.""",
            difficulty="medium",
            traits=[
                "Пишет длинные структурированные сообщения",
                "Задает несколько связанных вопросов в одном сообщении",
                "Ожидает подробных ответов на каждый пункт",
                "Использует нумерацию и списки",
                "Ценит когда отвечают на ВСЕ вопросы, не пропуская",
            ],
            multi_message_probability=0.1,
            max_messages_per_turn=2,
            objections=[
                """Добрый день! У меня несколько вопросов по инвестициям в недвижимость на Бали:

1. Какая средняя доходность по вашим объектам за последние 3 года?
2. Есть ли гарантия дохода и на какой срок?
3. Как устроено управление - своя УК или партнеры?
4. Какие налоги я буду платить как нерезидент?

Буду благодарен за подробный ответ по каждому пункту.""",
                """Спасибо за информацию. Есть ещё вопросы:

1. Какой минимальный порог входа?
2. Возможна ли рассрочка и на каких условиях?
3. Что происходит если застройщик не сдаст объект в срок?
4. Есть ли страховка рисков?
5. Как выглядит процесс покупки от начала до конца?

Прошу подробно расписать каждый пункт.""",
                """Хорошо, вижу что вы разбираетесь в теме.

Последний блок вопросов перед принятием решения:
- Примеры успешных кейсов ваших клиентов
- Документы которые вы предоставляете
- Гарантийные обязательства
- Выход из инвестиции - как продать?

После этого готов обсудить конкретные варианты.""",
            ],
            goal="zoom_after_detailed_answers",
            language="ru",
        ),
        initial_context="Аналитик из крупной компании, тщательно изучает все варианты",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_delays=[(3.0, 8.0)],  # Normal delays, long messages
            batch_sizes=[1],  # Single messages but long
            urgency_requests=[],
            timeout_multiplier=2.0,  # Allow more time for detailed responses
        ),
    ),

    # =========================================================================
    # Scenario 6: Interruption Pattern (HARD)
    # Sends message, waits for typing indicator, then sends another
    # =========================================================================
    StressScenario(
        name="Interruption Pattern",
        persona=PersonaDefinition(
            name="Прерывающий Клиент",
            description="""Клиент который постоянно дополняет свои сообщения.
            Начинает писать, потом добавляет 'и еще...', 'кстати...', 'забыл спросить...'.
            Часто прерывает когда видит что агент печатает.""",
            difficulty="hard",
            traits=[
                "Дополняет свои сообщения не дожидаясь ответа",
                "Часто пишет 'и еще одно', 'забыл сказать', 'кстати'",
                "Прерывает когда видит что агент печатает",
                "Меняет вопрос пока агент готовит ответ",
                "Хаотичный стиль общения",
            ],
            objections=[
                "Подождите, забыл спросить...",
                "И еще важный момент!",
                "Кстати, пока вы печатаете - еще вопрос",
                "Стоп, не отвечайте пока",
                "Дополню - это тоже важно",
            ],
            goal="zoom_if_handles_interruptions",
            language="ru",
            multi_message_probability=0.7,
            max_messages_per_turn=4,
        ),
        initial_context="Активный в соцсетях, привык к многозадачности",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_pattern=[("C", 1), ("C", 2), ("A", 1), ("C", 1), ("A", 2)],
            inter_message_delays=[(2.0, 10.0), (30.0, 90.0)],
            message_delays=[
                (0.5, 1.0),   # Initial message
                (2.0, 4.0),   # Wait a bit for agent to start typing
                (0.3, 0.6),   # Quick interruption
                (1.5, 3.0),   # Another pause
                (0.2, 0.5),   # Another quick addition
            ],
            batch_sizes=[1, 1, 2, 1, 2],  # Interruptions come in pairs
            urgency_requests=[],
            timeout_multiplier=0.8,  # Expect reasonably fast handling
        ),
    ),

    # =========================================================================
    # Scenario 7: Realistic Multi-Message (MEDIUM)
    # Tests realistic Telegram behavior with pauses up to 2 minutes
    # =========================================================================
    StressScenario(
        name="Realistic Multi-Message",
        persona=PersonaDefinition(
            name="Реалистичный Собеседник",
            description="""Клиент который общается как реальный человек в Telegram.
            Отправляет несколько сообщений подряд с паузами от нескольких секунд до пары минут.
            Имитирует реальное поведение - думает, дописывает мысли, отвлекается.""",
            difficulty="medium",
            traits=[
                "Отправляет мысли несколькими сообщениями",
                "Делает паузы между сообщениями (от 5 секунд до 2 минут)",
                "Иногда дополняет предыдущие мысли",
                "Естественный ритм общения",
                "Реалистичное поведение как в настоящем Telegram чате",
            ],
            objections=[
                "А если...",
                "Еще вопрос",
                "Минуту, подумаю",
                "Хм, интересно",
                "Понял, спасибо",
            ],
            goal="zoom_if_natural_conversation",
            language="ru",
            multi_message_probability=0.6,
            max_messages_per_turn=5,
        ),
        initial_context="Реальный клиент, нормальный темп общения",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
        stress_config=StressConfig(
            message_pattern=[("C", 3), ("A", 2), ("C", 2), ("A", 1)],
            inter_message_delays=[(5.0, 30.0), (30.0, 120.0)],  # Up to 2 min pauses
            message_delays=[(3.0, 8.0)],
            batch_sizes=[1],
            urgency_requests=[],
            timeout_multiplier=2.0,
        ),
    ),
]
"""
Complete list of 7 stress test scenarios for timing/pattern simulation.

Scenarios cover:
- Rapid message bursts (testing batching system)
- Slow responses (testing agent patience and follow-up)
- Urgency demands (testing priority handling)
- Mixed timing patterns (testing adaptability)
- Long messages (testing reading delay calculation)
- Interruption patterns (testing message aggregation)
- Realistic multi-message (testing natural Telegram behavior with long pauses)

All scenarios are in Russian and use challenging but realistic personas.
"""


# =============================================================================
# Helper Functions
# =============================================================================

def get_stress_scenario_by_name(name: str) -> StressScenario:
    """
    Get a stress scenario by its name (case-insensitive).

    Args:
        name: The name of the stress scenario to find.

    Returns:
        The matching StressScenario.

    Raises:
        ValueError: If no scenario with the given name is found.
    """
    for scenario in STRESS_SCENARIOS:
        if scenario.name.lower() == name.lower():
            return scenario
    raise ValueError(f"Stress scenario not found: {name}")


def get_stress_scenarios_by_difficulty(difficulty: str) -> list[StressScenario]:
    """
    Get all stress scenarios of a specified difficulty level.

    Args:
        difficulty: One of "easy", "medium", "hard", or "expert".

    Returns:
        List of StressScenario objects matching the difficulty.
    """
    return [
        scenario for scenario in STRESS_SCENARIOS
        if scenario.persona.difficulty == difficulty
    ]


def get_stress_scenario_names() -> list[str]:
    """
    Get a list of all stress scenario names.

    Returns:
        List of scenario name strings.
    """
    return [scenario.name for scenario in STRESS_SCENARIOS]


def get_scenarios_by_stress_type(stress_type: str) -> list[StressScenario]:
    """
    Get scenarios by their primary stress type.

    Args:
        stress_type: One of "timing", "content", or "pattern".
                    - timing: Rapid Fire Burst, Slow Responder
                    - content: Urgency Demand, Long Messages
                    - pattern: Mixed Timing, Interruption Pattern

    Returns:
        List of StressScenario objects matching the stress type.

    Raises:
        ValueError: If invalid stress type provided.
    """
    stress_type_mapping = {
        "timing": ["Rapid Fire Burst", "Slow Responder"],
        "content": ["Urgency Demand", "Long Messages"],
        "pattern": ["Mixed Timing", "Interruption Pattern", "Realistic Multi-Message"],
    }

    if stress_type not in stress_type_mapping:
        raise ValueError(
            f"Invalid stress type: {stress_type}. "
            f"Valid types: {list(stress_type_mapping.keys())}"
        )

    names = stress_type_mapping[stress_type]
    return [
        scenario for scenario in STRESS_SCENARIOS
        if scenario.name in names
    ]


def get_all_urgency_phrases() -> list[str]:
    """
    Get all urgency phrases from all scenarios.

    Returns:
        List of all unique urgency phrases.
    """
    all_phrases = []
    for scenario in STRESS_SCENARIOS:
        all_phrases.extend(scenario.stress_config.urgency_requests)
    return list(set(all_phrases))


# =============================================================================
# Module Self-Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Stress Scenarios Module - Self-Test")
    print("=" * 60)

    print(f"\nTotal stress scenarios: {len(STRESS_SCENARIOS)}")
    assert len(STRESS_SCENARIOS) == 7, f"Expected 7 scenarios, got {len(STRESS_SCENARIOS)}"

    medium = get_stress_scenarios_by_difficulty("medium")
    hard = get_stress_scenarios_by_difficulty("hard")

    print(f"\nDifficulty distribution:")
    print(f"  Medium: {len(medium)} (expected 3)")
    print(f"  Hard: {len(hard)} (expected 4)")

    assert len(medium) == 3, f"Expected 3 medium, got {len(medium)}"
    assert len(hard) == 4, f"Expected 4 hard, got {len(hard)}"

    timing = get_scenarios_by_stress_type("timing")
    content = get_scenarios_by_stress_type("content")
    pattern = get_scenarios_by_stress_type("pattern")

    print(f"\nStress type distribution:")
    print(f"  Timing: {len(timing)} (expected 2)")
    print(f"  Content: {len(content)} (expected 2)")
    print(f"  Pattern: {len(pattern)} (expected 3)")

    assert len(timing) == 2, f"Expected 2 timing, got {len(timing)}"
    assert len(content) == 2, f"Expected 2 content, got {len(content)}"
    assert len(pattern) == 3, f"Expected 3 pattern, got {len(pattern)}"

    print(f"\nLanguage check:")
    for scenario in STRESS_SCENARIOS:
        assert scenario.persona.language == "ru", \
            f"Scenario {scenario.name} should be Russian"
    print(f"  All {len(STRESS_SCENARIOS)} scenarios are in Russian: OK")

    print(f"\nAll scenarios:")
    for i, scenario in enumerate(STRESS_SCENARIOS, 1):
        config = scenario.stress_config
        outcome = scenario.expected_outcome.value if scenario.expected_outcome else "N/A"
        print(
            f"  {i}. {scenario.name} "
            f"({scenario.persona.difficulty}) "
            f"-> {outcome}"
        )

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
