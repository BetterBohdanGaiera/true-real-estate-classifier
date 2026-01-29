# Plan: Human-like Polish - Message Length, Timing & Typos

## Task Description
Add final polish to make the agent more human-like: control message length, vary response timing less predictably, and optionally add occasional typos with corrections.

## Objective
Make the sales agent communication indistinguishable from a real human by:
1. Controlling message length (no long monologues)
2. Adding more natural timing variation (not always 3-5 seconds)
3. Optionally adding occasional typos with self-corrections
4. Varying response patterns based on message type

## Problem Statement
Current robotic patterns:
- **Message length**: Agent can produce long essays when short answer is appropriate
- **Timing**: `random.uniform(3.0, 5.0)` is predictable - humans vary more
- **Perfect text**: Zero typos, zero corrections → unnatural
- **Consistent patterns**: Same delay regardless of message complexity

## Solution Approach
1. Add message length limits to agent config and prompts
2. Implement more natural timing distribution (non-uniform)
3. Optional: Add typo injection with correction messages
4. Vary timing based on message type and length

## Relevant Files

### Existing Files to Modify
- `src/sales_agent/crm/models.py` - Add message length config
- `src/sales_agent/agent/telegram_agent.py` - Add length instructions to prompt
- `src/sales_agent/telegram/telegram_service.py` - Improve timing variation
- `src/sales_agent/daemon.py` - Add typo injection option
- `src/sales_agent/config/agent_config.json` - Add polish config

### New Files to Create
- `src/sales_agent/humanizer/__init__.py` - Humanization utilities
- `src/sales_agent/humanizer/timing.py` - Natural timing distribution
- `src/sales_agent/humanizer/typo_injector.py` - Typo generation (optional)

## Step by Step Tasks

### 1. Add Polish Config to AgentConfig
- In `src/sales_agent/crm/models.py`, add:
```python
class HumanPolishConfig(BaseModel):
    """Configuration for human-like behavior polish."""
    # Message length limits
    max_message_length: int = 500  # chars
    target_message_length: int = 150  # ideal length
    warn_at_length: int = 300  # add prompt warning

    # Timing variation
    timing_mode: str = "natural"  # "uniform", "natural", "variable"
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 15.0

    # Typo settings (experimental)
    enable_typos: bool = False
    typo_probability: float = 0.05  # 5% of messages

    # Response style
    prefer_short_responses: bool = True
    split_long_messages: bool = False

# Add to AgentConfig:
human_polish: Optional[HumanPolishConfig] = None
```

### 2. Create Humanizer Module
- Create `src/sales_agent/humanizer/__init__.py`:
```python
"""
Humanizer module - Make agent communication more natural.

Provides:
- NaturalTiming: More human-like response timing
- TypoInjector: Optional typo generation (experimental)
- MessageSplitter: Split long messages naturally
"""
from .timing import NaturalTiming, calculate_natural_delay
from .typo_injector import TypoInjector

__all__ = [
    "NaturalTiming",
    "calculate_natural_delay",
    "TypoInjector",
]
```

### 3. Implement Natural Timing
- Create `src/sales_agent/humanizer/timing.py`:
```python
"""Natural timing distribution for human-like delays."""
import random
import math
from typing import Optional
from enum import Enum

class ResponseType(str, Enum):
    """Type of response affecting timing."""
    QUICK_ACK = "quick_ack"      # "ок", "да", short confirmations
    NORMAL = "normal"            # Standard responses
    THOUGHTFUL = "thoughtful"    # Complex questions, needs thinking
    LONG_READ = "long_read"      # Reading long incoming message

# Timing profiles (in seconds)
TIMING_PROFILES = {
    ResponseType.QUICK_ACK: {
        "base": 1.5,
        "variance": 1.0,
        "max": 4.0,
    },
    ResponseType.NORMAL: {
        "base": 3.0,
        "variance": 3.0,
        "max": 10.0,
    },
    ResponseType.THOUGHTFUL: {
        "base": 5.0,
        "variance": 5.0,
        "max": 15.0,
    },
    ResponseType.LONG_READ: {
        "base": 8.0,
        "variance": 7.0,
        "max": 20.0,
    },
}

def classify_response_type(
    incoming_message: str,
    outgoing_message: str
) -> ResponseType:
    """Classify the type of response for timing purposes."""
    incoming_len = len(incoming_message) if incoming_message else 0
    outgoing_len = len(outgoing_message) if outgoing_message else 0

    # Long incoming message = need time to read
    if incoming_len > 200:
        return ResponseType.LONG_READ

    # Short outgoing = quick acknowledgment
    if outgoing_len < 50:
        return ResponseType.QUICK_ACK

    # Long outgoing = thoughtful response
    if outgoing_len > 200:
        return ResponseType.THOUGHTFUL

    return ResponseType.NORMAL

def calculate_natural_delay(
    incoming_message: str,
    outgoing_message: str,
    mode: str = "natural"
) -> float:
    """
    Calculate a natural-feeling delay for response.

    Uses a log-normal distribution for more human-like variation:
    - Most responses cluster around a typical time
    - Occasional longer pauses (thinking, distracted)
    - Rare very quick responses

    Args:
        incoming_message: The message being responded to
        outgoing_message: The response being sent
        mode: "uniform" (current), "natural" (log-normal), "variable" (context-based)

    Returns:
        Delay in seconds
    """
    response_type = classify_response_type(incoming_message, outgoing_message)
    profile = TIMING_PROFILES[response_type]

    if mode == "uniform":
        # Current behavior - simple uniform distribution
        return random.uniform(profile["base"] - 1, profile["base"] + 2)

    elif mode == "natural":
        # Log-normal distribution - more realistic
        # Most values cluster around base, with occasional longer delays
        mu = math.log(profile["base"])
        sigma = 0.5  # Controls spread

        delay = random.lognormvariate(mu, sigma)

        # Add small random jitter
        delay += random.uniform(-0.5, 0.5)

        # Clamp to reasonable range
        return max(1.0, min(delay, profile["max"]))

    elif mode == "variable":
        # Context-based with more variation
        base = profile["base"]
        variance = profile["variance"]

        # Triangular distribution - peaks at base, tapers to edges
        delay = random.triangular(
            base - variance/2,
            base + variance,
            base
        )

        # 10% chance of "distracted" extra delay
        if random.random() < 0.1:
            delay += random.uniform(2, 5)

        return max(1.0, min(delay, profile["max"]))

    # Fallback
    return random.uniform(2.0, 5.0)

class NaturalTiming:
    """Service for natural response timing."""

    def __init__(self, mode: str = "natural"):
        self.mode = mode
        self._last_delay = None

    def get_delay(
        self,
        incoming_message: str,
        outgoing_message: str
    ) -> float:
        """Get delay for this response."""
        delay = calculate_natural_delay(
            incoming_message,
            outgoing_message,
            self.mode
        )

        # Avoid repeating exact same delay
        if self._last_delay and abs(delay - self._last_delay) < 0.5:
            delay += random.uniform(-1, 1)

        self._last_delay = delay
        return max(1.0, delay)

    def get_typing_duration(self, message_length: int) -> float:
        """Get realistic typing indicator duration."""
        # ~30 chars per second for fast typist, with variation
        chars_per_second = random.uniform(20, 40)
        duration = message_length / chars_per_second

        # Add thinking pauses for longer messages
        if message_length > 100:
            duration += random.uniform(0.5, 2)

        return max(1.0, min(duration, 8.0))
```

### 4. Implement Typo Injector (Optional)
- Create `src/sales_agent/humanizer/typo_injector.py`:
```python
"""Optional typo injection for human-like text (experimental)."""
import random
from typing import Optional, Tuple

# Common Russian typo patterns
TYPO_PATTERNS = [
    # Adjacent key typos (ЙЦУКЕН layout)
    ("а", "с"), ("о", "л"), ("е", "к"), ("и", "м"),
    ("н", "г"), ("т", "ь"), ("р", "п"),
    # Double letter mistakes
    ("нн", "н"), ("лл", "л"), ("сс", "с"),
    # Common mistakes
    ("тся", "ться"), ("ться", "тся"),
]

# Words that get commonly mistyped
COMMON_TYPOS = {
    "привет": ["прмвет", "приввет", "превет"],
    "хорошо": ["хорлшо", "хооршо", "хрошо"],
    "спасибо": ["спасмбо", "спассибо", "спаисбо"],
    "здравствуйте": ["здраствуйте", "здравствуйет"],
    "пожалуйста": ["пожалуста", "пожайлуста"],
}

class TypoInjector:
    """Inject occasional typos to make text more human-like."""

    def __init__(self, probability: float = 0.05):
        """
        Initialize typo injector.

        Args:
            probability: Chance of adding typo to any message (0.0-1.0)
        """
        self.probability = probability

    def should_add_typo(self) -> bool:
        """Randomly decide if this message should have a typo."""
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
        if len(words) < 3:
            return text, None  # Don't typo very short messages

        # Pick a random word to typo (not first or last)
        if len(words) <= 2:
            return text, None

        idx = random.randint(1, len(words) - 2)
        original_word = words[idx]

        # Check if it's a common typo word
        if original_word.lower() in COMMON_TYPOS:
            typo_word = random.choice(COMMON_TYPOS[original_word.lower()])
            words[idx] = typo_word
            typo_text = " ".join(words)
            correction = f"{original_word}*"
            return typo_text, correction

        # Otherwise, random character swap
        if len(original_word) >= 4:
            word_list = list(original_word)
            swap_idx = random.randint(1, len(word_list) - 2)
            # Swap adjacent characters
            word_list[swap_idx], word_list[swap_idx + 1] = \
                word_list[swap_idx + 1], word_list[swap_idx]
            words[idx] = "".join(word_list)
            typo_text = " ".join(words)
            correction = f"{original_word}*"
            return typo_text, correction

        return text, None

    def create_correction_message(self, correction: str) -> str:
        """Create a natural correction message."""
        templates = [
            correction,
            f"*{correction[:-1]}",
            correction,
        ]
        return random.choice(templates)
```

### 5. Add Length Control to Agent Prompt
- In `telegram_agent.py`, add to system prompt:
```python
length_instructions = f"""
## Длина Сообщений

КРИТИЧЕСКИ ВАЖНО - Контролируй длину:
- ИДЕАЛЬНО: {self.config.human_polish.target_message_length if self.config.human_polish else 150} символов
- МАКСИМУМ: {self.config.human_polish.max_message_length if self.config.human_polish else 500} символов
- НЕ пиши длинные абзацы - люди в мессенджерах пишут коротко
- Одна мысль = одно сообщение
- Если нужно много сказать - лучше разбить на 2 сообщения

Примеры хорошей длины:
- "Отлично! Вилла в Чангу - хороший выбор. Какой бюджет рассматриваете?" (62 символа)
- "Да, ROI 8-12% реально. Могу показать конкретные объекты." (55 символов)

Примеры ПЛОХОЙ длины:
- "Здравствуйте! Рад что вы заинтересовались недвижимостью на Бали. Это действительно прекрасное место для инвестиций... [и еще 400 символов]"
"""
```

### 6. Update Telegram Service Timing
- In `telegram_service.py`, replace timing calculation:
```python
from sales_agent.humanizer import NaturalTiming

class TelegramService:
    def __init__(self, client: TelegramClient, config: Optional[AgentConfig] = None):
        self.client = client
        self.config = config or AgentConfig()

        # Initialize natural timing
        mode = "natural"
        if config and config.human_polish:
            mode = config.human_polish.timing_mode
        self.timing = NaturalTiming(mode=mode)

    async def send_message(
        self,
        telegram_id: int | str,
        text: str,
        incoming_message: str = "",  # NEW: for timing calculation
        reply_to: Optional[int] = None
    ) -> dict:
        """Send message with natural timing."""

        # Calculate natural delay
        delay = self.timing.get_delay(incoming_message, text)

        # Typing simulation with natural duration
        if self.config.typing_simulation:
            typing_duration = self.timing.get_typing_duration(len(text))
            await self._simulate_typing(entity, text, typing_duration)

        await asyncio.sleep(delay)
        # ... send message
```

### 7. Add Typo Injection to Daemon (Optional)
- In `daemon.py`, after generating response:
```python
# Optional: Add occasional typo for human-like feel
if self.config.human_polish and self.config.human_polish.enable_typos:
    from sales_agent.humanizer import TypoInjector

    injector = TypoInjector(self.config.human_polish.typo_probability)
    typo_text, correction = injector.inject_typo(response_text)

    if correction:
        # Send typo version first
        await self.service.send_message(prospect.telegram_id, typo_text)
        await asyncio.sleep(random.uniform(0.5, 1.5))  # Quick correction
        # Send correction
        await self.service.send_message(prospect.telegram_id, correction)
        return  # Don't send original
```

### 8. Update Config File
- In `agent_config.json`, add:
```json
{
  "human_polish": {
    "max_message_length": 500,
    "target_message_length": 150,
    "warn_at_length": 300,
    "timing_mode": "natural",
    "min_delay_seconds": 1.0,
    "max_delay_seconds": 15.0,
    "enable_typos": false,
    "typo_probability": 0.05,
    "prefer_short_responses": true,
    "split_long_messages": false
  }
}
```

### 9. Add Message Length Validation
- In daemon, after generating response, check length:
```python
# Warn if response is too long
if len(action.message) > (self.config.human_polish.warn_at_length if self.config.human_polish else 300):
    console.print(f"[yellow]Warning: Response is {len(action.message)} chars (target: 150)[/yellow]")

# Hard limit
max_len = self.config.human_polish.max_message_length if self.config.human_polish else 500
if len(action.message) > max_len:
    action.message = action.message[:max_len-3] + "..."
    console.print(f"[yellow]Truncated to {max_len} chars[/yellow]")
```

### 10. Validate Implementation
- Test timing variation (observe multiple responses)
- Test message length enforcement
- Test typo injection (if enabled)
- Compare before/after feel

## Testing Strategy

### Unit Tests
- Test NaturalTiming distribution
- Test TypoInjector patterns
- Test response type classification

### Integration Tests
1. Send 10 messages → verify timing varies naturally
2. Ask complex question → verify response not too long
3. Enable typos → verify occasional typo + correction

### Observation Tests
- Have real person evaluate conversation naturalness
- Compare timing distribution histogram before/after
- Measure message length distribution

## Acceptance Criteria
- [ ] Response timing uses natural distribution (not uniform)
- [ ] Message length controlled (< 500 chars default)
- [ ] Agent prompt includes length instructions
- [ ] Config allows tuning all parameters
- [ ] Optional typo injection works correctly
- [ ] Timing varies based on message type

## Validation Commands
```bash
# Test humanizer module
uv run python -c "from sales_agent.humanizer import NaturalTiming, calculate_natural_delay; print('OK')"

# Test timing distribution
uv run python -c "
from sales_agent.humanizer.timing import calculate_natural_delay
import statistics

delays = [calculate_natural_delay('test', 'response', 'natural') for _ in range(100)]
print(f'Mean: {statistics.mean(delays):.2f}s')
print(f'Stdev: {statistics.stdev(delays):.2f}s')
print(f'Min: {min(delays):.2f}s, Max: {max(delays):.2f}s')
"

# Test typo injection
uv run python -c "
from sales_agent.humanizer.typo_injector import TypoInjector
injector = TypoInjector(probability=1.0)  # Force typo for testing
text, correction = injector.inject_typo('Здравствуйте, как дела?')
print(f'Original: Здравствуйте, как дела?')
print(f'With typo: {text}')
print(f'Correction: {correction}')
"
```

## Notes
- Typo injection is EXPERIMENTAL - disabled by default
- Natural timing may feel slower initially - that's intentional
- Log-normal distribution mimics human response patterns
- Message length limits may need agent retraining/prompting
- Consider A/B testing different timing modes
- Typos should be rare (< 5%) and always corrected
- Very short messages (< 20 chars) shouldn't have typos
