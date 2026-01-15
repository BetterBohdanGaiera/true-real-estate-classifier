"""
Claude Agent for Telegram communication.
Generates messages in the True Real Estate tone of voice.

Supports multiple skills (tone-of-voice, how-to-communicate) and
knowledge base integration for context-aware responses.
"""
import os
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from models import Prospect, ProspectStatus, AgentAction, AgentConfig
from knowledge_loader import KnowledgeLoader


# Load environment variables from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()  # Also try current directory


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

        return "\n".join(content_parts)

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

        # Build scheduling instructions
        scheduling_instructions = """
## Назначение Zoom-звонка

Когда клиент готов к звонку или вы собрали BANT:
- Предложи конкретные слоты: "Завтра в 14:00 или 16:00?"
- Используй action="check_availability" чтобы проверить свободные слоты
- Когда клиент выбрал время, используй action="schedule" с scheduling_data={"slot_id": "YYYYMMDD_HHMM"}

Важно: ВСЕГДА предлагай конкретные даты и время, не спрашивай "когда вам удобно".
"""

        # Build how-to-communicate section
        how_to_communicate_section = ""
        if how_to_communicate:
            how_to_communicate_section = f"""
## Методология Коммуникации (ЧТО говорить)

{how_to_communicate}
"""

        # Assemble complete prompt
        prompt = f"""Ты — {self.agent_name}, эксперт по недвижимости в агентстве True Real Estate на Бали.
Ты общаешься с потенциальными клиентами через Telegram от своего имени.

ВАЖНО: Ты пишешь РЕАЛЬНЫЕ сообщения реальным людям. Будь естественной, как настоящий человек.
НЕ начинай каждое сообщение одинаково. Варьируй приветствия и структуру.

## Твоя Задача
1. Вести диалог профессионально, но тепло
2. Собирать информацию о потребностях клиента (BANT: Budget, Authority, Need, Timeline)
3. Вести к Zoom-звонку с экспертом
4. Отвечать на вопросы о недвижимости на Бали используя базу знаний

## Правила Ответов
- Отвечай КОРОТКО и по делу (2-5 предложений обычно достаточно)
- Не повторяй информацию, которую клиент уже дал
- Задавай только ОДИН вопрос за раз (максимум два, если связаны)
- Используй формальное "Вы"
- Будь конкретной: "в 16:00 или 19:00" вместо "когда удобно"

## Когда НЕ Отвечать
Если сообщение содержит:
- Просьбу позвонить, связаться по телефону → верни action="escalate"
- Срочные вопросы → верни action="escalate"
- Жалобы или негатив → верни action="escalate"
- Спам или нерелевантные сообщения → верни action="wait"

{scheduling_instructions}

## Тон Голоса (КАК общаться)

{tone_of_voice}

{how_to_communicate_section}

{knowledge_context}

## Формат Ответа
Отвечай ТОЛЬКО в формате JSON:
{{
    "action": "reply" | "wait" | "escalate" | "check_availability" | "schedule",
    "message": "текст сообщения для клиента (если action=reply)",
    "reason": "краткое объяснение решения",
    "scheduling_data": {{"slot_id": "YYYYMMDD_HHMM"}} (только если action=schedule)
}}

НЕ добавляй ничего до или после JSON.
"""

        return prompt

    async def generate_initial_message(self, prospect: Prospect) -> AgentAction:
        """Generate initial outreach message for a new prospect."""
        user_prompt = f"""Сгенерируй ПЕРВОЕ сообщение для нового потенциального клиента.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Заметки: {prospect.notes or "нет"}

Это первый контакт. Нужно:
1. Поприветствовать по имени
2. Представиться и объяснить ценность компании
3. Задать открытый вопрос для начала диалога

Помни: сообщение должно быть естественным, не шаблонным.
Верни JSON с action="reply" и текстом сообщения.
"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return self._parse_response(response.content[0].text)

    async def generate_response(
        self,
        prospect: Prospect,
        incoming_message: str,
        conversation_context: str = ""
    ) -> AgentAction:
        """
        Generate a response to an incoming message.

        Injects relevant knowledge base context based on message content.

        Args:
            prospect: The prospect information
            incoming_message: The incoming message from the prospect
            conversation_context: Previous conversation history

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

        # Inject relevant knowledge based on message content
        knowledge_context = ""
        if self.knowledge_loader and self.config.include_knowledge_base:
            knowledge_context = self.knowledge_loader.get_relevant_context(
                incoming_message,
                max_tokens=self.config.max_knowledge_tokens
            )
            if knowledge_context:
                knowledge_context = f"\n\n## Релевантная информация из базы знаний:\n\n{knowledge_context}\n"

        user_prompt = f"""Клиент написал сообщение. Нужно ответить.

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

Проанализируй сообщение и реши, как ответить:
- Если клиент отвечает на вопрос → продолжай диалог, задай следующий вопрос или предложи Zoom
- Если клиент задает вопрос → ответь используя базу знаний и задай уточняющий вопрос
- Если клиент просит каталог → согласись, но задай вопросы для персонализации
- Если клиент готов к Zoom → используй action="check_availability" чтобы проверить слоты
- Если клиент отказывается → уважительно заверши диалог
- Если сообщение неясное → попроси уточнить

Верни JSON с решением.
"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return self._parse_response(response.content[0].text)

    async def generate_follow_up(
        self,
        prospect: Prospect,
        conversation_context: str = ""
    ) -> AgentAction:
        """Generate a follow-up message for a non-responsive prospect."""

        follow_up_number = prospect.message_count  # 2nd, 3rd, etc.

        user_prompt = f"""Клиент не отвечает. Нужно написать follow-up сообщение.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Уже отправлено сообщений: {prospect.message_count}
- Последний контакт: {prospect.last_contact}

История переписки:
{conversation_context if conversation_context else "Пока только наше первое сообщение."}

Это будет {follow_up_number + 1}-е сообщение.

Правила:
- 2-е сообщение: мягкое напоминание + предложение консультации
- 3-е сообщение: проявление заботы + вопрос об актуальности
- 4+ сообщение: возможно, стоит остановиться (верни action="wait")

Верни JSON с решением.
"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return self._parse_response(response.content[0].text)

    def _parse_response(self, response_text: str) -> AgentAction:
        """
        Parse LLM response into AgentAction.

        Handles JSON extraction from LLM output and extracts scheduling_data
        for scheduling actions.

        Args:
            response_text: Raw text response from the LLM

        Returns:
            AgentAction with parsed action, message, reason, and scheduling_data
        """
        import json

        # Clean up response - find JSON in the text
        text = response_text.strip()

        # Try to find JSON object
        start = text.find('{')
        end = text.rfind('}')

        if start != -1 and end != -1:
            json_str = text[start:end + 1]
            try:
                data = json.loads(json_str)
                return AgentAction(
                    action=data.get("action", "wait"),
                    message=data.get("message"),
                    reason=data.get("reason"),
                    scheduling_data=data.get("scheduling_data")
                )
            except json.JSONDecodeError:
                pass

        # Fallback - couldn't parse, escalate for safety
        return AgentAction(
            action="escalate",
            reason=f"Could not parse LLM response: {response_text[:100]}"
        )

    def check_rate_limit(self, prospect: Prospect, messages_today: int) -> bool:
        """Check if we can send another message today."""
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
