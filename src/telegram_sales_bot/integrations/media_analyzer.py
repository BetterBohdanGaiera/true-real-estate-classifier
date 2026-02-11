# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv"]
# ///
"""
Media content analyzer for Telegram messages.

This module provides the MediaAnalyzer class which handles analysis of different
media types received from Telegram conversations:

- **Photos**: Downloaded from Telegram, then analyzed via Claude Code CLI
  (`claude -p`) which uses its built-in Read tool for image understanding.
  This is the same approach used for all agent communication in the codebase.
- **Videos**: Downloaded from Telegram, audio track extracted via ffmpeg, then
  transcribed using ElevenLabs Speech-to-Text (via VoiceTranscriber).
- **Video notes** (circle messages): Same pipeline as videos -- audio extraction
  is sufficient since these are face-to-camera spoken messages.

Key design principles:
- Uses Claude Code CLI for image analysis (consistent with the rest of the codebase)
- Graceful degradation: if analysis fails, return placeholder text instead of
  raising exceptions.
- All operations are async (this is an async Telethon-based codebase).
- Temp files are always cleaned up in finally blocks.
- File size limit of 50 MB to avoid excessive memory and bandwidth usage.

Requirements:
- Claude Code CLI (`claude`) installed and available on PATH for photo analysis
- VoiceTranscriber instance (ElevenLabs) for video/audio transcription
- ffmpeg installed on the system for audio extraction from video files

Example:
    from telegram_sales_bot.integrations.elevenlabs import VoiceTranscriber
    from telegram_sales_bot.integrations.media_analyzer import MediaAnalyzer

    transcriber = VoiceTranscriber()
    analyzer = MediaAnalyzer(voice_transcriber=transcriber)

    # In a Telethon event handler:
    if event.photo:
        description = await analyzer.analyze_photo(client, message)
    elif event.video:
        text = await analyzer.analyze_video(client, message)
    elif event.video_note:
        text = await analyzer.analyze_video_note(client, message)
"""

import asyncio
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Add CLI task executor scripts to path (same pattern as cli_agent.py)
_PACKAGE_DIR = Path(__file__).parent.parent  # src/telegram_sales_bot/
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent  # project root
_CLI_SCRIPTS_DIR = _PROJECT_ROOT / ".claude" / "skills" / "cli-task-executor" / "scripts"
if str(_CLI_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CLI_SCRIPTS_DIR))

from execute_task import ClaudeTaskExecutor, TaskConfig, OutputFormat

# Maximum file size for analysis (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Photo analysis prompt for Claude Code CLI
PHOTO_ANALYSIS_PROMPT = (
    "Read the image file at {image_path} and describe it briefly (1-2 sentences) in Russian. "
    "Context: this is a photo from a client in a Bali real estate chat. "
    "If it's a screenshot, real estate property, document, or location - describe the content. "
    "If you can identify a specific area or landmark in Bali (like Tegallalang rice terraces, Uluwatu temple, Seminyak beach), name the area. "
    "If it's a selfie or photo of a person - just say it's a photo of a person. "
    "Reply ONLY with the description text, nothing else. No markdown, no formatting."
)


class MediaAnalyzer:
    """
    Analyzes media content: images via Claude Code CLI, videos via audio extraction + transcription.

    This class serves as the central media analysis component, routing each media
    type to the appropriate analysis backend:

    - Photos are analyzed via Claude Code CLI (`claude -p`) which uses its built-in
      Read tool for native image understanding. This is consistent with how the
      entire bot communicates -- through Claude Code CLI.
    - Videos and video notes have their audio extracted via ffmpeg, then
      transcribed via ElevenLabs through the VoiceTranscriber dependency.

    Attributes:
        voice_transcriber: Optional VoiceTranscriber instance for audio transcription.
        vision_enabled: Whether photo analysis via Claude Code CLI is available.
        transcription_enabled: Whether video audio transcription is available.

    Example:
        analyzer = MediaAnalyzer(voice_transcriber=transcriber)

        if analyzer.vision_enabled:
            desc = await analyzer.analyze_photo(client, message)

        if analyzer.transcription_enabled:
            text = await analyzer.analyze_video(client, message)
    """

    def __init__(
        self,
        voice_transcriber: Optional[Any] = None,
        cli_model: str = "claude-sonnet-4-20250514",
        cli_timeout: int = 30,
    ):
        """
        Initialize the MediaAnalyzer.

        Args:
            voice_transcriber: Optional VoiceTranscriber instance for transcribing
                             audio extracted from videos and video notes. If None,
                             video analysis will return placeholder text.
            cli_model: Claude model to use for photo analysis via CLI.
                      Defaults to Sonnet (fast, cost-effective for descriptions).
            cli_timeout: Timeout in seconds for CLI photo analysis calls.
        """
        self.voice_transcriber = voice_transcriber
        self._cli_model = cli_model
        self._cli_timeout = cli_timeout

        # Check if claude CLI is available
        self._claude_available = shutil.which("claude") is not None

        # Initialize CLI executor for photo analysis
        self._executor: Optional[ClaudeTaskExecutor] = None
        if self._claude_available:
            self._executor = ClaudeTaskExecutor(
                default_timeout=self._cli_timeout,
                default_model=self._cli_model,
            )
            logger.info("MediaAnalyzer: Photo analysis enabled via Claude Code CLI")
        else:
            logger.warning(
                "MediaAnalyzer: Photo analysis disabled (claude CLI not found on PATH)"
            )

    @property
    def vision_enabled(self) -> bool:
        """
        Check if photo analysis via Claude Code CLI is available.

        Returns:
            True if the Claude CLI is available on PATH, False otherwise.
        """
        return self._executor is not None

    @property
    def transcription_enabled(self) -> bool:
        """
        Check if video audio transcription is available.

        Returns:
            True if a VoiceTranscriber instance was provided, False otherwise.
        """
        return self.voice_transcriber is not None

    async def analyze_photo(self, client: Any, message: Any) -> str:
        """
        Download photo from Telegram, analyze with Claude Code CLI, return description.

        The photo is downloaded to a temporary file. The file path is passed to
        `claude -p` which uses its built-in Read tool to view the image and
        generate a description.

        Args:
            client: Telethon TelegramClient instance for downloading media.
            message: Telethon Message object containing a photo.

        Returns:
            A description string in the format "[Фото: description of contents]"
            (in Russian), or a placeholder like "[Фото]" if analysis fails.
        """
        if not self._executor:
            return "[Фото - анализ недоступен]"

        tmp_path: Optional[Path] = None
        try:
            # Create a temporary file for the downloaded photo
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            # Download photo from Telegram
            await client.download_media(message, str(tmp_path))

            if not tmp_path.exists() or tmp_path.stat().st_size == 0:
                return "[Фото]"

            # Check file size
            file_size = tmp_path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"Photo too large: {file_size} bytes")
                return "[Фото - слишком большой файл]"

            # Build the prompt with the image path
            prompt = PHOTO_ANALYSIS_PROMPT.format(image_path=str(tmp_path))

            # Call Claude Code CLI - it will use its Read tool to view the image
            config = TaskConfig(
                prompt=prompt,
                model=self._cli_model,
                max_turns=1,
                dangerously_skip_permissions=True,
                timeout=self._cli_timeout,
                output_format=OutputFormat.TEXT,
                cwd=str(_PROJECT_ROOT),
            )

            result = await self._executor.execute_with_config_async(config)

            if result.success and result.output and result.output.strip():
                description = result.output.strip()
                # Clean up any markdown artifacts or extra whitespace
                description = description.replace("```", "").strip()
                logger.info(f"Photo analyzed via CLI: {description[:100]}")
                return f"[Фото: {description}]"
            else:
                error_info = result.error or "empty response"
                logger.warning(f"Photo CLI analysis returned no result: {error_info}")
                return "[Фото]"

        except Exception as e:
            logger.error(f"Photo analysis failed: {e}")
            return "[Фото]"
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    async def _extract_audio_and_transcribe(
        self, client: Any, message: Any, suffix: str = ".mp4"
    ) -> str:
        """
        Download video, extract audio via ffmpeg, transcribe via ElevenLabs.

        This is the shared implementation for both video and video note analysis.
        The pipeline is: download video -> ffmpeg extracts audio to OGG/Opus ->
        VoiceTranscriber transcribes the audio -> return transcribed text.

        Args:
            client: Telethon TelegramClient instance for downloading media.
            message: Telethon Message object containing video or video_note.
            suffix: File extension for the downloaded video file (default ".mp4").

        Returns:
            Transcribed speech text from the video, or a placeholder string
            if transcription is unavailable or the video has no speech.
        """
        if not self.voice_transcriber:
            return "[Видео - расшифровка недоступна]"

        video_path: Optional[Path] = None
        audio_path: Optional[Path] = None
        try:
            # Create temporary files for video and extracted audio
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                video_path = Path(tmp.name)
            audio_path = video_path.with_suffix(".ogg")

            # Download video from Telegram
            await client.download_media(message, str(video_path))

            if not video_path.exists() or video_path.stat().st_size == 0:
                return "[Видео]"

            # Check file size
            file_size = video_path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.warning(
                    f"Video too large for analysis: {file_size} bytes"
                )
                return "[Видео - слишком большой файл для анализа]"

            # Extract audio via ffmpeg (OGG/Opus format, same as Telegram voice)
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-i",
                str(video_path),
                "-vn",  # No video output
                "-acodec",
                "libopus",  # OGG/Opus codec
                "-y",  # Overwrite output file
                str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0 or not audio_path.exists():
                logger.error(
                    f"ffmpeg audio extraction failed (rc={process.returncode}): "
                    f"{stderr.decode()[:200]}"
                )
                return "[Видео - не удалось извлечь аудио]"

            # Check if audio file has meaningful content
            # Very small files (< 100 bytes) likely contain no actual audio
            if audio_path.stat().st_size < 100:
                return "[Видео без речи]"

            # Transcribe extracted audio via ElevenLabs
            result = await self.voice_transcriber.transcribe(audio_path)

            if result.text.strip():
                logger.info(f"Video transcribed: {result.text[:100]}")
                return result.text
            else:
                return "[Видео без речи]"

        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return "[Видео]"
        finally:
            if video_path and video_path.exists():
                video_path.unlink(missing_ok=True)
            if audio_path and audio_path.exists():
                audio_path.unlink(missing_ok=True)

    async def analyze_video(self, client: Any, message: Any) -> str:
        """
        Extract audio from a video message and transcribe it.

        Args:
            client: Telethon TelegramClient instance for downloading media.
            message: Telethon Message object containing a video.

        Returns:
            Transcribed speech text from the video, or a placeholder string
            if transcription is unavailable or fails.
        """
        return await self._extract_audio_and_transcribe(
            client, message, suffix=".mp4"
        )

    async def analyze_video_note(self, client: Any, message: Any) -> str:
        """
        Extract audio from a video note (circle message) and transcribe it.

        For video notes (circular video messages), audio extraction is sufficient
        since these are face-to-camera messages where the spoken content is the
        primary information. Visual analysis is not performed.

        Args:
            client: Telethon TelegramClient instance for downloading media.
            message: Telethon Message object containing a video_note.

        Returns:
            Transcribed speech text from the video note, or a placeholder string
            if transcription is unavailable or fails.
        """
        return await self._extract_audio_and_transcribe(
            client, message, suffix=".mp4"
        )
