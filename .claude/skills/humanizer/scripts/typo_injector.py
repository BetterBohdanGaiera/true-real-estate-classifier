"""
Optional typo injection for human-like text (experimental).

This module provides typo generation and correction to make automated
messages appear more human-like. Typos are intentionally rare and always
followed by a correction message.

WARNING: This feature is experimental and disabled by default.
Use with caution as typos could impact professional perception.
"""
import random
from typing import Optional, Tuple


# Common Russian typo patterns based on ЙЦУКЕН keyboard layout
# Adjacent key typos - keys that are next to each other
TYPO_PATTERNS = [
    # Adjacent key typos (ЙЦУКЕН layout)
    ("а", "с"), ("о", "л"), ("е", "к"), ("и", "м"),
    ("н", "г"), ("т", "ь"), ("р", "п"),
    # Double letter mistakes
    ("нн", "н"), ("лл", "л"), ("сс", "с"),
    # Common grammatical mistakes
    ("тся", "ться"), ("ться", "тся"),
]


# Words that get commonly mistyped with realistic variants
COMMON_TYPOS = {
    "привет": ["прмвет", "приввет", "превет"],
    "хорошо": ["хорлшо", "хооршо", "хрошо"],
    "спасибо": ["спасмбо", "спассибо", "спаисбо"],
    "здравствуйте": ["здраствуйте", "здравствуйет"],
    "пожалуйста": ["пожалуста", "пожайлуста"],
    "конечно": ["конечон", "коненчо", "кончено"],
    "сегодня": ["сегодян", "седогня"],
    "встреча": ["встерча", "встреач"],
    "отлично": ["отлинчо", "отличон"],
    "договорились": ["договорилсиь", "доогворились"],
}


class TypoInjector:
    """
    Inject occasional typos to make text more human-like.

    Typos are rare (controlled by probability) and always result in
    a correction being returned so the sender can "fix" their mistake.
    """

    def __init__(self, probability: float = 0.05):
        """
        Initialize typo injector.

        Args:
            probability: Chance of adding typo to any message (0.0-1.0)
                        Default 0.05 (5%) - very rare
        """
        self.probability = max(0.0, min(1.0, probability))

    def should_add_typo(self) -> bool:
        """
        Randomly decide if this message should have a typo.

        Returns:
            True if typo should be added, False otherwise
        """
        return random.random() < self.probability

    def inject_typo(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Possibly inject a typo into text.

        Args:
            text: Original text

        Returns:
            Tuple of (modified_text, correction_text or None)
            If no typo added, returns (original, None)
        """
        if not self.should_add_typo():
            return text, None

        words = text.split()

        # Don't typo very short messages (< 3 words)
        if len(words) < 3:
            return text, None

        # Pick a random word to typo (not first or last for natural feel)
        if len(words) <= 2:
            return text, None

        idx = random.randint(1, len(words) - 2)
        original_word = words[idx]

        # Skip if word is too short
        if len(original_word) < 3:
            return text, None

        # Check if it's a common typo word (case-insensitive)
        lower_word = original_word.lower()
        if lower_word in COMMON_TYPOS:
            typo_word = random.choice(COMMON_TYPOS[lower_word])
            # Preserve original case for first letter
            if original_word[0].isupper():
                typo_word = typo_word[0].upper() + typo_word[1:]
            words[idx] = typo_word
            typo_text = " ".join(words)
            correction = f"{original_word}*"
            return typo_text, correction

        # Otherwise, random character swap for words with 4+ chars
        if len(original_word) >= 4:
            word_list = list(original_word)
            # Pick a position in the middle of the word (not first/last char)
            swap_idx = random.randint(1, len(word_list) - 2)
            # Swap adjacent characters
            word_list[swap_idx], word_list[swap_idx + 1] = (
                word_list[swap_idx + 1], word_list[swap_idx]
            )
            words[idx] = "".join(word_list)
            typo_text = " ".join(words)
            correction = f"{original_word}*"
            return typo_text, correction

        return text, None

    def create_correction_message(self, correction: str) -> str:
        """
        Create a natural correction message.

        Args:
            correction: The correction text (e.g., "слово*")

        Returns:
            Natural-looking correction message
        """
        # Various ways humans correct typos
        templates = [
            correction,           # Just the correction: "слово*"
            f"*{correction[:-1]}",  # Asterisk first: "*слово"
            correction,           # Repeat for more weight on simple correction
        ]
        return random.choice(templates)
