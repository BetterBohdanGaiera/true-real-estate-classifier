"""
ElevenLabs Skill Scripts - Voice transcription and media handling.

This package provides functionality for handling audio transcription and media
detection, primarily for use with Telegram messages.

Provides:
- VoiceTranscriber: Transcribe voice messages using ElevenLabs Speech-to-Text API
- TranscriptionResult: Pydantic model for transcription results
- detect_media_type: Detect media type from Telethon event objects
- MediaDetectionResult: Dataclass containing media detection results

Example:
    from voice_transcriber import VoiceTranscriber, TranscriptionResult
    from media_detector import detect_media_type, MediaDetectionResult

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

try:
    # When used as a package
    from .voice_transcriber import VoiceTranscriber, TranscriptionResult
    from .media_detector import detect_media_type, MediaDetectionResult
except ImportError:
    # When importing directly from scripts directory
    from voice_transcriber import VoiceTranscriber, TranscriptionResult
    from media_detector import detect_media_type, MediaDetectionResult

__all__ = [
    "VoiceTranscriber",
    "TranscriptionResult",
    "detect_media_type",
    "MediaDetectionResult",
]
