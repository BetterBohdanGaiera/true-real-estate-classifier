"""
Fetches conversation context directly from the Telegram API via Telethon.

Replaces ProspectManager.get_conversation_context() as the source of truth for
what the AI agent sees as conversation history. Instead of reading from a locally
stored JSON file, this module queries real Telegram chat messages and formats them
in the same ``[YYYY-MM-DD HH:MM] SenderName: text`` format that the agent prompt
expects.

Integrates with :class:`TranscriptionCache` to substitute rich text descriptions
for media messages (voice transcriptions, photo descriptions, etc.) instead of
showing plain placeholders like ``[Voice message]``.

A short-lived in-memory cache (default 10 s TTL) prevents redundant Telegram API
calls within the same processing cycle.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Any

from telethon import TelegramClient

logger = logging.getLogger(__name__)


class TelegramChatHistoryFetcher:
    """Fetches and formats chat history directly from Telegram API.

    Replaces ProspectManager.get_conversation_context() as the source of truth.
    Uses the actual Telegram chat messages rather than locally stored JSON.

    Integrates with TranscriptionCache to provide rich text descriptions
    for media messages (voice transcriptions, photo descriptions, etc.)
    """

    def __init__(
        self,
        client: TelegramClient,
        bot_user_id: int,
        transcription_cache: Optional[Any] = None,  # TranscriptionCache instance
    ):
        """Initialize the chat history fetcher.

        Args:
            client: Telethon TelegramClient instance.
            bot_user_id: Telegram user ID of the bot account (to identify
                "agent" messages vs. prospect messages).
            transcription_cache: Optional
                :class:`~telegram_sales_bot.temporal.transcription_cache.TranscriptionCache`
                for looking up media transcriptions.
        """
        self.client = client
        self.bot_user_id = bot_user_id
        self.transcription_cache = transcription_cache

        # Short-lived cache: avoids redundant API calls within the same
        # processing cycle.
        # key: str(telegram_id) -> value: (unix_timestamp, formatted_context)
        self._context_cache: dict[str, tuple[float, str]] = {}
        self._cache_ttl_seconds: float = 10.0  # 10 second TTL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_conversation_context(
        self,
        telegram_id: int | str,
        prospect_name: str,
        agent_name: str = "Вы",
        limit: int = 30,
    ) -> str:
        """Fetch and format recent messages from Telegram chat as context string.

        Produces output in the **same format** as
        ``ProspectManager.get_conversation_context()``::

            [YYYY-MM-DD HH:MM] SenderName: message text

        Args:
            telegram_id: Telegram user ID (numeric) or username of the chat
                partner.
            prospect_name: Display name for the prospect's messages.
            agent_name: Display name for the bot's own messages (default
                ``"Вы"``).
            limit: Maximum number of messages to fetch from the Telegram API.

        Returns:
            Formatted conversation context string with messages in
            chronological order (oldest first). Returns an empty string on
            failure or when no messages exist.
        """
        cache_key = str(telegram_id)

        # Check short-lived cache
        if cache_key in self._context_cache:
            cached_time, cached_context = self._context_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl_seconds:
                logger.debug(
                    "Using cached context for %s (age: %.1fs)",
                    cache_key,
                    time.time() - cached_time,
                )
                return cached_context

        try:
            # Resolve the entity and fetch messages from Telegram
            entity = await self.client.get_entity(telegram_id)

            messages = []
            async for msg in self.client.iter_messages(entity, limit=limit):
                messages.append(msg)
                await asyncio.sleep(0.05)  # Light rate limiting

            if not messages:
                return ""

            # Reverse to chronological order (oldest first)
            messages.reverse()

            # Get cached transcriptions for this chat (bulk lookup)
            cached_transcriptions: dict[int, str] = {}
            if self.transcription_cache:
                cached_transcriptions = self.transcription_cache.get_for_chat(
                    telegram_id
                )

            # Format each message
            lines: list[str] = []
            for msg in messages:
                # Determine sender
                is_agent = msg.out
                sender_name = agent_name if is_agent else prospect_name

                # Determine message text
                text = self._get_message_text(msg, cached_transcriptions)

                # Format timestamp
                if msg.date:
                    timestamp = msg.date.strftime("%Y-%m-%d %H:%M")
                else:
                    timestamp = "????-??-?? ??:??"

                lines.append(f"[{timestamp}] {sender_name}: {text}")

            context = "\n".join(lines)

            # Store in short-lived cache
            self._context_cache[cache_key] = (time.time(), context)

            logger.debug(
                "Fetched %d messages from Telegram for %s",
                len(messages),
                cache_key,
            )
            return context

        except Exception as e:
            logger.error(
                "Failed to fetch chat history from Telegram for %s: %s",
                telegram_id,
                e,
            )
            return ""

    def invalidate_cache(self, telegram_id: int | str) -> None:
        """Invalidate the cached context for a specific chat.

        Call this when you know the context has changed (e.g., a new message
        was sent or received).

        Args:
            telegram_id: Telegram user ID or username whose cache entry
                should be removed.
        """
        cache_key = str(telegram_id)
        self._context_cache.pop(cache_key, None)

    def clear_cache(self) -> None:
        """Clear all cached contexts."""
        self._context_cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_message_text(
        self, msg: Any, cached_transcriptions: dict[int, str]
    ) -> str:
        """Extract text from a Telethon message, using cache for media.

        The priority is:

        1. If a transcription/analysis result exists in the cache for this
           message ID, use that (optionally appending the original caption).
        2. If the message has plain text, return it.
        3. For media without a cache entry, return a Russian-language
           placeholder describing the media type.

        Args:
            msg: Telethon ``Message`` object.
            cached_transcriptions: Dict of ``{message_id: transcription_text}``
                obtained from :meth:`TranscriptionCache.get_for_chat`.

        Returns:
            Text representation of the message.
        """
        # 1. Check transcription cache first (voice, photo, video media)
        if msg.id in cached_transcriptions:
            cached_text = cached_transcriptions[msg.id]
            # If there's also a caption, include it
            if msg.text and msg.text.strip():
                return f"{cached_text}\nПодпись: {msg.text}"
            return cached_text

        # 2. Regular text message
        if msg.text:
            return msg.text

        # 3. Media without cache - show placeholder
        if msg.media:
            return self._media_placeholder(msg)

        return "[пустое сообщение]"

    @staticmethod
    def _media_placeholder(msg: Any) -> str:
        """Return a Russian-language placeholder string for a media message.

        Detection order mirrors
        :func:`~telegram_sales_bot.integrations.media_detector.detect_media_type`.

        Args:
            msg: Telethon ``Message`` object that has a ``media`` attribute.

        Returns:
            A bracketed placeholder string, e.g. ``"[Голосовое сообщение]"``.
        """
        if hasattr(msg, "voice") and msg.voice:
            return "[Голосовое сообщение]"
        if hasattr(msg, "video_note") and msg.video_note:
            return "[Кругляш]"
        if hasattr(msg, "sticker") and msg.sticker:
            emoji = getattr(msg.sticker, "alt", "") or "\U0001F44D"
            return f"[Стикер: {emoji}]"
        if hasattr(msg, "photo") and msg.photo:
            return "[Фото]"
        if hasattr(msg, "video") and msg.video:
            return "[Видео]"
        if hasattr(msg, "document") and msg.document:
            return "[Документ]"
        if hasattr(msg, "gif") and msg.gif:
            return "[GIF]"
        if hasattr(msg, "audio") and msg.audio:
            return "[Аудио]"
        return "[Медиа]"
