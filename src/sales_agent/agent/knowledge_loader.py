"""
Knowledge base loader for Telegram agent.
Detects topics from user messages and selectively loads relevant context.
"""
import logging
from pathlib import Path
from typing import Optional

import tiktoken

logger = logging.getLogger(__name__)


# Topic file mapping
TOPIC_FILES = {
    "00": "00_MASTER_CHEATSHEET.md",
    "01": "01_BALI_GEOGRAPHY.md",
    "02": "02_LEGAL_FRAMEWORK.md",
    "03": "03_TAX_GUIDE.md",
    "04": "04_FINANCIAL_MODEL_ANALYSIS.md",
    "05": "05_SALES_TOOLKIT.md",
    "06": "06_MARKET_ANALYSIS.md",
    "07": "07_OPEN_QUESTIONS.md",
    "08": "08_IMPROVEMENT_PROPOSALS.md",
    "09": "09_GLOSSARY.md",
    "10": "10_RISK_TAXONOMY.md",
    "11": "11_CLIENT_TEMPLATES.md",
}

# Topic display names for context formatting
TOPIC_NAMES = {
    "00": "Главная шпаргалка",
    "01": "География Бали",
    "02": "Правовая база",
    "03": "Налоги",
    "04": "Анализ финансовых моделей",
    "05": "Инструменты продаж",
    "06": "Анализ рынка",
    "07": "Открытые вопросы",
    "08": "Предложения по улучшению",
    "09": "Глоссарий",
    "10": "Таксономия рисков",
    "11": "Шаблоны для клиентов",
}

# Priority order for topics (most commonly needed first)
TOPIC_PRIORITY = ["01", "02", "03", "04", "05", "06", "09", "10", "11", "07", "08"]


class KnowledgeLoader:
    """Loads and manages knowledge base context for agent responses."""

    # Topic keyword mapping (Russian keywords, lowercase)
    TOPIC_KEYWORDS = {
        "01": [
            "геогра", "район", "локация", "чангу", "убуд", "семиньяк",
            "букит", "санур", "нуса", "улувату", "перереран", "керобокан",
            "бедугул", "амед", "ловина", "канди", "денпасар", "кута",
            "легиан", "джимбаран", "танджунг", "печенг", "region", "location"
        ],
        "02": [
            "legal", "leasehold", "freehold", "закон", "право", "собственность",
            "владение", "оформлен", "pt pma", "pma", "нотариус", "контракт",
            "договор", "регистрац", "юридич", "наследов", "продлен"
        ],
        "03": [
            "налог", "ндфл", "tax", "налогообложен", "bali tax", "rental tax",
            "ставка", "резидент", "нерезидент", "комисси", "сбор"
        ],
        "04": [
            "доход", "roi", "инвестиц", "окупаем", "прибыл", "финанс", "модел",
            "доходность", "рентабельн", "заполняем", "выручк", "чистый доход",
            "промоушен", "промо период", "расчет", "калькуляц"
        ],
        "05": [
            "преимуществ", "usp", "почему", "продаж", "конкурент", "возражен",
            "true real estate", "комиссия агент", "estate market", "ai аналитик",
            "отдел заботы", "напрямую дешевле", "зачем агентство"
        ],
        "06": [
            "рынок", "тренд", "цен", "спрос", "предложен", "market", "аналитик",
            "прогноз", "статистик", "данные", "динамик"
        ],
        "07": [
            "вопрос", "непонятн", "question", "уточнен", "неясн"
        ],
        "08": [
            "улучшен", "предложен", "improvement", "добавить", "дополн"
        ],
        "09": [
            "глоссар", "термин", "что значит", "glossary", "определен",
            "расшифров", "аббревиатур", "что такое"
        ],
        "10": [
            "риск", "опасн", "проблем", "risk", "недостат", "минус",
            "сложност", "подводн", "камн"
        ],
        "11": [
            "шаблон", "template", "пример", "скрипт", "образец", "форма"
        ],
    }

    def __init__(self, knowledge_base_path: Path):
        """
        Initialize with path to knowledge_base_final directory.

        Args:
            knowledge_base_path: Path to the knowledge_base_final directory
        """
        self.knowledge_base_path = Path(knowledge_base_path)
        self._encoding: Optional[tiktoken.Encoding] = None

    @property
    def encoding(self) -> tiktoken.Encoding:
        """Lazy load tiktoken encoding."""
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        return self._encoding

    def detect_topics(self, message: str) -> list[str]:
        """
        Detect relevant topic IDs from a message.

        Args:
            message: User message to analyze

        Returns:
            List of topic IDs like ["01", "04"] based on keyword matches,
            sorted by priority.
        """
        message_lower = message.lower()
        detected = set()

        for topic_id, keywords in self.TOPIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    detected.add(topic_id)
                    break  # One match is enough per topic

        # Sort by priority order
        result = [t for t in TOPIC_PRIORITY if t in detected]
        return result

    def load_master_cheatsheet(self) -> str:
        """
        Load the master cheatsheet (always available).

        Returns:
            Content of the master cheatsheet, or empty string if not found.
        """
        return self.load_topic("00")

    def load_topic(self, topic_id: str) -> str:
        """
        Load a specific topic file by ID.

        Args:
            topic_id: Topic ID (e.g., "01" for BALI_GEOGRAPHY)

        Returns:
            Content of the topic file, or empty string if not found.
        """
        if topic_id not in TOPIC_FILES:
            logger.warning(f"Unknown topic ID: {topic_id}")
            return ""

        file_path = self.knowledge_base_path / TOPIC_FILES[topic_id]

        if not file_path.exists():
            logger.warning(f"Topic file not found: {file_path}")
            return ""

        try:
            return file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError) as e:
            logger.error(f"Error reading topic file {file_path}: {e}")
            return ""

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens in the text.
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def get_relevant_context(self, message: str, max_tokens: int = 4000) -> str:
        """
        Get relevant knowledge context for a message.

        Strategy:
        1. Always include master cheatsheet (~500-700 tokens)
        2. Detect topics from message
        3. Load topic files in order of relevance until token limit
        4. Return formatted string ready for prompt injection

        Args:
            message: User message to get context for
            max_tokens: Maximum tokens to include (default 4000)

        Returns:
            Formatted context string with relevant knowledge base content.
        """
        if not self.knowledge_base_path.exists():
            logger.warning(
                f"Knowledge base path does not exist: {self.knowledge_base_path}"
            )
            return ""

        sections = []
        total_tokens = 0

        # 1. Always include master cheatsheet
        master_content = self.load_master_cheatsheet()
        if master_content:
            master_section = f"### {TOPIC_NAMES['00']}\n\n{master_content}"
            master_tokens = self.count_tokens(master_section)

            if master_tokens <= max_tokens:
                sections.append(master_section)
                total_tokens = master_tokens
            else:
                # Truncate master cheatsheet if too large
                truncated = self._truncate_to_tokens(master_content, max_tokens - 100)
                sections.append(f"### {TOPIC_NAMES['00']} (сокращено)\n\n{truncated}")
                return self._format_context(sections)

        # 2. Detect topics from message
        detected_topics = self.detect_topics(message)

        # 3. Load topic files until token limit
        for topic_id in detected_topics:
            topic_content = self.load_topic(topic_id)
            if not topic_content:
                continue

            topic_section = f"### {TOPIC_NAMES[topic_id]}\n\n{topic_content}"
            topic_tokens = self.count_tokens(topic_section)

            if total_tokens + topic_tokens <= max_tokens:
                sections.append(topic_section)
                total_tokens += topic_tokens
            else:
                # Check if we can fit a truncated version
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 200:  # Only add if meaningful space left
                    truncated = self._truncate_to_tokens(
                        topic_content, remaining_tokens - 100
                    )
                    sections.append(
                        f"### {TOPIC_NAMES[topic_id]} (сокращено)\n\n{truncated}"
                    )
                break  # No more space

        return self._format_context(sections)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text with ellipsis if needed.
        """
        if max_tokens <= 0:
            return ""

        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoding.decode(truncated_tokens)

        # Try to end at a sentence or paragraph boundary
        last_paragraph = truncated_text.rfind("\n\n")
        last_sentence = max(
            truncated_text.rfind(". "),
            truncated_text.rfind(".\n"),
        )

        if last_paragraph > len(truncated_text) * 0.7:
            return truncated_text[:last_paragraph] + "\n\n..."
        elif last_sentence > len(truncated_text) * 0.7:
            return truncated_text[: last_sentence + 1] + "\n\n..."
        else:
            return truncated_text + "..."

    def _format_context(self, sections: list[str]) -> str:
        """
        Format sections into final context string.

        Args:
            sections: List of formatted section strings

        Returns:
            Complete formatted context for prompt injection.
        """
        if not sections:
            return ""

        header = "## База знаний\n\n"
        content = "\n\n---\n\n".join(sections)
        return header + content


# Simple test
if __name__ == "__main__":
    import sys

    # Find project root
    project_root = Path(__file__).parent.parent.parent.parent.parent
    kb_path = project_root / "knowledge_base_final"

    if not kb_path.exists():
        print(f"Knowledge base not found at: {kb_path}")
        sys.exit(1)

    loader = KnowledgeLoader(kb_path)

    # Test topic detection
    test_messages = [
        "Какая доходность у вилл в Чангу?",
        "Расскажите про налоги на Бали",
        "Что такое leasehold?",
        "Какие риски есть при покупке?",
        "Просто интересуюсь недвижимостью",
    ]

    print("=== Topic Detection Test ===\n")
    for msg in test_messages:
        topics = loader.detect_topics(msg)
        print(f"Message: {msg}")
        print(f"Topics: {topics}")
        print()

    # Test context loading
    print("\n=== Context Loading Test ===\n")
    context = loader.get_relevant_context("Какая доходность у вилл в Чангу?", max_tokens=2000)
    tokens = loader.count_tokens(context)
    print(f"Token count: {tokens}")
    print(f"Context length: {len(context)} chars")
    print(f"\nFirst 500 chars:\n{context[:500]}...")
