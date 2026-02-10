"""
Track used phrases for conversation context.

Templates removed - AI generates all phrases. This module only tracks
what phrases have been used so the AI agent can avoid repetition by
receiving usage history as context.
"""
from typing import Optional


class PhraseTracker:
    """
    Track phrases used in conversations to provide context to the AI agent.

    The AI agent generates all greetings, openings, and closing questions
    on its own. This tracker records what was used so that conversation
    history can inform future phrase generation and avoid repetition.

    Attributes:
        used_greetings: Set of greetings already used with this prospect.
        used_phrases: Set of other phrases (openings, closings, etc.) used.

    Example:
        >>> tracker = PhraseTracker()
        >>> tracker.record_greeting("AI-generated greeting text")
        >>> tracker.record_phrase("AI-generated opening text")
        >>> greetings, phrases = tracker.get_used_lists()
    """

    def __init__(
        self,
        used_greetings: Optional[list[str]] = None,
        used_phrases: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize tracker with optional history.

        Args:
            used_greetings: Previously used greetings (from prospect record).
            used_phrases: Previously used phrases (from prospect record).
        """
        self.used_greetings: set[str] = set(used_greetings or [])
        self.used_phrases: set[str] = set(used_phrases or [])

    def record_phrase(self, phrase: str) -> None:
        """
        Record a phrase as used.

        Args:
            phrase: The phrase to mark as used.
        """
        self.used_phrases.add(phrase)

    def record_greeting(self, greeting: str) -> None:
        """
        Record a greeting as used.

        Args:
            greeting: The greeting to mark as used.
        """
        self.used_greetings.add(greeting)

    def get_used_lists(self) -> tuple[list[str], list[str]]:
        """
        Get used greetings and phrases as lists for storage.

        Returns:
            Tuple of (used_greetings list, used_phrases list).
        """
        return list(self.used_greetings), list(self.used_phrases)

    def reset(self) -> None:
        """Reset all tracked phrases (start fresh)."""
        self.used_greetings.clear()
        self.used_phrases.clear()
