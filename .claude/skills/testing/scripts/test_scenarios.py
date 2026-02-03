"""
Test Scenarios for Telegram Agent Conversation Simulation.

This module defines 10 challenging persona scenarios for testing the TelegramAgent's
conversation skills across different difficulty levels and client types.

Scenarios range from easy (testing escalation triggers) to expert (insider market knowledge),
covering various objection patterns, communication styles, and expected outcomes.

Difficulty Distribution:
- Easy: 1 scenario
- Medium: 3 scenarios
- Hard: 5 scenarios
- Expert: 1 scenario

Language Distribution:
- Russian: 9 scenarios
- English: 1 scenario
"""

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
# SCENARIOS - 10 Challenging Test Personas
# =============================================================================

SCENARIOS: list[ConversationScenario] = [
    # =========================================================================
    # Scenario 1: Skeptical Financist (HARD)
    # Professional investor demanding ROI data before any engagement
    # =========================================================================
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
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 2: Catalog Requester (HARD)
    # Wants materials only, refuses calls, tests agent persistence
    # =========================================================================
    ConversationScenario(
        name="Catalog Requester",
        persona=PersonaDefinition(
            name="Марина Каталожница",
            description="""Типичный лид, который хочет только каталог и отказывается
            от любых звонков. Привыкла получать информацию самостоятельно.
            Не доверяет продажникам, считает что ее "разведут".""",
            difficulty="hard",
            traits=[
                "Постоянно просит скинуть каталог/PDF/презентацию",
                "Отказывается от Zoom под любым предлогом",
                "Говорит 'я сама посмотрю и напишу если заинтересует'",
                "Не отвечает на вопросы о бюджете и сроках",
                "Подозревает манипуляции в любом предложении",
            ],
            objections=[
                "Просто скиньте каталог, я сама разберусь",
                "Не хочу созваниваться, мне неудобно",
                "Я не готова к разговору, дайте материалы",
                "Зачем мне Zoom если можно просто прислать PDF?",
                "Я занята, некогда созваниваться",
            ],
            goal="refuse_zoom_want_catalog_only",
            language="ru",
        ),
        initial_context="Оставила заявку на сайте, указала 'хочу каталог'",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 3: After the War Deferred (MEDIUM)
    # Ukrainian, emotional timing objection about investing during war
    # =========================================================================
    ConversationScenario(
        name="After the War Deferred",
        persona=PersonaDefinition(
            name="Олег Украинец",
            description="""Украинец, эмоционально реагирует на предложение инвестировать
            во время войны. Считает неуместным думать о Бали когда дома война.
            Но при этом понимает важность диверсификации.""",
            difficulty="medium",
            traits=[
                "Эмоционально реагирует на тему инвестиций во время войны",
                "Говорит 'куплю после войны'",
                "Внутренне понимает важность сохранения капитала",
                "Может быть переубежден фактами о других украинцах",
                "Ценит эмпатию и понимание ситуации",
            ],
            objections=[
                "Сейчас не время думать о Бали, у нас война",
                "Куплю после войны, когда всё успокоится",
                "Как можно инвестировать когда страна воюет?",
                "Деньги нужны здесь, а не на острове",
            ],
            goal="may_zoom_after_empathy_and_facts",
            language="ru",
        ),
        initial_context="Заявка из таргетированной рекламы на Украину",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 4: Leasehold Skeptic (HARD)
    # Legally savvy, distrusts leasehold, wants freehold only
    # =========================================================================
    ConversationScenario(
        name="Leasehold Skeptic",
        persona=PersonaDefinition(
            name="Андрей Юрист",
            description="""Юридически подкованный клиент, который не понимает и не доверяет
            leasehold. Хочет только freehold/"настоящую собственность".
            Знает про риски в Индонезии и боится потерять деньги.""",
            difficulty="hard",
            traits=[
                "Категорически против leasehold",
                "Знает юридическую терминологию",
                "Спрашивает про Hak Pakai, Hak Milik, IMB",
                "Боится что через 30 лет всё отберут",
                "Сравнивает с европейской недвижимостью",
            ],
            objections=[
                "Leasehold это не собственность, это аренда",
                "Через 30 лет землю заберут обратно",
                "В Европе за эти деньги можно купить квартиру в собственность",
                "А если застройщик обанкротится? Кто продлит аренду?",
                "Законы в Индонезии могут измениться",
            ],
            goal="may_zoom_after_legal_clarification",
            language="ru",
        ),
        initial_context="Нашел через поиск Google, искал 'недвижимость Бали риски'",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 5: Price Haggler (MEDIUM)
    # Asks for discounts, compares prices, wants best deal
    # =========================================================================
    ConversationScenario(
        name="Price Haggler",
        persona=PersonaDefinition(
            name="Виктор Торговец",
            description="""Клиент, который всегда торгуется и ищет скидки.
            Сравнивает цены с другими агентствами и застройщиками напрямую.
            Хочет получить лучшую цену любой ценой.""",
            difficulty="medium",
            traits=[
                "Постоянно спрашивает про скидки",
                "Говорит что у конкурентов дешевле",
                "Просит скинуть комиссию",
                "Торгуется на каждом этапе",
                "Ищет эксклюзивные условия",
            ],
            objections=[
                "Можно скидку за счет вашей комиссии?",
                "У другого агента этот же объект дешевле на 5%",
                "Если куплю напрямую у застройщика будет дешевле?",
                "Что вы можете предложить мне особенного?",
                "Готов купить сегодня если дадите хорошую цену",
            ],
            goal="zoom_for_exclusive_offer",
            language="ru",
        ),
        initial_context="Перешел с YouTube канала, смотрел обзоры объектов",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 6: Bali Insider (EXPERT)
    # Lives on Bali, knows market inside-out, tests agent knowledge
    # =========================================================================
    ConversationScenario(
        name="Bali Insider",
        persona=PersonaDefinition(
            name="Дмитрий Балиец",
            description="""Уже живет на Бали 3+ года, знает рынок изнутри.
            Знает застройщиков, цены, локации. Проверяет компетентность агента.
            Имеет собственную сеть контактов на острове.""",
            difficulty="expert",
            traits=[
                "Называет конкретные районы и проекты по имени",
                "Знает реальные цены и заполняемость",
                "Имеет контакты застройщиков напрямую",
                "Проверяет агента на знание рынка",
                "Задает провокационные вопросы про конкретные объекты",
            ],
            objections=[
                "Я знаю этот проект, он уже год как задерживается",
                "У меня друг купил напрямую дешевле на 20%",
                "В Чангу уже перегрет рынок, все знают",
                "Этот застройщик кинул инвесторов в прошлом проекте",
                "Зачем мне агент если я сам на острове?",
            ],
            goal="zoom_only_if_agent_proves_value",
            language="ru",
        ),
        initial_context="Живет в Чангу, получил рекомендацию от знакомого",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 7: Phone Request Escalation (EASY)
    # Tests escalation trigger when client requests phone call
    # =========================================================================
    ConversationScenario(
        name="Phone Request Escalation",
        persona=PersonaDefinition(
            name="Сергей Звонок",
            description="""Клиент который сразу просит позвонить по телефону.
            Не любит переписку, хочет живой разговор голосом.
            Настаивает на звонке вместо Zoom.""",
            difficulty="easy",
            traits=[
                "Сразу просит номер телефона",
                "Не любит долгую переписку",
                "Хочет услышать живой голос",
                "Готов к разговору прямо сейчас",
            ],
            objections=[
                "Позвоните мне лучше, так удобнее",
                "Давайте по телефону поговорим",
                "Не люблю переписку, можно голосом?",
                "Скиньте номер, я сам перезвоню",
            ],
            goal="wants_phone_call_escalation",
            language="ru",
        ),
        initial_context="Звонок на горячую линию, попросили написать в Telegram",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ESCALATED,
    ),

    # =========================================================================
    # Scenario 8: Silent Treatment (HARD)
    # Minimal responses, tests agent's follow-up skills
    # =========================================================================
    ConversationScenario(
        name="Silent Treatment",
        persona=PersonaDefinition(
            name="Игорь Молчун",
            description="""Клиент который отвечает односложно или вообще не отвечает.
            Читает сообщения но долго думает. Не дает обратной связи.
            Может внезапно согласиться если агент не давит.""",
            difficulty="hard",
            traits=[
                "Отвечает односложно: 'ок', 'понял', 'посмотрю'",
                "Долгие паузы между ответами",
                "Не задает вопросов сам",
                "Читает но не отвечает (seen без ответа)",
                "Внезапно может согласиться или отказать",
            ],
            objections=[
                "Ок",
                "Понял",
                "Подумаю",
                "Позже напишу",
                "...",
            ],
            goal="may_zoom_if_not_pressured",
            language="ru",
        ),
        initial_context="Подписался на канал, ответил на вопрос в директ",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.FOLLOW_UP_PROPOSED,
    ),

    # =========================================================================
    # Scenario 9: Rapid Fire Questions (HARD)
    # Sends 3-4 questions per message, tests agent's ability to handle
    # =========================================================================
    ConversationScenario(
        name="Rapid Fire Questions",
        persona=PersonaDefinition(
            name="Анна Вопрос",
            description="""Клиент который задает много вопросов сразу в одном сообщении.
            Хочет получить всю информацию быстро. Нетерпелива, ценит скорость.
            Если агент отвечает не на все вопросы - раздражается.""",
            difficulty="hard",
            traits=[
                "Задает 3-4 вопроса в одном сообщении",
                "Нетерпелива, хочет быстрых ответов",
                "Раздражается если пропустили вопрос",
                "Переспрашивает если ответ неполный",
                "Ценит структурированные ответы",
            ],
            objections=[
                "Так какая доходность? И какой минимальный вход? И в какой валюте расчет? И есть ли рассрочка?",
                "Вы не ответили на мой второй вопрос про налоги",
                "Слишком долго, можно короче и по делу?",
                "Еще вопрос: а как с визой? И налоги в России платить? И можно ли продать потом?",
            ],
            goal="zoom_for_structured_answers",
            language="ru",
        ),
        initial_context="Реферал от друга который уже купил виллу",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),

    # =========================================================================
    # Scenario 10: English Speaker (MEDIUM)
    # Singapore investor, English language, different cultural context
    # =========================================================================
    ConversationScenario(
        name="English Speaker",
        persona=PersonaDefinition(
            name="James Chen",
            description="""Singaporean investor looking to diversify portfolio into Bali.
            Speaks English only, familiar with property investment in SEA region.
            Professional, expects high service standards and clear communication.""",
            difficulty="medium",
            traits=[
                "Professional business communication style",
                "Familiar with SEA property markets",
                "Compares Bali with Phuket and Koh Samui",
                "Asks about management company and ROI guarantees",
                "Values transparency and detailed information",
            ],
            objections=[
                "Why Bali over Phuket? Thailand has better infrastructure",
                "What's the guaranteed yield? I need numbers",
                "How do I verify the developer's track record?",
                "Is there an English-speaking management company?",
                "What about currency risk with IDR?",
            ],
            goal="zoom_for_professional_presentation",
            language="en",
        ),
        initial_context="LinkedIn connection, saw post about Bali investment",
        agent_initiates=True,
        expected_outcome=ConversationOutcome.ZOOM_SCHEDULED,
    ),
]
"""
Complete list of 10 test scenarios for conversation simulation.

Scenarios cover:
- Different difficulty levels (easy, medium, hard, expert)
- Various objection patterns (financial, legal, emotional, practical)
- Different communication styles (verbose, silent, rapid-fire)
- Both Russian and English languages
- Multiple expected outcomes (scheduled, escalated, follow-up)
"""


# =============================================================================
# Helper Functions
# =============================================================================

def get_scenario_by_name(name: str) -> ConversationScenario:
    """
    Get a scenario by its name (case-insensitive).

    Args:
        name: The name of the scenario to find.

    Returns:
        The matching ConversationScenario.

    Raises:
        ValueError: If no scenario with the given name is found.

    Example:
        >>> scenario = get_scenario_by_name("Skeptical Financist")
        >>> scenario.persona.difficulty
        'hard'
    """
    for scenario in SCENARIOS:
        if scenario.name.lower() == name.lower():
            return scenario
    raise ValueError(f"Scenario not found: {name}")


def get_scenarios_by_difficulty(difficulty: str) -> list[ConversationScenario]:
    """
    Get all scenarios of a specified difficulty level.

    Args:
        difficulty: One of "easy", "medium", "hard", or "expert".

    Returns:
        List of ConversationScenario objects matching the difficulty.

    Example:
        >>> hard_scenarios = get_scenarios_by_difficulty("hard")
        >>> len(hard_scenarios)
        5
    """
    return [
        scenario for scenario in SCENARIOS
        if scenario.persona.difficulty == difficulty
    ]


def get_scenarios_by_language(language: str) -> list[ConversationScenario]:
    """
    Get all scenarios of a specified language.

    Args:
        language: Either "ru" for Russian or "en" for English.

    Returns:
        List of ConversationScenario objects matching the language.

    Example:
        >>> english_scenarios = get_scenarios_by_language("en")
        >>> len(english_scenarios)
        1
    """
    return [
        scenario for scenario in SCENARIOS
        if scenario.persona.language == language
    ]


def get_scenario_names() -> list[str]:
    """
    Get a list of all scenario names.

    Returns:
        List of scenario name strings.

    Example:
        >>> names = get_scenario_names()
        >>> "Skeptical Financist" in names
        True
    """
    return [scenario.name for scenario in SCENARIOS]


# =============================================================================
# Module Self-Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Test Scenarios Module - Self-Test")
    print("=" * 60)

    # Verify SCENARIOS count
    print(f"\nTotal scenarios: {len(SCENARIOS)}")
    assert len(SCENARIOS) == 10, f"Expected 10 scenarios, got {len(SCENARIOS)}"

    # Verify difficulty distribution
    easy = get_scenarios_by_difficulty("easy")
    medium = get_scenarios_by_difficulty("medium")
    hard = get_scenarios_by_difficulty("hard")
    expert = get_scenarios_by_difficulty("expert")

    print(f"\nDifficulty distribution:")
    print(f"  Easy: {len(easy)} (expected 1)")
    print(f"  Medium: {len(medium)} (expected 3)")
    print(f"  Hard: {len(hard)} (expected 5)")
    print(f"  Expert: {len(expert)} (expected 1)")

    assert len(easy) == 1, f"Expected 1 easy, got {len(easy)}"
    assert len(medium) == 3, f"Expected 3 medium, got {len(medium)}"
    assert len(hard) == 5, f"Expected 5 hard, got {len(hard)}"
    assert len(expert) == 1, f"Expected 1 expert, got {len(expert)}"

    # Verify language distribution
    russian = get_scenarios_by_language("ru")
    english = get_scenarios_by_language("en")

    print(f"\nLanguage distribution:")
    print(f"  Russian: {len(russian)} (expected 9)")
    print(f"  English: {len(english)} (expected 1)")

    assert len(russian) == 9, f"Expected 9 Russian, got {len(russian)}"
    assert len(english) == 1, f"Expected 1 English, got {len(english)}"

    # Verify helper functions
    print(f"\nTesting helper functions:")

    try:
        scenario = get_scenario_by_name("Skeptical Financist")
        print(f"  get_scenario_by_name('Skeptical Financist'): OK")
    except ValueError:
        print(f"  get_scenario_by_name('Skeptical Financist'): FAILED")

    try:
        get_scenario_by_name("NonExistent")
        print(f"  get_scenario_by_name('NonExistent'): FAILED (should raise)")
    except ValueError:
        print(f"  get_scenario_by_name('NonExistent'): OK (raised ValueError)")

    # Print all scenarios
    print(f"\nAll scenarios:")
    for i, scenario in enumerate(SCENARIOS, 1):
        outcome = scenario.expected_outcome.value if scenario.expected_outcome else "N/A"
        print(
            f"  {i}. {scenario.name} "
            f"({scenario.persona.difficulty}, {scenario.persona.language}) "
            f"-> {outcome}"
        )

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
