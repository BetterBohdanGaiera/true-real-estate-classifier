"""
Messaging module - Message batching and debounce management.

This module provides message buffering capabilities for the sales agent,
implementing a debounce pattern for incoming messages:
- BufferedMessage: Pydantic model for individual buffered messages with metadata
- MessageBuffer: Manages message batching with debounce timer logic

The batching system allows accumulating multiple rapid messages from a prospect
and processing them as a single batch, creating more natural conversational flow.
This mimics human behavior where a person reads all messages before responding.

Example usage:
    from sales_agent.messaging import MessageBuffer, BufferedMessage
    from datetime import datetime

    async def process_batch(prospect_id: str, messages: list[BufferedMessage]) -> None:
        # Process all messages together
        combined = "\\n".join(msg.text for msg in messages)
        print(f"Processing {len(messages)} messages from {prospect_id}")

    buffer = MessageBuffer(
        timeout_range=(3.0, 5.0),
        flush_callback=process_batch,
        max_messages=10,
        max_wait_seconds=30.0
    )

    # Add messages - they accumulate until timeout or limits
    msg = BufferedMessage(message_id=123, text="Hello", timestamp=datetime.now())
    await buffer.add_message("prospect_123", msg)
"""

from .message_buffer import BufferedMessage, MessageBuffer

__all__ = [
    "BufferedMessage",
    "MessageBuffer",
]
