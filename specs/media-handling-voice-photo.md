# Plan: Media Handling - Voice Messages & Photo/Document Support

## Task Description
Implement comprehensive handling for non-text messages in Telegram conversations: voice messages (transcription via ElevenLabs), photos, videos, documents, and stickers. Currently, the system only processes `event.text`, causing crashes on media-only messages and ignoring all media context.

## Objective
Enable the sales agent to properly receive, process, and respond to:
1. Voice messages (transcribed to text via ElevenLabs API)
2. Photos/videos (acknowledged and stored in context)
3. Documents (acknowledged with filename/type)
4. Stickers/GIFs (interpreted as emoji reactions)

## Problem Statement
When prospects send non-text messages:
- **Voice messages**: `event.text = None` → crash at `event.text[:100]` (line 647)
- **Photos/videos**: Only caption processed, visual content lost
- **Documents**: Completely ignored
- **Stickers/GIFs**: `event.text = None` → treated as empty, ignored

This causes missed communication and confused prospects who feel ignored.

## Solution Approach
1. Create `src/sales_agent/media/` module with voice transcription and media detection
2. Update `ConversationMessage` model to track `media_type` field
3. Modify daemon handler to detect media BEFORE text processing
4. Add media handling instructions to agent system prompt
5. Use ElevenLabs API for voice transcription (OGG format supported natively)

## Relevant Files

### Existing Files to Modify
- `src/sales_agent/daemon.py:610-668` - Message handler needs media type detection before `event.text` access
- `src/sales_agent/crm/models.py:35-41` - `ConversationMessage` needs `media_type` field
- `src/sales_agent/crm/prospect_manager.py:176-220` - Recording methods need `media_type` parameter
- `src/sales_agent/messaging/message_buffer.py:26-42` - `BufferedMessage` needs media fields
- `src/sales_agent/agent/telegram_agent.py:184-357` - System prompt needs media handling section
- `src/sales_agent/config/agent_config.json` - Add media handling config section

### New Files to Create
- `src/sales_agent/media/__init__.py` - Module exports
- `src/sales_agent/media/voice_transcriber.py` - ElevenLabs transcription service
- `src/sales_agent/media/media_detector.py` - Media type detection from Telethon events

### Reference Files
- `.claude/skills/eleven-labs/scripts/transcribe.py` - ElevenLabs API pattern (lines 93-142)
- `src/sales_agent/telegram/telegram_fetch.py:533-602` - Media download pattern
- `src/sales_agent/scheduling/__init__.py` - Module structure pattern

## Implementation Phases

### Phase 1: Foundation (Models & Module Structure)
- Add `MessageMediaType` enum to models.py
- Update `ConversationMessage` with media_type field
- Update `BufferedMessage` with media fields
- Create media module directory structure

### Phase 2: Core Implementation (Transcription & Detection)
- Implement `VoiceTranscriber` service using ElevenLabs API
- Implement `detect_media_type()` function for Telethon events
- Update daemon handler to detect media before text processing
- Update recording methods to accept media_type

### Phase 3: Integration & Polish
- Add media handling instructions to agent system prompt
- Add media_handling config section
- Test with real voice messages and photos
- Handle edge cases (empty voice, corrupt files)

## Step by Step Tasks

### 1. Add Media Type Enum to Models
- In `src/sales_agent/crm/models.py` after line 33, add:
```python
class MessageMediaType(str, Enum):
    """Type of message media."""
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    STICKER = "sticker"
    GIF = "gif"
    VIDEO_NOTE = "video_note"
    AUDIO = "audio"
```

### 2. Update ConversationMessage Model
- In `src/sales_agent/crm/models.py` lines 35-41, add fields:
```python
class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    id: int
    sender: Literal["agent", "prospect"]
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # NEW FIELDS
    media_type: MessageMediaType = MessageMediaType.TEXT
    transcription: Optional[str] = None  # For voice messages
```

### 3. Update BufferedMessage Model
- In `src/sales_agent/messaging/message_buffer.py` lines 26-42, add:
```python
class BufferedMessage(BaseModel):
    message_id: int
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # NEW FIELDS
    has_media: bool = False
    media_type: Optional[str] = None  # "voice", "photo", etc.
```

### 4. Create Media Module Structure
- Create `src/sales_agent/media/__init__.py`:
```python
"""
Media module - Voice transcription and media handling for Telegram messages.

Provides:
- VoiceTranscriber: Transcribe voice messages using ElevenLabs API
- detect_media_type: Detect media type from Telethon event objects

Example:
    from sales_agent.media import VoiceTranscriber, detect_media_type

    transcriber = VoiceTranscriber()
    text = await transcriber.transcribe(audio_path)
"""
from .voice_transcriber import VoiceTranscriber
from .media_detector import detect_media_type, MediaDetectionResult

__all__ = [
    "VoiceTranscriber",
    "detect_media_type",
    "MediaDetectionResult",
]
```

### 5. Implement Media Detector
- Create `src/sales_agent/media/media_detector.py`:
```python
"""Media type detection from Telethon events."""
from dataclasses import dataclass
from typing import Optional
from telethon.tl.types import DocumentAttributeAudio

@dataclass
class MediaDetectionResult:
    """Result of media type detection."""
    has_media: bool
    media_type: Optional[str]  # "voice", "photo", "video", etc.
    file_name: Optional[str] = None
    file_size: Optional[int] = None

def detect_media_type(event) -> MediaDetectionResult:
    """Detect media type from Telethon NewMessage event."""
    if event.voice:
        return MediaDetectionResult(True, "voice")
    if event.video_note:
        return MediaDetectionResult(True, "video_note")
    if event.sticker:
        emoji = event.sticker.alt or "👍"
        return MediaDetectionResult(True, "sticker", file_name=emoji)
    if event.gif:
        return MediaDetectionResult(True, "gif")
    if event.photo:
        return MediaDetectionResult(True, "photo")
    if event.video:
        return MediaDetectionResult(True, "video")
    if event.audio:
        return MediaDetectionResult(True, "audio")
    if event.document:
        # Check if it's a voice message via document attributes
        if event.document.attributes:
            for attr in event.document.attributes:
                if isinstance(attr, DocumentAttributeAudio) and attr.voice:
                    return MediaDetectionResult(True, "voice")
        return MediaDetectionResult(True, "document")

    return MediaDetectionResult(False, None)
```

### 6. Implement Voice Transcriber Service
- Create `src/sales_agent/media/voice_transcriber.py`:
```python
"""Voice message transcription using ElevenLabs API."""
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class TranscriptionResult(BaseModel):
    """Result of voice transcription."""
    text: str
    language_code: str = "unknown"
    language_probability: Optional[float] = None
    duration_seconds: Optional[float] = None

class VoiceTranscriber:
    """Transcribe voice messages using ElevenLabs Speech-to-Text API."""

    ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment")

    @property
    def enabled(self) -> bool:
        """Check if transcription is available."""
        return bool(self.api_key)

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to audio file (OGG, MP3, WAV supported)

        Returns:
            TranscriptionResult with transcribed text

        Raises:
            Exception: If transcription fails
        """
        headers = {"xi-api-key": self.api_key}
        data = {
            "model_id": "scribe_v2",
            "timestamps_granularity": "none",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (audio_path.name, f, "audio/ogg")}
                response = await client.post(
                    self.ENDPOINT,
                    headers=headers,
                    data=data,
                    files=files
                )

        if response.status_code != 200:
            raise Exception(f"Transcription failed: {response.status_code} - {response.text}")

        result = response.json()
        return TranscriptionResult(
            text=result.get("text", ""),
            language_code=result.get("language_code", "unknown"),
            language_probability=result.get("language_probability")
        )

    async def transcribe_telegram_voice(
        self,
        client,
        message
    ) -> TranscriptionResult:
        """
        Download and transcribe a Telegram voice message.

        Args:
            client: Telethon TelegramClient
            message: Telethon Message with voice attribute

        Returns:
            TranscriptionResult with transcribed text
        """
        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await client.download_media(message, str(tmp_path))
            result = await self.transcribe(tmp_path)
            return result
        finally:
            tmp_path.unlink(missing_ok=True)
```

### 7. Update Daemon Message Handler
- In `src/sales_agent/daemon.py`, after line 35, add import:
```python
from sales_agent.media import VoiceTranscriber, detect_media_type, MediaDetectionResult
```

- In `TelegramDaemon.__init__` (line 93), add:
```python
self.voice_transcriber = None  # Initialized in initialize()
```

- In `TelegramDaemon.initialize()` (after line 241), add:
```python
# Initialize voice transcriber (optional)
try:
    self.voice_transcriber = VoiceTranscriber()
    console.print(f"  [green]✓[/green] Voice transcription enabled (ElevenLabs)")
except ValueError:
    self.voice_transcriber = None
    console.print(f"  [yellow]⚠[/yellow] Voice transcription disabled (no ELEVENLABS_API_KEY)")
```

- In `handle_incoming` (line 646), BEFORE accessing event.text, add:
```python
# Detect media type BEFORE accessing event.text
media_result = detect_media_type(event)
message_text = event.text or ""

# Handle voice messages - transcribe to text
if media_result.media_type == "voice" and self.voice_transcriber:
    try:
        console.print(f"[cyan]Transcribing voice message from {prospect.name}...[/cyan]")
        transcription = await self.voice_transcriber.transcribe_telegram_voice(
            self.client, event.message
        )
        message_text = transcription.text
        console.print(f"[green]Transcribed:[/green] {message_text[:100]}...")
    except Exception as e:
        console.print(f"[yellow]Transcription failed: {e}[/yellow]")
        message_text = "[Голосовое сообщение - не удалось распознать]"

# Handle other media types
elif media_result.has_media and not message_text:
    if media_result.media_type == "sticker":
        message_text = f"[Стикер: {media_result.file_name or '👍'}]"
    elif media_result.media_type == "photo":
        message_text = "[Фото]"
    elif media_result.media_type == "video":
        message_text = "[Видео]"
    elif media_result.media_type == "document":
        message_text = f"[Документ: {media_result.file_name or 'файл'}]"
    else:
        message_text = f"[{media_result.media_type}]"

# Safe logging (replaces crash-prone event.text[:100])
display_text = message_text[:100] if message_text else "[пустое сообщение]"
console.print(f"\n[cyan]← Received from {prospect.name}:[/cyan] {display_text}...")
```

### 8. Update Prospect Manager Recording Methods
- In `src/sales_agent/crm/prospect_manager.py`, update `record_response` (line 176):
```python
def record_response(
    self,
    telegram_id: int | str,
    message_id: int,
    message_text: str,
    media_type: str = "text"  # NEW PARAMETER
) -> None:
```

- Update the ConversationMessage creation to include media_type

### 9. Add Media Handling to Agent System Prompt
- In `src/sales_agent/agent/telegram_agent.py`, in `_build_system_prompt()` after line 339, add:
```python
media_handling_instructions = """
## Обработка Медиа

ВАЖНО: Клиенты могут отправлять разные типы сообщений.

Форматы входящих сообщений:
- Обычный текст: просто текст сообщения
- Голосовое: [расшифровка голосового сообщения]
- Фото: [Фото] или [Фото]: подпись
- Стикер: [Стикер: 👍] - интерпретируй как emoji-реакцию
- Документ: [Документ: filename.pdf]

ПРАВИЛА:
1. Голосовые сообщения - отвечай как на обычный текст, НЕ упоминай что это было голосовое
2. Фото без подписи - можешь уточнить: "Получил фото! Это объект который вас интересует?"
3. Стикеры - интерпретируй как реакцию (👍 = подтверждение, ❤️ = нравится)
4. Документы - подтверди получение: "Спасибо, посмотрю документ!"

Если клиент отправил ТОЛЬКО медиа без текста и это не стикер-реакция:
- Подожди 5-10 секунд - возможно напишет пояснение
- Или уточни: "Получил! Можете пояснить что это?"
"""
```

### 10. Add Media Config Section
- In `src/sales_agent/crm/models.py`, add after FollowUpPollingConfig:
```python
class MediaHandlingConfig(BaseModel):
    """Configuration for media message handling."""
    enabled: bool = True
    transcribe_voice: bool = True
    voice_transcriber: str = "elevenlabs"  # or "whisper"
    acknowledge_photos: bool = True
    acknowledge_documents: bool = True
```

- Add to AgentConfig:
```python
media_handling: Optional[MediaHandlingConfig] = None
```

### 11. Validate Implementation
- Test voice message transcription with real Telegram voice
- Test photo handling (with and without caption)
- Test sticker interpretation
- Test document acknowledgment
- Verify no crashes on media-only messages

## Testing Strategy

### Unit Tests
- `test_media_detector.py` - Test all media type detections
- `test_voice_transcriber.py` - Mock ElevenLabs API responses

### Integration Tests
1. Send voice message from @bohdanpytaichuk to @BetterBohdan
2. Verify transcription in console logs
3. Verify agent responds naturally (not mentioning "voice")
4. Send photo without caption - verify acknowledgment
5. Send sticker - verify interpreted as reaction

### Edge Cases
- Empty voice message (< 1 second)
- Very long voice message (> 5 minutes)
- Corrupt audio file
- Photo without caption
- Multiple media in one message
- ElevenLabs API timeout

## Acceptance Criteria
- [ ] Voice messages transcribed via ElevenLabs and processed as text
- [ ] Photos trigger appropriate acknowledgment or clarification
- [ ] Stickers interpreted as emoji reactions (action="wait" for 👍)
- [ ] Documents acknowledged with filename
- [ ] No crashes on media-only messages (event.text = None)
- [ ] Media type stored in conversation history
- [ ] Agent prompt includes media handling instructions
- [ ] Config allows enabling/disabling transcription

## Validation Commands
```bash
# Test module imports
uv run python -c "from sales_agent.media import VoiceTranscriber, detect_media_type; print('OK')"

# Test media detector
uv run python -c "from sales_agent.media.media_detector import detect_media_type; print('OK')"

# Test voice transcriber (requires ELEVENLABS_API_KEY)
uv run python -c "from sales_agent.media.voice_transcriber import VoiceTranscriber; t = VoiceTranscriber(); print('Enabled:', t.enabled)"

# Compile check
uv run python -m py_compile src/sales_agent/media/__init__.py src/sales_agent/media/voice_transcriber.py src/sales_agent/media/media_detector.py

# Run daemon for manual testing
PYTHONPATH=src uv run python src/sales_agent/daemon.py
# Then send voice message from @bohdanpytaichuk
```

## Notes
- ElevenLabs API supports OGG natively - NO audio conversion needed
- Telegram voice messages are OGG/OPUS format
- ELEVENLABS_API_KEY required in .env for voice transcription
- Graceful degradation: if no API key, voice shows as "[Голосовое сообщение]"
- Rate limits: ElevenLabs has per-minute limits on free tier
- Temp files cleaned up after transcription
- Consider adding OpenAI Whisper as fallback transcriber
