"""
Prospect Manager for Telegram Agent.
Manages the list of prospects and their conversation state.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import Prospect, ProspectStatus, ConversationMessage


class ProspectManager:
    """Manages prospects and their conversation states."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self._prospects: dict[str, Prospect] = {}
        self._load_prospects()

    def _load_prospects(self) -> None:
        """Load prospects from config file."""
        if not self.config_path.exists():
            # Create default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_prospects()
            return

        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for p_data in data.get("prospects", []):
            # Convert string dates to datetime
            if "first_contact" in p_data and p_data["first_contact"]:
                p_data["first_contact"] = datetime.fromisoformat(p_data["first_contact"])
            if "last_contact" in p_data and p_data["last_contact"]:
                p_data["last_contact"] = datetime.fromisoformat(p_data["last_contact"])
            if "last_response" in p_data and p_data["last_response"]:
                p_data["last_response"] = datetime.fromisoformat(p_data["last_response"])

            # Convert conversation history
            if "conversation_history" in p_data:
                p_data["conversation_history"] = [
                    ConversationMessage(
                        id=m["id"],
                        sender=m["sender"],
                        text=m["text"],
                        timestamp=datetime.fromisoformat(m["timestamp"])
                    )
                    for m in p_data["conversation_history"]
                ]

            prospect = Prospect(**p_data)
            key = self._normalize_id(prospect.telegram_id)
            self._prospects[key] = prospect

    def _save_prospects(self) -> None:
        """Save prospects to config file."""
        data = {
            "prospects": [
                {
                    **p.model_dump(),
                    "first_contact": p.first_contact.isoformat() if p.first_contact else None,
                    "last_contact": p.last_contact.isoformat() if p.last_contact else None,
                    "last_response": p.last_response.isoformat() if p.last_response else None,
                    "conversation_history": [
                        {
                            "id": m.id,
                            "sender": m.sender,
                            "text": m.text,
                            "timestamp": m.timestamp.isoformat()
                        }
                        for m in p.conversation_history
                    ]
                }
                for p in self._prospects.values()
            ]
        }

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_id(self, telegram_id: int | str) -> str:
        """Normalize telegram ID for lookup."""
        if isinstance(telegram_id, int):
            return str(telegram_id)
        # Remove @ prefix for usernames
        return telegram_id.lstrip('@').lower()

    def get_all_prospects(self) -> list[Prospect]:
        """Get all prospects."""
        return list(self._prospects.values())

    def get_new_prospects(self) -> list[Prospect]:
        """Get prospects that haven't been contacted yet."""
        return [p for p in self._prospects.values() if p.status == ProspectStatus.NEW]

    def get_active_prospects(self) -> list[Prospect]:
        """Get prospects with active conversations."""
        return [
            p for p in self._prospects.values()
            if p.status in [ProspectStatus.CONTACTED, ProspectStatus.IN_CONVERSATION]
        ]

    def is_prospect(self, telegram_id: int | str) -> bool:
        """Check if a telegram ID is a known prospect."""
        key = self._normalize_id(telegram_id)
        return key in self._prospects

    def get_prospect(self, telegram_id: int | str) -> Optional[Prospect]:
        """Get prospect by telegram ID."""
        key = self._normalize_id(telegram_id)
        return self._prospects.get(key)

    def add_prospect(
        self,
        telegram_id: int | str,
        name: str,
        context: str,
        notes: str = ""
    ) -> Prospect:
        """Add a new prospect."""
        key = self._normalize_id(telegram_id)

        if key in self._prospects:
            raise ValueError(f"Prospect {telegram_id} already exists")

        prospect = Prospect(
            telegram_id=telegram_id,
            name=name,
            context=context,
            notes=notes
        )

        self._prospects[key] = prospect
        self._save_prospects()
        return prospect

    def remove_prospect(self, telegram_id: int | str) -> bool:
        """Remove a prospect."""
        key = self._normalize_id(telegram_id)
        if key in self._prospects:
            del self._prospects[key]
            self._save_prospects()
            return True
        return False

    def mark_contacted(self, telegram_id: int | str, message_id: int, message_text: str) -> None:
        """Mark prospect as contacted (initial message sent)."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            raise ValueError(f"Prospect {telegram_id} not found")

        now = datetime.now()

        if prospect.first_contact is None:
            prospect.first_contact = now

        prospect.last_contact = now
        prospect.status = ProspectStatus.CONTACTED
        prospect.message_count += 1

        prospect.conversation_history.append(
            ConversationMessage(
                id=message_id,
                sender="agent",
                text=message_text,
                timestamp=now
            )
        )

        self._save_prospects()

    def record_response(self, telegram_id: int | str, message_id: int, message_text: str) -> None:
        """Record a response from a prospect."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            raise ValueError(f"Prospect {telegram_id} not found")

        now = datetime.now()
        prospect.last_response = now
        prospect.status = ProspectStatus.IN_CONVERSATION

        prospect.conversation_history.append(
            ConversationMessage(
                id=message_id,
                sender="prospect",
                text=message_text,
                timestamp=now
            )
        )

        self._save_prospects()

    def record_agent_message(self, telegram_id: int | str, message_id: int, message_text: str) -> None:
        """Record an agent message (reply to prospect)."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            raise ValueError(f"Prospect {telegram_id} not found")

        now = datetime.now()
        prospect.last_contact = now
        prospect.message_count += 1

        prospect.conversation_history.append(
            ConversationMessage(
                id=message_id,
                sender="agent",
                text=message_text,
                timestamp=now
            )
        )

        self._save_prospects()

    def update_status(self, telegram_id: int | str, status: ProspectStatus) -> None:
        """Update prospect status."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            raise ValueError(f"Prospect {telegram_id} not found")

        prospect.status = status
        self._save_prospects()

    def get_conversation_context(self, telegram_id: int | str, limit: int = 20) -> str:
        """Get formatted conversation history for LLM context."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            return ""

        messages = prospect.conversation_history[-limit:]

        lines = []
        for msg in messages:
            sender = "Вы" if msg.sender == "agent" else prospect.name
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{timestamp}] {sender}: {msg.text}")

        return "\n".join(lines)

    def should_follow_up(self, telegram_id: int | str, hours: int = 24) -> bool:
        """Check if we should follow up with a prospect."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            return False

        # Skip if not in active status
        if prospect.status not in [ProspectStatus.CONTACTED, ProspectStatus.IN_CONVERSATION]:
            return False

        # Check if we've heard back
        if prospect.last_response and prospect.last_contact:
            # They responded after our last message - wait for response before following up
            if prospect.last_response > prospect.last_contact:
                return False

        # Check time since last contact
        if prospect.last_contact:
            hours_since = (datetime.now() - prospect.last_contact).total_seconds() / 3600
            return hours_since >= hours

        return False

    def get_messages_sent_today(self, telegram_id: int | str) -> int:
        """Get number of messages sent today to a prospect."""
        key = self._normalize_id(telegram_id)
        prospect = self._prospects.get(key)

        if not prospect:
            return 0

        today = datetime.now().date()
        count = 0

        for msg in prospect.conversation_history:
            if msg.sender == "agent" and msg.timestamp.date() == today:
                count += 1

        return count
