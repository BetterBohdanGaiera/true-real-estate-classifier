# Plan: Context & Memory - Initial Messages, Phrase Tracking, Long Context

## Task Description
Improve conversation context and memory: vary initial messages to avoid detection, track used phrases to prevent repetition, and handle long conversation context without losing important information from the beginning.

## Objective
Enable the sales agent to:
1. Generate varied initial messages (not identical every time)
2. Track phrases/greetings used to avoid repetition
3. Preserve important context from long conversations (not just last 20 messages)
4. Summarize old context while keeping recent messages detailed

## Problem Statement
Current gaps:
- **Initial messages**: Same template every time → client notices if reset
- **Phrase repetition**: "Рад познакомиться!" in every conversation → robotic
- **Context loss**: Only last 20 messages kept → early BANT info lost
- No conversation summary for long dialogues

## Solution Approach
1. Create initial message templates with variations
2. Track used phrases per prospect in conversation metadata
3. Implement context summarization for old messages
4. Add "important facts" extraction and storage

## Relevant Files

### Existing Files to Modify
- `src/sales_agent/agent/telegram_agent.py` - Initial message generation, phrase tracking
- `src/sales_agent/crm/models.py` - Add used_phrases, extracted_facts fields
- `src/sales_agent/crm/prospect_manager.py` - Context summarization, fact extraction
- `src/sales_agent/config/agent_config.json` - Initial message templates

### New Files to Create
- `src/sales_agent/context/__init__.py` - Context management module
- `src/sales_agent/context/phrase_tracker.py` - Track used phrases
- `src/sales_agent/context/context_summarizer.py` - Summarize old conversations
- `src/sales_agent/context/fact_extractor.py` - Extract important facts

## Implementation Phases

### Phase 1: Foundation
- Add metadata fields to Prospect model
- Create context module structure
- Define initial message templates

### Phase 2: Core Implementation
- Implement phrase tracking
- Implement context summarization
- Implement fact extraction

### Phase 3: Integration
- Integrate with agent prompts
- Test variation and memory
- Fine-tune summarization

## Step by Step Tasks

### 1. Update Prospect Model for Memory
- In `src/sales_agent/crm/models.py`, add to Prospect:
```python
class Prospect(BaseModel):
    # ... existing fields ...

    # Context memory fields
    used_greetings: list[str] = Field(default_factory=list)  # Greetings already used
    used_phrases: list[str] = Field(default_factory=list)    # Key phrases used
    extracted_facts: dict = Field(default_factory=dict)      # BANT and other facts
    conversation_summary: Optional[str] = None               # Summary of old messages
    summary_updated_at: Optional[datetime] = None
```

### 2. Create Context Module
- Create `src/sales_agent/context/__init__.py`:
```python
"""
Context module - Conversation memory and context management.

Provides:
- PhraseTracker: Track and avoid phrase repetition
- ContextSummarizer: Summarize long conversation history
- FactExtractor: Extract and store important facts (BANT)
"""
from .phrase_tracker import PhraseTracker
from .context_summarizer import ContextSummarizer
from .fact_extractor import FactExtractor, ExtractedFacts

__all__ = [
    "PhraseTracker",
    "ContextSummarizer",
    "FactExtractor",
    "ExtractedFacts",
]
```

### 3. Implement Phrase Tracker
- Create `src/sales_agent/context/phrase_tracker.py`:
```python
"""Track used phrases to avoid repetition."""
from typing import Optional
import random

# Greeting variations
GREETING_TEMPLATES = [
    "Здравствуйте, {name}!",
    "Добрый день, {name}!",
    "{name}, приветствую!",
    "Привет, {name}!",
    "{name}, здравствуйте!",
    "Добрый день!",
]

# Opening phrases (after greeting)
OPENING_PHRASES = [
    "Меня зовут {agent}, я эксперт по недвижимости в True Real Estate.",
    "Я {agent} из True Real Estate, занимаюсь недвижимостью на Бали.",
    "{agent}, True Real Estate. Помогаю с недвижимостью на Бали.",
    "Это {agent}, эксперт True Real Estate по Бали.",
]

# Closing questions (for initial message)
CLOSING_QUESTIONS = [
    "Расскажите, что именно вас интересует?",
    "Какой тип недвижимости рассматриваете?",
    "Что для вас важно в объекте?",
    "Какие у вас планы по недвижимости?",
    "Чем могу помочь?",
]

class PhraseTracker:
    """Track and select non-repeated phrases."""

    def __init__(self, used_greetings: list[str] = None, used_phrases: list[str] = None):
        self.used_greetings = set(used_greetings or [])
        self.used_phrases = set(used_phrases or [])

    def get_greeting(self, client_name: str) -> str:
        """Get a greeting that hasn't been used yet."""
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
        """Get an opening phrase that hasn't been used."""
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
        """Get a closing question that hasn't been used."""
        available = [q for q in CLOSING_QUESTIONS if q not in self.used_phrases]

        if not available:
            available = CLOSING_QUESTIONS

        choice = random.choice(available)
        self.used_phrases.add(choice)
        return choice

    def record_phrase(self, phrase: str) -> None:
        """Record a phrase as used."""
        self.used_phrases.add(phrase)

    def get_used_lists(self) -> tuple[list[str], list[str]]:
        """Get used greetings and phrases as lists for storage."""
        return list(self.used_greetings), list(self.used_phrases)
```

### 4. Implement Context Summarizer
- Create `src/sales_agent/context/context_summarizer.py`:
```python
"""Summarize long conversation history."""
from datetime import datetime
from typing import Optional
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

SUMMARIZE_PROMPT = """Summarize this conversation history in 2-3 sentences.
Focus on:
1. What the client is looking for (property type, location, budget)
2. Key requirements mentioned
3. Current stage of conversation

Conversation:
{conversation}

Summary (in Russian):"""

class ContextSummarizer:
    """Summarize old conversation context."""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def should_summarize(
        self,
        total_messages: int,
        last_summary_at: Optional[datetime],
        threshold: int = 30
    ) -> bool:
        """Check if conversation should be summarized."""
        if total_messages < threshold:
            return False

        if last_summary_at is None:
            return True

        # Re-summarize if > 20 new messages since last summary
        # This is approximate - would need message count at summary time
        return True

    def summarize(
        self,
        conversation_text: str,
        existing_summary: Optional[str] = None
    ) -> str:
        """
        Generate summary of conversation.

        Args:
            conversation_text: Formatted conversation history
            existing_summary: Previous summary to incorporate

        Returns:
            Summary string
        """
        prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text[:4000])

        if existing_summary:
            prompt = f"Previous summary: {existing_summary}\n\n" + prompt

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def build_context_with_summary(
        self,
        summary: Optional[str],
        recent_messages: list,
        recent_count: int = 15
    ) -> str:
        """
        Build context combining summary and recent messages.

        Args:
            summary: Summary of older messages
            recent_messages: Recent conversation messages
            recent_count: How many recent messages to include in full

        Returns:
            Combined context string
        """
        parts = []

        if summary:
            parts.append(f"[Краткое содержание предыдущего разговора]\n{summary}\n")

        if recent_messages:
            parts.append("[Последние сообщения]")
            for msg in recent_messages[-recent_count:]:
                sender = "Вы" if msg.sender == "agent" else "Клиент"
                parts.append(f"{sender}: {msg.text}")

        return "\n".join(parts)
```

### 5. Implement Fact Extractor
- Create `src/sales_agent/context/fact_extractor.py`:
```python
"""Extract and store important facts from conversations."""
from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class ExtractedFacts:
    """Extracted BANT and other facts."""
    # Budget
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: str = "USD"

    # Authority
    is_decision_maker: Optional[bool] = None
    other_stakeholders: list[str] = field(default_factory=list)

    # Need
    property_type: Optional[str] = None  # villa, apartment, land
    location_preferences: list[str] = field(default_factory=list)
    purpose: Optional[str] = None  # investment, living, rental

    # Timeline
    timeline: Optional[str] = None  # "urgent", "3 months", "1 year"

    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "budget_currency": self.budget_currency,
            "is_decision_maker": self.is_decision_maker,
            "property_type": self.property_type,
            "location_preferences": self.location_preferences,
            "purpose": self.purpose,
            "timeline": self.timeline,
            "email": self.email,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedFacts":
        """Create from dictionary."""
        return cls(
            budget_min=data.get("budget_min"),
            budget_max=data.get("budget_max"),
            budget_currency=data.get("budget_currency", "USD"),
            is_decision_maker=data.get("is_decision_maker"),
            property_type=data.get("property_type"),
            location_preferences=data.get("location_preferences", []),
            purpose=data.get("purpose"),
            timeline=data.get("timeline"),
            email=data.get("email"),
        )

class FactExtractor:
    """Extract facts from conversation messages."""

    # Budget patterns
    BUDGET_PATTERNS = [
        r"(\d+)\s*[kкК]",  # 500k, 500к
        r"\$\s*(\d+)",     # $500000
        r"(\d+)\s*тыс",    # 500 тысяч
        r"(\d+)\s*млн",    # 1 млн
        r"бюджет[:\s]+(\d+)", # бюджет: 500000
    ]

    # Location patterns
    LOCATION_KEYWORDS = [
        "чангу", "canggu", "семиньяк", "seminyak", "убуд", "ubud",
        "санур", "sanur", "нуса дуа", "nusa dua", "улувату", "uluwatu",
        "букит", "bukit", "джимбаран", "jimbaran"
    ]

    # Property type patterns
    PROPERTY_TYPES = {
        r"вилл[ауы]": "villa",
        r"апартамент": "apartment",
        r"земл[яюе]|участ[ок]": "land",
        r"дом": "house",
        r"студи[яю]": "studio",
    }

    def extract_from_message(
        self,
        message: str,
        existing: Optional[ExtractedFacts] = None
    ) -> ExtractedFacts:
        """
        Extract facts from a single message.

        Args:
            message: Message text to analyze
            existing: Existing facts to update

        Returns:
            Updated ExtractedFacts
        """
        facts = existing or ExtractedFacts()
        message_lower = message.lower()

        # Extract budget
        for pattern in self.BUDGET_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                amount = int(match.group(1))
                # Normalize to full amount
                if "k" in message_lower or "к" in message_lower:
                    amount *= 1000
                if "млн" in message_lower:
                    amount *= 1000000

                if facts.budget_min is None or amount < facts.budget_min:
                    facts.budget_min = amount
                if facts.budget_max is None or amount > facts.budget_max:
                    facts.budget_max = amount

        # Extract location
        for loc in self.LOCATION_KEYWORDS:
            if loc in message_lower and loc not in facts.location_preferences:
                facts.location_preferences.append(loc)

        # Extract property type
        for pattern, prop_type in self.PROPERTY_TYPES.items():
            if re.search(pattern, message_lower):
                facts.property_type = prop_type
                break

        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            facts.email = email_match.group(0)

        # Extract purpose
        if "инвестиц" in message_lower:
            facts.purpose = "investment"
        elif "жить" in message_lower or "переезд" in message_lower:
            facts.purpose = "living"
        elif "сдавать" in message_lower or "аренд" in message_lower:
            facts.purpose = "rental"

        return facts

    def extract_from_conversation(
        self,
        messages: list,
        existing: Optional[ExtractedFacts] = None
    ) -> ExtractedFacts:
        """Extract facts from full conversation."""
        facts = existing or ExtractedFacts()

        for msg in messages:
            if msg.sender == "prospect":
                facts = self.extract_from_message(msg.text, facts)

        return facts
```

### 6. Update Initial Message Generation
- In `telegram_agent.py`, update `generate_initial_message`:
```python
async def generate_initial_message(self, prospect: Prospect) -> AgentAction:
    """Generate varied initial outreach message."""
    from sales_agent.context import PhraseTracker

    # Initialize phrase tracker with prospect's history
    tracker = PhraseTracker(
        used_greetings=prospect.used_greetings,
        used_phrases=prospect.used_phrases
    )

    # Get varied components
    greeting = tracker.get_greeting(prospect.name)
    opening = tracker.get_opening(self.agent_name)
    question = tracker.get_closing_question()

    # Build prompt with variation hints
    user_prompt = f"""Сгенерируй ПЕРВОЕ сообщение для нового клиента.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}

ОБЯЗАТЕЛЬНО используй эти элементы:
- Приветствие: "{greeting}"
- Представление: "{opening}"
- Завершающий вопрос (можешь перефразировать): "{question}"

Собери из них естественное сообщение (1-3 предложения).
НЕ копируй дословно - адаптируй под контекст.

Верни JSON с action="reply".
"""

    # ... call Claude API ...

    # After generating, update used phrases
    used_greetings, used_phrases = tracker.get_used_lists()
    # Store back to prospect (via prospect_manager)
```

### 7. Update Context Building
- In `prospect_manager.py`, update `get_conversation_context`:
```python
def get_conversation_context(
    self,
    telegram_id: int | str,
    recent_limit: int = 15,
    include_summary: bool = True
) -> str:
    """Get formatted conversation context with summary."""
    prospect = self.get_prospect(telegram_id)
    if not prospect:
        return ""

    # If we have a summary and many messages, use it
    if include_summary and prospect.conversation_summary and len(prospect.conversation_history) > 20:
        from sales_agent.context import ContextSummarizer
        summarizer = ContextSummarizer()
        return summarizer.build_context_with_summary(
            prospect.conversation_summary,
            prospect.conversation_history,
            recent_count=recent_limit
        )

    # Otherwise return recent messages
    messages = prospect.conversation_history[-recent_limit:]
    lines = []
    for msg in messages:
        sender = "Вы" if msg.sender == "agent" else prospect.name
        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{timestamp}] {sender}: {msg.text}")

    return "\n".join(lines)
```

### 8. Add Facts to Agent Context
- When generating response, include extracted facts:
```python
facts_context = ""
if prospect.extracted_facts:
    facts = ExtractedFacts.from_dict(prospect.extracted_facts)
    facts_context = f"""
Известные факты о клиенте:
- Бюджет: {facts.budget_min}-{facts.budget_max} {facts.budget_currency if facts.budget_min else 'не указан'}
- Тип объекта: {facts.property_type or 'не указан'}
- Локации: {', '.join(facts.location_preferences) or 'не указаны'}
- Цель: {facts.purpose or 'не указана'}
- Email: {facts.email or 'не указан'}
"""
```

### 9. Validate Implementation
- Test initial message variation (reset prospect multiple times)
- Test phrase tracking persistence
- Test context summarization
- Test fact extraction

## Testing Strategy

### Unit Tests
- Test PhraseTracker variation
- Test FactExtractor patterns
- Test ContextSummarizer output

### Integration Tests
1. Reset prospect, generate initial message 5 times → verify variation
2. Long conversation (30+ messages) → verify summary generated
3. Extract budget from various formats → verify parsing

### Edge Cases
- All greetings used
- Very long conversation (100+ messages)
- Facts mentioned in different formats
- Multi-language messages

## Acceptance Criteria
- [ ] Initial messages vary (different greeting, opening each time)
- [ ] Used phrases tracked per prospect
- [ ] Conversations > 30 messages get summarized
- [ ] BANT facts extracted and stored
- [ ] Context includes summary + recent messages
- [ ] No "Рад познакомиться" repetition within same prospect

## Validation Commands
```bash
# Test context module
uv run python -c "from sales_agent.context import PhraseTracker, FactExtractor; print('OK')"

# Test phrase variation
uv run python -c "
from sales_agent.context.phrase_tracker import PhraseTracker
tracker = PhraseTracker()
for i in range(5):
    print(tracker.get_greeting('Алексей'))
"

# Test fact extraction
uv run python -c "
from sales_agent.context.fact_extractor import FactExtractor
extractor = FactExtractor()
facts = extractor.extract_from_message('Хочу виллу в Чангу за 500к')
print(f'Type: {facts.property_type}, Budget: {facts.budget_max}, Location: {facts.location_preferences}')
"
```

## Notes
- Phrase tracking adds state to prospects - ensure serialization works
- Summary generation uses Claude API - adds latency and cost
- Consider caching summaries (don't regenerate every message)
- Fact extraction is regex-based - may miss complex expressions
- Budget currency detection could be improved
- Consider user confirmation for extracted facts
