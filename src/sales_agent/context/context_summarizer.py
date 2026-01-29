"""
Summarize long conversation history.

This module provides ContextSummarizer which uses Claude API to create
concise summaries of older messages while preserving important context,
allowing the agent to maintain awareness of long conversations without
exceeding context limits.
"""
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
import os

from dotenv import load_dotenv

load_dotenv()

if TYPE_CHECKING:
    from anthropic import Anthropic


# Prompt for summarizing conversation history
SUMMARIZE_PROMPT = """Summarize this conversation history in 2-3 sentences.
Focus on:
1. What the client is looking for (property type, location, budget)
2. Key requirements mentioned
3. Current stage of conversation
4. Any important facts about the client

Conversation:
{conversation}

Summary (in Russian, concise and factual):"""


# Prompt for incremental summary updates
UPDATE_SUMMARY_PROMPT = """Update this summary with new information from recent messages.
Keep it to 2-3 sentences, preserving important existing facts.

Previous summary:
{previous_summary}

New messages:
{new_messages}

Updated summary (in Russian, concise and factual):"""


class ContextSummarizer:
    """
    Summarize old conversation context to preserve important information.

    Uses Claude API to generate concise summaries that capture key facts
    from older messages, allowing the agent to maintain context across
    long conversations without using excessive tokens.

    Attributes:
        client: Anthropic API client
        model: Model to use for summarization

    Example:
        >>> summarizer = ContextSummarizer()
        >>> summary = summarizer.summarize(conversation_text)
        >>> context = summarizer.build_context_with_summary(summary, recent_messages)
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize summarizer with Anthropic client.

        Args:
            model: Claude model to use for summarization
        """
        # Lazy import to avoid import-time failures if anthropic package has issues
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def should_summarize(
        self,
        total_messages: int,
        last_summary_at: Optional[datetime] = None,
        threshold: int = 30,
        messages_since_summary: Optional[int] = None
    ) -> bool:
        """
        Check if conversation should be summarized.

        Args:
            total_messages: Total number of messages in conversation
            last_summary_at: When the last summary was created
            threshold: Message count threshold before summarization
            messages_since_summary: Number of new messages since last summary

        Returns:
            True if summarization should occur
        """
        # Don't summarize short conversations
        if total_messages < threshold:
            return False

        # Always summarize if no previous summary exists
        if last_summary_at is None:
            return True

        # Re-summarize if significant new messages since last summary
        if messages_since_summary is not None and messages_since_summary >= 20:
            return True

        # Default to true for long conversations
        return total_messages >= threshold

    def summarize(
        self,
        conversation_text: str,
        existing_summary: Optional[str] = None,
        max_input_chars: int = 4000
    ) -> str:
        """
        Generate summary of conversation.

        Args:
            conversation_text: Formatted conversation history
            existing_summary: Previous summary to incorporate (for incremental updates)
            max_input_chars: Maximum characters of conversation to include

        Returns:
            Summary string in Russian
        """
        # Truncate conversation if too long
        truncated_conversation = conversation_text[:max_input_chars]

        if existing_summary:
            # Incremental update of existing summary
            prompt = UPDATE_SUMMARY_PROMPT.format(
                previous_summary=existing_summary,
                new_messages=truncated_conversation
            )
        else:
            # Generate fresh summary
            prompt = SUMMARIZE_PROMPT.format(conversation=truncated_conversation)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def build_context_with_summary(
        self,
        summary: Optional[str],
        recent_messages: list[Any],
        recent_count: int = 15
    ) -> str:
        """
        Build context combining summary and recent messages.

        Creates a formatted string that includes the conversation summary
        (if available) followed by the most recent messages in detail.

        Args:
            summary: Summary of older messages (or None if no summary)
            recent_messages: Recent conversation messages
            recent_count: How many recent messages to include in full

        Returns:
            Combined context string ready for agent prompt
        """
        parts = []

        if summary:
            parts.append(f"[Краткое содержание предыдущего разговора]\n{summary}\n")

        if recent_messages:
            parts.append("[Последние сообщения]")
            # Take only the most recent messages
            messages_to_include = recent_messages[-recent_count:]

            for msg in messages_to_include:
                # Handle different message formats
                if hasattr(msg, 'sender') and hasattr(msg, 'text'):
                    sender = "Вы" if msg.sender == "agent" else "Клиент"
                    text = msg.text
                    if hasattr(msg, 'timestamp'):
                        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
                        parts.append(f"[{timestamp}] {sender}: {text}")
                    else:
                        parts.append(f"{sender}: {text}")
                elif isinstance(msg, dict):
                    sender = "Вы" if msg.get('sender') == "agent" else "Клиент"
                    text = msg.get('text', '')
                    parts.append(f"{sender}: {text}")
                else:
                    # Fallback for plain text
                    parts.append(str(msg))

        return "\n".join(parts)

    def format_conversation_for_summary(
        self,
        messages: list[Any],
        max_messages: Optional[int] = None
    ) -> str:
        """
        Format conversation messages into text for summarization.

        Args:
            messages: List of ConversationMessage objects or dicts
            max_messages: Maximum messages to include (None for all)

        Returns:
            Formatted conversation text
        """
        lines = []
        messages_to_process = messages if max_messages is None else messages[:max_messages]

        for msg in messages_to_process:
            if hasattr(msg, 'sender') and hasattr(msg, 'text'):
                sender = "Agent" if msg.sender == "agent" else "Client"
                lines.append(f"{sender}: {msg.text}")
            elif isinstance(msg, dict):
                sender = "Agent" if msg.get('sender') == "agent" else "Client"
                lines.append(f"{sender}: {msg.get('text', '')}")
            else:
                lines.append(str(msg))

        return "\n".join(lines)
