# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Media type detection from Telethon events.

This module provides functionality to detect the type of media content
in incoming Telegram messages. It analyzes Telethon NewMessage events
and returns structured information about any media present.

Supported media types:
- voice: Voice messages (audio recordings)
- video_note: Video notes (circular video messages)
- sticker: Stickers (with emoji representation)
- gif: GIF animations
- photo: Photos and images
- video: Videos
- audio: Audio files (music, etc.)
- document: Documents and other files

Example:
    from media_detector import detect_media_type, MediaDetectionResult

    @client.on(events.NewMessage)
    async def handler(event):
        media_result = detect_media_type(event)
        if media_result.has_media:
            print(f"Received {media_result.media_type}")
        else:
            print("Text-only message")
"""

from dataclasses import dataclass
from typing import Optional, Any

# Import Telethon type for voice detection via document attributes
try:
    from telethon.tl.types import DocumentAttributeAudio
except ImportError:
    # Fallback if telethon not installed - will still work but voice
    # detection via document attributes won't function
    DocumentAttributeAudio = None


@dataclass
class MediaDetectionResult:
    """
    Result of media type detection from a Telegram message.

    Attributes:
        has_media: True if the message contains media content
        media_type: Type of media ("voice", "photo", "video", etc.) or None for text
        file_name: Original filename for documents, emoji for stickers, or None
        file_size: Size of the media file in bytes, or None if not applicable

    Example:
        result = MediaDetectionResult(
            has_media=True,
            media_type="voice",
            file_name=None,
            file_size=15360
        )
    """

    has_media: bool
    media_type: Optional[str]  # "voice", "photo", "video", "sticker", etc.
    file_name: Optional[str] = None
    file_size: Optional[int] = None


def detect_media_type(event: Any) -> MediaDetectionResult:
    """
    Detect media type from a Telethon NewMessage event.

    Analyzes the event object to determine what type of media (if any)
    is attached to the message. The detection order is important as
    some media types can overlap (e.g., voice messages are technically
    documents with specific attributes).

    Args:
        event: Telethon NewMessage event object with media attributes.
               Expected to have attributes like: voice, video_note, sticker,
               gif, photo, video, audio, document

    Returns:
        MediaDetectionResult with has_media=True and the detected type,
        or has_media=False and media_type=None for text-only messages.

    Detection priority:
        1. Voice messages (event.voice)
        2. Video notes (event.video_note) - circular video messages
        3. Stickers (event.sticker) - includes emoji alt text
        4. GIFs (event.gif)
        5. Photos (event.photo)
        6. Videos (event.video)
        7. Audio files (event.audio)
        8. Documents (event.document) - also checks for voice via attributes
        9. Text-only (no media)

    Example:
        @client.on(events.NewMessage)
        async def handler(event):
            result = detect_media_type(event)

            if result.media_type == "voice":
                # Handle voice message
                text = await transcribe(event.message)
            elif result.media_type == "sticker":
                # Interpret as emoji reaction
                emoji = result.file_name  # Contains the sticker emoji
            elif result.has_media:
                # Other media - acknowledge receipt
                print(f"Received {result.media_type}")
    """
    # Check for voice message first (most common non-text in conversations)
    if hasattr(event, "voice") and event.voice:
        file_size = None
        if hasattr(event, "document") and event.document:
            file_size = getattr(event.document, "size", None)
        return MediaDetectionResult(
            has_media=True,
            media_type="voice",
            file_name=None,
            file_size=file_size,
        )

    # Check for video note (circular video messages)
    if hasattr(event, "video_note") and event.video_note:
        file_size = None
        if hasattr(event, "document") and event.document:
            file_size = getattr(event.document, "size", None)
        return MediaDetectionResult(
            has_media=True,
            media_type="video_note",
            file_name=None,
            file_size=file_size,
        )

    # Check for sticker
    if hasattr(event, "sticker") and event.sticker:
        # Extract emoji representation from sticker
        emoji = None
        if hasattr(event.sticker, "alt"):
            emoji = event.sticker.alt
        if not emoji:
            emoji = "\U0001F44D"  # Default thumbs up emoji
        return MediaDetectionResult(
            has_media=True,
            media_type="sticker",
            file_name=emoji,  # Store emoji in file_name
            file_size=None,
        )

    # Check for GIF
    if hasattr(event, "gif") and event.gif:
        return MediaDetectionResult(
            has_media=True,
            media_type="gif",
            file_name=None,
            file_size=None,
        )

    # Check for photo
    if hasattr(event, "photo") and event.photo:
        # Photos don't have a direct size attribute easily accessible
        return MediaDetectionResult(
            has_media=True,
            media_type="photo",
            file_name=None,
            file_size=None,
        )

    # Check for video
    if hasattr(event, "video") and event.video:
        file_size = None
        if hasattr(event, "document") and event.document:
            file_size = getattr(event.document, "size", None)
        return MediaDetectionResult(
            has_media=True,
            media_type="video",
            file_name=None,
            file_size=file_size,
        )

    # Check for audio (music files, not voice)
    if hasattr(event, "audio") and event.audio:
        file_size = None
        file_name = None
        if hasattr(event, "document") and event.document:
            file_size = getattr(event.document, "size", None)
            # Try to get filename from document attributes
            if hasattr(event.document, "attributes"):
                for attr in event.document.attributes:
                    if hasattr(attr, "file_name"):
                        file_name = attr.file_name
                        break
        return MediaDetectionResult(
            has_media=True,
            media_type="audio",
            file_name=file_name,
            file_size=file_size,
        )

    # Check for document (files, PDFs, etc.)
    if hasattr(event, "document") and event.document:
        # Some voice messages come as documents with audio attributes
        # Check if this is actually a voice message
        if hasattr(event.document, "attributes") and event.document.attributes:
            for attr in event.document.attributes:
                if DocumentAttributeAudio is not None:
                    if isinstance(attr, DocumentAttributeAudio) and getattr(
                        attr, "voice", False
                    ):
                        return MediaDetectionResult(
                            has_media=True,
                            media_type="voice",
                            file_name=None,
                            file_size=getattr(event.document, "size", None),
                        )

        # Regular document - try to get filename
        file_name = None
        if hasattr(event.document, "attributes"):
            for attr in event.document.attributes:
                if hasattr(attr, "file_name"):
                    file_name = attr.file_name
                    break

        return MediaDetectionResult(
            has_media=True,
            media_type="document",
            file_name=file_name,
            file_size=getattr(event.document, "size", None),
        )

    # No media detected - text-only message
    return MediaDetectionResult(
        has_media=False,
        media_type=None,
        file_name=None,
        file_size=None,
    )
