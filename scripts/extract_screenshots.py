#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "rich", "pydantic"]
# ///
"""
Screenshot Extractor - Extract key frame screenshots from videos at regular intervals.

Captures visual moments from presentation slides, Excel spreadsheets, charts,
and market data for reference using FFmpeg.

Requirements:
- FFmpeg must be installed on the system
"""

import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator
from rich.console import Console
from rich.panel import Panel

console = Console(width=120)


class ScreenshotConfig(BaseModel):
    """Configuration for screenshot extraction."""

    video_path: Path
    output_dir: Path
    interval: int = 30  # seconds between frames
    width: int = 1280  # output image width
    start: int | None = None  # start time in seconds
    end: int | None = None  # end time in seconds
    quality: int = 2  # JPEG quality (1-31, lower is better)

    @field_validator("video_path")
    @classmethod
    def validate_video_exists(cls, v: Path) -> Path:
        """Validate that video file exists."""
        if not v.exists():
            raise ValueError(f"Video file not found: {v}")
        if not v.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return v

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        """Validate interval is positive."""
        if v <= 0:
            raise ValueError("Interval must be positive")
        return v

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        """Validate width is reasonable."""
        if v < 100 or v > 7680:
            raise ValueError("Width must be between 100 and 7680 pixels")
        return v

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        """Validate JPEG quality is in valid range."""
        if v < 1 or v > 31:
            raise ValueError("Quality must be between 1 (best) and 31 (worst)")
        return v


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_video_duration(video_path: Path) -> float | None:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def calculate_frame_count(config: ScreenshotConfig, duration: float) -> int:
    """Calculate expected number of frames to extract."""
    start_time = config.start or 0
    end_time = config.end or duration

    # Clamp to video duration
    start_time = max(0, min(start_time, duration))
    end_time = max(start_time, min(end_time, duration))

    time_span = end_time - start_time
    if time_span <= 0:
        return 0

    # fps=1/interval means one frame every 'interval' seconds
    return max(1, int(time_span / config.interval) + 1)


def build_ffmpeg_command(config: ScreenshotConfig) -> list[str]:
    """Build the FFmpeg command for screenshot extraction."""
    cmd = ["ffmpeg", "-y"]  # -y to overwrite without asking

    # Input file
    cmd.extend(["-i", str(config.video_path)])

    # Time range filters
    if config.start is not None:
        cmd.extend(["-ss", str(config.start)])
    if config.end is not None:
        cmd.extend(["-to", str(config.end)])

    # Video filter: fps and scale
    # fps=1/N means 1 frame every N seconds
    vf_filters = [
        f"fps=1/{config.interval}",
        f"scale={config.width}:-1",
    ]
    cmd.extend(["-vf", ",".join(vf_filters)])

    # Output quality (qscale:v for JPEG)
    cmd.extend(["-qscale:v", str(config.quality)])

    # Output pattern
    output_pattern = config.output_dir / "frame_%04d.jpg"
    cmd.append(str(output_pattern))

    return cmd


def extract_screenshots(config: ScreenshotConfig) -> int:
    """
    Extract screenshots from video using FFmpeg.

    Returns the count of frames extracted.
    """
    # Create output directory if it doesn't exist
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Build and run FFmpeg command
    cmd = build_ffmpeg_command(config)

    console.print(
        Panel(
            f"[cyan]Running FFmpeg command:[/cyan]\n{' '.join(cmd)}",
            title="FFmpeg Command",
            expand=True,
        )
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        console.print(
            Panel(
                f"[red]FFmpeg error:[/red]\n{error_msg}",
                title="Extraction Failed",
                expand=True,
            )
        )
        sys.exit(1)

    # Count extracted frames
    frames = list(config.output_dir.glob("frame_*.jpg"))
    return len(frames)


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def main():
    """Main entry point for screenshot extraction."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Extract key frame screenshots from videos at regular intervals using FFmpeg.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract frames every 30 seconds (default)
  uv run scripts/extract_screenshots.py "data/video.mp4" output/

  # Custom interval - every 60 seconds
  uv run scripts/extract_screenshots.py "data/video.mp4" output/ --interval 60

  # Specific time range (120s to 600s)
  uv run scripts/extract_screenshots.py "data/video.mp4" output/ --start 120 --end 600

  # Custom scaling to 1920px width
  uv run scripts/extract_screenshots.py "data/video.mp4" output/ --width 1920

  # High quality output
  uv run scripts/extract_screenshots.py "data/video.mp4" output/ --quality 1
        """,
    )

    parser.add_argument(
        "video",
        type=str,
        help="Path to the video file to extract screenshots from",
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Directory to save extracted screenshots",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval between frames in seconds (default: 30)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Output image width in pixels, height scales proportionally (default: 1280)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Start time in seconds (default: beginning of video)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="End time in seconds (default: end of video)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=2,
        help="JPEG quality (1-31, lower is better quality, default: 2)",
    )

    args = parser.parse_args()

    # Check FFmpeg installation
    if not check_ffmpeg():
        console.print(
            Panel(
                "[red]FFmpeg is not installed![/red]\n\n"
                "Please install FFmpeg:\n"
                "[cyan]macOS:[/cyan] brew install ffmpeg\n"
                "[cyan]Ubuntu/Debian:[/cyan] apt-get install ffmpeg\n"
                "[cyan]Windows:[/cyan] choco install ffmpeg",
                title="Missing Dependency",
                expand=True,
            )
        )
        sys.exit(1)

    # Resolve paths
    video_path = Path(args.video).resolve()
    output_dir = Path(args.output_dir).resolve()

    # Create configuration
    try:
        config = ScreenshotConfig(
            video_path=video_path,
            output_dir=output_dir,
            interval=args.interval,
            width=args.width,
            start=args.start,
            end=args.end,
            quality=args.quality,
        )
    except ValueError as e:
        console.print(
            Panel(
                f"[red]Configuration error:[/red]\n{e}",
                title="Invalid Configuration",
                expand=True,
            )
        )
        sys.exit(1)

    # Get video duration
    duration = get_video_duration(config.video_path)
    if duration is None:
        console.print(
            Panel(
                "[yellow]Warning:[/yellow] Could not determine video duration.\n"
                "Proceeding with extraction anyway.",
                title="Duration Unknown",
                expand=True,
            )
        )
        expected_frames = "Unknown"
    else:
        expected_frames = calculate_frame_count(config, duration)

    # Display configuration
    start_display = format_duration(config.start) if config.start else "00:00:00"
    end_display = format_duration(config.end) if config.end else (format_duration(duration) if duration else "End")

    config_info = (
        f"[cyan]Video:[/cyan] {config.video_path.name}\n"
        f"[cyan]Output Directory:[/cyan] {config.output_dir}\n"
        f"[cyan]Interval:[/cyan] {config.interval} seconds\n"
        f"[cyan]Output Width:[/cyan] {config.width}px\n"
        f"[cyan]Time Range:[/cyan] {start_display} - {end_display}\n"
        f"[cyan]JPEG Quality:[/cyan] {config.quality}\n"
        f"[cyan]Expected Frames:[/cyan] {expected_frames}"
    )

    if duration:
        config_info += f"\n[cyan]Video Duration:[/cyan] {format_duration(duration)}"

    console.print(
        Panel(
            config_info,
            title="Screenshot Extraction Configuration",
            expand=True,
        )
    )

    # Extract screenshots
    console.print(
        Panel(
            "[bold green]Starting screenshot extraction...[/bold green]",
            title="Processing",
            expand=True,
        )
    )

    frame_count = extract_screenshots(config)

    # Show results
    if frame_count > 0:
        # List some of the extracted frames
        frames = sorted(config.output_dir.glob("frame_*.jpg"))[:5]
        frame_list = "\n".join([f"  - {f.name}" for f in frames])
        if len(list(config.output_dir.glob("frame_*.jpg"))) > 5:
            frame_list += f"\n  ... and {frame_count - 5} more"

        console.print(
            Panel(
                f"[green]Successfully extracted {frame_count} screenshots![/green]\n\n"
                f"[cyan]Output directory:[/cyan] {config.output_dir}\n\n"
                f"[cyan]Extracted frames:[/cyan]\n{frame_list}",
                title="Extraction Complete",
                expand=True,
            )
        )
    else:
        console.print(
            Panel(
                "[yellow]No frames were extracted.[/yellow]\n\n"
                "This could mean:\n"
                "- The video is shorter than the interval\n"
                "- The time range is invalid\n"
                "- FFmpeg encountered an issue",
                title="No Output",
                expand=True,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
