# Plan: Integration - Connect All Modules to Daemon & Services

## Task Description
Integrate all 5 newly created modules (media, temporal, context, humanizer, message-events) into the main daemon.py, telegram_agent.py, and telegram_service.py files.

## Objective
Make all new features active in the running system:
1. Media detection and voice transcription in daemon message handler
2. Message event handlers (edit, delete) in daemon
3. Pause detection and timezone tracking in daemon
4. Phrase tracking and fact extraction in agent
5. Natural timing in telegram service

## Files to Modify

### Primary Integration Points
1. **`src/sales_agent/daemon.py`** - Main integration hub
2. **`src/sales_agent/agent/telegram_agent.py`** - Agent prompts and generation
3. **`src/sales_agent/telegram/telegram_service.py`** - Timing integration
4. **`src/sales_agent/config/agent_config.json`** - Add new config sections

## Integration Tasks

### Task 1: Daemon - Media Handling Integration

**Location:** `daemon.py` lines 610-700 (handle_incoming)

**Add imports at top:**
```python
from sales_agent.media import VoiceTranscriber, detect_media_type, MediaDetectionResult
```

**Add to TelegramDaemon.__init__:**
```python
self.voice_transcriber: Optional[VoiceTranscriber] = None
```

**Add to TelegramDaemon.initialize() after line 241:**
```python
# Initialize voice transcriber (optional)
try:
    self.voice_transcriber = VoiceTranscriber()
    console.print(f"  [green]✓[/green] Voice transcription enabled (ElevenLabs)")
except ValueError as e:
    self.voice_transcriber = None
    console.print(f"  [yellow]⚠[/yellow] Voice transcription disabled: {e}")
```

**In handle_incoming, BEFORE accessing event.text (around line 646):**
```python
# Detect media type BEFORE accessing event.text (prevents crash on None)
media_result = detect_media_type(event)
message_text = event.text or ""

# Handle voice messages - transcribe to text
if media_result.media_type == "voice" and self.voice_transcriber:
    try:
        console.print(f"[cyan]🎤 Transcribing voice from {prospect.name}...[/cyan]")
        transcription = await self.voice_transcriber.transcribe_telegram_voice(
            self.client, event.message
        )
        message_text = transcription.text
        console.print(f"[green]Transcribed:[/green] {message_text[:100]}...")
    except Exception as e:
        console.print(f"[yellow]Transcription failed: {e}[/yellow]")
        message_text = "[Голосовое сообщение]"

# Handle other media types
elif media_result.has_media and not message_text:
    if media_result.media_type == "sticker":
        emoji = media_result.file_name or "👍"
        message_text = f"[Стикер: {emoji}]"
    elif media_result.media_type == "photo":
        message_text = "[Фото]"
    elif media_result.media_type == "video":
        message_text = "[Видео]"
    elif media_result.media_type == "document":
        message_text = f"[Документ]"
    else:
        message_text = f"[{media_result.media_type}]"

# Safe logging (replaces crash-prone event.text[:100])
display_text = message_text[:100] if message_text else "[пустое сообщение]"
console.print(f"\n[cyan]← Received from {prospect.name}:[/cyan] {display_text}...")
```

**Update record_response call to use message_text:**
```python
self.prospect_manager.record_response(
    prospect.telegram_id,
    event.id,
    message_text  # Use processed message_text, not event.text
)
```

### Task 2: Daemon - Message Event Handlers

**Add after handle_incoming registration (around line 700):**
```python
@self.client.on(events.MessageEdited(incoming=True))
async def handle_message_edited(event):
    """Handle edited messages from prospects."""
    if not event.is_private:
        return

    sender = await event.get_sender()
    if not sender:
        return

    prospect = self.prospect_manager.get_prospect(sender.id)
    if not prospect:
        return

    console.print(f"[yellow]✎ Message edited by {prospect.name}:[/yellow] {event.text[:50] if event.text else ''}...")

    self.prospect_manager.mark_message_edited(
        prospect.telegram_id,
        event.id,
        new_text=event.text or "",
        edited_at=datetime.now()
    )

@self.client.on(events.MessageDeleted)
async def handle_message_deleted(event):
    """Handle deleted messages."""
    for msg_id in event.deleted_ids:
        for prospect in self.prospect_manager.get_all_prospects():
            if self.prospect_manager.has_message(prospect.telegram_id, msg_id):
                console.print(f"[red]✗ Message {msg_id} deleted by {prospect.name}[/red]")
                self.prospect_manager.mark_message_deleted(prospect.telegram_id, msg_id)
                break
```

### Task 3: Daemon - Pause Detection & Forward/Reply Context

**Add import:**
```python
from sales_agent.temporal import detect_pause, PauseDetector
```

**In handle_incoming, after getting prospect, add pause detection:**
```python
# Detect conversation pause
gap = detect_pause(
    prospect.last_contact,
    prospect.last_response,
    datetime.now()
)

if gap.hours >= 24:
    console.print(f"[dim]Conversation gap: {gap.hours:.0f}h ({gap.pause_type.value})[/dim]")
```

**Extract forward and reply-to info:**
```python
# Extract forward info
is_forwarded = event.message.fwd_from is not None
forward_from = None
if is_forwarded and event.message.fwd_from:
    fwd = event.message.fwd_from
    forward_from = fwd.from_name if fwd.from_name else "unknown"
    console.print(f"[cyan]↪ Forwarded from {forward_from}[/cyan]")

# Extract reply-to context
reply_to_id = None
reply_to_text = None
if event.message.reply_to:
    reply_to_id = event.message.reply_to.reply_to_msg_id
    try:
        replied_msg = await self.client.get_messages(event.chat_id, ids=reply_to_id)
        if replied_msg and replied_msg.text:
            reply_to_text = replied_msg.text[:200]
            console.print(f"[dim]↩ Reply to: {reply_to_text[:50]}...[/dim]")
    except Exception:
        pass
```

### Task 4: Daemon - Pass Gap Context to Agent

**When calling agent.generate_response, pass gap:**
```python
action = await self.agent.generate_response(
    prospect,
    message_text,
    conversation_context=context,
    gap=gap  # NEW parameter
)
```

### Task 5: TelegramAgent - Add Gap and Media Context

**Update generate_response signature:**
```python
async def generate_response(
    self,
    prospect: Prospect,
    incoming_message: str,
    conversation_context: str = "",
    gap: Optional[Any] = None  # NEW
) -> AgentAction:
```

**Add gap context to user_prompt:**
```python
# Gap context for long pauses
gap_context = ""
if gap and gap.hours >= 24:
    gap_context = f"""
КОНТЕКСТ ПАУЗЫ: Прошло {gap.hours:.0f} часов с последнего сообщения.
{f'Рекомендуемое приветствие: "{gap.suggested_greeting}"' if gap.suggested_greeting else ''}
Учитывай паузу - можешь мягко напомнить контекст разговора.
"""
```

**Add media handling to system prompt (in _build_system_prompt):**
```python
media_instructions = """
## Обработка Медиа

Форматы входящих сообщений:
- Голосовое: расшифрованный текст (отвечай как на обычное сообщение)
- [Фото]: клиент отправил фото
- [Стикер: 👍]: интерпретируй как реакцию
- [Документ]: клиент отправил файл

Правила:
1. Голосовые - отвечай естественно, НЕ упоминай что это было голосовое
2. Стикеры - это реакции (👍 = подтверждение), можешь вернуть action="wait"
3. Фото без текста - уточни: "Получил фото! Это объект который интересует?"
"""
```

### Task 6: TelegramAgent - Phrase Tracking for Initial Messages

**Add import:**
```python
from sales_agent.context import PhraseTracker
```

**Update generate_initial_message:**
```python
async def generate_initial_message(self, prospect: Prospect) -> AgentAction:
    """Generate varied initial outreach message."""
    # Initialize phrase tracker with prospect's history
    tracker = PhraseTracker(
        used_greetings=prospect.used_greetings,
        used_phrases=prospect.used_phrases
    )

    greeting = tracker.get_greeting(prospect.name)
    opening = tracker.get_opening(self.agent_name)
    question = tracker.get_closing_question()

    user_prompt = f"""Сгенерируй ПЕРВОЕ сообщение для нового клиента.

Клиент: {prospect.name}
Контекст: {prospect.context}

ИСПОЛЬЗУЙ эти элементы (можешь перефразировать):
- Приветствие: "{greeting}"
- Представление: "{opening}"
- Вопрос: "{question}"

Собери естественное сообщение (2-3 предложения, до 200 символов).
Верни JSON с action="reply".
"""
    # ... rest of method
```

### Task 7: TelegramService - Natural Timing

**Add import:**
```python
from sales_agent.humanizer import NaturalTiming
```

**Update __init__:**
```python
def __init__(self, client: TelegramClient, config: Optional[AgentConfig] = None):
    self.client = client
    self.config = config or AgentConfig()

    # Initialize natural timing
    timing_mode = "natural"
    if config and config.human_polish:
        timing_mode = config.human_polish.timing_mode
    self.natural_timing = NaturalTiming(mode=timing_mode)
```

**Update send_message to accept incoming_message:**
```python
async def send_message(
    self,
    telegram_id: int | str,
    text: str,
    incoming_message: str = "",  # NEW
    reply_to: Optional[int] = None
) -> dict:
    # ... resolve entity ...

    # Use natural timing
    delay = self.natural_timing.get_delay(incoming_message, text)

    # Typing simulation
    if self.config.typing_simulation:
        typing_duration = self.natural_timing.get_typing_duration(len(text))
        await self._simulate_typing(entity, text)
        # Note: _simulate_typing already has its own timing

    await asyncio.sleep(delay)
    # ... send message ...
```

### Task 8: Update Config File

**Add to agent_config.json:**
```json
{
  "human_polish": {
    "max_message_length": 500,
    "target_message_length": 150,
    "timing_mode": "natural",
    "enable_typos": false,
    "typo_probability": 0.05
  }
}
```

## Validation Commands

```bash
# Test full integration
PYTHONPATH=src uv run python -c "
from sales_agent.daemon import TelegramDaemon
print('Daemon imports OK')
"

# Run daemon for live testing
PYTHONPATH=src uv run python src/sales_agent/daemon.py
```

## Acceptance Criteria
- [ ] Voice messages transcribed and processed
- [ ] Media types detected without crashes
- [ ] Edit/delete events tracked
- [ ] Pause detection provides context
- [ ] Initial messages vary
- [ ] Natural timing in responses
- [ ] Config file updated
