#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "rich", "pydantic", "httpx"]
# ///
"""
Video Processor - Unified Pipeline for Video Transcription and Analysis

Processes a single video through the complete pipeline:
- Transcription with ElevenLabs API
- Optional visual analysis with Gemini API
- Optional screenshot extraction with FFmpeg

Uses existing skill scripts for the heavy lifting while providing
a unified interface for video processing.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown

console = Console(width=120)

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base"

# Skill script paths
TRANSCRIBE_SCRIPT = SKILLS_DIR / "eleven-labs" / "scripts" / "transcribe.py"
ANALYZE_VIDEO_SCRIPT = SKILLS_DIR / "video-analysis" / "scripts" / "analyze_video.py"


class VideoConfig(BaseModel):
    """Configuration for video processing."""

    video_path: Path
    output_name: str
    audio_only: bool = False
    visual_type: Literal["presentation", "excel", "statistics", "general"] | None = None
    extract_screenshots: bool = False
    screenshot_interval: int = 30
    language: str = "ru"
    max_retries: int = 3
    retry_delay: float = 5.0


class VideoMetadata(BaseModel):
    """Metadata for video processing."""

    filename: str
    duration_minutes: float = 0.0
    requires_visual_analysis: bool = False
    visual_content_type: str | None = None
    output_name: str


class ProcessingResult(BaseModel):
    """Result of video processing."""

    success: bool
    transcript_path: Path | None = None
    analysis_path: Path | None = None
    screenshots_dir: Path | None = None
    error_message: str | None = None


# Prompt templates for different visual content types
VISUAL_PROMPTS = {
    "presentation": """Analyze this video which contains presentation slides.
The transcript of the audio is provided below for context.

For each distinct slide or visual change, extract:
1. Slide/section title or heading
2. Key bullet points or text content
3. Any diagrams, charts, or visual elements (describe them)
4. Timestamps when slides change

Focus on capturing all textual content from the slides accurately.

=== TRANSCRIPT FOR CONTEXT ===
{transcript}
=== END TRANSCRIPT ===

Please provide a structured markdown analysis with timestamps.""",
    "excel": """Analyze this video which shows an Excel spreadsheet walkthrough.
The transcript of the audio is provided below for context.

For each visible spreadsheet section, extract:
1. Sheet/tab names visible
2. Column headers and row labels
3. Key formulas or calculations shown (if visible)
4. Data values and their context
5. Any charts or graphs shown
6. Timestamps for major sections

Focus on capturing the spreadsheet structure and key numerical data.

=== TRANSCRIPT FOR CONTEXT ===
{transcript}
=== END TRANSCRIPT ===

Please provide a structured markdown analysis with timestamps.""",
    "statistics": """Analyze this video which contains market statistics and data visualizations.
The transcript of the audio is provided below for context.

For each data visualization, extract:
1. Chart/graph type and title
2. Axis labels and units
3. Key data points and trends
4. Table contents (if any)
5. Map visualizations (regions, values shown)
6. Statistical figures mentioned
7. Timestamps for each visualization

Focus on extracting numerical data and statistics accurately.

=== TRANSCRIPT FOR CONTEXT ===
{transcript}
=== END TRANSCRIPT ===

Please provide a structured markdown analysis with timestamps.""",
    "general": """Analyze the visual content of this video.
The transcript of the audio is provided below for context.

Describe:
1. Key visual elements and scenes
2. Any text or graphics shown on screen
3. Important visual changes with timestamps
4. Relevant visual details that complement the audio

=== TRANSCRIPT FOR CONTEXT ===
{transcript}
=== END TRANSCRIPT ===

Please provide a structured markdown analysis with timestamps.""",
}


def check_api_keys(config: VideoConfig) -> bool:
    """Verify required API keys are available."""
    load_dotenv(PROJECT_ROOT / ".env")

    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        console.print(
            Panel(
                "[red]ELEVENLABS_API_KEY not found![/red]\n\n"
                "Add to your .env file:\n"
                "[cyan]ELEVENLABS_API_KEY=your_api_key_here[/cyan]",
                title="Missing API Key",
                expand=True,
            )
        )
        return False

    if not config.audio_only:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            console.print(
                Panel(
                    "[red]GEMINI_API_KEY not found![/red]\n\n"
                    "Required for visual analysis. Add to your .env file:\n"
                    "[cyan]GEMINI_API_KEY=your_api_key_here[/cyan]\n\n"
                    "Or use [cyan]--audio-only[/cyan] flag to skip visual analysis.",
                    title="Missing API Key",
                    expand=True,
                )
            )
            return False

    return True


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
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


def run_with_retry(
    cmd: list[str],
    description: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> subprocess.CompletedProcess:
    """Run a command with retry logic."""
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=1800,  # 30 minute timeout for long videos
            )
            return result
        except subprocess.CalledProcessError as e:
            last_error = e
            if attempt < max_retries:
                console.print(
                    f"[yellow]Attempt {attempt} failed for {description}. "
                    f"Retrying in {retry_delay}s...[/yellow]"
                )
                time.sleep(retry_delay)
            else:
                console.print(f"[red]All {max_retries} attempts failed for {description}[/red]")
        except subprocess.TimeoutExpired as e:
            last_error = e
            console.print(f"[red]Timeout expired for {description}[/red]")
            break

    raise last_error  # type: ignore


def transcribe_video(config: VideoConfig) -> Path | None:
    """Transcribe video using ElevenLabs API."""
    transcript_dir = KNOWLEDGE_BASE / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    output_path = transcript_dir / f"{config.output_name}_transcript.md"

    console.print(
        Panel(
            f"[bold]Transcribing:[/bold] {config.video_path.name}\n"
            f"[bold]Output:[/bold] {output_path}\n"
            f"[bold]Language:[/bold] {config.language}",
            title="ElevenLabs Transcription",
            expand=True,
        )
    )

    cmd = [
        "uv",
        "run",
        str(TRANSCRIBE_SCRIPT),
        str(config.video_path),
        "--diarize",
        "--format",
        "markdown",
        "--language",
        config.language,
        "--output",
        str(output_path),
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Transcribing audio...", total=None)
            run_with_retry(
                cmd,
                "transcription",
                config.max_retries,
                config.retry_delay,
            )

        if output_path.exists():
            console.print(
                Panel(
                    f"[green]Transcript saved to:[/green] {output_path}\n"
                    f"[bold]Size:[/bold] {output_path.stat().st_size / 1024:.1f} KB",
                    title="Transcription Complete",
                    expand=True,
                )
            )
            return output_path
        else:
            console.print(
                Panel(
                    "[red]Transcript file was not created[/red]",
                    title="Transcription Failed",
                    expand=True,
                )
            )
            return None

    except Exception as e:
        console.print(
            Panel(
                f"[red]Transcription failed:[/red]\n{str(e)}",
                title="Transcription Error",
                expand=True,
            )
        )
        return None


def analyze_visual(config: VideoConfig, transcript_path: Path) -> Path | None:
    """Analyze video visuals with Gemini using transcript context."""
    analysis_dir = KNOWLEDGE_BASE / "visual_analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    output_path = analysis_dir / f"{config.output_name}_analysis.md"

    # Read transcript for context
    transcript_content = transcript_path.read_text(encoding="utf-8")

    # Get appropriate prompt template
    visual_type = config.visual_type or "general"
    prompt_template = VISUAL_PROMPTS.get(visual_type, VISUAL_PROMPTS["general"])
    enriched_prompt = prompt_template.format(transcript=transcript_content)

    console.print(
        Panel(
            f"[bold]Analyzing:[/bold] {config.video_path.name}\n"
            f"[bold]Visual Type:[/bold] {visual_type}\n"
            f"[bold]Output:[/bold] {output_path}\n"
            f"[bold]Transcript Context:[/bold] {len(transcript_content)} chars",
            title="Gemini Visual Analysis",
            expand=True,
        )
    )

    cmd = [
        "uv",
        "run",
        str(ANALYZE_VIDEO_SCRIPT),
        "analyze",
        str(config.video_path),
        enriched_prompt,
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Analyzing video visuals...", total=None)
            result = run_with_retry(
                cmd,
                "visual analysis",
                config.max_retries,
                config.retry_delay,
            )

        # Save the analysis output
        analysis_content = result.stdout
        if analysis_content:
            # Create markdown document with metadata
            markdown_content = f"""# Visual Analysis: {config.output_name}

**Video:** {config.video_path.name}
**Analysis Type:** {visual_type}
**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---

{analysis_content}
"""
            output_path.write_text(markdown_content, encoding="utf-8")

            console.print(
                Panel(
                    f"[green]Analysis saved to:[/green] {output_path}\n"
                    f"[bold]Size:[/bold] {output_path.stat().st_size / 1024:.1f} KB",
                    title="Visual Analysis Complete",
                    expand=True,
                )
            )
            return output_path
        else:
            console.print(
                Panel(
                    "[red]No analysis content returned[/red]",
                    title="Visual Analysis Failed",
                    expand=True,
                )
            )
            return None

    except Exception as e:
        console.print(
            Panel(
                f"[red]Visual analysis failed:[/red]\n{str(e)}",
                title="Visual Analysis Error",
                expand=True,
            )
        )
        return None


def extract_screenshots(config: VideoConfig) -> Path | None:
    """Extract screenshots from video using FFmpeg."""
    if not check_ffmpeg():
        console.print(
            Panel(
                "[red]FFmpeg is not installed![/red]\n\n"
                "Install with:\n"
                "[cyan]brew install ffmpeg[/cyan] (macOS)\n"
                "[cyan]apt-get install ffmpeg[/cyan] (Ubuntu/Debian)",
                title="Missing Dependency",
                expand=True,
            )
        )
        return None

    screenshots_dir = KNOWLEDGE_BASE / "screenshots" / config.output_name
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold]Extracting screenshots from:[/bold] {config.video_path.name}\n"
            f"[bold]Output directory:[/bold] {screenshots_dir}\n"
            f"[bold]Interval:[/bold] Every {config.screenshot_interval} seconds",
            title="Screenshot Extraction",
            expand=True,
        )
    )

    # FFmpeg command to extract frames at specified interval
    output_pattern = str(screenshots_dir / f"{config.output_name}_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-i",
        str(config.video_path),
        "-vf",
        f"fps=1/{config.screenshot_interval}",
        "-q:v",
        "2",  # High quality JPEGs
        output_pattern,
        "-y",  # Overwrite existing files
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Extracting screenshots...", total=None)
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=600,  # 10 minute timeout
            )

        # Count extracted screenshots
        screenshot_count = len(list(screenshots_dir.glob("*.jpg")))

        if screenshot_count > 0:
            console.print(
                Panel(
                    f"[green]Screenshots extracted:[/green] {screenshot_count} images\n"
                    f"[bold]Directory:[/bold] {screenshots_dir}",
                    title="Screenshot Extraction Complete",
                    expand=True,
                )
            )
            return screenshots_dir
        else:
            console.print(
                Panel(
                    "[red]No screenshots were extracted[/red]",
                    title="Screenshot Extraction Failed",
                    expand=True,
                )
            )
            return None

    except subprocess.CalledProcessError as e:
        console.print(
            Panel(
                f"[red]Screenshot extraction failed:[/red]\n{e.stderr.decode() if e.stderr else str(e)}",
                title="Screenshot Error",
                expand=True,
            )
        )
        return None
    except subprocess.TimeoutExpired:
        console.print(
            Panel(
                "[red]Screenshot extraction timed out[/red]",
                title="Screenshot Error",
                expand=True,
            )
        )
        return None


def process_video(config: VideoConfig) -> ProcessingResult:
    """Process a video through the complete pipeline."""
    result = ProcessingResult(success=False)

    # Print processing summary
    console.print(
        Panel(
            f"[bold cyan]Video Processing Pipeline[/bold cyan]\n\n"
            f"[bold]Video:[/bold] {config.video_path.name}\n"
            f"[bold]Output Name:[/bold] {config.output_name}\n"
            f"[bold]Mode:[/bold] {'Audio Only' if config.audio_only else 'Full Analysis'}\n"
            f"[bold]Visual Type:[/bold] {config.visual_type or 'N/A'}\n"
            f"[bold]Screenshots:[/bold] {'Yes' if config.extract_screenshots else 'No'}",
            title="Processing Configuration",
            expand=True,
        )
    )

    # Step 1: Transcribe video
    console.print("\n[bold]Step 1/3: Transcription[/bold]\n")
    transcript_path = transcribe_video(config)
    if not transcript_path:
        result.error_message = "Transcription failed"
        return result
    result.transcript_path = transcript_path

    # Step 2: Visual analysis (if required)
    if not config.audio_only and config.visual_type:
        console.print("\n[bold]Step 2/3: Visual Analysis[/bold]\n")
        analysis_path = analyze_visual(config, transcript_path)
        if analysis_path:
            result.analysis_path = analysis_path
        else:
            console.print("[yellow]Visual analysis failed, continuing...[/yellow]")
    else:
        console.print("\n[bold]Step 2/3: Visual Analysis[/bold] (Skipped - audio only mode)\n")

    # Step 3: Screenshot extraction (if requested)
    if config.extract_screenshots:
        console.print("\n[bold]Step 3/3: Screenshot Extraction[/bold]\n")
        screenshots_dir = extract_screenshots(config)
        if screenshots_dir:
            result.screenshots_dir = screenshots_dir
        else:
            console.print("[yellow]Screenshot extraction failed, continuing...[/yellow]")
    else:
        console.print("\n[bold]Step 3/3: Screenshot Extraction[/bold] (Skipped)\n")

    result.success = True
    return result


def main():
    """Main entry point."""
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Process video through transcription and analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Audio-only video (transcription only)
  uv run scripts/process_video.py "data/BaliRegions(text_is_enough).mp4" \\
    --output-name bali_regions \\
    --audio-only

  # Visual analysis with presentation slides
  uv run scripts/process_video.py "data/CompanyPresentation.mp4" \\
    --output-name company_presentation \\
    --visual-type presentation \\
    --screenshots

  # Excel walkthrough with custom screenshot interval
  uv run scripts/process_video.py "data/FinancialModels.mp4" \\
    --output-name financial_models \\
    --visual-type excel \\
    --screenshots \\
    --screenshot-interval 30
        """,
    )

    parser.add_argument(
        "video",
        type=Path,
        help="Path to video file to process",
    )
    parser.add_argument(
        "--output-name",
        required=True,
        help="Base name for output files (e.g., 'company_presentation')",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Only transcribe audio, skip visual analysis",
    )
    parser.add_argument(
        "--visual-type",
        choices=["presentation", "excel", "statistics", "general"],
        default=None,
        help="Type of visual content for specialized analysis",
    )
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Extract screenshots from video",
    )
    parser.add_argument(
        "--screenshot-interval",
        type=int,
        default=30,
        help="Interval in seconds between screenshots (default: 30)",
    )
    parser.add_argument(
        "--language",
        default="ru",
        help="Language code for transcription (default: ru)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for API calls (default: 3)",
    )

    args = parser.parse_args()

    # Validate video file exists
    video_path = args.video
    if not video_path.is_absolute():
        video_path = PROJECT_ROOT / video_path

    if not video_path.exists():
        console.print(
            Panel(
                f"[red]Video file not found:[/red] {video_path}",
                title="File Error",
                expand=True,
            )
        )
        sys.exit(1)

    # Create configuration
    config = VideoConfig(
        video_path=video_path,
        output_name=args.output_name,
        audio_only=args.audio_only,
        visual_type=args.visual_type,
        extract_screenshots=args.screenshots,
        screenshot_interval=args.screenshot_interval,
        language=args.language,
        max_retries=args.max_retries,
    )

    # Check API keys
    if not check_api_keys(config):
        sys.exit(1)

    # Process video
    result = process_video(config)

    # Print final summary
    if result.success:
        summary_lines = ["[green]Processing completed successfully![/green]\n"]

        if result.transcript_path:
            summary_lines.append(f"[bold]Transcript:[/bold] {result.transcript_path}")

        if result.analysis_path:
            summary_lines.append(f"[bold]Visual Analysis:[/bold] {result.analysis_path}")

        if result.screenshots_dir:
            screenshot_count = len(list(result.screenshots_dir.glob("*.jpg")))
            summary_lines.append(
                f"[bold]Screenshots:[/bold] {result.screenshots_dir} ({screenshot_count} images)"
            )

        console.print(
            Panel(
                "\n".join(summary_lines),
                title="Processing Summary",
                expand=True,
            )
        )
    else:
        console.print(
            Panel(
                f"[red]Processing failed:[/red] {result.error_message}",
                title="Processing Error",
                expand=True,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
