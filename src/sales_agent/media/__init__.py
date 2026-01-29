"""
Media module - Voice transcription and media handling for Telegram messages.

This module provides functionality for handling non-text messages in Telegram
conversations, including voice message transcription and media type detection.

Provides:
- VoiceTranscriber: Transcribe voice messages using ElevenLabs Speech-to-Text API
- detect_media_type: Detect media type from Telethon event objects
- MediaDetectionResult: Dataclass containing media detection results

Example:
    from sales_agent.media import VoiceTranscriber, detect_media_type

    # Detect media type from incoming Telegram event
    media_result = detect_media_type(event)
    if media_result.media_type == "voice":
        transcriber = VoiceTranscriber()
        result = await transcriber.transcribe_telegram_voice(client, event.message)
        print(f"Transcribed: {result.text}")

Note:
    Voice transcription requires ELEVENLABS_API_KEY environment variable.
    Telegram voice messages are OGG format which ElevenLabs supports natively.
"""

from .voice_transcriber import VoiceTranscriber, TranscriptionResult
from .media_detector import detect_media_type, MediaDetectionResult

__all__ = [
    "VoiceTranscriber",
    "TranscriptionResult",
    "detect_media_type",
    "MediaDetectionResult",
]
