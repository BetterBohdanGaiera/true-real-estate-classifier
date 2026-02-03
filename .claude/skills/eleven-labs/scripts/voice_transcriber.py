# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "python-dotenv", "pydantic"]
# ///
"""
Voice message transcription using ElevenLabs Speech-to-Text API.

This module provides the VoiceTranscriber class for transcribing audio files,
particularly Telegram voice messages, using the ElevenLabs Scribe API.

Key features:
- Async transcription of audio files (OGG, MP3, WAV, etc.)
- Direct integration with Telethon for downloading and transcribing voice messages
- Automatic temp file cleanup after transcription
- Detailed transcription results including language detection

Requirements:
- ELEVENLABS_API_KEY environment variable must be set
- httpx library for async HTTP requests

Example:
    from voice_transcriber import VoiceTranscriber

    # Initialize transcriber
    transcriber = VoiceTranscriber()

    # Transcribe a local audio file
    result = await transcriber.transcribe(Path("/path/to/audio.ogg"))
    print(f"Transcribed text: {result.text}")
    print(f"Language: {result.language_code}")

    # Transcribe directly from Telegram message
    result = await transcriber.transcribe_telegram_voice(client, message)
    print(f"Voice message: {result.text}")
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class TranscriptionResult(BaseModel):
    """
    Result of voice transcription.

    Attributes:
        text: The transcribed text content
        language_code: Detected language code (e.g., "ru", "en", "uk")
        language_probability: Confidence score for language detection (0-1)
        duration_seconds: Duration of the audio in seconds (if available)

    Example:
        result = TranscriptionResult(
            text="Hello, I'm interested in the property",
            language_code="en",
            language_probability=0.95,
            duration_seconds=5.2
        )
    """

    text: str
    language_code: str = "unknown"
    language_probability: Optional[float] = None
    duration_seconds: Optional[float] = None


class VoiceTranscriber:
    """
    Transcribe voice messages using ElevenLabs Speech-to-Text API.

    This class provides methods to transcribe audio files and Telegram voice
    messages using the ElevenLabs Scribe API. It handles the HTTP communication,
    file uploads, and response parsing.

    The ElevenLabs API supports various audio formats natively including:
    - OGG (Telegram voice format)
    - MP3
    - WAV
    - M4A
    - WEBM

    Attributes:
        ENDPOINT: ElevenLabs Speech-to-Text API endpoint URL
        api_key: ElevenLabs API key (from constructor or environment)

    Example:
        # Using environment variable
        transcriber = VoiceTranscriber()

        # Using explicit API key
        transcriber = VoiceTranscriber(api_key="your_api_key")

        # Check if transcription is available
        if transcriber.enabled:
            result = await transcriber.transcribe(audio_path)
    """

    ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the VoiceTranscriber.

        Args:
            api_key: ElevenLabs API key. If not provided, reads from
                    ELEVENLABS_API_KEY environment variable.

        Raises:
            ValueError: If no API key is found in arguments or environment.

        Example:
            # Using environment variable (recommended)
            transcriber = VoiceTranscriber()

            # Using explicit API key
            transcriber = VoiceTranscriber(api_key="sk-...")
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY not found. "
                "Set it in your .env file or pass it to the constructor."
            )
        logger.debug("VoiceTranscriber initialized successfully")

    @property
    def enabled(self) -> bool:
        """
        Check if voice transcription is available.

        Returns:
            True if API key is configured and transcription is available,
            False otherwise.
        """
        return bool(self.api_key)

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe an audio file to text.

        Sends the audio file to ElevenLabs Speech-to-Text API and returns
        the transcription result. The API supports various audio formats
        including OGG (Telegram voice), MP3, WAV, M4A, and WEBM.

        Args:
            audio_path: Path to the audio file to transcribe.
                       File must exist and be readable.

        Returns:
            TranscriptionResult containing the transcribed text and metadata.

        Raises:
            FileNotFoundError: If the audio file doesn't exist.
            Exception: If the API request fails (includes status code and error message).

        Example:
            result = await transcriber.transcribe(Path("voice.ogg"))
            print(f"Text: {result.text}")
            print(f"Language: {result.language_code}")
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing audio file: {audio_path}")

        headers = {"xi-api-key": self.api_key}

        # Request parameters for ElevenLabs Scribe API
        data = {
            "model_id": "scribe_v2",
            "timestamps_granularity": "none",  # We only need the text
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(audio_path, "rb") as f:
                # Determine MIME type based on file extension
                suffix = audio_path.suffix.lower()
                mime_types = {
                    ".ogg": "audio/ogg",
                    ".mp3": "audio/mpeg",
                    ".wav": "audio/wav",
                    ".m4a": "audio/m4a",
                    ".webm": "audio/webm",
                }
                mime_type = mime_types.get(suffix, "audio/ogg")

                files = {"file": (audio_path.name, f, mime_type)}
                response = await client.post(
                    self.ENDPOINT,
                    headers=headers,
                    data=data,
                    files=files,
                )

        if response.status_code != 200:
            error_msg = f"Transcription failed: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()
        logger.info(
            f"Transcription successful. Language: {result.get('language_code', 'unknown')}"
        )

        return TranscriptionResult(
            text=result.get("text", ""),
            language_code=result.get("language_code", "unknown"),
            language_probability=result.get("language_probability"),
            duration_seconds=None,  # Not provided by API without timestamps
        )

    async def transcribe_telegram_voice(
        self,
        client: Any,
        message: Any,
    ) -> TranscriptionResult:
        """
        Download and transcribe a Telegram voice message.

        This is a convenience method that handles downloading the voice message
        from Telegram, saving it to a temporary file, transcribing it, and
        cleaning up the temp file afterward.

        Args:
            client: Telethon TelegramClient instance for downloading media.
            message: Telethon Message object with voice attribute.
                    Must have downloadable media (voice message).

        Returns:
            TranscriptionResult containing the transcribed text and metadata.

        Raises:
            Exception: If download fails or transcription fails.

        Example:
            @client.on(events.NewMessage)
            async def handler(event):
                if event.voice:
                    result = await transcriber.transcribe_telegram_voice(
                        client, event.message
                    )
                    print(f"User said: {result.text}")

        Note:
            The temporary file is automatically cleaned up after transcription,
            even if an error occurs during processing.
        """
        logger.info("Downloading Telegram voice message for transcription")

        # Create temporary file with .ogg extension (Telegram voice format)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Download the voice message to temp file
            await client.download_media(message, str(tmp_path))
            logger.debug(f"Voice message downloaded to: {tmp_path}")

            # Transcribe the downloaded file
            result = await self.transcribe(tmp_path)
            logger.info(f"Voice message transcribed: {result.text[:100]}...")

            return result

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
                logger.debug(f"Temp file cleaned up: {tmp_path}")
