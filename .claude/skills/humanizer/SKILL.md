---
name: humanizer
description: Natural timing and optional typo injection for human-like agent communication. Use when implementing response delays, typing indicators, or making automated messages feel more natural.
trigger: Response timing, typing delays, human-like pauses, typo injection, natural delays
---

# Humanizer

Makes agent responses feel more human through natural timing distribution and optional typo injection.

## Overview

The humanizer module provides two main capabilities:

1. **Natural Timing** - Statistical delay calculations that mimic human response patterns
2. **Typo Injection** - Optional, experimental feature for adding realistic typos with corrections

## Source Location

```
src/sales_agent/humanizer/
├── __init__.py          # Public API exports
├── timing.py            # Natural timing with log-normal distribution
└── typo_injector.py     # Optional typo generation (experimental)
```

## Natural Timing

### Why Statistical Distribution?

Human responses do not follow uniform random timing. Instead, they exhibit patterns:

- Most responses cluster around a typical time
- Occasional longer pauses (thinking, distraction)
- Rare very quick responses

The module uses **log-normal distribution** which naturally produces this pattern - values cluster near a median with a "long tail" of occasional longer delays.

### Response Types

Messages are classified into four types, each with different timing profiles:

| Type | Description | Base Delay | Max Delay |
|------|-------------|------------|-----------|
| `QUICK_ACK` | Short confirmations ("ok", "da") | 1.5s | 4s |
| `NORMAL` | Standard responses | 3.0s | 10s |
| `THOUGHTFUL` | Complex questions, longer responses | 5.0s | 15s |
| `LONG_READ` | Reading long incoming messages | 8.0s | 20s |

Classification is automatic based on message length:
- Incoming > 200 chars = `LONG_READ`
- Outgoing < 50 chars = `QUICK_ACK`
- Outgoing > 200 chars = `THOUGHTFUL`
- Otherwise = `NORMAL`

### Timing Modes

Three modes are available:

| Mode | Description | Best For |
|------|-------------|----------|
| `uniform` | Simple uniform distribution | Testing, predictable behavior |
| `natural` | Log-normal distribution (default) | Production - most human-like |
| `variable` | Triangular distribution with distraction | High variation scenarios |

### Usage Examples

```python
from sales_agent.humanizer import NaturalTiming, calculate_natural_delay

# Using NaturalTiming class (recommended)
timing = NaturalTiming(mode="natural")

incoming = "Привет! Расскажите о виллах на Бали"
outgoing = "Добрый день! С удовольствием помогу с выбором."

# Get response delay
delay = timing.get_delay(incoming, outgoing)  # Returns ~3-10 seconds
await asyncio.sleep(delay)

# Get typing indicator duration
typing_duration = timing.get_typing_duration(len(outgoing))  # Returns 1-8 seconds

# Using function directly (for one-off calculations)
delay = calculate_natural_delay(incoming, outgoing, mode="natural")
```

### Integration Pattern

Typical integration with Telegram sending:

```python
from sales_agent.humanizer import NaturalTiming

timing = NaturalTiming(mode="natural")

async def send_message_naturally(client, chat_id, incoming_msg, outgoing_msg):
    # Calculate natural delay before responding
    delay = timing.get_delay(incoming_msg, outgoing_msg)
    await asyncio.sleep(delay)

    # Show typing indicator for realistic duration
    typing_duration = timing.get_typing_duration(len(outgoing_msg))
    async with client.action(chat_id, 'typing'):
        await asyncio.sleep(typing_duration)

    # Send the message
    await client.send_message(chat_id, outgoing_msg)
```

## Typo Injection (Experimental)

**WARNING:** This feature is experimental and disabled by default. Use with caution as typos could impact professional perception.

### Concept

Occasionally adds realistic typos to messages, then provides a correction message (like humans do when they notice a typo and send a quick fix).

### Usage

```python
from sales_agent.humanizer import TypoInjector

# Initialize with low probability (5% default)
injector = TypoInjector(probability=0.05)

text = "Привет, как дела?"
modified_text, correction = injector.inject_typo(text)

if correction:
    # Send the typo version first
    await send_message(modified_text)  # "Прмвет, как дела?"
    await asyncio.sleep(1)
    # Then send correction
    await send_message(correction)  # "Привет*"
else:
    # No typo was added, send original
    await send_message(text)
```

### Typo Patterns

The module uses Russian ЙЦУКЕН keyboard layout for realistic typos:

- **Adjacent key swaps**: а/с, о/л, е/к, и/м, н/г, т/ь, р/п
- **Common word typos**: "привет" -> "прмвет", "хорошо" -> "хорлшо"
- **Character transpositions**: Swapping adjacent characters in middle of words

### When to Use

- Very casual conversations where typos feel natural
- Building rapport over extended interactions
- Never in formal business communications

## API Reference

### Classes

```python
class NaturalTiming:
    def __init__(self, mode: str = "natural")
    def get_delay(self, incoming_message: str, outgoing_message: str) -> float
    def get_typing_duration(self, message_length: int) -> float

class TypoInjector:
    def __init__(self, probability: float = 0.05)
    def should_add_typo(self) -> bool
    def inject_typo(self, text: str) -> Tuple[str, Optional[str]]
    def create_correction_message(self, correction: str) -> str

class ResponseType(str, Enum):
    QUICK_ACK = "quick_ack"
    NORMAL = "normal"
    THOUGHTFUL = "thoughtful"
    LONG_READ = "long_read"
```

### Functions

```python
def calculate_natural_delay(
    incoming_message: str,
    outgoing_message: str,
    mode: str = "natural"
) -> float
    """Returns delay in seconds (always >= 1.0)"""

def classify_response_type(
    incoming_message: str,
    outgoing_message: str
) -> ResponseType
    """Classify message for timing purposes"""
```

### Constants

```python
TIMING_PROFILES: dict  # Base/variance/max for each ResponseType
COMMON_TYPOS: dict     # Russian word -> typo variants mapping
```

## Best Practices

1. **Use "natural" mode in production** - provides the most human-like distribution
2. **Use "uniform" mode in tests** - more predictable for assertions
3. **Always apply typing indicator** - shows "typing..." before sending
4. **Avoid repetitive delays** - `NaturalTiming` class automatically prevents this
5. **Keep typo probability low** - 5% or less for professional contexts
6. **Disable typos for important messages** - booking confirmations, pricing, etc.

## License

MIT
