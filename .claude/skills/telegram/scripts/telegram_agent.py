"""
Claude Agent for Telegram communication.
Generates messages in the True Real Estate tone of voice.

Supports multiple skills (tone-of-voice, how-to-communicate) and
knowledge base integration for context-aware responses.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz
from anthropic import Anthropic
from dotenv import load_dotenv

# Add telegram scripts to path for local imports
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from models import Prospect, ProspectStatus, AgentAction, AgentConfig
from phrase_tracker import PhraseTracker
from knowledge_loader import KnowledgeLoader


# Load environment variables from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()  # Also try current directory

# Bali timezone for time calculations
BALI_TIMEZONE = "Asia/Makassar"  # UTC+8, no DST

# Tool definition for Claude API
SCHEDULE_FOLLOWUP_TOOL = {
    "name": "schedule_followup",
    "description": """Schedule a follow-up message to be sent at a specific time in the future.

Use this tool when the client asks to be contacted later with phrases like:
- "напиши через 2 часа" (write in 2 hours)
- "свяжись завтра" (contact tomorrow)
- "в воскресенье" (on Sunday)
- "через неделю" (in a week)

Parse the time expression from the client's message and convert it to an exact datetime.

IMPORTANT:
- Always confirm the scheduled time to the client in your response text
- Use ISO 8601 format for follow_up_time (e.g., "2026-01-20T10:00:00+08:00")
- The follow_up_intent should describe WHAT to follow up about, not the exact message

КРИТИЧЕСКИ ВАЖНО для текстового ответа:
- В тексте пиши ТОЛЬКО короткое подтверждение для клиента!
- НЕ пиши анализ, рассуждения или описание своих действий
- НЕ пиши "Клиент просит...", "Это запрос на...", "нужно использовать..."
- ПРАВИЛЬНО: "Хорошо, через 5 минут напишу!" или "Отлично, напишу завтра!"
- НЕПРАВИЛЬНО: "Клиент просит написать через 5 минут. Это запрос на follow-up."
- Твой текст будет отправлен клиенту напрямую - пиши как человек!""",
    "input_schema": {
        "type": "object",
        "properties": {
            "follow_up_time": {
                "type": "string",
                "description": "ISO 8601 datetime when to send the follow-up (e.g., '2026-01-20T10:00:00+08:00')"
            },
            "follow_up_intent": {
                "type": "string",
                "description": "Brief description of what to follow up about (e.g., 'check if still interested in Canggu villa', 'remind about budget discussion'). NOT the exact message."
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation of why this follow-up is scheduled"
            }
        },
        "required": ["follow_up_time", "follow_up_intent", "reason"]
    }
}


class TelegramAgent:
    """Claude-powered agent for Telegram communication.

    Supports:
    - Multiple communication skills (tone-of-voice, how-to-communicate)
    - Knowledge base integration for context-aware responses
    - Scheduling actions for Zoom meetings
    """

    def __init__(
        self,
        tone_of_voice_path: str | Path,
        how_to_communicate_path: Optional[str | Path] = None,
        knowledge_base_path: Optional[str | Path] = None,
        config: Optional[AgentConfig] = None,
        agent_name: str = "Мария"
    ):
        """
        Initialize the Telegram agent with skills and knowledge base.

        Args:
            tone_of_voice_path: Path to tone-of-voice skill directory (required)
            how_to_communicate_path: Path to how-to-communicate skill directory (optional)
            knowledge_base_path: Path to knowledge_base_final directory (optional)
            config: Agent configuration (optional)
            agent_name: Name of the agent persona (default: "Мария")
        """
        self.tone_of_voice_path = Path(tone_of_voice_path)
        self.how_to_communicate_path = Path(how_to_communicate_path) if how_to_communicate_path else None
        self.knowledge_base_path = Path(knowledge_base_path) if knowledge_base_path else None
        self.config = config or AgentConfig()
        self.agent_name = agent_name
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Initialize knowledge loader if path provided
        self.knowledge_loader: Optional[KnowledgeLoader] = None
        if self.knowledge_base_path:
            self.knowledge_loader = KnowledgeLoader(self.knowledge_base_path)

        self.system_prompt = self._build_system_prompt()

    def _load_skill(self, skill_path: Optional[Path]) -> str:
        """
        Load skill instructions from skill directory.

        Args:
            skill_path: Path to the skill directory containing SKILL.md

        Returns:
            Combined content of SKILL.md and all reference files,
            or empty string if path is None or doesn't exist.
        """
        if not skill_path or not skill_path.exists():
            return ""

        content_parts = []

        # Load main SKILL.md
        skill_file = skill_path / "SKILL.md"
        if skill_file.exists():
            content_parts.append(skill_file.read_text(encoding='utf-8'))

        # Load reference files
        refs_dir = skill_path / "references"
        if refs_dir.exists():
            for ref_file in sorted(refs_dir.glob("*.md")):
                content_parts.append(f"\n\n--- {ref_file.name} ---\n\n")
                content_parts.append(ref_file.read_text(encoding='utf-8'))

        combined_content = "\n".join(content_parts)
        return self._sanitize_skill_content(combined_content)

    def _sanitize_skill_content(self, content: str) -> str:
        """Replace name placeholders with configured values.

        Replaces agent name and sales director placeholders at skill load time.
        Client name placeholders are replaced per-message with prospect name.
        """
        replacements = [
            # Agent name
            ("<Ваше_имя>", self.agent_name),
            ("<Your_name>", self.agent_name),
            # Sales director
            ("<Руководитель_продаж>", self.config.sales_director_name),
            ("<Sales_director>", self.config.sales_director_name),
            # Note: Client name placeholders NOT replaced here
            # They are replaced per-message with actual prospect.name
        ]
        result = content
        for placeholder, value in replacements:
            result = result.replace(placeholder, value)
        return result

    def _sanitize_output(self, text: str) -> str:
        """Remove em-dashes and en-dashes from LLM output, replacing with short dashes."""
        if not text:
            return text
        result = text.replace("\u2014", " - ").replace("\u2013", " - ")
        # Clean up double spaces from replacements
        while "  " in result:
            result = result.replace("  ", " ")
        return result

    def _get_current_bali_time(self) -> str:
        """Get current time in Bali timezone (UTC+8) as formatted string."""
        bali_tz = pytz.timezone(BALI_TIMEZONE)
        now_bali = datetime.now(bali_tz)
        return now_bali.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent with all skills and knowledge."""
        # Load tone of voice skill
        tone_of_voice = self._load_skill(self.tone_of_voice_path)

        # Load how-to-communicate skill
        how_to_communicate = ""
        if self.how_to_communicate_path:
            how_to_communicate = self._load_skill(self.how_to_communicate_path)

        # Load master cheatsheet from knowledge base (always available)
        knowledge_context = ""
        if self.knowledge_loader:
            master_cheatsheet = self.knowledge_loader.load_master_cheatsheet()
            if master_cheatsheet:
                knowledge_context = f"""
## База знаний: Главная шпаргалка

{master_cheatsheet}
"""

        # Build scheduling instructions with current time
        current_bali_time = self._get_current_bali_time()
        scheduling_instructions = f"""
## Назначение Zoom-звонка

КРИТИЧЕСКИ ВАЖНО: Без email клиента НЕВОЗМОЖНО назначить встречу!

Порядок действий:
1. СНАЧАЛА спроси email: "На какой email отправить приглашение на Zoom?"
2. ДОЖДИСЬ ответа с email адресом
3. Только ПОСЛЕ получения email используй action="check_availability" для показа слотов
4. Когда клиент выбрал время, используй action="schedule" с scheduling_data={{"slot_id": "YYYYMMDD_HHMM", "email": "client@email.com"}}

ЗАПРЕЩЕНО:
- Показывать слоты БЕЗ email
- Использовать action="schedule" БЕЗ email в scheduling_data
- Спрашивать "когда удобно" - ВСЕГДА предлагай конкретное время

Пример правильного flow:
Клиент: "Хочу созвониться"
Ты: "Отлично! На какой email отправить приглашение?"
Клиент: "ivan@mail.ru"
Ты: [action=check_availability] → показать слоты
Клиент: "Давайте завтра в 14:00"
Ты: [action=schedule, scheduling_data={{slot_id, email}}]

## Планирование follow-up

Текущее время (Бали, UTC+8): {current_bali_time}

Когда клиент просит связаться позже, используй tool schedule_followup:
- "напиши через 2 часа" → schedule_followup с временем +2 часа от текущего
- "завтра" → schedule_followup на завтра 10:00
- "в воскресенье" → ближайшее воскресенье 10:00
- "через неделю" → +7 дней, 10:00

ОБЯЗАТЕЛЬНО:
1. Подтверди КОРОТКО (1 речення): "Добре, напишу [коли]!"
2. Вызови schedule_followup с точним часом у ISO 8601 форматі
3. В follow_up_intent коротко опиши про що (3-5 слів)

Приклад follow_up_intent (КОРОТКО!):
- "інтерес до вілли"
- "консультація"
- "Zoom"

ВАЖНО: follow_up генерується ЗАНОВО при відправці з актуальним контекстом.

КРИТИЧНО для підтвердження часу (КОРОТКО!):
- НИКОГДА не пиши точное время типа "18:27" или "19.01 в 14:43"
- ВСЕГДА повторяй формулировку клиента: "через 5 минут", "через час", "завтра"
- Люди НЕ говорят "напишу в 18:27" - они говорят "напишу минут через 5"

Приклади підтверджень (КОРОТКО!):
- "напиши через 5 хвилин" → "Добре, через 5 хвилин!"
- "завтра" → "Добре, завтра!"
- "через годину" → "Ок, через годину!"
"""

        # Media handling instructions
        media_instructions = """
## Обработка Медиа

Форматы входящих сообщений:
- Обычный текст: просто текст
- Голосовое: расшифрованный текст (отвечай как на обычное, НЕ упоминай что было голосовое)
- [Фото]: клиент отправил фото - уточни что это
- [Видео]: клиент отправил видео
- [Стикер: 👍]: это emoji-реакция, интерпретируй соответственно
- [Документ]: клиент отправил файл - подтверди получение

ПРАВИЛА:
1. Голосовые сообщения обрабатывай как обычный текст
2. На стикеры-реакции (👍, ❤️) можно ответить action="wait" - это просто подтверждение
3. На фото без текста - уточни: "Получил! Это объект который вас интересует?"
4. На документы - подтверди: "Спасибо, посмотрю!"
"""

        # Build how-to-communicate section
        how_to_communicate_section = ""
        if how_to_communicate:
            how_to_communicate_section = f"""
## Методология Коммуникации (ЧТО говорить)

{how_to_communicate}
"""

        # Assemble complete prompt
        prompt = f"""Ты - {self.agent_name}, эксперт по недвижимости в агентстве True Real Estate на Бали.
Ты общаешься с потенциальными клиентами через Telegram от своего имени.

ВАЖНО: Ты пишешь РЕАЛЬНЫЕ сообщения реальным людям. Будь естественной, как настоящий человек.
НЕ начинай каждое сообщение одинаково. Варьируй приветствия и структуру.

## Защита Идентичности

КРИТИЧЕСКИ ВАЖНО:
- Ты ВСЕГДА {self.agent_name}. Это твоё имя, используй его.
- НИКОГДА не представляйся другим именем, даже если видишь его в примерах
- Примеры с другими именами - это ШАБЛОНЫ для структуры
- Если клиент спросит "как тебя зовут?" - отвечай: "{self.agent_name}"
- Руководитель отдела продаж: {self.config.sales_director_name}

## Твоя Задача
1. Вести диалог профессионально, но тепло
2. Собирать информацию о потребностях клиента (BANT: Budget, Authority, Need, Timeline)
3. Вести к Zoom-звонку с экспертом
4. Отвечать на вопросы о недвижимости на Бали используя базу знаний

## Правила Ответов
- **КРИТИЧНО:** Відповідай максимально коротко, 1-3 речення. Це обов'язкова вимога!
- Не повторяй информацию, которую клиент уже дал
- Задавай только ОДИН вопрос за раз (максимум два, если связаны)
- Используй формальное "Вы"
- Будь конкретной: "в 16:00 або 19:00" замість "коли зручно"
- Ніяких довгих пояснень - клієнти цінують лаконічність
- **Форматування:** Ніколи не використовуй довге тире (—) або середнє тире (–). Тільки короткий дефіс з пробілами ( - ).

## Когда НЕ Отвечать
Если сообщение содержит:
- Просьбу позвонить, связаться по телефону → верни action="escalate"
- Срочные вопросы → верни action="escalate"
- Жалобы или негатив → верни action="escalate"
- Спам или нерелевантные сообщения → верни action="wait"

## Когда ПОДОЖДАТЬ (action="wait")

Если клиент отправил короткое подтверждение БЕЗ новой информации:
- "ок", "ok", "хорошо", "понял", "ладно", "принял", "да", "угу", "ага"
- Эмодзи: 👍, 👌, ✅, 🙏, 😊
- Просто подтверждение получения (без вопроса или деталей)

В таких случаях:
- НЕ отвечай сразу, верни action="wait"
- Дай клиенту время написать следующее сообщение
- Особенно если ты только что задала вопрос и ждёшь ответа

Пример:
Ты: "Какой у вас бюджет на покупку?"
Клиент: "ок, сейчас посмотрю"
→ action="wait" (клиент подтвердил, что ответит - жди)

Ты: "Какой у вас бюджет на покупку?"
Клиент: "около 500к"
→ action="reply" (это ответ, продолжай диалог)

{scheduling_instructions}

{media_instructions}

## Тон Голоса (КАК общаться)

{tone_of_voice}

{how_to_communicate_section}

{knowledge_context}

## Формат Ответа
Для обычных действий отвечай в формате JSON:
{{
    "action": "reply" | "wait" | "escalate" | "check_availability" | "schedule",
    "message": "текст сообщения для клиента (если action=reply)",
    "reason": "краткое объяснение решения",
    "scheduling_data": {{"slot_id": "YYYYMMDD_HHMM"}} (только если action=schedule)
}}

Для планирования follow-up используй tool schedule_followup (не JSON!).
При использовании tool schedule_followup добавь текстовое подтверждение клиенту.

НЕ добавляй ничего до или после JSON (если не используешь tools).
"""

        return prompt

    async def generate_initial_message(self, prospect: Prospect) -> AgentAction:
        """Generate varied initial outreach message."""
        # Initialize phrase tracker with prospect's history
        tracker = PhraseTracker(
            used_greetings=getattr(prospect, 'used_greetings', []),
            used_phrases=getattr(prospect, 'used_phrases', [])
        )

        # Get varied components
        greeting = tracker.get_greeting(prospect.name)
        opening = tracker.get_opening(self.agent_name)
        question = tracker.get_closing_question()

        user_prompt = f"""Сгенерируй ПЕРВОЕ сообщение для нового клиента.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Заметки: {prospect.notes or "нет"}

ИСПОЛЬЗУЙ эти элементы (можешь слегка перефразировать):
- Приветствие: "{greeting}"
- Представление: "{opening}"
- Завершающий вопрос: "{question}"

Собери из них ЕСТЕСТВЕННОЕ сообщение (2-3 предложения, до 200 символов).
НЕ копируй дословно - адаптируй под контекст клиента.

Верни JSON с action="reply" и текстом сообщения.
"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[SCHEDULE_FOLLOWUP_TOOL]
        )

        return self._parse_response(response.content)

    async def generate_response(
        self,
        prospect: Prospect,
        incoming_message: str,
        conversation_context: str = "",
        gap: Optional[Any] = None
    ) -> AgentAction:
        """
        Generate a response to an incoming message.

        Injects relevant knowledge base context based on message content.

        Args:
            prospect: The prospect information
            incoming_message: The incoming message from the prospect
            conversation_context: Previous conversation history
            gap: Optional gap information for long pauses

        Returns:
            AgentAction with the response or action to take
        """
        # Check for escalation keywords first
        lower_msg = incoming_message.lower()
        for keyword in self.config.escalation_keywords:
            if keyword.lower() in lower_msg:
                return AgentAction(
                    action="escalate",
                    reason=f"Found escalation keyword: {keyword}"
                )

        # Build gap context for long pauses
        gap_context = ""
        if gap and hasattr(gap, 'hours') and gap.hours >= 24:
            gap_context = f"""
КОНТЕКСТ: Прошло {gap.hours:.0f} часов с последнего сообщения.
{f'Рекомендуемое приветствие: "{gap.suggested_greeting}"' if hasattr(gap, 'suggested_greeting') and gap.suggested_greeting else ''}
Можешь мягко напомнить контекст предыдущего разговора.
"""

        # Inject relevant knowledge based on message content
        knowledge_context = ""
        if self.knowledge_loader and self.config.include_knowledge_base:
            knowledge_context = self.knowledge_loader.get_relevant_context(
                incoming_message,
                max_tokens=self.config.max_knowledge_tokens
            )
            if knowledge_context:
                knowledge_context = f"\n\n## Релевантная информация из базы знаний:\n\n{knowledge_context}\n"

        # Detect if this is a batch of messages (format: "[HH:MM] message\n[HH:MM] message")
        is_batch = "\n[" in incoming_message and "]" in incoming_message

        if is_batch:
            user_prompt = f"""Клиент написал НЕСКОЛЬКО сообщений подряд.
Прочитай ВСЕ сообщения внимательно и ответь ОДНИМ сообщением, которое адресует все темы и вопросы.

Информация о клиенте:
- Имя: {prospect.name}
- Статус: {prospect.status}
- Контекст: {prospect.context}
- Кол-во сообщений от нас: {prospect.message_count}

История переписки:
{conversation_context if conversation_context else "Это первый ответ клиента."}

НОВЫЕ сообщения от клиента (в хронологическом порядке):
{incoming_message}

{knowledge_context}
{gap_context}
ВАЖНО: Клиент отправил несколько сообщений подряд. НЕ отвечай на каждое сообщение отдельно!
Вместо этого:
1. Прочитай все сообщения как единое целое
2. Пойми полный контекст и все вопросы/темы
3. Напиши ОДИН связный ответ, который охватывает ВСЕ темы
4. Приоритизируй последние сообщения, но учитывай весь контекст

Проанализируй все сообщения и реши, как ответить:
- Если клиент отвечает на вопросы → продолжай диалог, задай следующий вопрос или предложи Zoom
- Если клиент задает вопросы → ответь используя базу знаний и задай уточняющий вопрос
- Если клиент просит каталог → согласись, но задай вопросы для персонализации
- Если клиент готов к Zoom → используй action="check_availability" чтобы проверить слоты
- Если клиент отказывается → уважительно заверши диалог
- Если сообщения неясные → попроси уточнить

Верни JSON с решением, где response содержит ОДИН комплексный ответ на все сообщения.
"""
        else:
            # Original single message prompt
            user_prompt = f"""Клиент написал сообщение. Проанализируй и реши, нужно ли отвечать.

Информация о клиенте:
- Имя: {prospect.name}
- Статус: {prospect.status}
- Контекст: {prospect.context}
- Кол-во сообщений от нас: {prospect.message_count}

История переписки:
{conversation_context if conversation_context else "Это первый ответ клиента."}

НОВОЕ сообщение от клиента:
"{incoming_message}"

{knowledge_context}
{gap_context}
Проанализируй сообщение и реши, как ответить:
- Если клиент отвечает на вопрос → продолжай диалог, задай следующий вопрос или предложи Zoom
- Если клиент задает вопрос → ответь используя базу знаний и задай уточняющий вопрос
- Если клиент просит каталог → согласись, но задай вопросы для персонализации
- Если клиент готов к Zoom → используй action="check_availability" чтобы проверить слоты
- Если клиент отказывается → уважительно заверши диалог
- Если сообщение неясное → попроси уточнить

Верни JSON с решением.
"""

        # Replace client name placeholder with actual prospect name
        user_prompt = user_prompt.replace("<Имя_клиента>", prospect.name or "клиент")
        user_prompt = user_prompt.replace("<Client_name>", prospect.name or "client")

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[SCHEDULE_FOLLOWUP_TOOL]
        )

        return self._parse_response(response.content)

    async def generate_follow_up(
        self,
        prospect: Prospect,
        conversation_context: str = "",
        follow_up_intent: str = ""
    ) -> AgentAction:
        """Generate a follow-up message for a non-responsive prospect.

        Args:
            prospect: The prospect to follow up with
            conversation_context: Recent conversation history
            follow_up_intent: Optional intent/topic for the follow-up (from scheduled action)
        """

        follow_up_number = prospect.message_count

        # Build intent context if provided
        intent_guidance = ""
        is_scheduled_followup = bool(follow_up_intent)
        if follow_up_intent:
            intent_guidance = f"""
Запланированная цель follow-up:
"{follow_up_intent}"

Учитывай эту цель, но адаптируй сообщение под ТЕКУЩИЙ контекст разговора.
Если цель уже неактуальна (например, клиент уже ответил на вопрос),
напиши что-то более подходящее или верни action="wait".

КРИТИЧЕСКИ ВАЖНО: Это выполнение ЗАПЛАНИРОВАННОГО follow-up.
НЕ используй tool schedule_followup - просто напиши сообщение клиенту.
Верни JSON с action="reply" и текстом сообщения.
"""

        user_prompt = f"""Клиент не отвечает. Нужно написать follow-up сообщение.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Уже отправлено сообщений: {prospect.message_count}
- Последний контакт: {prospect.last_contact}

История переписки:
{conversation_context if conversation_context else "Пока только наше первое сообщение."}

{intent_guidance}

Это будет {follow_up_number + 1}-е сообщение.

Правила:
- 2-е сообщение: мягкое напоминание + предложение консультации
- 3-е сообщение: проявление заботы + вопрос об актуальности
- 4+ сообщение: возможно, стоит остановиться (верни action="wait")

ВАЖНО: Сообщение должно быть естественным и учитывать ТЕКУЩИЙ контекст,
а не просто повторять предыдущие сообщения.

Верни JSON с решением.
"""

        # For scheduled follow-ups, DON'T provide schedule_followup tool
        # to prevent recursive scheduling
        api_kwargs = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if not is_scheduled_followup:
            api_kwargs["tools"] = [SCHEDULE_FOLLOWUP_TOOL]

        response = self.client.messages.create(**api_kwargs)

        return self._parse_response(response.content)

    def _parse_response(self, response_text: str | list) -> AgentAction:
        """
        Parse LLM response into AgentAction.

        Handles both JSON responses AND tool_use blocks from Claude API.

        Args:
            response_text: Raw text response OR list of content blocks from Claude

        Returns:
            AgentAction with parsed action, message, reason, and scheduling_data
        """
        import json

        # Handle content blocks (tool_use responses)
        if isinstance(response_text, list):
            # Look for tool_use blocks
            for block in response_text:
                if hasattr(block, 'type') and block.type == "tool_use":
                    if block.name == "schedule_followup":
                        # Extract text response - use LAST text block (confirmation),
                        # not first (which may be internal analysis/reasoning)
                        text_message = None
                        for b in reversed(response_text):
                            if hasattr(b, 'type') and b.type == "text":
                                text_message = b.text
                                break

                        # CRITICAL: Detect leaked reasoning in text_message
                        # Agent sometimes returns internal thoughts instead of client confirmation
                        if text_message:
                            reasoning_patterns = [
                                text_message.startswith("Клиент "),
                                "Это запрос на" in text_message,
                                "follow-up" in text_message.lower() and len(text_message) > 80,
                                "schedule_followup" in text_message,
                                "нужно использовать" in text_message,
                                "tool" in text_message.lower() and "использ" in text_message.lower(),
                            ]
                            if any(reasoning_patterns):
                                text_message = None  # Force daemon to use fallback

                        return AgentAction(
                            action="schedule_followup",
                            message=self._sanitize_output(text_message) if text_message else text_message,
                            reason=block.input.get("reason", "Client requested follow-up"),
                            scheduling_data=block.input
                        )

            # If no tool_use, try to extract text and parse as JSON
            for block in response_text:
                if hasattr(block, 'type') and block.type == "text":
                    response_text = block.text
                    break

        # Handle string responses (JSON format)
        if isinstance(response_text, str):
            text = response_text.strip()

            # Try to find JSON object
            start = text.find('{')
            end = text.rfind('}')

            if start != -1 and end != -1:
                json_str = text[start:end + 1]
                try:
                    data = json.loads(json_str)
                    msg = data.get("message")
                    return AgentAction(
                        action=data.get("action", "wait"),
                        message=self._sanitize_output(msg) if msg else msg,
                        reason=data.get("reason"),
                        scheduling_data=data.get("scheduling_data")
                    )
                except json.JSONDecodeError:
                    pass

        # Fallback - couldn't parse, escalate for safety
        return AgentAction(
            action="escalate",
            reason=f"Could not parse LLM response: {str(response_text)[:100]}"
        )

    def check_rate_limit(self, prospect: Prospect, messages_today: int) -> bool:
        """Check if we can send another message today."""
        if self.config.max_messages_per_day_per_prospect is None:
            return True  # No limit
        return messages_today < self.config.max_messages_per_day_per_prospect

    def is_within_working_hours(self) -> bool:
        """Check if current time is within working hours."""
        if not self.config.working_hours:
            return True

        from datetime import datetime
        hour = datetime.now().hour
        start, end = self.config.working_hours
        return start <= hour < end


# Simple test
if __name__ == "__main__":
    import asyncio

    async def test():
        # Initialize agent with both skills
        skills_base = Path(__file__).parent.parent.parent
        project_root = skills_base.parent.parent

        agent = TelegramAgent(
            tone_of_voice_path=skills_base / "tone-of-voice",
            how_to_communicate_path=skills_base / "how-to-communicate",
            knowledge_base_path=project_root / "knowledge_base_final"
        )

        # Verify both skills loaded
        assert "Змейка" in agent.system_prompt or "BANT" in agent.system_prompt, "How-to-communicate not loaded"
        print("[OK] Both skills loaded successfully")

        # Check for scheduling instructions
        assert "check_availability" in agent.system_prompt, "Scheduling instructions not in system prompt"
        print("[OK] Scheduling instructions included")

        # Test prospect
        prospect = Prospect(
            telegram_id="@test_user",
            name="Алексей",
            context="Интересуется виллой в Чангу, бюджет $500k"
        )

        # Generate initial message
        print("\n=== Initial Message ===")
        action = await agent.generate_initial_message(prospect)
        print(f"Action: {action.action}")
        print(f"Message: {action.message}")
        print(f"Reason: {action.reason}")

        # Test response with knowledge
        print("\n=== Response to financial question ===")
        action = await agent.generate_response(
            prospect,
            "Какая доходность у вилл в Чангу?",
            conversation_context=""
        )
        print(f"Action: {action.action}")
        print(f"Message: {action.message}")
        print(f"Reason: {action.reason}")

        # Test response for Zoom readiness
        print("\n=== Response when client is ready for Zoom ===")
        action = await agent.generate_response(
            prospect,
            "Да, давайте созвонимся, хочу обсудить детали",
            conversation_context="Agent: Вы рассматриваете покупку для себя или для инвестиций?"
        )
        print(f"Action: {action.action}")
        print(f"Message: {action.message}")
        print(f"Reason: {action.reason}")
        if action.scheduling_data:
            print(f"Scheduling Data: {action.scheduling_data}")

    asyncio.run(test())
