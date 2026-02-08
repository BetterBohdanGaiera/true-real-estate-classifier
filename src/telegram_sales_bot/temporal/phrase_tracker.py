"""
Track used phrases to avoid repetition in conversations.

This module provides PhraseTracker which maintains history of greetings,
opening phrases, and closing questions used with each prospect to ensure
variety and avoid robotic-sounding repetition.
"""
from typing import Optional
import random

# Greeting variations - used at the start of initial messages
GREETING_TEMPLATES = [
    "Здравствуйте, {name}!",
    "Добрый день, {name}!",
    "{name}, приветствую!",
    "Привет, {name}!",
    "{name}, здравствуйте!",
    "Добрый день!",
    "Приветствую, {name}!",
    "{name}, добрый день!",
]

# Opening phrases (after greeting) - introduce the agent
OPENING_PHRASES = [
    "Меня зовут {agent}, я эксперт по недвижимости в True Real Estate.",
    "Я {agent} из True Real Estate, занимаюсь недвижимостью на Бали.",
    "{agent}, True Real Estate. Помогаю с недвижимостью на Бали.",
    "Это {agent}, эксперт True Real Estate по Бали.",
    "Меня зовут {agent}, работаю в True Real Estate.",
    "{agent} из True Real Estate, специализируюсь на недвижимости Бали.",
]

# Closing questions (for initial message) - engage the prospect
CLOSING_QUESTIONS = [
    "Расскажите, что именно вас интересует?",
    "Какой тип недвижимости рассматриваете?",
    "Что для вас важно в объекте?",
    "Какие у вас планы по недвижимости?",
    "Чем могу помочь?",
    "Что вас привлекает в недвижимости Бали?",
    "Какие у вас критерии выбора?",
]

class PhraseTracker:
    """
    Track and select non-repeated phrases for natural conversation variety.

    Maintains separate histories for greetings, opening phrases, and
    closing questions. When all options are exhausted, resets and
    picks randomly.

    Attributes:
        used_greetings: Set of greetings already used with this prospect
        used_phrases: Set of other phrases (openings, closings) used

    Example:
        >>> tracker = PhraseTracker()
        >>> greeting = tracker.get_greeting("Алексей")
        >>> opening = tracker.get_opening("Мария")
        >>> question = tracker.get_closing_question()
        >>> # Later, save to prospect
        >>> greetings, phrases = tracker.get_used_lists()
    """

    def __init__(
        self,
        used_greetings: Optional[list[str]] = None,
        used_phrases: Optional[list[str]] = None
    ):
        """
        Initialize tracker with optional history.

        Args:
            used_greetings: Previously used greetings (from prospect record)
            used_phrases: Previously used phrases (from prospect record)
        """
        self.used_greetings: set[str] = set(used_greetings or [])
        self.used_phrases: set[str] = set(used_phrases or [])

    def get_greeting(self, client_name: str) -> str:
        """
        Get a greeting that hasn't been used yet.

        Args:
            client_name: The prospect's name to include in greeting

        Returns:
            A formatted greeting string
        """
        available = [
            g.format(name=client_name)
            for g in GREETING_TEMPLATES
            if g.format(name=client_name) not in self.used_greetings
        ]

        if not available:
            # All used, reset and pick random
            available = [g.format(name=client_name) for g in GREETING_TEMPLATES]

        choice = random.choice(available)
        self.used_greetings.add(choice)
        return choice

    def get_opening(self, agent_name: str) -> str:
        """
        Get an opening phrase that hasn't been used.

        Args:
            agent_name: The agent's name to include in opening

        Returns:
            A formatted opening phrase string
        """
        available = [
            p.format(agent=agent_name)
            for p in OPENING_PHRASES
            if p.format(agent=agent_name) not in self.used_phrases
        ]

        if not available:
            available = [p.format(agent=agent_name) for p in OPENING_PHRASES]

        choice = random.choice(available)
        self.used_phrases.add(choice)
        return choice

    def get_closing_question(self) -> str:
        """
        Get a closing question that hasn't been used.

        Returns:
            A closing question string
        """
        available = [q for q in CLOSING_QUESTIONS if q not in self.used_phrases]

        if not available:
            available = list(CLOSING_QUESTIONS)

        choice = random.choice(available)
        self.used_phrases.add(choice)
        return choice

    def record_phrase(self, phrase: str) -> None:
        """
        Record a phrase as used.

        Args:
            phrase: The phrase to mark as used
        """
        self.used_phrases.add(phrase)

    def record_greeting(self, greeting: str) -> None:
        """
        Record a greeting as used.

        Args:
            greeting: The greeting to mark as used
        """
        self.used_greetings.add(greeting)

    def get_used_lists(self) -> tuple[list[str], list[str]]:
        """
        Get used greetings and phrases as lists for storage.

        Returns:
            Tuple of (used_greetings list, used_phrases list)
        """
        return list(self.used_greetings), list(self.used_phrases)

    def reset(self) -> None:
        """Reset all tracked phrases (start fresh)."""
        self.used_greetings.clear()
        self.used_phrases.clear()
