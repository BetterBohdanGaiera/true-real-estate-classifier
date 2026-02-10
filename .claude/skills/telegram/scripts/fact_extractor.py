"""
Extract and store important facts from conversations.

This module provides FactExtractor which analyzes conversation messages
to extract BANT (Budget, Authority, Need, Timeline) and other relevant
facts about the prospect.
"""
from dataclasses import dataclass, field
from typing import Optional, Any
import re


@dataclass
class ExtractedFacts:
    """
    Extracted BANT and other facts from conversation.

    BANT Framework:
    - Budget: Financial parameters for the purchase
    - Authority: Decision-making power and stakeholders
    - Need: Property requirements and preferences
    - Timeline: Urgency and purchase timeframe

    Attributes:
        budget_min: Minimum budget mentioned (normalized to full amount)
        budget_max: Maximum budget mentioned (normalized to full amount)
        budget_currency: Currency for budget (default USD)
        is_decision_maker: Whether prospect is the decision maker
        other_stakeholders: List of other decision makers mentioned
        property_type: Type of property (villa, apartment, land, etc.)
        location_preferences: List of preferred locations
        purpose: Purpose of purchase (investment, living, rental)
        timeline: Purchase timeline (urgent, 3 months, 1 year, etc.)
        email: Contact email if provided
        phone: Contact phone if provided
    """
    # Budget
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: str = "USD"

    # Authority
    is_decision_maker: Optional[bool] = None
    other_stakeholders: list[str] = field(default_factory=list)

    # Need
    property_type: Optional[str] = None  # villa, apartment, land, house, studio
    location_preferences: list[str] = field(default_factory=list)
    purpose: Optional[str] = None  # investment, living, rental
    bedrooms: Optional[int] = None
    features: list[str] = field(default_factory=list)  # pool, ocean view, etc.

    # Timeline
    timeline: Optional[str] = None  # "urgent", "3 months", "1 year"

    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for storage.

        Returns:
            Dictionary representation suitable for JSON storage
        """
        return {
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "budget_currency": self.budget_currency,
            "is_decision_maker": self.is_decision_maker,
            "other_stakeholders": self.other_stakeholders,
            "property_type": self.property_type,
            "location_preferences": self.location_preferences,
            "purpose": self.purpose,
            "bedrooms": self.bedrooms,
            "features": self.features,
            "timeline": self.timeline,
            "email": self.email,
            "phone": self.phone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractedFacts":
        """
        Create from dictionary.

        Args:
            data: Dictionary with fact fields

        Returns:
            ExtractedFacts instance
        """
        return cls(
            budget_min=data.get("budget_min"),
            budget_max=data.get("budget_max"),
            budget_currency=data.get("budget_currency", "USD"),
            is_decision_maker=data.get("is_decision_maker"),
            other_stakeholders=data.get("other_stakeholders", []),
            property_type=data.get("property_type"),
            location_preferences=data.get("location_preferences", []),
            purpose=data.get("purpose"),
            bedrooms=data.get("bedrooms"),
            features=data.get("features", []),
            timeline=data.get("timeline"),
            email=data.get("email"),
            phone=data.get("phone"),
        )

    def merge_with(self, other: "ExtractedFacts") -> "ExtractedFacts":
        """
        Merge with another ExtractedFacts, preferring non-None values.

        Args:
            other: Another ExtractedFacts to merge

        Returns:
            New ExtractedFacts with merged values
        """
        return ExtractedFacts(
            budget_min=other.budget_min if other.budget_min is not None else self.budget_min,
            budget_max=other.budget_max if other.budget_max is not None else self.budget_max,
            budget_currency=other.budget_currency if other.budget_currency != "USD" else self.budget_currency,
            is_decision_maker=other.is_decision_maker if other.is_decision_maker is not None else self.is_decision_maker,
            other_stakeholders=list(set(self.other_stakeholders + other.other_stakeholders)),
            property_type=other.property_type if other.property_type is not None else self.property_type,
            location_preferences=list(set(self.location_preferences + other.location_preferences)),
            purpose=other.purpose if other.purpose is not None else self.purpose,
            bedrooms=other.bedrooms if other.bedrooms is not None else self.bedrooms,
            features=list(set(self.features + other.features)),
            timeline=other.timeline if other.timeline is not None else self.timeline,
            email=other.email if other.email is not None else self.email,
            phone=other.phone if other.phone is not None else self.phone,
        )

    def format_for_context(self) -> str:
        """
        Format extracted facts for inclusion in agent context.

        Returns:
            Formatted string describing known facts
        """
        parts = []

        if self.budget_min is not None or self.budget_max is not None:
            if self.budget_min == self.budget_max and self.budget_min is not None:
                parts.append(f"- Byudzhet: {self.budget_min:,} {self.budget_currency}")
            elif self.budget_min is not None and self.budget_max is not None:
                parts.append(f"- Byudzhet: {self.budget_min:,}-{self.budget_max:,} {self.budget_currency}")
            elif self.budget_min is not None:
                parts.append(f"- Byudzhet: ot {self.budget_min:,} {self.budget_currency}")
            else:
                parts.append(f"- Byudzhet: do {self.budget_max:,} {self.budget_currency}")

        if self.property_type:
            type_labels = {
                "villa": "villa",
                "apartment": "apartamenty",
                "land": "zemlya",
                "house": "dom",
                "studio": "studiya",
            }
            parts.append(f"- Tip ob''yekta: {type_labels.get(self.property_type, self.property_type)}")

        if self.location_preferences:
            parts.append(f"- Lokatsii: {', '.join(self.location_preferences)}")

        if self.purpose:
            purpose_labels = {
                "investment": "investitsii",
                "living": "dlya prozhivaniya",
                "rental": "dlya sdachi v arendu",
            }
            parts.append(f"- Tsel': {purpose_labels.get(self.purpose, self.purpose)}")

        if self.bedrooms:
            parts.append(f"- Spalen: {self.bedrooms}")

        if self.features:
            parts.append(f"- Trebovaniya: {', '.join(self.features)}")

        if self.timeline:
            parts.append(f"- Sroki: {self.timeline}")

        if self.email:
            parts.append(f"- Email: {self.email}")

        if not parts:
            return ""

        return "Izvestnyye fakty o kliyente:\n" + "\n".join(parts)


class FactExtractor:
    """
    Extract facts from conversation messages using pattern matching.

    Uses regex patterns to identify budget amounts, locations, property types,
    and other relevant information from message text.

    Example:
        >>> extractor = FactExtractor()
        >>> facts = extractor.extract_from_message("Khochu villu v Changgu za 500k")
        >>> print(facts.property_type)  # "villa"
        >>> print(facts.budget_max)     # 500000
        >>> print(facts.location_preferences)  # ["changgu"]
    """

    # Budget patterns - capture numeric amounts with various formats
    BUDGET_PATTERNS = [
        (r"(\d+)\s*[kK]", 1000),           # 500k, 500K
        (r"\$\s*(\d[\d\s]*\d)", 1),          # $500000, $ 500 000
        (r"(\d[\d\s]*\d)\s*\$", 1),          # 500000$
        (r"(\d+)\s*tys", 1000),              # 500 tysyach
        (r"(\d+(?:[.,]\d+)?)\s*mln", 1000000),  # 1 mln, 1.5 mln
        (r"byudzhet[:\s]+(\d[\d\s]*)", 1),    # byudzhet: 500000
        (r"(\d[\d\s]*\d)\s*(?:doll|usd)", 1),  # 500000 dollarov/usd
    ]

    # Budget range patterns - capture min-max ranges
    BUDGET_RANGE_PATTERNS = [
        (r"(\d+)\s*[-]\s*(\d+)\s*[kK]", 1000),   # 300-500k, 300-500K
        (r"ot\s*(\d+)\s*do\s*(\d+)\s*[kK]", 1000),  # ot 300 do 500k
        (r"\$\s*(\d+)\s*[-]\s*\$?\s*(\d+)", 1),    # $300-$500 or $300-500
    ]

    # Location keywords - Bali regions and areas
    LOCATION_KEYWORDS = [
        "changgu", "canggu",
        "seminyak", "seminyak",
        "ubud", "ubud",
        "sanur", "sanur",
        "nusa dua", "nusa dua",
        "uluwatu", "uluwatu",
        "bukit", "bukit",
        "jimbaran", "jimbaran",
        "kuta", "kuta",
        "legian", "legian",
        "tabanan", "tabanan",
        "amed", "amed",
        "lovina", "lovina",
        "echo beach", "echo beach",
    ]

    # Property type patterns - regex patterns mapped to types
    PROPERTY_TYPES = {
        r"vill[auy]": "villa",
        r"apartament[yai]?": "apartment",
        r"zeml[yaiu]|uchast[ok]": "land",
        r"dom[a]?": "house",
        r"studi[yaiu]": "studio",
        r"taunhaus": "townhouse",
        r"pentkhaus": "penthouse",
    }

    # Purpose indicators
    PURPOSE_PATTERNS = {
        "investment": [r"investits", r"vlozhen", r"dokhod", r"roi", r"okupaem"],
        "living": [r"zhit", r"pereyezd", r"pereekhat", r"pmzh", r"postoyann"],
        "rental": [r"sdavat", r"arend", r"arendn", r"rental"],
    }

    # Timeline patterns
    TIMELINE_PATTERNS = [
        (r"srochno|asap|kak mozhno skoreye", "urgent"),
        (r"v blizhaysh|skoro|na dnyakh", "within_month"),
        (r"(\d+)\s*mes", "{} months"),
        (r"cherez\s*god|v sleduyushchem godu", "1 year"),
        (r"ne srochno|ne toropl", "no_rush"),
    ]

    # Bedroom patterns
    BEDROOM_PATTERNS = [
        r"(\d+)\s*(?:spaln|bedroom|br)",
        r"(\d+)\s*(?:komnat)",
    ]

    # Feature patterns
    FEATURE_KEYWORDS = {
        "pool": [r"basseyn", r"pool"],
        "ocean_view": [r"vid na okean", r"ocean view", r"s vidom"],
        "rice_field_view": [r"vid na ris", r"rice field", r"risov"],
        "private": [r"privatn", r"private", r"uyedin"],
        "gated": [r"okhranyaem", r"gated", r"zakryt"],
        "new": [r"nov[ya]", r"new build", r"svezh"],
        "furnished": [r"mebel", r"furnished", r"obstavlen"],
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
            existing: Existing facts to update (new facts override)

        Returns:
            Updated ExtractedFacts with any new information found
        """
        facts = ExtractedFacts()
        message_lower = message.lower()

        # Extract budget
        self._extract_budget(message_lower, facts)

        # Extract location
        self._extract_locations(message_lower, facts)

        # Extract property type
        self._extract_property_type(message_lower, facts)

        # Extract email
        self._extract_email(message, facts)

        # Extract phone
        self._extract_phone(message, facts)

        # Extract purpose
        self._extract_purpose(message_lower, facts)

        # Extract timeline
        self._extract_timeline(message_lower, facts)

        # Extract bedrooms
        self._extract_bedrooms(message_lower, facts)

        # Extract features
        self._extract_features(message_lower, facts)

        # Merge with existing if provided
        if existing:
            return existing.merge_with(facts)

        return facts

    def _extract_budget(self, message: str, facts: ExtractedFacts) -> None:
        """Extract budget amounts from message."""
        # First, try to extract budget ranges (min-max)
        for pattern, multiplier in self.BUDGET_RANGE_PATTERNS:
            match = re.search(pattern, message)
            if match:
                try:
                    min_str = match.group(1).replace(" ", "").replace(",", ".")
                    max_str = match.group(2).replace(" ", "").replace(",", ".")
                    min_amount = int(float(min_str) * multiplier)
                    max_amount = int(float(max_str) * multiplier)

                    # Update min/max with range values
                    if facts.budget_min is None or min_amount < facts.budget_min:
                        facts.budget_min = min_amount
                    if facts.budget_max is None or max_amount > facts.budget_max:
                        facts.budget_max = max_amount
                    return  # Range found, no need for single patterns
                except (ValueError, IndexError):
                    continue

        # If no range found, try single budget patterns
        for pattern, multiplier in self.BUDGET_PATTERNS:
            match = re.search(pattern, message)
            if match:
                # Remove spaces from captured number
                amount_str = match.group(1).replace(" ", "").replace(",", ".")
                try:
                    # Handle decimal amounts (e.g., 1.5 mln)
                    amount = float(amount_str) * multiplier
                    amount = int(amount)

                    # Update min/max
                    if facts.budget_min is None or amount < facts.budget_min:
                        facts.budget_min = amount
                    if facts.budget_max is None or amount > facts.budget_max:
                        facts.budget_max = amount
                except ValueError:
                    continue

    def _extract_locations(self, message: str, facts: ExtractedFacts) -> None:
        """Extract location preferences from message."""
        for loc in self.LOCATION_KEYWORDS:
            if loc in message and loc not in facts.location_preferences:
                # Normalize location name
                normalized = loc
                if normalized not in facts.location_preferences:
                    facts.location_preferences.append(normalized)

    def _extract_property_type(self, message: str, facts: ExtractedFacts) -> None:
        """Extract property type from message."""
        for pattern, prop_type in self.PROPERTY_TYPES.items():
            if re.search(pattern, message):
                facts.property_type = prop_type
                return  # Take first match

    def _extract_email(self, message: str, facts: ExtractedFacts) -> None:
        """Extract email address from message."""
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            facts.email = email_match.group(0).lower()

    def _extract_phone(self, message: str, facts: ExtractedFacts) -> None:
        """Extract phone number from message."""
        # Match various phone formats
        phone_patterns = [
            r'\+\d{1,3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 999 123 45 67
            r'\+\d{10,15}',  # +79991234567
            r'\d{10,11}',    # 89991234567
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, message)
            if match:
                facts.phone = match.group(0)
                return

    def _extract_purpose(self, message: str, facts: ExtractedFacts) -> None:
        """Extract purchase purpose from message."""
        for purpose, patterns in self.PURPOSE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    facts.purpose = purpose
                    return

    def _extract_timeline(self, message: str, facts: ExtractedFacts) -> None:
        """Extract timeline/urgency from message."""
        for pattern, timeline_value in self.TIMELINE_PATTERNS:
            match = re.search(pattern, message)
            if match:
                if "{}" in timeline_value:
                    # Pattern with capture group for months
                    facts.timeline = timeline_value.format(match.group(1))
                else:
                    facts.timeline = timeline_value
                return

    def _extract_bedrooms(self, message: str, facts: ExtractedFacts) -> None:
        """Extract number of bedrooms from message."""
        for pattern in self.BEDROOM_PATTERNS:
            match = re.search(pattern, message)
            if match:
                try:
                    facts.bedrooms = int(match.group(1))
                    return
                except ValueError:
                    continue

    def _extract_features(self, message: str, facts: ExtractedFacts) -> None:
        """Extract property features from message."""
        for feature, patterns in self.FEATURE_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    if feature not in facts.features:
                        facts.features.append(feature)
                    break

    def extract_from_conversation(
        self,
        messages: list,
        existing: Optional[ExtractedFacts] = None
    ) -> ExtractedFacts:
        """
        Extract facts from full conversation.

        Args:
            messages: List of ConversationMessage objects
            existing: Existing facts to update

        Returns:
            ExtractedFacts with all information from conversation
        """
        facts = existing or ExtractedFacts()

        for msg in messages:
            # Only extract from prospect messages
            if hasattr(msg, 'sender') and msg.sender == "prospect":
                text = msg.text if hasattr(msg, 'text') else str(msg)
                facts = self.extract_from_message(text, facts)
            elif isinstance(msg, str):
                # Handle plain string messages
                facts = self.extract_from_message(msg, facts)

        return facts
