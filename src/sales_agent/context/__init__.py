"""
Context module - Conversation memory and context management.

This module provides utilities for managing conversation context,
including phrase variation, fact extraction, and context summarization
for long conversations.

Provides:
- PhraseTracker: Track and avoid phrase repetition for natural variety
- ContextSummarizer: Summarize long conversation history
- FactExtractor: Extract and store important facts (BANT)
- ExtractedFacts: Dataclass for storing extracted prospect information

Example usage:
    from sales_agent.context import PhraseTracker, FactExtractor, ExtractedFacts

    # Vary greetings and phrases
    tracker = PhraseTracker(used_greetings=prospect.used_greetings)
    greeting = tracker.get_greeting("Алексей")
    opening = tracker.get_opening("Мария")

    # Extract facts from messages
    extractor = FactExtractor()
    facts = extractor.extract_from_message("Хочу виллу в Чангу за 500к")
    print(facts.property_type)  # "villa"
    print(facts.budget_max)     # 500000

    # Summarize long conversations
    from sales_agent.context import ContextSummarizer
    summarizer = ContextSummarizer()
    if summarizer.should_summarize(len(messages)):
        summary = summarizer.summarize(conversation_text)
"""
from .phrase_tracker import (
    PhraseTracker,
    GREETING_TEMPLATES,
    OPENING_PHRASES,
    CLOSING_QUESTIONS,
)
from .fact_extractor import FactExtractor, ExtractedFacts

# Lazy import for ContextSummarizer to avoid import-time issues with anthropic
def __getattr__(name: str):
    if name == "ContextSummarizer":
        from .context_summarizer import ContextSummarizer
        return ContextSummarizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Main classes
    "PhraseTracker",
    "ContextSummarizer",
    "FactExtractor",
    "ExtractedFacts",
    # Template constants
    "GREETING_TEMPLATES",
    "OPENING_PHRASES",
    "CLOSING_QUESTIONS",
]
