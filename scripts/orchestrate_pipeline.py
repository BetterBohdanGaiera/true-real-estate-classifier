#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "rich", "pydantic"]
# ///
"""
Video Knowledge Extraction Pipeline Orchestrator

Main orchestration script that coordinates the entire video knowledge extraction pipeline.
Runs all phases in order: setup, transcription, visual analysis, screenshot extraction,
PDF processing, and knowledge synthesis.
"""

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# Initialize console with fixed width for full-width panels
console = Console(width=120)

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base"


class VideoTask(BaseModel):
    """Video processing task configuration."""

    path: str
    output_name: str
    audio_only: bool = False
    visual_type: str | None = None
    screenshots: bool = False


class PhaseResult(BaseModel):
    """Result of a pipeline phase."""

    phase_name: str
    success: bool
    duration_seconds: float = 0.0
    items_processed: int = 0
    items_total: int = 0
    errors: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)


class PipelineState(BaseModel):
    """Current state of the pipeline."""

    phase: str = "not_started"
    total_videos: int = 0
    processed_videos: int = 0
    errors: list[str] = Field(default_factory=list)
    completed_phases: list[str] = Field(default_factory=list)
    phase_results: list[PhaseResult] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None


class PipelineConfig(BaseModel):
    """Pipeline configuration options."""

    phases: list[str] = Field(default_factory=lambda: [
        "setup", "transcription", "visual_analysis", "screenshots", "pdf", "synthesis"
    ])
    skip_setup: bool = False
    dry_run: bool = False
    workers: int = 3
    max_retries: int = 3
    retry_delay: float = 5.0


# Video processing configuration
VIDEOS = [
    VideoTask(
        path="data/BaliRegions(text_is_enough).mp4",
        output_name="bali_regions",
        audio_only=True,
    ),
    VideoTask(
        path="data/LeaseHoldFreeHoldDifference(AudioIsEnough).mp4",
        output_name="leasehold_freehold",
        audio_only=True,
    ),
    VideoTask(
        path="data/CompanyPresentation(PresentationSlidesInclude).mp4",
        output_name="company_presentation",
        visual_type="presentation",
        screenshots=True,
    ),
    VideoTask(
        path="data/EstateMarketSiteUnderstanding.mp4",
        output_name="estate_market_site",
        visual_type="general",
        screenshots=True,
    ),
    VideoTask(
        path="data/EstateMarketStatisticWalktrough.mp4",
        output_name="estate_market_statistics",
        visual_type="statistics",
        screenshots=True,
    ),
    VideoTask(
        path="data/FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4",
        output_name="financial_models",
        visual_type="excel",
        screenshots=True,
    ),
]

# PDF document configuration
PDF_DOCUMENT = "data/CompanyPresentationExtra.pdf"


def validate_api_keys() -> tuple[bool, list[str]]:
    """Validate required API keys are present."""
    missing_keys = []

    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key or elevenlabs_key == "your_elevenlabs_api_key_here":
        missing_keys.append("ELEVENLABS_API_KEY")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        missing_keys.append("GEMINI_API_KEY")

    return len(missing_keys) == 0, missing_keys


def validate_source_files() -> tuple[bool, list[str], list[str]]:
    """Validate all source files exist."""
    valid_files = []
    missing_files = []

    for video in VIDEOS:
        video_path = PROJECT_ROOT / video.path
        if video_path.exists():
            valid_files.append(video.path)
        else:
            missing_files.append(video.path)

    pdf_path = PROJECT_ROOT / PDF_DOCUMENT
    if pdf_path.exists():
        valid_files.append(PDF_DOCUMENT)
    else:
        missing_files.append(PDF_DOCUMENT)

    return len(missing_files) == 0, valid_files, missing_files


def run_command_with_retry(
    cmd: list[str],
    description: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    timeout: int = 1800,
) -> tuple[bool, str]:
    """Run a command with retry logic. Returns (success, error_message)."""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
            return True, ""
        except subprocess.CalledProcessError as e:
            last_error = e.stderr or str(e)
            if attempt < max_retries:
                console.print(
                    f"[yellow]Attempt {attempt}/{max_retries} failed for {description}. "
                    f"Retrying in {retry_delay}s...[/yellow]"
                )
                time.sleep(retry_delay)
            else:
                console.print(f"[red]All {max_retries} attempts failed for {description}[/red]")
        except subprocess.TimeoutExpired:
            last_error = f"Timeout expired after {timeout}s"
            console.print(f"[red]Timeout expired for {description}[/red]")
            break

    return False, last_error


def run_setup(dry_run: bool = False) -> PhaseResult:
    """Run setup_knowledge_base.py."""
    result = PhaseResult(phase_name="setup", success=False, items_total=1)
    start_time = time.time()

    console.print(
        Panel(
            "[bold]Running Knowledge Base Setup[/bold]\n\n"
            "Creating directory structure and validating source files.",
            title="Phase 1: Setup",
            expand=True,
        )
    )

    if dry_run:
        console.print("[yellow]DRY RUN: Would run setup_knowledge_base.py[/yellow]")
        result.success = True
        result.items_processed = 1
        result.duration_seconds = time.time() - start_time
        return result

    cmd = ["uv", "run", str(SCRIPTS_DIR / "setup_knowledge_base.py")]
    success, error = run_command_with_retry(cmd, "setup", max_retries=1)

    if success:
        result.success = True
        result.items_processed = 1
        result.output_files.append(str(KNOWLEDGE_BASE))
    else:
        result.errors.append(f"Setup failed: {error}")

    result.duration_seconds = time.time() - start_time
    return result


def process_single_video_transcription(
    video: VideoTask,
    config: PipelineConfig,
) -> tuple[str, bool, str, str | None]:
    """Process transcription for a single video. Returns (output_name, success, error, output_path)."""
    video_path = PROJECT_ROOT / video.path

    cmd = [
        "uv",
        "run",
        str(SCRIPTS_DIR / "process_video.py"),
        str(video_path),
        "--output-name",
        video.output_name,
        "--audio-only",  # Only transcribe in this phase
        "--language",
        "ru",
        "--max-retries",
        str(config.max_retries),
    ]

    if config.dry_run:
        return video.output_name, True, "", f"{KNOWLEDGE_BASE}/transcripts/{video.output_name}_transcript.md"

    success, error = run_command_with_retry(
        cmd,
        f"transcription of {video.output_name}",
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        timeout=1800,  # 30 min timeout for long videos
    )

    output_path = None
    if success:
        output_path = str(KNOWLEDGE_BASE / "transcripts" / f"{video.output_name}_transcript.md")

    return video.output_name, success, error, output_path


def run_transcription_phase(config: PipelineConfig) -> PhaseResult:
    """Run transcription for all videos in parallel."""
    result = PhaseResult(
        phase_name="transcription",
        success=False,
        items_total=len(VIDEOS),
    )
    start_time = time.time()

    console.print(
        Panel(
            f"[bold]Transcribing {len(VIDEOS)} Videos[/bold]\n\n"
            f"Using ElevenLabs Scribe API with {config.workers} parallel workers.",
            title="Phase 2: Transcription",
            expand=True,
        )
    )

    if config.dry_run:
        console.print("[yellow]DRY RUN: Would transcribe all videos[/yellow]")
        for video in VIDEOS:
            console.print(f"  - {video.output_name}: {video.path}")
        result.success = True
        result.items_processed = len(VIDEOS)
        result.duration_seconds = time.time() - start_time
        return result

    # Process videos in parallel
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Transcribing videos...", total=len(VIDEOS))

        with ThreadPoolExecutor(max_workers=config.workers) as executor:
            futures = {
                executor.submit(
                    process_single_video_transcription, video, config
                ): video
                for video in VIDEOS
            }

            for future in as_completed(futures):
                video = futures[future]
                try:
                    output_name, success, error, output_path = future.result()
                    if success:
                        result.items_processed += 1
                        if output_path:
                            result.output_files.append(output_path)
                        console.print(f"[green]Completed:[/green] {output_name}")
                    else:
                        result.errors.append(f"{output_name}: {error}")
                        console.print(f"[red]Failed:[/red] {output_name}")
                except Exception as e:
                    result.errors.append(f"{video.output_name}: {str(e)}")
                    console.print(f"[red]Error:[/red] {video.output_name}")

                progress.update(task, advance=1)

    result.success = result.items_processed > 0
    result.duration_seconds = time.time() - start_time
    return result


def process_single_video_visual(
    video: VideoTask,
    config: PipelineConfig,
) -> tuple[str, bool, str, str | None]:
    """Process visual analysis for a single video. Returns (output_name, success, error, output_path)."""
    video_path = PROJECT_ROOT / video.path

    cmd = [
        "uv",
        "run",
        str(SCRIPTS_DIR / "process_video.py"),
        str(video_path),
        "--output-name",
        video.output_name,
        "--visual-type",
        video.visual_type or "general",
        "--language",
        "ru",
        "--max-retries",
        str(config.max_retries),
    ]

    if config.dry_run:
        return video.output_name, True, "", f"{KNOWLEDGE_BASE}/visual_analysis/{video.output_name}_analysis.md"

    success, error = run_command_with_retry(
        cmd,
        f"visual analysis of {video.output_name}",
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        timeout=1800,
    )

    output_path = None
    if success:
        output_path = str(KNOWLEDGE_BASE / "visual_analysis" / f"{video.output_name}_analysis.md")

    return video.output_name, success, error, output_path


def run_visual_analysis_phase(config: PipelineConfig) -> PhaseResult:
    """Run visual analysis for videos that require it (sequentially to respect rate limits)."""
    visual_videos = [v for v in VIDEOS if not v.audio_only and v.visual_type]
    result = PhaseResult(
        phase_name="visual_analysis",
        success=False,
        items_total=len(visual_videos),
    )
    start_time = time.time()

    console.print(
        Panel(
            f"[bold]Analyzing {len(visual_videos)} Videos with Visual Content[/bold]\n\n"
            "Using Gemini API for visual analysis.\n"
            "[dim]Processing sequentially to respect API rate limits.[/dim]",
            title="Phase 3: Visual Analysis",
            expand=True,
        )
    )

    if config.dry_run:
        console.print("[yellow]DRY RUN: Would analyze visual content[/yellow]")
        for video in visual_videos:
            console.print(f"  - {video.output_name}: {video.visual_type}")
        result.success = True
        result.items_processed = len(visual_videos)
        result.duration_seconds = time.time() - start_time
        return result

    # Process videos sequentially to respect Gemini rate limits
    for video in visual_videos:
        console.print(f"\n[bold]Processing:[/bold] {video.output_name} ({video.visual_type})")

        output_name, success, error, output_path = process_single_video_visual(video, config)

        if success:
            result.items_processed += 1
            if output_path:
                result.output_files.append(output_path)
            console.print(f"[green]Completed:[/green] {output_name}")
        else:
            result.errors.append(f"{output_name}: {error}")
            console.print(f"[red]Failed:[/red] {output_name}")

    result.success = result.items_processed > 0
    result.duration_seconds = time.time() - start_time
    return result


def process_single_video_screenshots(
    video: VideoTask,
    config: PipelineConfig,
) -> tuple[str, bool, str, str | None]:
    """Extract screenshots from a single video. Returns (output_name, success, error, output_dir)."""
    video_path = PROJECT_ROOT / video.path
    output_dir = KNOWLEDGE_BASE / "screenshots" / video.output_name

    cmd = [
        "uv",
        "run",
        str(SCRIPTS_DIR / "extract_screenshots.py"),
        str(video_path),
        str(output_dir),
        "--interval",
        "30",
        "--width",
        "1280",
        "--quality",
        "2",
    ]

    if config.dry_run:
        return video.output_name, True, "", str(output_dir)

    success, error = run_command_with_retry(
        cmd,
        f"screenshot extraction for {video.output_name}",
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        timeout=600,  # 10 min timeout for screenshot extraction
    )

    return video.output_name, success, error, str(output_dir) if success else None


def run_screenshot_phase(config: PipelineConfig) -> PhaseResult:
    """Extract screenshots from videos that require them."""
    screenshot_videos = [v for v in VIDEOS if v.screenshots]
    result = PhaseResult(
        phase_name="screenshots",
        success=False,
        items_total=len(screenshot_videos),
    )
    start_time = time.time()

    console.print(
        Panel(
            f"[bold]Extracting Screenshots from {len(screenshot_videos)} Videos[/bold]\n\n"
            f"Using FFmpeg with {config.workers} parallel workers.\n"
            "[dim]Capturing frames every 30 seconds.[/dim]",
            title="Phase 4: Screenshot Extraction",
            expand=True,
        )
    )

    if config.dry_run:
        console.print("[yellow]DRY RUN: Would extract screenshots[/yellow]")
        for video in screenshot_videos:
            console.print(f"  - {video.output_name}")
        result.success = True
        result.items_processed = len(screenshot_videos)
        result.duration_seconds = time.time() - start_time
        return result

    # Process videos in parallel (FFmpeg is CPU-bound, not API-limited)
    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = {
            executor.submit(
                process_single_video_screenshots, video, config
            ): video
            for video in screenshot_videos
        }

        for future in as_completed(futures):
            video = futures[future]
            try:
                output_name, success, error, output_dir = future.result()
                if success:
                    result.items_processed += 1
                    if output_dir:
                        result.output_files.append(output_dir)
                    console.print(f"[green]Completed:[/green] {output_name}")
                else:
                    result.errors.append(f"{output_name}: {error}")
                    console.print(f"[red]Failed:[/red] {output_name}")
            except Exception as e:
                result.errors.append(f"{video.output_name}: {str(e)}")
                console.print(f"[red]Error:[/red] {video.output_name}")

    result.success = result.items_processed > 0
    result.duration_seconds = time.time() - start_time
    return result


def run_pdf_extraction(config: PipelineConfig) -> PhaseResult:
    """Extract PDF content."""
    result = PhaseResult(
        phase_name="pdf",
        success=False,
        items_total=1,
    )
    start_time = time.time()

    pdf_path = PROJECT_ROOT / PDF_DOCUMENT

    console.print(
        Panel(
            f"[bold]Extracting PDF Content[/bold]\n\n"
            f"File: {PDF_DOCUMENT}",
            title="Phase 5: PDF Extraction",
            expand=True,
        )
    )

    if config.dry_run:
        console.print("[yellow]DRY RUN: Would extract PDF content[/yellow]")
        result.success = True
        result.items_processed = 1
        result.duration_seconds = time.time() - start_time
        return result

    cmd = [
        "uv",
        "run",
        str(SCRIPTS_DIR / "extract_pdf.py"),
        str(pdf_path),
    ]

    success, error = run_command_with_retry(
        cmd,
        "PDF extraction",
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        timeout=300,
    )

    if success:
        result.success = True
        result.items_processed = 1
        output_path = KNOWLEDGE_BASE / "documents" / "companypresentationextra.md"
        result.output_files.append(str(output_path))
    else:
        result.errors.append(f"PDF extraction failed: {error}")

    result.duration_seconds = time.time() - start_time
    return result


def run_synthesis(config: PipelineConfig) -> PhaseResult:
    """Synthesize knowledge articles from all extracted content."""
    result = PhaseResult(
        phase_name="synthesis",
        success=False,
        items_total=6,  # 6 articles to generate
    )
    start_time = time.time()

    console.print(
        Panel(
            "[bold]Knowledge Synthesis[/bold]\n\n"
            "Combining transcripts, visual analysis, and documents into knowledge articles.\n\n"
            "[yellow]Note:[/yellow] synthesize_knowledge.py script is not yet implemented.\n"
            "This phase will be skipped for now.",
            title="Phase 6: Knowledge Synthesis",
            expand=True,
        )
    )

    # Check if synthesis script exists
    synthesis_script = SCRIPTS_DIR / "synthesize_knowledge.py"
    if not synthesis_script.exists():
        console.print(
            "[yellow]Synthesis script not found. Skipping this phase.[/yellow]\n"
            "[dim]The synthesis step combines all extracted content into knowledge articles.[/dim]"
        )
        result.success = True  # Not a failure, just not implemented yet
        result.items_processed = 0
        result.duration_seconds = time.time() - start_time
        return result

    if config.dry_run:
        console.print("[yellow]DRY RUN: Would synthesize knowledge articles[/yellow]")
        result.success = True
        result.items_processed = 6
        result.duration_seconds = time.time() - start_time
        return result

    cmd = ["uv", "run", str(synthesis_script)]
    success, error = run_command_with_retry(
        cmd,
        "knowledge synthesis",
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        timeout=600,
    )

    if success:
        result.success = True
        result.items_processed = 6
        # Add expected article paths
        articles = [
            "01_bali_regions_overview.md",
            "02_company_overview.md",
            "03_estate_market_understanding.md",
            "04_market_statistics.md",
            "05_financial_models_taxes.md",
            "06_leasehold_vs_freehold.md",
        ]
        for article in articles:
            result.output_files.append(str(KNOWLEDGE_BASE / "articles" / article))
    else:
        result.errors.append(f"Synthesis failed: {error}")

    result.duration_seconds = time.time() - start_time
    return result


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def generate_completion_report(state: PipelineState) -> str:
    """Generate final completion report in markdown format."""
    total_duration = 0
    if state.start_time and state.end_time:
        total_duration = (state.end_time - state.start_time).total_seconds()

    # Count totals
    total_transcripts = 0
    total_visual_analyses = 0
    total_screenshot_dirs = 0
    total_pdfs = 0
    total_articles = 0

    for result in state.phase_results:
        if result.phase_name == "transcription":
            total_transcripts = result.items_processed
        elif result.phase_name == "visual_analysis":
            total_visual_analyses = result.items_processed
        elif result.phase_name == "screenshots":
            total_screenshot_dirs = result.items_processed
        elif result.phase_name == "pdf":
            total_pdfs = result.items_processed
        elif result.phase_name == "synthesis":
            total_articles = result.items_processed

    report_lines = [
        "# Pipeline Completion Report",
        "",
        "## Summary",
        f"- Total Videos Processed: {state.processed_videos}/{state.total_videos}",
        f"- PDF Documents Processed: {total_pdfs}/1",
        f"- Articles Generated: {total_articles}/6",
        f"- Total Duration: {format_duration(total_duration)}",
        "",
        "## Phase Results",
    ]

    for result in state.phase_results:
        status = "[green]Success[/green]" if result.success else "[red]Failed[/red]"
        status_symbol = "+" if result.success else "x"
        report_lines.append(
            f"{status_symbol} {result.phase_name.replace('_', ' ').title()}: "
            f"{result.items_processed}/{result.items_total} "
            f"({format_duration(result.duration_seconds)})"
        )

    report_lines.extend([
        "",
        "## Output Files",
        "",
        f"### Transcripts ({total_transcripts} files)",
    ])

    transcript_dir = KNOWLEDGE_BASE / "transcripts"
    if transcript_dir.exists():
        for f in sorted(transcript_dir.glob("*.md")):
            report_lines.append(f"- {f.name}")

    report_lines.extend([
        "",
        f"### Visual Analyses ({total_visual_analyses} files)",
    ])

    visual_dir = KNOWLEDGE_BASE / "visual_analysis"
    if visual_dir.exists():
        for f in sorted(visual_dir.glob("*.md")):
            report_lines.append(f"- {f.name}")

    report_lines.extend([
        "",
        f"### Screenshots ({total_screenshot_dirs} directories)",
    ])

    screenshots_dir = KNOWLEDGE_BASE / "screenshots"
    if screenshots_dir.exists():
        for d in sorted(screenshots_dir.iterdir()):
            if d.is_dir():
                count = len(list(d.glob("*.jpg")))
                report_lines.append(f"- {d.name}/: {count} images")

    report_lines.extend([
        "",
        f"### Documents ({total_pdfs} files)",
    ])

    docs_dir = KNOWLEDGE_BASE / "documents"
    if docs_dir.exists():
        for f in sorted(docs_dir.glob("*.md")):
            report_lines.append(f"- {f.name}")

    report_lines.extend([
        "",
        f"### Articles ({total_articles} files)",
    ])

    articles_dir = KNOWLEDGE_BASE / "articles"
    if articles_dir.exists():
        for f in sorted(articles_dir.glob("*.md")):
            report_lines.append(f"- {f.name}")

    # Errors section
    all_errors = []
    for result in state.phase_results:
        all_errors.extend(result.errors)
    all_errors.extend(state.errors)

    report_lines.extend([
        "",
        "## Errors",
    ])

    if all_errors:
        for error in all_errors:
            report_lines.append(f"- {error}")
    else:
        report_lines.append("None")

    report_lines.extend([
        "",
        "## Next Steps",
        "- Review knowledge_base/articles/ for generated content",
        "- Check knowledge_base/questions.md for items requiring clarification",
        "- Use knowledge_base/index.md to navigate the knowledge base",
        "",
        f"*Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    return "\n".join(report_lines)


def display_completion_report(state: PipelineState) -> None:
    """Display and save the completion report."""
    report = generate_completion_report(state)

    # Create a summary table for display
    table = Table(title="Phase Results", expand=True)
    table.add_column("Phase", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Progress", justify="center")
    table.add_column("Duration", justify="right")

    for result in state.phase_results:
        status = "[green]Success[/green]" if result.success else "[red]Failed[/red]"
        progress = f"{result.items_processed}/{result.items_total}"
        duration = format_duration(result.duration_seconds)
        table.add_row(result.phase_name.replace("_", " ").title(), status, progress, duration)

    console.print(table)
    console.print()

    # Calculate total duration
    total_duration = 0
    if state.start_time and state.end_time:
        total_duration = (state.end_time - state.start_time).total_seconds()

    # Count errors
    all_errors = []
    for result in state.phase_results:
        all_errors.extend(result.errors)

    # Overall summary
    if all_errors:
        summary = (
            f"[yellow]Pipeline completed with {len(all_errors)} error(s)[/yellow]\n\n"
            f"Total Duration: {format_duration(total_duration)}\n\n"
            f"Errors:\n"
        )
        for error in all_errors[:5]:  # Show first 5 errors
            summary += f"  - {error}\n"
        if len(all_errors) > 5:
            summary += f"  ... and {len(all_errors) - 5} more"
    else:
        summary = (
            f"[green]Pipeline completed successfully![/green]\n\n"
            f"Total Duration: {format_duration(total_duration)}\n\n"
            f"Output Directory: {KNOWLEDGE_BASE}"
        )

    console.print(
        Panel(
            summary,
            title="Pipeline Complete",
            expand=True,
            border_style="green" if not all_errors else "yellow",
        )
    )

    # Save report to file
    report_path = KNOWLEDGE_BASE / "pipeline_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.replace("[green]", "").replace("[/green]", "")
                           .replace("[red]", "").replace("[/red]", "")
                           .replace("[yellow]", "").replace("[/yellow]", ""), encoding="utf-8")
    console.print(f"\n[dim]Full report saved to: {report_path}[/dim]")


def main():
    """Main entry point for the pipeline orchestrator."""
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Video Knowledge Extraction Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  uv run scripts/orchestrate_pipeline.py

  # Run specific phases only
  uv run scripts/orchestrate_pipeline.py --phases setup,transcription

  # Skip setup (if already done)
  uv run scripts/orchestrate_pipeline.py --skip-setup

  # Dry run
  uv run scripts/orchestrate_pipeline.py --dry-run

  # Limit parallel workers
  uv run scripts/orchestrate_pipeline.py --workers 3
        """,
    )

    parser.add_argument(
        "--phases",
        type=str,
        default="setup,transcription,visual_analysis,screenshots,pdf,synthesis",
        help="Comma-separated list of phases to run (default: all phases)",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip the setup phase",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually running commands",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers for video processing (default: 3)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for failed API calls (default: 3)",
    )

    args = parser.parse_args()

    # Parse phases
    phases = [p.strip() for p in args.phases.split(",")]
    if args.skip_setup and "setup" in phases:
        phases.remove("setup")

    config = PipelineConfig(
        phases=phases,
        skip_setup=args.skip_setup,
        dry_run=args.dry_run,
        workers=args.workers,
        max_retries=args.max_retries,
    )

    # Initialize pipeline state
    state = PipelineState(
        total_videos=len(VIDEOS),
        start_time=datetime.now(),
    )

    # Display header
    console.print(
        Panel(
            "[bold green]Video Knowledge Extraction Pipeline[/bold green]\n\n"
            f"Processing {len(VIDEOS)} videos and 1 PDF document\n\n"
            f"Phases: {', '.join(phases)}\n"
            f"Workers: {config.workers}\n"
            f"Dry Run: {config.dry_run}",
            title="Pipeline Orchestrator",
            expand=True,
        )
    )
    console.print()

    # Phase 1: Validate API keys
    console.print("[bold]Validating API Keys...[/bold]")
    api_keys_valid, missing_keys = validate_api_keys()
    if not api_keys_valid:
        console.print(
            Panel(
                f"[red]Missing required API keys:[/red]\n\n"
                + "\n".join([f"  - {key}" for key in missing_keys])
                + "\n\nPlease add these keys to your .env file.",
                title="Configuration Error",
                expand=True,
            )
        )
        sys.exit(1)
    console.print("[green]API keys validated.[/green]\n")

    # Phase 2: Validate source files
    console.print("[bold]Validating Source Files...[/bold]")
    files_valid, valid_files, missing_files = validate_source_files()
    if not files_valid:
        console.print(
            Panel(
                f"[yellow]Warning: Some source files are missing:[/yellow]\n\n"
                + "\n".join([f"  - {f}" for f in missing_files])
                + "\n\nPipeline will continue but some phases may fail.",
                title="Missing Files Warning",
                expand=True,
            )
        )
    else:
        console.print(f"[green]All {len(valid_files)} source files validated.[/green]\n")

    # Run pipeline phases
    phase_handlers = {
        "setup": lambda: run_setup(config.dry_run),
        "transcription": lambda: run_transcription_phase(config),
        "visual_analysis": lambda: run_visual_analysis_phase(config),
        "screenshots": lambda: run_screenshot_phase(config),
        "pdf": lambda: run_pdf_extraction(config),
        "synthesis": lambda: run_synthesis(config),
    }

    for phase in phases:
        state.phase = phase
        handler = phase_handlers.get(phase)

        if handler:
            console.print()
            result = handler()
            state.phase_results.append(result)
            state.completed_phases.append(phase)

            if phase == "transcription":
                state.processed_videos = result.items_processed

            if not result.success and result.errors:
                state.errors.extend(result.errors)
        else:
            console.print(f"[yellow]Unknown phase: {phase}[/yellow]")

    # Complete pipeline
    state.end_time = datetime.now()
    state.phase = "completed"

    console.print()
    console.print("=" * 120)
    console.print()

    # Generate completion report
    display_completion_report(state)


if __name__ == "__main__":
    main()
