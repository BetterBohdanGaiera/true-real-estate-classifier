"""
Knowledge base loader for Telegram agent.
Loads knowledge base context for the AI agent, which decides topic relevance on its own.
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


class KnowledgeLoader:
    """Loads and manages knowledge base context for agent responses."""

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

    def get_available_topics_summary(self) -> str:
        """
        Return a formatted string listing all available knowledge base topics.

        This is intended for injection into the agent's system prompt so the AI
        knows what topic files exist and can request them as needed.

        Returns:
            Formatted multi-line string listing all topics by ID and name.
        """
        lines = ["Доступные разделы базы знаний:"]
        for topic_id in sorted(TOPIC_NAMES.keys()):
            if topic_id == "00":
                continue  # Master cheatsheet is always loaded separately
            lines.append(f"- {topic_id}: {TOPIC_NAMES[topic_id]}")
        return "\n".join(lines)

    def get_relevant_context(self, message: str, max_tokens: int = 4000) -> str:
        """
        Get relevant knowledge context for a message.

        Strategy:
        1. Always include master cheatsheet
        2. Append a summary of available topics so the AI agent knows
           what knowledge sections exist
        3. The AI agent decides which topics are relevant (no keyword matching)

        Args:
            message: User message to get context for (kept for backward
                     compatibility but no longer used for keyword detection)
            max_tokens: Maximum tokens to include (default 4000)

        Returns:
            Formatted context string with relevant knowledge base content.
        """
        if not self.knowledge_base_path.exists():
            logger.warning(
                f"Knowledge base path does not exist: {self.knowledge_base_path}"
            )
            return ""

        sections: list[str] = []
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

        # 2. Append available topics summary so the AI knows what exists
        topics_summary = self.get_available_topics_summary()
        summary_section = f"### Справочник разделов\n\n{topics_summary}"
        summary_tokens = self.count_tokens(summary_section)

        if total_tokens + summary_tokens <= max_tokens:
            sections.append(summary_section)
            total_tokens += summary_tokens

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

    # Test available topics summary
    print("=== Available Topics Summary ===\n")
    print(loader.get_available_topics_summary())
    print()

    # Test context loading
    print("\n=== Context Loading Test ===\n")
    context = loader.get_relevant_context(
        "Какая доходность у вилл в Чангу?", max_tokens=2000
    )
    tokens = loader.count_tokens(context)
    print(f"Token count: {tokens}")
    print(f"Context length: {len(context)} chars")
    print(f"\nFirst 500 chars:\n{context[:500]}...")
