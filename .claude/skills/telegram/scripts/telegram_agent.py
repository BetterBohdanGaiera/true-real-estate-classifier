"""
Claude Agent for Telegram communication.
Generates messages in the True Real Estate tone of voice.
"""
import os
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from models import Prospect, ProspectStatus, AgentAction, AgentConfig


# Load environment variables from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()  # Also try current directory


class TelegramAgent:
    """Claude-powered agent for Telegram communication."""

    def __init__(
        self,
        tone_of_voice_path: str | Path,
        config: Optional[AgentConfig] = None,
        agent_name: str = "Мария"
    ):
        self.tone_of_voice_path = Path(tone_of_voice_path)
        self.config = config or AgentConfig()
        self.agent_name = agent_name
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.system_prompt = self._build_system_prompt()

    def _load_tone_of_voice(self) -> str:
        """Load tone of voice instructions from skill files."""
        content_parts = []

        # Load main SKILL.md
        skill_file = self.tone_of_voice_path / "SKILL.md"
        if skill_file.exists():
            content_parts.append(skill_file.read_text(encoding='utf-8'))

        # Load reference files
        refs_dir = self.tone_of_voice_path / "references"
        if refs_dir.exists():
            for ref_file in refs_dir.glob("*.md"):
                content_parts.append(f"\n\n--- {ref_file.name} ---\n\n")
                content_parts.append(ref_file.read_text(encoding='utf-8'))

        return "\n".join(content_parts)

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        tone_of_voice = self._load_tone_of_voice()

        return f"""Ты — {self.agent_name}, эксперт по недвижимости в агентстве True Real Estate на Бали.
Ты общаешься с потенциальными клиентами через Telegram от своего имени.

ВАЖНО: Ты пишешь РЕАЛЬНЫЕ сообщения реальным людям. Будь естественной, как настоящий человек.
НЕ начинай каждое сообщение одинаково. Варьируй приветствия и структуру.

## Твоя Задача
1. Вести диалог профессионально, но тепло
2. Собирать информацию о потребностях клиента
3. Вести к Zoom-звонку с экспертом
4. Отвечать на вопросы о недвижимости на Бали

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

## Тон Голоса и Инструкции

{tone_of_voice}

## Формат Ответа
Отвечай ТОЛЬКО в формате JSON:
{{
    "action": "reply" | "wait" | "escalate",
    "message": "текст сообщения для клиента (если action=reply)",
    "reason": "краткое объяснение решения"
}}

НЕ добавляй ничего до или после JSON.
"""

    async def generate_initial_message(self, prospect: Prospect) -> str:
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
        """Generate a response to an incoming message."""

        # Check for escalation keywords first
        lower_msg = incoming_message.lower()
        for keyword in self.config.escalation_keywords:
            if keyword.lower() in lower_msg:
                return AgentAction(
                    action="escalate",
                    reason=f"Found escalation keyword: {keyword}"
                )

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

Проанализируй сообщение и реши, как ответить:
- Если клиент отвечает на вопрос → продолжай диалог, задай следующий вопрос или предложи Zoom
- Если клиент задает вопрос → ответь и задай уточняющий вопрос
- Если клиент просит каталог → согласись, но задай вопросы для персонализации
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
        """Parse LLM response into AgentAction."""
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
                    reason=data.get("reason")
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
        # Initialize agent
        agent = TelegramAgent(
            tone_of_voice_path=Path(__file__).parent.parent.parent / "tone-of-voice"
        )

        # Test prospect
        prospect = Prospect(
            telegram_id="@test_user",
            name="Алексей",
            context="Интересуется виллой в Чангу, бюджет $500k"
        )

        # Generate initial message
        print("=== Initial Message ===")
        action = await agent.generate_initial_message(prospect)
        print(f"Action: {action.action}")
        print(f"Message: {action.message}")
        print(f"Reason: {action.reason}")

        # Test response
        print("\n=== Response to 'Да, для инвестиций' ===")
        action = await agent.generate_response(
            prospect,
            "Да, для инвестиций",
            conversation_context=""
        )
        print(f"Action: {action.action}")
        print(f"Message: {action.message}")
        print(f"Reason: {action.reason}")

    asyncio.run(test())
