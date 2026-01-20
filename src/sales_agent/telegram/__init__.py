"""
Telegram integration module - Message sending and service layer.

This module provides Telegram communication capabilities for the sales agent:
- TelegramService: Human-like message sending with typing simulation
- bot_send: Bot API fallback for sending messages

Example usage:
    from sales_agent.telegram import TelegramService, bot_send

    # Using TelegramService for human-like messaging
    service = await create_telegram_service()
    await service.send_message(chat_id, "Hello!")

    # Using bot_send for direct Bot API access
    result = await bot_send.send_message(chat_id, "Hello!")
"""
from .telegram_service import TelegramService, is_private_chat, is_group_or_channel
from . import bot_send

__all__ = [
    "TelegramService",
    "is_private_chat",
    "is_group_or_channel",
    "bot_send",
]
