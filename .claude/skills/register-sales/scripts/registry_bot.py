# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-telegram-bot>=21.0",
#   "asyncpg>=0.29.0",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
"""
Sales Representative Registry Bot.

A conversational Telegram bot for self-service sales rep registration.

Note: This file was migrated from src/sales_agent/registry/registry_bot.py
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Local imports - support both package and standalone usage
try:
    from .registry_models import (
        ConversationState,
        UserSession,
        SalesRepStatus,
    )
    from . import sales_rep_manager
    from . import test_prospect_manager
except ImportError:
    from registry_models import (
        ConversationState,
        UserSession,
        SalesRepStatus,
    )
    import sales_rep_manager
    import test_prospect_manager

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# Conversation states
(
    IDLE,
    ASK_REGISTER,
    ASK_NAME,
    ASK_EMAIL,
    ASK_UNREGISTER,
) = range(5)


# Natural language patterns (Russian)
PATTERNS = {
    "yes": re.compile(r"^(да|yes|конечно|давай|хочу|ок|ok|ага|угу)$", re.I),
    "no": re.compile(r"^(нет|no|не хочу|не надо|отмена|cancel)$", re.I),
    "unregister": re.compile(r"(отключ|удал|выход|уйти|отписа|unregister)", re.I),
    "my_clients": re.compile(r"(мои клиент|мои проспект|my client|my prospect)", re.I),
    "status": re.compile(r"(статус|status|профиль|profile)", re.I),
    "help": re.compile(r"(помощь|help|что умеешь|\?)", re.I),
}


class RegistryBot:
    """Telegram bot for sales representative registration."""

    def __init__(self, token: str, corporate_email_domain: str = "truerealestate.bali"):
        self.token = token
        self.corporate_email_domain = corporate_email_domain
        self.application: Application = None
        self.sessions: Dict[int, UserSession] = {}

    def get_session(self, telegram_id: int) -> UserSession:
        """Get or create a session for a user."""
        if telegram_id not in self.sessions:
            self.sessions[telegram_id] = UserSession(telegram_id=telegram_id)
        return self.sessions[telegram_id]

    def clear_session(self, telegram_id: int) -> None:
        """Clear session data for a user."""
        if telegram_id in self.sessions:
            del self.sessions[telegram_id]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /start command or first message."""
        user = update.effective_user
        telegram_id = user.id

        # Check if already registered
        rep = await sales_rep_manager.get_by_telegram_id(telegram_id)

        if rep and rep.status == SalesRepStatus.ACTIVE:
            await update.message.reply_text(
                f"Привет, {rep.name}! Вы уже зарегистрированы.\n\n"
                "Доступные действия:\n"
                "* «мои клиенты» - посмотреть тестовых клиентов\n"
                "* «статус» - ваш профиль\n"
                "* «отключиться» - отменить регистрацию"
            )
            return IDLE

        # Not registered - ask if they want to register
        await update.message.reply_text(
            "Привет! Я бот для регистрации менеджеров по продажам.\n\n"
            "Хотите зарегистрироваться?"
        )
        return ASK_REGISTER

    async def ask_register_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle response to 'want to register?' question."""
        text = update.message.text.strip()
        logger.info(f"ASK_REGISTER received: {text}")

        if PATTERNS["yes"].match(text):
            await update.message.reply_text("Отлично! Как вас зовут? (Имя и Фамилия)")
            return ASK_NAME
        elif PATTERNS["no"].match(text):
            await update.message.reply_text(
                "Хорошо, если передумаете - просто напишите /start"
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Не понял ответ. Хотите зарегистрироваться?\n"
                "Напишите «да» или «нет»."
            )
            return ASK_REGISTER

    async def ask_name_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle name input."""
        user = update.effective_user
        text = update.message.text.strip()
        logger.info(f"ASK_NAME received: {text}")

        # Validate name (at least 2 words, allow Cyrillic and Latin)
        words = text.split()
        if len(words) < 2:
            await update.message.reply_text(
                "Пожалуйста, введите имя и фамилию (например: Иван Петров)"
            )
            return ASK_NAME

        # Store name in session
        session = self.get_session(user.id)
        session.temp_name = text
        session.state = ConversationState.ASK_EMAIL

        await update.message.reply_text(
            f"Приятно познакомиться, {text}!\n\n"
            f"Теперь укажите ваш email:"
        )
        return ASK_EMAIL

    async def ask_email_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle email input and complete registration."""
        user = update.effective_user
        text = update.message.text.strip().lower()
        logger.info(f"ASK_EMAIL received: {text}")

        # Validate email format
        email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
        if not email_pattern.match(text):
            await update.message.reply_text(
                "Неверный формат email. Пожалуйста, введите корректный email:"
            )
            return ASK_EMAIL

        # Get session data
        session = self.get_session(user.id)

        if not session.temp_name:
            await update.message.reply_text(
                "Произошла ошибка. Начнем сначала.\n"
                "Как вас зовут?"
            )
            return ASK_NAME

        try:
            # Create sales rep (auto-approved)
            rep = await sales_rep_manager.create_sales_rep(
                telegram_id=user.id,
                name=session.temp_name,
                email=text,
                telegram_username=user.username,
                auto_approve=True,
            )

            # Clear session
            self.clear_session(user.id)

            await update.message.reply_text(
                f"Поздравляю, {rep.name}! Вы зарегистрированы!\n\n"
                f"Ваш профиль:\n"
                f"* Имя: {rep.name}\n"
                f"* Email: {rep.email}\n"
                f"* Статус: Активен\n\n"
                "Напишите «мои клиенты» чтобы получить первого тестового клиента."
            )

            logger.info(f"New sales rep registered: {rep.name} ({rep.email})")
            return IDLE

        except Exception as e:
            logger.error(f"Failed to create sales rep: {e}")
            await update.message.reply_text(
                "Произошла ошибка при регистрации. Попробуйте позже."
            )
            return ConversationHandler.END

    async def handle_idle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle messages from registered users in IDLE state."""
        user = update.effective_user
        telegram_id = user.id
        text = update.message.text.strip()
        logger.info(f"IDLE received: {text}")

        # Check if registered
        rep = await sales_rep_manager.get_by_telegram_id(telegram_id)

        if not rep or rep.status != SalesRepStatus.ACTIVE:
            # Not registered anymore, restart
            await update.message.reply_text(
                "Вы не зарегистрированы. Хотите зарегистрироваться?"
            )
            return ASK_REGISTER

        # Handle registered user commands
        if PATTERNS["unregister"].search(text):
            await update.message.reply_text(
                f"Вы уверены, что хотите отменить регистрацию?\n"
                f"Ваш профиль: {rep.name}, {rep.email}\n\n"
                "Напишите «да» для подтверждения или «нет» для отмены."
            )
            return ASK_UNREGISTER

        if PATTERNS["my_clients"].search(text):
            return await self._show_my_clients(update, rep)

        if PATTERNS["status"].search(text):
            await update.message.reply_text(
                f"Ваш профиль:\n\n"
                f"Имя: {rep.name}\n"
                f"Email: {rep.email}\n"
                f"Статус: Активен\n"
                f"Telegram: @{rep.telegram_username or 'не указан'}\n"
                f"Зарегистрирован: {rep.registered_at.strftime('%d.%m.%Y') if rep.registered_at else 'N/A'}"
            )
            return IDLE

        if PATTERNS["help"].search(text):
            await update.message.reply_text(
                "Доступные команды:\n\n"
                "* «мои клиенты» - список тестовых клиентов\n"
                "* «статус» - ваш профиль\n"
                "* «отключиться» - отменить регистрацию\n"
                "* «помощь» - это сообщение"
            )
            return IDLE

        # Default response
        await update.message.reply_text(
            f"Привет, {rep.name}! Чем могу помочь?\n\n"
            "Напишите «помощь» для списка команд."
        )
        return IDLE

    async def _show_my_clients(self, update: Update, rep) -> int:
        """Show test prospects assigned to the rep."""
        prospects = await test_prospect_manager.get_prospects_for_rep(rep.id)

        if not prospects:
            # Try to assign some unreached prospects
            unreached = await test_prospect_manager.get_unreached_prospects()
            if unreached:
                prospect = unreached[0]
                await test_prospect_manager.assign_prospect_to_rep(prospect.id, rep.id)
                prospects = [prospect]
                await update.message.reply_text("Вам назначен новый тестовый клиент!")

        if not prospects:
            await update.message.reply_text(
                "У вас пока нет назначенных клиентов.\n"
                "Новые клиенты будут назначены автоматически."
            )
            return IDLE

        lines = ["Ваши тестовые клиенты:\n"]
        for i, p in enumerate(prospects, 1):
            status_emoji = {
                "unreached": "[RED]",
                "contacted": "[YELLOW]",
                "in_conversation": "[GREEN]",
                "converted": "[OK]",
                "archived": "[GREY]",
            }.get(p.status, "[GREY]")

            lines.append(
                f"{i}. {status_emoji} {p.name}\n"
                f"   TG: {p.telegram_id}\n"
                f"   Контекст: {p.context or 'не указан'}"
            )

        await update.message.reply_text("\n".join(lines))
        return IDLE

    async def ask_unregister_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle unregistration confirmation."""
        user = update.effective_user
        text = update.message.text.strip()
        logger.info(f"ASK_UNREGISTER received: {text}")

        if PATTERNS["yes"].match(text):
            success = await sales_rep_manager.remove_rep(user.id)

            if success:
                self.clear_session(user.id)
                await update.message.reply_text(
                    "Ваша регистрация отменена.\n"
                    "Если передумаете - напишите /start"
                )
                logger.info(f"Sales rep unregistered: {user.id}")
            else:
                await update.message.reply_text(
                    "Не удалось отменить регистрацию. Попробуйте позже."
                )
            return ConversationHandler.END

        elif PATTERNS["no"].match(text):
            await update.message.reply_text("Отлично, регистрация сохранена!")
            return IDLE

        else:
            await update.message.reply_text(
                "Не понял ответ. Отменить регистрацию?\n"
                "Напишите «да» или «нет»."
            )
            return ASK_UNREGISTER

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /cancel command."""
        user = update.effective_user
        self.clear_session(user.id)
        await update.message.reply_text(
            "Действие отменено. Напишите /start когда будете готовы."
        )
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Exception while handling update {update}: {context.error}")

    def build_application(self) -> Application:
        """Build the telegram application with handlers."""
        self.application = Application.builder().token(self.token).build()

        # Conversation handler for registration flow
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.start_command),
            ],
            states={
                IDLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_idle),
                ],
                ASK_REGISTER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_register_response),
                ],
                ASK_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_name_response),
                ],
                ASK_EMAIL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_email_response),
                ],
                ASK_UNREGISTER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_unregister_response),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start_command),
            ],
            allow_reentry=False,  # Don't allow entry points to interrupt conversation
        )

        self.application.add_handler(conv_handler)
        self.application.add_error_handler(self.error_handler)

        return self.application

    async def run(self) -> None:
        """Run the bot with polling."""
        app = self.build_application()
        await app.initialize()
        await app.start()

        logger.info("Registry bot started. Polling for messages...")

        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def create_and_run_bot(token: str = None) -> None:
    """Create and run the registry bot."""
    if token is None:
        token = os.getenv("REGISTRY_BOT_TOKEN")
        if not token:
            raise ValueError("REGISTRY_BOT_TOKEN environment variable is not set.")

    corporate_domain = os.getenv("CORPORATE_EMAIL_DOMAIN", "truerealestate.bali")

    bot = RegistryBot(token=token, corporate_email_domain=corporate_domain)
    await bot.run()
