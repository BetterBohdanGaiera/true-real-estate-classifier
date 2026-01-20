#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-genai", "python-dotenv"]
# ///
"""
Video Analysis Script using Google Gemini 3 Pro

Analyzes video files and YouTube URLs using Gemini's multimodal capabilities.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


def find_env_file() -> Path | None:
    """Find .env file by searching up from current directory."""
    current = Path.cwd()
    while current != current.parent:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent
    return None


def get_api_key() -> str | None:
    """Load and return GEMINI_API_KEY from environment."""
    env_file = find_env_file()
    if env_file:
        load_dotenv(env_file)
    return os.getenv("GEMINI_API_KEY")


def is_youtube_url(url: str) -> bool:
    """Check if the input is a YouTube URL."""
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=",
        r"^https?://youtu\.be/",
        r"^https?://(www\.)?youtube\.com/embed/",
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def setup_command() -> int:
    """Check if GEMINI_API_KEY is configured."""
    api_key = get_api_key()

    if api_key:
        # Mask the key for display
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(json.dumps({
            "success": True,
            "message": "GEMINI_API_KEY is configured",
            "key_preview": masked
        }, indent=2))
        return 0
    else:
        print(json.dumps({
            "success": False,
            "message": "GEMINI_API_KEY not found",
            "instructions": [
                "1. Get your API key from https://aistudio.google.com/apikey",
                "2. Add to your .env file: GEMINI_API_KEY=your_key_here"
            ]
        }, indent=2))
        return 1


def analyze_command(args: argparse.Namespace) -> int:
    """Analyze a video file or YouTube URL."""
    api_key = get_api_key()

    if not api_key:
        error = {
            "success": False,
            "error": "GEMINI_API_KEY not configured. Run 'setup' command for instructions."
        }
        print(json.dumps(error, indent=2) if args.json else error["error"])
        return 1

    video_input = args.video
    prompt = args.prompt or "Summarize this video, describing the key events and content."
    model_id = args.model

    try:
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)

        # Prepare content based on input type
        if is_youtube_url(video_input):
            # YouTube URL - use file_data with URI
            video_part = types.Part(
                file_data=types.FileData(file_uri=video_input)
            )
            input_display = video_input
        else:
            # Local file - upload via File API
            video_path = Path(video_input)
            if not video_path.exists():
                error = {
                    "success": False,
                    "error": f"Video file not found: {video_input}"
                }
                print(json.dumps(error, indent=2) if args.json else error["error"])
                return 1

            # Build video metadata for clipping/fps
            video_metadata = None
            if args.fps or args.start is not None or args.end is not None:
                metadata_kwargs = {}
                if args.fps:
                    metadata_kwargs["fps"] = args.fps
                if args.start is not None:
                    metadata_kwargs["start_offset"] = f"{args.start}s"
                if args.end is not None:
                    metadata_kwargs["end_offset"] = f"{args.end}s"
                video_metadata = types.VideoMetadata(**metadata_kwargs)

            # Upload the file
            uploaded_file = client.files.upload(file=str(video_path))

            if video_metadata:
                video_part = types.Part(
                    file_data=types.FileData(file_uri=uploaded_file.uri),
                    video_metadata=video_metadata
                )
            else:
                video_part = uploaded_file

            input_display = str(video_path.name)

        # Generate content
        response = client.models.generate_content(
            model=model_id,
            contents=[video_part, prompt]
        )

        analysis_text = response.text

        if args.json:
            result = {
                "success": True,
                "model": model_id,
                "input": input_display,
                "prompt": prompt,
                "analysis": analysis_text
            }
            print(json.dumps(result, indent=2))
        else:
            print(analysis_text)

        return 0

    except Exception as e:
        error = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(error, indent=2) if args.json else f"Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Analyze videos using Google Gemini 3 Pro"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    subparsers.add_parser("setup", help="Check API key configuration")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a video")
    analyze_parser.add_argument(
        "video",
        help="Path to video file or YouTube URL"
    )
    analyze_parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Analysis prompt (default: summarize)"
    )
    analyze_parser.add_argument(
        "--model",
        default="gemini-3-pro-preview",
        help="Gemini model to use (default: gemini-3-pro-preview)"
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    analyze_parser.add_argument(
        "--fps",
        type=int,
        help="Frame rate sampling (default: 1)"
    )
    analyze_parser.add_argument(
        "--start",
        type=int,
        help="Start offset in seconds"
    )
    analyze_parser.add_argument(
        "--end",
        type=int,
        help="End offset in seconds"
    )

    args = parser.parse_args()

    if args.command == "setup":
        return setup_command()
    elif args.command == "analyze":
        return analyze_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
