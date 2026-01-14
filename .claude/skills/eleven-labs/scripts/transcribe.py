# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "python-dotenv", "rich", "pydantic"]
# ///
"""
ElevenLabs Speech-to-Text Transcription Script

Transcribes audio and video files using the ElevenLabs Scribe API.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import os

console = Console(width=120)


class Word(BaseModel):
    """Word-level transcription details."""
    text: str
    start: float
    end: float
    type: str = "word"
    speaker_id: str | None = None
    logprob: float | None = None


class Entity(BaseModel):
    """Detected entity in transcription."""
    text: str
    type: str
    start_index: int
    end_index: int


class TranscriptionResponse(BaseModel):
    """ElevenLabs transcription API response."""
    language_code: str
    language_probability: float | None = None
    text: str
    words: list[Word] = []
    entities: list[Entity] = []
    transcription_id: str | None = None


class TranscriptionRequest(BaseModel):
    """Request parameters for transcription."""
    model_id: str = "scribe_v2"
    language_code: str | None = None
    tag_audio_events: bool = True
    diarize: bool = False
    num_speakers: int | None = None
    timestamps_granularity: Literal["none", "word", "character"] = "word"
    entity_detection: str | None = None


def get_api_key() -> str:
    """Get API key from environment."""
    load_dotenv(override=True)
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[red]ELEVENLABS_API_KEY not found![/red]\n\n"
                "Add to your .env file:\n"
                "[cyan]ELEVENLABS_API_KEY=your_api_key_here[/cyan]",
                title="Configuration Error",
                expand=True,
            )
        )
        sys.exit(1)
    return api_key


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def transcribe_file(
    file_path: Path | None,
    url: str | None,
    request: TranscriptionRequest,
    api_key: str,
) -> TranscriptionResponse:
    """Send transcription request to ElevenLabs API."""
    endpoint = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}

    data = {
        "model_id": request.model_id,
        "tag_audio_events": str(request.tag_audio_events).lower(),
        "timestamps_granularity": request.timestamps_granularity,
    }

    if request.language_code:
        data["language_code"] = request.language_code
    if request.diarize:
        data["diarize"] = "true"
    if request.num_speakers:
        data["num_speakers"] = str(request.num_speakers)
    if request.entity_detection:
        data["entity_detection"] = request.entity_detection

    with console.status("[bold green]Transcribing audio...[/bold green]"):
        with httpx.Client(timeout=600.0) as client:
            if url:
                data["cloud_storage_url"] = url
                response = client.post(endpoint, headers=headers, data=data)
            elif file_path:
                with open(file_path, "rb") as f:
                    files = {"file": (file_path.name, f)}
                    response = client.post(
                        endpoint, headers=headers, data=data, files=files
                    )
            else:
                raise ValueError("Either file_path or url must be provided")

    if response.status_code != 200:
        console.print(
            Panel(
                f"[red]API Error ({response.status_code}):[/red]\n{response.text}",
                title="Transcription Failed",
                expand=True,
            )
        )
        sys.exit(1)

    return TranscriptionResponse.model_validate(response.json())


def format_text(response: TranscriptionResponse) -> str:
    """Format as plain text."""
    return response.text


def format_json(response: TranscriptionResponse) -> str:
    """Format as JSON."""
    return response.model_dump_json(indent=2)


def format_markdown(response: TranscriptionResponse) -> str:
    """Format as markdown with timestamps and speakers."""
    lines = ["# Transcription", ""]
    lines.append(f"**Language:** {response.language_code}")

    if response.words:
        duration = max(w.end for w in response.words)
        lines.append(f"**Duration:** {format_timestamp(duration)}")

    lines.extend(["", "## Transcript", ""])

    if response.words and any(w.speaker_id for w in response.words):
        current_speaker = None
        current_text = []
        current_start = 0.0

        for word in response.words:
            if word.speaker_id != current_speaker:
                if current_text:
                    timestamp = format_timestamp(current_start)
                    speaker = current_speaker or "Unknown"
                    text = " ".join(current_text)
                    lines.append(f"[{timestamp}] **{speaker}:** {text}")

                current_speaker = word.speaker_id
                current_text = [word.text]
                current_start = word.start
            else:
                current_text.append(word.text)

        if current_text:
            timestamp = format_timestamp(current_start)
            speaker = current_speaker or "Unknown"
            text = " ".join(current_text)
            lines.append(f"[{timestamp}] **{speaker}:** {text}")
    else:
        lines.append(response.text)

    if response.entities:
        lines.extend(["", "## Entities Detected", ""])
        for entity in response.entities:
            lines.append(f"- **{entity.type}:** {entity.text}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video using ElevenLabs Speech-to-Text API"
    )
    parser.add_argument("file", nargs="?", help="Audio/video file to transcribe")
    parser.add_argument("--url", help="URL to audio/video file (S3, GCS, R2, CDN)")
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--diarize", action="store_true", help="Enable speaker diarization"
    )
    parser.add_argument(
        "--num-speakers", type=int, help="Expected number of speakers (max 32)"
    )
    parser.add_argument(
        "--timestamps",
        choices=["none", "word", "character"],
        default="word",
        help="Timestamp granularity (default: word)",
    )
    parser.add_argument(
        "--entities",
        choices=["all", "pii", "phi", "pci"],
        help="Enable entity detection",
    )
    parser.add_argument("--language", help="ISO language code (auto-detect if omitted)")
    parser.add_argument(
        "--model",
        choices=["scribe_v1", "scribe_v1_experimental", "scribe_v2"],
        default="scribe_v2",
        help="Transcription model (default: scribe_v2)",
    )
    parser.add_argument(
        "--no-audio-events", action="store_true", help="Disable audio event tagging"
    )
    parser.add_argument("--output", "-o", help="Save output to file")

    args = parser.parse_args()

    if not args.file and not args.url:
        console.print(
            Panel(
                "[red]Error:[/red] Either a file path or --url must be provided",
                title="Missing Input",
                expand=True,
            )
        )
        sys.exit(1)

    file_path = Path(args.file) if args.file else None
    if file_path and not file_path.exists():
        console.print(
            Panel(
                f"[red]Error:[/red] File not found: {file_path}",
                title="File Error",
                expand=True,
            )
        )
        sys.exit(1)

    api_key = get_api_key()

    request = TranscriptionRequest(
        model_id=args.model,
        language_code=args.language,
        tag_audio_events=not args.no_audio_events,
        diarize=args.diarize,
        num_speakers=args.num_speakers,
        timestamps_granularity=args.timestamps,
        entity_detection=args.entities,
    )

    response = transcribe_file(file_path, args.url, request, api_key)

    if args.format == "text":
        output = format_text(response)
    elif args.format == "json":
        output = format_json(response)
    else:
        output = format_markdown(response)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        console.print(
            Panel(
                f"[green]Transcription saved to:[/green] {output_path}",
                title="Success",
                expand=True,
            )
        )
    else:
        if args.format == "markdown":
            console.print(Panel(Markdown(output), title="Transcription", expand=True))
        elif args.format == "json":
            console.print(Panel(output, title="Transcription (JSON)", expand=True))
        else:
            console.print(Panel(output, title="Transcription", expand=True))


if __name__ == "__main__":
    main()
