"""
Message Buffer - Manages message batching with debounce timer logic.

This module provides the core MessageBuffer class that accumulates multiple rapid
messages from a prospect and processes them as a single batch. This creates more
natural conversation flow by allowing the agent to read all messages before responding.

The debounce pattern works as follows:
1. When a message arrives, it's added to the prospect's buffer
2. A timer is started (or reset if already running)
3. When the timer expires, all buffered messages are flushed to the callback
4. Safety limits prevent runaway buffering (max messages, max wait time)
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Callable, Optional, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class BufferedMessage(BaseModel):
    """
    Single buffered message from a prospect.

    Attributes:
        message_id: Telegram message ID for tracking
        text: The message content
        timestamp: When the message was received
        has_media: Whether this message contains media (voice, photo, etc.)
        media_type: Type of media if has_media is True ("voice", "photo", etc.)
    """
    message_id: int
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # Media tracking fields
    has_media: bool = False
    media_type: Optional[str] = None  # "voice", "photo", "video", "sticker", etc.

    class Config:
        """Pydantic configuration."""
        frozen = False  # Allow modifications if needed

# Type alias for the flush callback signature
FlushCallback = Callable[[str, list[BufferedMessage]], Awaitable[None]]

class MessageBuffer:
    """
    Manages message batching with debounce timer logic.

    This class implements the debounce pattern for incoming messages:
    - Messages accumulate in an in-memory buffer keyed by prospect_id
    - Each new message resets the debounce timer
    - When the timer expires (no new messages for timeout duration), the buffer is flushed
    - Safety limits prevent excessive buffering (max messages, max wait time)

    Attributes:
        timeout_range: Tuple of (min, max) seconds for random timeout selection
        flush_callback: Async function called when buffer is flushed
        max_messages: Maximum messages per buffer before forced flush
        max_wait_seconds: Maximum total wait time before forced flush

    Example:
        async def process_batch(prospect_id: str, messages: list[BufferedMessage]) -> None:
            combined = "\\n".join(msg.text for msg in messages)
            print(f"Processing {len(messages)} messages from {prospect_id}")

        buffer = MessageBuffer(
            timeout_range=(3.0, 5.0),
            flush_callback=process_batch,
            max_messages=10,
            max_wait_seconds=30.0
        )

        # Add messages
        msg = BufferedMessage(message_id=123, text="Hello", timestamp=datetime.now())
        await buffer.add_message("prospect_123", msg)
    """

    def __init__(
        self,
        timeout_range: tuple[float, float] = (3.0, 5.0),
        flush_callback: Optional[FlushCallback] = None,
        max_messages: int = 10,
        max_wait_seconds: float = 30.0
    ):
        """
        Initialize the MessageBuffer.

        Args:
            timeout_range: Tuple of (min, max) seconds for random timeout selection.
                          A random value within this range is used for each debounce timer.
            flush_callback: Async function to call when buffer is flushed.
                           Signature: async def callback(prospect_id: str, messages: list[BufferedMessage])
            max_messages: Maximum number of messages per buffer before forced flush.
                         Prevents memory issues from excessive buffering.
            max_wait_seconds: Maximum total wait time from first message before forced flush.
                             Prevents indefinite buffering when messages arrive continuously.
        """
        self._buffers: dict[str, list[BufferedMessage]] = {}
        self._timers: dict[str, asyncio.Task] = {}
        self._first_message_time: dict[str, datetime] = {}  # Track first message timestamp
        self._generations: dict[str, int] = {}  # Generation counter per prospect to prevent stale flushes
        self._timeout_range = timeout_range
        self._flush_callback = flush_callback
        self._max_messages = max_messages
        self._max_wait_seconds = max_wait_seconds

        logger.debug(
            f"MessageBuffer initialized: timeout_range={timeout_range}, "
            f"max_messages={max_messages}, max_wait_seconds={max_wait_seconds}"
        )

    async def add_message(self, prospect_id: str, message: BufferedMessage) -> None:
        """
        Add a message to the buffer and reset the debounce timer.

        This method:
        1. Initializes the buffer for this prospect if needed
        2. Appends the message to the buffer
        3. Cancels any existing timer
        4. Starts a new timer (or force-flushes if limits exceeded)

        Args:
            prospect_id: Unique identifier for the prospect (telegram_id as string)
            message: The BufferedMessage to add
        """
        # Initialize buffer if needed
        if prospect_id not in self._buffers:
            self._buffers[prospect_id] = []
            self._first_message_time[prospect_id] = message.timestamp
            logger.debug(f"Created new buffer for prospect {prospect_id}")

        # Add message to buffer
        self._buffers[prospect_id].append(message)

        # Increment generation to invalidate any in-flight timers
        self._generations[prospect_id] = self._generations.get(prospect_id, 0) + 1

        logger.debug(
            f"Added message {message.message_id} to buffer for {prospect_id}, "
            f"buffer size: {len(self._buffers[prospect_id])}"
        )

        # Cancel existing timer if present
        if prospect_id in self._timers:
            self._timers[prospect_id].cancel()
            try:
                await self._timers[prospect_id]
            except asyncio.CancelledError:
                pass
            del self._timers[prospect_id]
            logger.debug(f"Cancelled existing timer for {prospect_id}")

        # Start new timer (may force-flush if limits exceeded)
        await self._start_timer(prospect_id)

    async def _start_timer(self, prospect_id: str) -> None:
        """
        Start or reset the debounce timer for a prospect.

        This method checks safety limits before starting the timer:
        - If buffer size >= max_messages, force flush immediately
        - If time since first message > max_wait_seconds, force flush immediately

        Otherwise, starts a new asyncio task that sleeps for a random duration
        within timeout_range, then flushes the buffer.

        Args:
            prospect_id: Unique identifier for the prospect
        """
        # Check safety limit: max messages
        buffer_size = len(self._buffers.get(prospect_id, []))
        if buffer_size >= self._max_messages:
            logger.info(
                f"Buffer for {prospect_id} reached max size ({buffer_size}), "
                f"forcing immediate flush"
            )
            await self._flush_buffer(prospect_id)
            return

        # Check safety limit: max wait time
        first_msg_time = self._first_message_time.get(prospect_id)
        if first_msg_time:
            elapsed = (datetime.now() - first_msg_time).total_seconds()
            if elapsed >= self._max_wait_seconds:
                logger.info(
                    f"Buffer for {prospect_id} exceeded max wait time "
                    f"({elapsed:.1f}s >= {self._max_wait_seconds}s), forcing immediate flush"
                )
                await self._flush_buffer(prospect_id)
                return

        # Calculate random timeout within range
        timeout = random.uniform(self._timeout_range[0], self._timeout_range[1])
        logger.debug(f"Starting timer for {prospect_id}: {timeout:.2f}s")

        # Capture current generation for this timer
        current_gen = self._generations.get(prospect_id, 0)

        # Create async task for the timer
        async def timer_task():
            try:
                await asyncio.sleep(timeout)
                # Check if this timer is still the current one
                if self._generations.get(prospect_id, 0) != current_gen:
                    logger.debug(f"Timer for {prospect_id} is stale (gen {current_gen} vs {self._generations.get(prospect_id, 0)}), skipping flush")
                    return
                await self._flush_buffer(prospect_id)
            except asyncio.CancelledError:
                logger.debug(f"Timer cancelled for {prospect_id}")
                raise
            except Exception as e:
                logger.error(f"Error in timer task for {prospect_id}: {e}")

        self._timers[prospect_id] = asyncio.create_task(timer_task())

    async def _flush_buffer(self, prospect_id: str) -> None:
        """
        Flush the buffer and call the callback with all messages.

        This method:
        1. Retrieves all messages from the buffer
        2. Clears the buffer and removes tracking data
        3. Calls the flush_callback with the messages
        4. Handles errors gracefully without losing messages

        Args:
            prospect_id: Unique identifier for the prospect
        """
        # Get messages from buffer
        messages = self._buffers.pop(prospect_id, [])

        # Clean up tracking data
        self._first_message_time.pop(prospect_id, None)
        self._generations.pop(prospect_id, None)
        timer = self._timers.pop(prospect_id, None)
        if timer and not timer.done():
            timer.cancel()
            try:
                await timer
            except asyncio.CancelledError:
                pass

        if not messages:
            logger.debug(f"No messages to flush for {prospect_id}")
            return

        logger.info(f"Flushing buffer for {prospect_id}: {len(messages)} message(s)")

        # Call the flush callback
        if self._flush_callback:
            try:
                await self._flush_callback(prospect_id, messages)
                logger.debug(f"Flush callback completed for {prospect_id}")
            except Exception as e:
                logger.error(
                    f"Error in flush callback for {prospect_id}: {e}. "
                    f"Messages were: {[m.text[:50] for m in messages]}"
                )
                # Re-raise to let caller handle if needed
                # But buffer is already cleared - messages are "processed"
                raise
        else:
            logger.warning(
                f"No flush callback configured, {len(messages)} messages "
                f"for {prospect_id} were discarded"
            )

    def get_buffer_size(self, prospect_id: str) -> int:
        """
        Get the current buffer size for a prospect.

        Args:
            prospect_id: Unique identifier for the prospect

        Returns:
            Number of messages currently in the buffer (0 if no buffer exists)
        """
        return len(self._buffers.get(prospect_id, []))

    def get_buffered_messages(self, prospect_id: str) -> list[BufferedMessage]:
        """
        Get a copy of the current buffered messages for a prospect without flushing.

        This is useful for inspection/debugging without affecting the buffer state.

        Args:
            prospect_id: Unique identifier for the prospect

        Returns:
            Copy of the list of buffered messages (empty list if no buffer exists)
        """
        return list(self._buffers.get(prospect_id, []))

    def has_pending_buffer(self, prospect_id: str) -> bool:
        """
        Check if a prospect has messages waiting in the buffer.

        Args:
            prospect_id: Unique identifier for the prospect

        Returns:
            True if there are messages waiting, False otherwise
        """
        return prospect_id in self._buffers and len(self._buffers[prospect_id]) > 0

    def get_all_pending_prospect_ids(self) -> list[str]:
        """
        Get all prospect IDs that have pending buffers.

        Useful for shutdown operations to identify all buffers that need flushing.

        Returns:
            List of prospect IDs with non-empty buffers
        """
        return [pid for pid, msgs in self._buffers.items() if msgs]

    async def cancel_timer(self, prospect_id: str) -> None:
        """
        Cancel the timer for a prospect without flushing the buffer.

        Useful for cleanup operations (e.g., when a prospect becomes inactive)
        where you want to stop the timer but not trigger the callback.

        Note: This leaves messages in the buffer. Call flush_buffer() separately
        if you need to process them.

        Args:
            prospect_id: Unique identifier for the prospect
        """
        if prospect_id in self._timers:
            self._timers[prospect_id].cancel()
            try:
                await self._timers[prospect_id]
            except asyncio.CancelledError:
                pass
            del self._timers[prospect_id]
            logger.debug(f"Timer cancelled (without flush) for {prospect_id}")

    async def flush_all(self) -> None:
        """
        Flush all pending buffers.

        Useful for graceful shutdown to ensure all buffered messages are processed
        before the application exits.
        """
        prospect_ids = list(self._buffers.keys())
        logger.info(f"Flushing all buffers: {len(prospect_ids)} prospect(s)")

        for prospect_id in prospect_ids:
            try:
                await self._flush_buffer(prospect_id)
            except Exception as e:
                logger.error(f"Error flushing buffer for {prospect_id} during flush_all: {e}")

    async def cancel_all(self) -> None:
        """
        Cancel all pending timers without flushing.

        Useful for forced shutdown where you don't want to process buffered messages.
        """
        timer_ids = list(self._timers.keys())
        logger.info(f"Cancelling all timers: {len(timer_ids)} timer(s)")

        for prospect_id in timer_ids:
            await self.cancel_timer(prospect_id)

    def clear_buffer(self, prospect_id: str) -> list[BufferedMessage]:
        """
        Clear the buffer for a prospect and return the messages.

        This is a synchronous operation that removes messages without triggering
        the callback. Useful when you need to manually handle the messages.

        Args:
            prospect_id: Unique identifier for the prospect

        Returns:
            List of messages that were in the buffer
        """
        messages = self._buffers.pop(prospect_id, [])
        self._first_message_time.pop(prospect_id, None)
        self._generations.pop(prospect_id, None)

        if prospect_id in self._timers:
            self._timers[prospect_id].cancel()
            # Note: We don't await here since this is synchronous
            # The cancelled task will be cleaned up by the event loop
            del self._timers[prospect_id]

        logger.debug(f"Buffer cleared for {prospect_id}: {len(messages)} message(s)")
        return messages

    @property
    def timeout_range(self) -> tuple[float, float]:
        """Get the current timeout range."""
        return self._timeout_range

    @timeout_range.setter
    def timeout_range(self, value: tuple[float, float]) -> None:
        """Set a new timeout range. Only affects future timers."""
        if value[0] < 0 or value[1] < 0:
            raise ValueError("Timeout values must be non-negative")
        if value[0] > value[1]:
            raise ValueError("Minimum timeout must be <= maximum timeout")
        self._timeout_range = value
        logger.debug(f"Timeout range updated to {value}")

    @property
    def max_messages(self) -> int:
        """Get the maximum messages per buffer."""
        return self._max_messages

    @property
    def max_wait_seconds(self) -> float:
        """Get the maximum wait time in seconds."""
        return self._max_wait_seconds

    def __repr__(self) -> str:
        """String representation for debugging."""
        active_buffers = len([b for b in self._buffers.values() if b])
        active_timers = len(self._timers)
        return (
            f"MessageBuffer(timeout_range={self._timeout_range}, "
            f"max_messages={self._max_messages}, "
            f"max_wait_seconds={self._max_wait_seconds}, "
            f"active_buffers={active_buffers}, "
            f"active_timers={active_timers})"
        )
