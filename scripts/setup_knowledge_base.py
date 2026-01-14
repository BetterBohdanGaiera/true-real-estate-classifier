#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "rich", "pydantic"]
# ///
"""
Knowledge Base Setup Script

Creates the complete directory structure for the knowledge base extraction pipeline.
This is the first script that runs to prepare the output directories for transcripts,
visual analysis, screenshots, documents, and articles.
"""

import sys
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize console with fixed width for full-width panels
console = Console(width=120)

# Base path for the project
PROJECT_ROOT = Path(__file__).parent.parent


class SourceFile(BaseModel):
    """Represents a source file to validate."""

    name: str
    path: Path
    exists: bool = False
    file_type: str = "unknown"

    def validate_exists(self) -> bool:
        """Check if the source file exists."""
        self.exists = self.path.exists()
        return self.exists


class DirectoryStructure(BaseModel):
    """Knowledge base directory structure configuration."""

    base: Path
    transcripts: Path = Field(default=None)
    visual_analysis: Path = Field(default=None)
    screenshots: Path = Field(default=None)
    documents: Path = Field(default=None)
    articles: Path = Field(default=None)

    # Screenshot subdirectories
    screenshot_subdirs: ClassVar[list[str]] = [
        "company_presentation",
        "estate_market_site",
        "estate_market_statistics",
        "financial_models",
    ]

    def model_post_init(self, __context) -> None:
        """Initialize derived paths after model creation."""
        self.transcripts = self.base / "transcripts"
        self.visual_analysis = self.base / "visual_analysis"
        self.screenshots = self.base / "screenshots"
        self.documents = self.base / "documents"
        self.articles = self.base / "articles"

    def get_all_directories(self) -> list[Path]:
        """Return all directories that need to be created."""
        dirs = [
            self.base,
            self.transcripts,
            self.visual_analysis,
            self.screenshots,
            self.documents,
            self.articles,
        ]
        # Add screenshot subdirectories
        for subdir in self.screenshot_subdirs:
            dirs.append(self.screenshots / subdir)
        return dirs


class SetupResult(BaseModel):
    """Result of the setup operation."""

    directories_created: list[str] = Field(default_factory=list)
    directories_existed: list[str] = Field(default_factory=list)
    template_files_created: list[str] = Field(default_factory=list)
    source_files_valid: list[str] = Field(default_factory=list)
    source_files_missing: list[str] = Field(default_factory=list)
    success: bool = True
    error_message: str | None = None


def get_source_files(data_dir: Path) -> list[SourceFile]:
    """Get the list of source files to validate."""
    source_files = [
        SourceFile(
            name="BaliRegions(text_is_enough).mp4",
            path=data_dir / "BaliRegions(text_is_enough).mp4",
            file_type="video",
        ),
        SourceFile(
            name="LeaseHoldFreeHoldDifference(AudioIsEnough).mp4",
            path=data_dir / "LeaseHoldFreeHoldDifference(AudioIsEnough).mp4",
            file_type="video",
        ),
        SourceFile(
            name="CompanyPresentation(PresentationSlidesInclude).mp4",
            path=data_dir / "CompanyPresentation(PresentationSlidesInclude).mp4",
            file_type="video",
        ),
        SourceFile(
            name="EstateMarketSiteUnderstanding.mp4",
            path=data_dir / "EstateMarketSiteUnderstanding.mp4",
            file_type="video",
        ),
        SourceFile(
            name="EstateMarketStatisticWalktrough.mp4",
            path=data_dir / "EstateMarketStatisticWalktrough.mp4",
            file_type="video",
        ),
        SourceFile(
            name="FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4",
            path=data_dir / "FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4",
            file_type="video",
        ),
        SourceFile(
            name="CompanyPresentationExtra.pdf",
            path=data_dir / "CompanyPresentationExtra.pdf",
            file_type="pdf",
        ),
    ]
    return source_files


def create_directories(structure: DirectoryStructure, result: SetupResult) -> None:
    """Create all required directories for the knowledge base."""
    for directory in structure.get_all_directories():
        if directory.exists():
            result.directories_existed.append(str(directory))
        else:
            directory.mkdir(parents=True, exist_ok=True)
            result.directories_created.append(str(directory))


def create_questions_template(base_path: Path, result: SetupResult) -> None:
    """Create the questions.md template file."""
    questions_path = base_path / "questions.md"

    template_content = """# Questions Requiring Clarification

This document tracks unclear items, ambiguities, and questions that arose during the knowledge extraction process. Each question should be categorized by source material and include relevant timestamps or page references.

## How to Use This Document

- Add questions as they arise during processing
- Include timestamp or page references where applicable
- Mark questions as resolved with [x] when answered
- Add resolution notes below each resolved question

---

## Bali Regions
<!-- Questions about regional information, geography, areas -->

- [ ]

## Company Presentation
<!-- Questions about company structure, offerings, processes -->

- [ ]

## Estate Market Site
<!-- Questions about market site navigation, features, data -->

- [ ]

## Estate Market Statistics
<!-- Questions about charts, data points, statistics -->

- [ ]

## Financial Models & Taxes
<!-- Questions about formulas, calculations, tax rates -->

- [ ]

## Leasehold vs Freehold
<!-- Questions about property ownership types, legal aspects -->

- [ ]

## PDF Document
<!-- Questions about additional presentation materials -->

- [ ]

---

## Resolved Questions

<!-- Move resolved questions here with their answers -->

"""

    if not questions_path.exists():
        questions_path.write_text(template_content, encoding="utf-8")
        result.template_files_created.append(str(questions_path))


def create_index_template(base_path: Path, result: SetupResult) -> None:
    """Create the index.md template file."""
    index_path = base_path / "index.md"

    template_content = """# Knowledge Base Index

This knowledge base contains extracted information from training videos and documents related to Bali real estate.

## Quick Navigation

### Knowledge Articles
- [01. Bali Regions Overview](articles/01_bali_regions_overview.md)
- [02. Company Overview](articles/02_company_overview.md)
- [03. Estate Market Understanding](articles/03_estate_market_understanding.md)
- [04. Market Statistics](articles/04_market_statistics.md)
- [05. Financial Models & Taxes](articles/05_financial_models_taxes.md)
- [06. Leasehold vs Freehold](articles/06_leasehold_vs_freehold.md)

### Raw Materials

#### Transcripts
- [Bali Regions Transcript](transcripts/bali_regions_transcript.md)
- [Leasehold Freehold Transcript](transcripts/leasehold_freehold_transcript.md)
- [Company Presentation Transcript](transcripts/company_presentation_transcript.md)
- [Estate Market Site Transcript](transcripts/estate_market_site_transcript.md)
- [Estate Market Statistics Transcript](transcripts/estate_market_statistics_transcript.md)
- [Financial Models Transcript](transcripts/financial_models_transcript.md)

#### Visual Analysis
- [Company Presentation Analysis](visual_analysis/company_presentation_analysis.md)
- [Estate Market Site Analysis](visual_analysis/estate_market_site_analysis.md)
- [Estate Market Statistics Analysis](visual_analysis/estate_market_statistics_analysis.md)
- [Financial Models Analysis](visual_analysis/financial_models_analysis.md)

#### Documents
- [Company Presentation Extra (PDF)](documents/company_presentation_extra.md)

#### Screenshots
- [Company Presentation Screenshots](screenshots/company_presentation/)
- [Estate Market Site Screenshots](screenshots/estate_market_site/)
- [Estate Market Statistics Screenshots](screenshots/estate_market_statistics/)
- [Financial Models Screenshots](screenshots/financial_models/)

### Meta
- [Questions Requiring Clarification](questions.md)

---

## Source Materials Summary

| Material | Type | Duration/Size | Processing Status |
|----------|------|---------------|-------------------|
| BaliRegions(text_is_enough).mp4 | Video | ~79 min | Pending |
| LeaseHoldFreeHoldDifference(AudioIsEnough).mp4 | Video | ~32 min | Pending |
| CompanyPresentation(PresentationSlidesInclude).mp4 | Video | ~21 min | Pending |
| EstateMarketSiteUnderstanding.mp4 | Video | ~19 min | Pending |
| EstateMarketStatisticWalktrough.mp4 | Video | ~40 min | Pending |
| FinantialModels&Taxes(ExcelWalktroughAnalysisInVideo).mp4 | Video | ~63 min | Pending |
| CompanyPresentationExtra.pdf | PDF | 112KB | Pending |

---

*Last updated: Not yet processed*
"""

    if not index_path.exists():
        index_path.write_text(template_content, encoding="utf-8")
        result.template_files_created.append(str(index_path))


def validate_source_files(data_dir: Path, result: SetupResult) -> bool:
    """Validate all source files exist."""
    source_files = get_source_files(data_dir)
    all_valid = True

    for source_file in source_files:
        if source_file.validate_exists():
            result.source_files_valid.append(source_file.name)
        else:
            result.source_files_missing.append(source_file.name)
            all_valid = False

    return all_valid


def display_source_file_status(data_dir: Path) -> bool:
    """Display source file validation status in a table."""
    source_files = get_source_files(data_dir)

    table = Table(title="Source Files Validation", expand=True)
    table.add_column("File Name", style="cyan", no_wrap=False)
    table.add_column("Type", style="magenta", justify="center")
    table.add_column("Status", justify="center")

    all_valid = True
    for source_file in source_files:
        exists = source_file.validate_exists()
        if not exists:
            all_valid = False
        status = "[green]Found[/green]" if exists else "[red]Missing[/red]"
        table.add_row(source_file.name, source_file.file_type, status)

    console.print(table)
    return all_valid


def display_directory_structure(structure: DirectoryStructure) -> None:
    """Display the directory structure that will be created."""
    tree_content = f"""
[bold cyan]{structure.base.name}/[/bold cyan]
├── [cyan]transcripts/[/cyan]           # Raw transcriptions from ElevenLabs
├── [cyan]visual_analysis/[/cyan]       # Gemini enriched analysis
├── [cyan]screenshots/[/cyan]           # Key visual captures
│   ├── [dim]company_presentation/[/dim]
│   ├── [dim]estate_market_site/[/dim]
│   ├── [dim]estate_market_statistics/[/dim]
│   └── [dim]financial_models/[/dim]
├── [cyan]documents/[/cyan]             # Extracted PDF content
├── [cyan]articles/[/cyan]              # Final structured knowledge articles
├── [yellow]questions.md[/yellow]           # Unclear items requiring clarification
└── [yellow]index.md[/yellow]               # Knowledge base index
"""
    console.print(Panel(tree_content, title="Directory Structure", expand=True))


def display_result_summary(result: SetupResult) -> None:
    """Display the setup result summary."""
    if result.success:
        summary_parts = []

        if result.directories_created:
            summary_parts.append(
                f"[green]Created {len(result.directories_created)} directories[/green]"
            )
        if result.directories_existed:
            summary_parts.append(
                f"[dim]{len(result.directories_existed)} directories already existed[/dim]"
            )
        if result.template_files_created:
            summary_parts.append(
                f"[green]Created {len(result.template_files_created)} template files[/green]"
            )

        summary = "\n".join(summary_parts)

        if result.source_files_missing:
            summary += f"\n\n[yellow]Warning: {len(result.source_files_missing)} source files missing[/yellow]"
            for missing in result.source_files_missing:
                summary += f"\n  - [dim]{missing}[/dim]"

        console.print(Panel(summary, title="Setup Complete", expand=True, border_style="green"))
    else:
        console.print(
            Panel(
                f"[red]Setup failed:[/red]\n{result.error_message}",
                title="Setup Failed",
                expand=True,
                border_style="red",
            )
        )


def main() -> int:
    """Main entry point for the setup script."""
    # Load environment variables
    load_dotenv()

    # Display header
    console.print(
        Panel(
            "[bold]Knowledge Base Setup[/bold]\n\n"
            "Creating directory structure for the video & PDF knowledge extraction pipeline.",
            title="Knowledge Base Extraction Pipeline",
            expand=True,
        )
    )
    console.print()

    # Initialize paths
    knowledge_base_path = PROJECT_ROOT / "knowledge_base"
    data_dir = PROJECT_ROOT / "data"

    # Create directory structure model
    structure = DirectoryStructure(base=knowledge_base_path)

    # Display planned structure
    display_directory_structure(structure)
    console.print()

    # Validate source files
    console.print(
        Panel(
            "[bold]Validating source files...[/bold]",
            title="Source Validation",
            expand=True,
        )
    )
    console.print()

    all_files_valid = display_source_file_status(data_dir)
    console.print()

    # Initialize result tracking
    result = SetupResult()

    # Validate source files for result
    validate_source_files(data_dir, result)

    if not all_files_valid:
        console.print(
            Panel(
                "[yellow]Warning:[/yellow] Some source files are missing.\n"
                "The directory structure will still be created, but processing will require all source files.",
                title="Missing Files Warning",
                expand=True,
                border_style="yellow",
            )
        )
        console.print()

    # Create directories
    console.print(
        Panel(
            "[bold]Creating directory structure...[/bold]",
            title="Creating Directories",
            expand=True,
        )
    )
    console.print()

    try:
        create_directories(structure, result)
        create_questions_template(knowledge_base_path, result)
        create_index_template(knowledge_base_path, result)
    except Exception as e:
        result.success = False
        result.error_message = str(e)

    # Display final summary
    display_result_summary(result)

    # Return appropriate exit code
    if not result.success:
        return 1
    if result.source_files_missing:
        return 0  # Warning but not failure
    return 0


if __name__ == "__main__":
    sys.exit(main())
