"""
CLI-based Claude Agent for Telegram communication.
Replaces direct Anthropic API calls with Claude Code CLI subprocess invocations
via the ClaudeTaskExecutor class.

Produces identical conversational behavior (replies, waits, scheduling,
availability checks, follow-ups) but executes through `claude -p` instead
of direct API calls. This unlocks Claude Code features like session persistence,
structured output via JSON schema, budget control, and multi-turn context.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz
from dotenv import load_dotenv

from telegram_sales_bot.core.models import Prospect, ProspectStatus, AgentAction, AgentConfig
from telegram_sales_bot.knowledge.loader import KnowledgeLoader

# Add CLI task executor scripts to path
_PACKAGE_DIR = Path(__file__).parent.parent  # src/telegram_sales_bot/
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent  # project root
_CLI_SCRIPTS_DIR = _PROJECT_ROOT / ".claude" / "skills" / "cli-task-executor" / "scripts"
if str(_CLI_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CLI_SCRIPTS_DIR))

from execute_task import ClaudeTaskExecutor, TaskConfig, TaskResult, OutputFormat

load_dotenv(_PROJECT_ROOT / '.env')
load_dotenv()

# Bali timezone for time calculations
BALI_TIMEZONE = "Asia/Makassar"  # UTC+8, no DST

# Path to the JSON schema for structured output
AGENT_SCHEMA_PATH = Path(__file__).parent / "agent_schema.json"

# Path to the system prompt template
SYSTEM_PROMPT_TEMPLATE_PATH = _PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "agent_system_prompt.md"


class CLITelegramAgent:
    """Claude-powered agent for Telegram communication via Claude Code CLI.

    Uses ClaudeTaskExecutor to invoke `claude -p` with structured JSON output
    instead of direct Anthropic API calls. Supports session management for
    conversation continuity.
    """

    def __init__(
        self,
        tone_of_voice_path: str | Path,
        how_to_communicate_path: Optional[str | Path] = None,
        knowledge_base_path: Optional[str | Path] = None,
        config: Optional[AgentConfig] = None,
        agent_name: str = "Мария"
    ):
        self.tone_of_voice_path = Path(tone_of_voice_path)
        self.how_to_communicate_path = Path(how_to_communicate_path) if how_to_communicate_path else None
        self.knowledge_base_path = Path(knowledge_base_path) if knowledge_base_path else None
        self.config = config or AgentConfig()
        self.agent_name = agent_name

        # Initialize CLI executor
        self.executor = ClaudeTaskExecutor(
            default_timeout=self.config.cli_timeout,
            default_model=self.config.cli_model,
        )

        # Session management: prospect_id -> session_id
        self.sessions: dict[str, str] = {}

        # Initialize knowledge loader if path provided
        self.knowledge_loader: Optional[KnowledgeLoader] = None
        if self.knowledge_base_path:
            self.knowledge_loader = KnowledgeLoader(self.knowledge_base_path)

        # Load the JSON schema once
        self._schema = self._load_schema()

        # Pre-build the base system prompt
        self.system_prompt = self._build_system_prompt()

    def _load_schema(self) -> dict[str, Any]:
        """Load the agent output JSON schema."""
        with open(AGENT_SCHEMA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_skill(self, skill_path: Optional[Path]) -> str:
        """Load skill instructions from skill directory."""
        if not skill_path or not skill_path.exists():
            return ""

        content_parts = []

        skill_file = skill_path / "SKILL.md"
        if skill_file.exists():
            content_parts.append(skill_file.read_text(encoding='utf-8'))

        refs_dir = skill_path / "references"
        if refs_dir.exists():
            for ref_file in sorted(refs_dir.glob("*.md")):
                content_parts.append(f"\n\n--- {ref_file.name} ---\n\n")
                content_parts.append(ref_file.read_text(encoding='utf-8'))

        combined_content = "\n".join(content_parts)
        return self._sanitize_skill_content(combined_content)

    def _sanitize_skill_content(self, content: str) -> str:
        """Replace name placeholders with configured values."""
        replacements = [
            ("<Ваше_имя>", self.agent_name),
            ("<Your_name>", self.agent_name),
            ("<Руководитель_продаж>", self.config.sales_director_name),
            ("<Sales_director>", self.config.sales_director_name),
        ]
        result = content
        for placeholder, value in replacements:
            result = result.replace(placeholder, value)
        return result

    def _sanitize_output(self, text: str) -> str:
        """Remove em-dashes and en-dashes from LLM output."""
        if not text:
            return text
        result = text.replace("\u2014", " - ").replace("\u2013", " - ")
        while "  " in result:
            result = result.replace("  ", " ")
        return result

    def _get_current_bali_time(self) -> str:
        """Get current time in Bali timezone (UTC+8) as formatted string."""
        bali_tz = pytz.timezone(BALI_TIMEZONE)
        now_bali = datetime.now(bali_tz)
        return now_bali.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _build_system_prompt(self) -> str:
        """Build system prompt from template with all skills and knowledge injected."""
        # Load tone of voice skill
        tone_of_voice = self._load_skill(self.tone_of_voice_path)

        # Load how-to-communicate skill
        how_to_communicate_section = ""
        if self.how_to_communicate_path:
            how_to_communicate = self._load_skill(self.how_to_communicate_path)
            if how_to_communicate:
                how_to_communicate_section = f"""## Методология Коммуникации (ЧТО говорить)

{how_to_communicate}"""

        # Load master cheatsheet from knowledge base
        knowledge_context = ""
        if self.knowledge_loader:
            master_cheatsheet = self.knowledge_loader.load_master_cheatsheet()
            if master_cheatsheet:
                knowledge_context = f"""## База знаний: Главная шпаргалка

{master_cheatsheet}"""

        current_bali_time = self._get_current_bali_time()

        # Read template and fill placeholders via replace (not .format() - template has literal JSON braces)
        if SYSTEM_PROMPT_TEMPLATE_PATH.exists():
            prompt = SYSTEM_PROMPT_TEMPLATE_PATH.read_text(encoding='utf-8')
        else:
            raise FileNotFoundError(f"System prompt template not found: {SYSTEM_PROMPT_TEMPLATE_PATH}")

        replacements = {
            "{agent_name}": self.agent_name,
            "{sales_director_name}": self.config.sales_director_name,
            "{current_bali_time}": current_bali_time,
            "{tone_of_voice}": tone_of_voice,
            "{how_to_communicate_section}": how_to_communicate_section,
            "{knowledge_context}": knowledge_context,
        }
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)

        return prompt

    def _build_task_config(
        self,
        user_prompt: str,
        prospect_id: str,
        include_followup_tool: bool = True,
    ) -> TaskConfig:
        """Build a TaskConfig for CLI execution."""
        # Refresh time-sensitive parts of system prompt
        current_bali_time = self._get_current_bali_time()
        system_prompt = self.system_prompt.replace(
            self.system_prompt.split("Текущее время (Бали, UTC+8): ")[1].split("\n")[0],
            current_bali_time
        ) if "Текущее время (Бали, UTC+8): " in self.system_prompt else self.system_prompt

        config = TaskConfig(
            prompt=user_prompt,
            system_prompt=system_prompt,
            output_format=OutputFormat.JSON,
            # NOTE: --json-schema causes CLI to hang on API errors (credit balance, auth failures)
            # Instead, rely on system prompt instructions for JSON output format
            model=self.config.cli_model,
            max_turns=1,
            dangerously_skip_permissions=True,
            timeout=self.config.cli_timeout,
            cwd=str(_PROJECT_ROOT),
        )

        # Session management
        session_id = self.sessions.get(prospect_id)
        if session_id:
            config.resume = session_id

        # Budget control
        if self.config.cli_max_budget_usd:
            config.max_budget_usd = self.config.cli_max_budget_usd

        return config

    def _parse_cli_result(self, result: TaskResult, prospect_id: str) -> AgentAction:
        """Parse TaskResult into AgentAction and update session."""
        # Update session ID for conversation continuity
        if result.session_id:
            self.sessions[prospect_id] = result.session_id

        if not result.success:
            # Extract error from CLI JSON envelope (is_error + result field)
            error_msg = result.error
            if not error_msg and result.parsed_json:
                if result.parsed_json.get("is_error"):
                    error_msg = result.parsed_json.get("result", "unknown error")

            # Handle stale session: if resume failed, clear session and signal retry
            if error_msg and "no conversation found" in error_msg.lower():
                self.sessions.pop(prospect_id, None)
                return AgentAction(
                    action="_retry",
                    reason=f"Stale session cleared for {prospect_id}, retry without resume"
                )

            return AgentAction(
                action="escalate",
                reason=f"CLI execution failed: {error_msg or 'unknown error'}"
            )

        # Try to extract the agent response from parsed JSON
        parsed = result.parsed_json
        if not parsed:
            return AgentAction(
                action="escalate",
                reason=f"Could not parse CLI output as JSON: {result.output[:200]}"
            )

        # The CLI with --output-format json wraps the response in a result envelope
        # The actual content is in the "result" field as a string that contains our JSON
        agent_data = None

        # Case 1: parsed_json has a "result" key with the actual response string
        if "result" in parsed and isinstance(parsed["result"], str):
            try:
                agent_data = json.loads(parsed["result"])
            except json.JSONDecodeError:
                # Try to find JSON in the result string
                text = parsed["result"]
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1:
                    try:
                        agent_data = json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        pass

        # Case 2: parsed_json IS the agent response directly
        if not agent_data and "action" in parsed:
            agent_data = parsed

        if not agent_data:
            return AgentAction(
                action="escalate",
                reason=f"No valid agent response found in CLI output: {result.output[:200]}"
            )

        # Build AgentAction from parsed data
        msg = agent_data.get("message")
        return AgentAction(
            action=agent_data.get("action", "wait"),
            message=self._sanitize_output(msg) if msg else msg,
            reason=agent_data.get("reason"),
            scheduling_data=agent_data.get("scheduling_data"),
        )

    async def _execute_and_parse(self, user_prompt: str, prospect_id: str, **kwargs) -> AgentAction:
        """Execute CLI call with retry on stale session."""
        config = self._build_task_config(user_prompt, prospect_id, **kwargs)
        result = await self.executor.execute_with_config_async(config)
        action = self._parse_cli_result(result, prospect_id)

        # Retry once if stale session was cleared
        if action.action == "_retry":
            config = self._build_task_config(user_prompt, prospect_id, **kwargs)
            result = await self.executor.execute_with_config_async(config)
            action = self._parse_cli_result(result, prospect_id)

        return action

    async def generate_initial_message(self, prospect: Prospect) -> AgentAction:
        """Generate varied initial outreach message."""
        # Inject relevant knowledge for initial context
        knowledge_context = ""
        if self.knowledge_loader and self.config.include_knowledge_base:
            knowledge_context = self.knowledge_loader.get_relevant_context(
                prospect.context,
                max_tokens=self.config.max_knowledge_tokens
            )
            if knowledge_context:
                knowledge_context = f"\nРелевантная информация из базы знаний:\n{knowledge_context}\n"

        # Include previously used greetings so AI avoids repetition
        used_greetings_context = ""
        used_greetings = getattr(prospect, 'used_greetings', [])
        if used_greetings:
            used_greetings_context = f"\nУже использованные приветствия (НЕ повторяй):\n" + "\n".join(f'- "{g}"' for g in used_greetings) + "\n"

        user_prompt = f"""Сгенерируй ПЕРВОЕ сообщение для нового клиента.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Заметки: {prospect.notes or "нет"}
{used_greetings_context}
Напиши ЕСТЕСТВЕННОЕ приветственное сообщение (2-3 предложения, до 200 символов):
1. Поприветствуй клиента по имени
2. Представься как {self.agent_name} из True Real Estate
3. Задай один вовлекающий вопрос по контексту клиента

Будь естественной, варьируй стиль. НЕ используй одинаковые формулировки.
{knowledge_context}
Верни JSON с action="reply" и текстом сообщения."""

        prospect_id = str(prospect.telegram_id)
        return await self._execute_and_parse(user_prompt, prospect_id)

    async def generate_response(
        self,
        prospect: Prospect,
        incoming_message: str,
        conversation_context: str = "",
        gap: Optional[Any] = None
    ) -> AgentAction:
        """Generate a response to an incoming message."""
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
                knowledge_context = f"\n\nРелевантная информация из базы знаний:\n{knowledge_context}\n"

        # Detect if this is a batch of messages
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
- Если клиент назвал КОНКРЕТНОЕ время → action="check_availability" С scheduling_data (preferred_time, preferred_date, client_timezone)
- Если клиент дал email И время в одном батче → action="check_availability" С scheduling_data включая время
- Если клиент отказывается → уважительно заверши диалог
- Если сообщения неясные → попроси уточнить

Верни JSON с решением, где message содержит ОДИН комплексный ответ на все сообщения."""
        else:
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
- Если клиент назвал КОНКРЕТНОЕ время (например "завтра в 10:15 по Варшаве") → action="check_availability" С scheduling_data: preferred_time, preferred_date, client_timezone
- Если клиент отказывается → уважительно заверши диалог
- Если сообщение неясное → попроси уточнить

Верни JSON с решением."""

        # Replace client name placeholder with actual prospect name
        user_prompt = user_prompt.replace("<Имя_клиента>", prospect.name or "клиент")
        user_prompt = user_prompt.replace("<Client_name>", prospect.name or "client")

        prospect_id = str(prospect.telegram_id)
        return await self._execute_and_parse(user_prompt, prospect_id)

    async def generate_follow_up(
        self,
        prospect: Prospect,
        conversation_context: str = "",
        follow_up_intent: str = ""
    ) -> AgentAction:
        """Generate a follow-up message for a non-responsive prospect."""
        follow_up_number = prospect.message_count

        intent_guidance = ""
        if follow_up_intent:
            intent_guidance = f"""
Запланированная цель follow-up:
"{follow_up_intent}"

Учитывай эту цель, но адаптируй сообщение под ТЕКУЩИЙ контекст разговора.
Если цель уже неактуальна (например, клиент уже ответил на вопрос),
напиши что-то более подходящее или верни action="wait".

КРИТИЧЕСКИ ВАЖНО: Это выполнение ЗАПЛАНИРОВАННОГО follow-up.
НЕ используй action="schedule_followup" - просто напиши сообщение клиенту.
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

Верни JSON с решением."""

        prospect_id = str(prospect.telegram_id)
        return await self._execute_and_parse(
            user_prompt,
            prospect_id,
            include_followup_tool=not bool(follow_up_intent),
        )

    def check_rate_limit(self, prospect: Prospect, messages_today: int) -> bool:
        """Check if we can send another message today."""
        if self.config.max_messages_per_day_per_prospect is None:
            return True
        return messages_today < self.config.max_messages_per_day_per_prospect

    def is_within_working_hours(self) -> bool:
        """Check if current time is within working hours."""
        if not self.config.working_hours:
            return True
        hour = datetime.now().hour
        start, end = self.config.working_hours
        return start <= hour < end
