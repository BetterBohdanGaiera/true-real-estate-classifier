"""
Telegram Service wrapper for the agent.
Handles all Telegram communication with human-like behavior.
"""
import asyncio
import random
from datetime import datetime
from typing import Optional, Callable, Any

from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction

# Import from consolidated telegram_fetch in the same package
from sales_agent.telegram.telegram_fetch import (
    get_client,
    resolve_entity,
    get_chat_type,
    format_message,
    CONFIG_FILE,
    load_config
)

from sales_agent.crm.models import AgentConfig


class TelegramService:
    """Wrapper for Telegram operations with human-like behavior."""

    def __init__(self, client: TelegramClient, config: Optional[AgentConfig] = None):
        self.client = client
        self.config = config or AgentConfig()

    async def send_message(
        self,
        telegram_id: int | str,
        text: str,
        reply_to: Optional[int] = None
    ) -> dict:
        """Send a message with human-like delay and typing simulation."""

        # Resolve entity
        entity, resolved_name = await resolve_entity(self.client, str(telegram_id))

        if entity is None:
            return {"sent": False, "error": f"Could not resolve {telegram_id}"}

        # Simulate typing (if enabled)
        if self.config.typing_simulation:
            await self._simulate_typing(entity, text)

        # Human-like delay before sending (scaled by message length)
        delay = self._calculate_delay(text)
        await asyncio.sleep(delay)

        # Send message
        try:
            msg = await self.client.send_message(
                entity,
                text,
                reply_to=reply_to
            )
            return {
                "sent": True,
                "chat": resolved_name,
                "message_id": msg.id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"sent": False, "error": str(e)}

    def _calculate_delay(self, text: str) -> float:
        """Calculate response delay based on message length.

        Delay tiers:
        - Short (<50 chars): quick acknowledgments
        - Medium (50-200 chars): standard responses
        - Long (>200 chars): detailed explanations
        """
        text_length = len(text)

        if text_length < 50:
            delay_range = self.config.delay_short
        elif text_length <= 200:
            delay_range = self.config.delay_medium
        else:
            delay_range = self.config.delay_long

        return random.uniform(*delay_range)

    def _calculate_reading_delay(self, incoming_text: str) -> float:
        """Calculate delay to simulate reading an incoming message.

        Simulates human reading time before responding.
        Uses reading_delay config fields based on incoming message length.

        Delay tiers:
        - Short (<50 chars): quick messages
        - Medium (50-200 chars): standard messages
        - Long (>200 chars): detailed messages
        """
        text_length = len(incoming_text) if incoming_text else 0

        if text_length < 50:
            delay_range = self.config.reading_delay_short
        elif text_length <= 200:
            delay_range = self.config.reading_delay_medium
        else:
            delay_range = self.config.reading_delay_long

        return random.uniform(*delay_range)

    async def _simulate_typing(self, entity, text: str) -> None:
        """Simulate typing indicator based on message length."""
        # Estimate typing time: ~50 chars per second for a fast typist
        # But we want to seem human, so slower
        chars_per_second = 20
        typing_duration = len(text) / chars_per_second

        # Minimum 1 second, maximum 5 seconds
        typing_duration = max(1.0, min(typing_duration, 5.0))

        try:
            # Send typing action
            await self.client(SetTypingRequest(
                peer=entity,
                action=SendMessageTypingAction()
            ))
            await asyncio.sleep(typing_duration)
        except Exception:
            # Typing simulation is not critical, ignore errors
            pass

    async def get_chat_history(
        self,
        telegram_id: int | str,
        limit: int = 20
    ) -> list[dict]:
        """Get recent messages from a chat."""
        entity, resolved_name = await resolve_entity(self.client, str(telegram_id))

        if entity is None:
            return []

        chat_type = get_chat_type(entity)
        messages = []

        async for msg in self.client.iter_messages(entity, limit=limit):
            messages.append(format_message(msg, resolved_name, chat_type))
            await asyncio.sleep(0.05)  # Light rate limiting

        return messages

    async def get_me(self) -> dict:
        """Get info about the authenticated user."""
        me = await self.client.get_me()
        return {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": me.phone
        }

    async def mark_read(self, telegram_id: int | str) -> bool:
        """Mark all messages in a chat as read."""
        try:
            entity, _ = await resolve_entity(self.client, str(telegram_id))
            if entity:
                await self.client.send_read_acknowledge(entity)
                return True
        except Exception:
            pass
        return False

    async def delete_messages(
        self,
        telegram_id: int | str,
        message_ids: list[int],
        revoke: bool = True
    ) -> int:
        """Delete messages from a chat.

        Note: Can only delete messages sent by the authenticated account (center),
        not the prospect's replies.

        Args:
            telegram_id: Telegram ID or username of the chat
            message_ids: List of message IDs to delete
            revoke: If True, delete for both sides (default: True)

        Returns:
            Number of messages successfully deleted
        """
        if not message_ids:
            return 0

        # Resolve entity
        entity, resolved_name = await resolve_entity(self.client, str(telegram_id))

        if entity is None:
            print(f"Warning: Could not resolve entity for {telegram_id}")
            return 0

        try:
            # Delete messages using Telethon API
            deleted = await self.client.delete_messages(
                entity,
                message_ids,
                revoke=revoke
            )
            # deleted is an AffectedMessages object with pts_count
            deleted_count = len(message_ids) if deleted else 0
            return deleted_count
        except Exception as e:
            # Deletion is not critical, log but don't raise
            print(f"Warning: Could not delete messages: {e}")
            return 0

    async def delete_conversation_messages(
        self,
        telegram_id: int | str,
        message_ids: list[int]
    ) -> int:
        """Delete agent's messages from a conversation.

        This is a convenience wrapper around delete_messages for cleaning up
        agent-sent messages during test resets.

        Note: Can only delete messages sent by the authenticated account (center),
        not the prospect's replies.

        Args:
            telegram_id: Prospect's telegram ID or username
            message_ids: List of message IDs to delete (agent-sent only)

        Returns:
            Number of messages deleted
        """
        return await self.delete_messages(telegram_id, message_ids, revoke=True)

    async def notify_escalation(
        self,
        notify_id: str,
        prospect_name: str,
        reason: str,
        original_message: str
    ) -> bool:
        """Send escalation notification to administrator."""
        if not notify_id:
            return False

        text = f"""🔔 **Требуется внимание**

Клиент: {prospect_name}
Причина: {reason}

Сообщение:
> {original_message}
"""

        result = await self.send_message(notify_id, text)
        return result.get("sent", False)


class MessageHandler:
    """Handles incoming messages and routes them to callbacks."""

    def __init__(self, service: TelegramService):
        self.service = service
        self.handlers: list[Callable] = []

    def register(self, handler: Callable) -> None:
        """Register a message handler callback."""
        self.handlers.append(handler)

    async def process_message(self, event: Any) -> None:
        """Process an incoming message through all handlers."""
        for handler in self.handlers:
            try:
                await handler(event)
            except Exception as e:
                print(f"Error in message handler: {e}")


# Utility functions

async def create_telegram_service(config: Optional[AgentConfig] = None) -> TelegramService:
    """Create and initialize a TelegramService instance."""
    client = await get_client()
    return TelegramService(client, config)


def is_private_chat(entity) -> bool:
    """Check if an entity is a private chat (user)."""
    return isinstance(entity, User)


def is_group_or_channel(entity) -> bool:
    """Check if an entity is a group or channel."""
    return isinstance(entity, (Chat, Channel))


# Simple test
if __name__ == "__main__":
    async def test():
        print("Initializing Telegram service...")
        service = await create_telegram_service()

        print("\nGetting account info...")
        me = await service.get_me()
        print(f"Logged in as: {me['first_name']} (@{me['username']})")

        # Don't send messages in test - just verify connection
        print("\nService initialized successfully!")

        await service.client.disconnect()

    asyncio.run(test())
