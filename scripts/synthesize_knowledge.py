#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "rich", "pydantic"]
# ///
"""
Knowledge Synthesis Script

Synthesizes extracted transcripts, visual analyses, and PDF content into structured
knowledge articles. Combines all source materials per topic, creates cross-references,
and generates the knowledge base index.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize console with fixed width for full-width panels
console = Console(width=120)

# Base path for the project
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_BASE_PATH = PROJECT_ROOT / "knowledge_base"


class ArticleSources(BaseModel):
    """Source materials for an article."""

    transcripts: list[str] = Field(default_factory=list)
    analyses: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)


class SourceContent(BaseModel):
    """Content loaded from source files."""

    transcript_content: dict[str, str] = Field(default_factory=dict)
    analysis_content: dict[str, str] = Field(default_factory=dict)
    document_content: dict[str, str] = Field(default_factory=dict)
    screenshot_paths: list[Path] = Field(default_factory=list)


class Article(BaseModel):
    """Structured knowledge article."""

    filename: str
    title: str
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    detailed_content: str = ""
    visual_references: list[str] = Field(default_factory=list)
    related_articles: list[str] = Field(default_factory=list)
    source_materials: list[str] = Field(default_factory=list)


class ArticleConfig(BaseModel):
    """Configuration for a single article."""

    id: str
    filename: str
    title: str
    sources: ArticleSources
    related: list[str] = Field(default_factory=list)
    description: str = ""


class SynthesisConfig(BaseModel):
    """Configuration for the knowledge synthesis process."""

    # Article configurations
    articles: ClassVar[list[ArticleConfig]] = [
        ArticleConfig(
            id="01_bali_regions_overview",
            filename="01_bali_regions_overview.md",
            title="Bali Regions Overview",
            sources=ArticleSources(
                transcripts=["bali_regions_transcript.md"],
                analyses=[],
                documents=[],
                screenshots=[],
            ),
            related=[
                "02_company_overview",
                "03_estate_market_understanding",
                "06_leasehold_vs_freehold",
            ],
            description="Comprehensive guide to Bali's regions for real estate investment",
        ),
        ArticleConfig(
            id="02_company_overview",
            filename="02_company_overview.md",
            title="Company Overview",
            sources=ArticleSources(
                transcripts=["company_presentation_transcript.md"],
                analyses=["company_presentation_analysis.md"],
                documents=["companypresentationextra.md", "company_extra.md"],
                screenshots=["company_presentation"],
            ),
            related=[
                "01_bali_regions_overview",
                "03_estate_market_understanding",
                "05_financial_models_taxes",
            ],
            description="True Real Estate company structure, services, and offerings",
        ),
        ArticleConfig(
            id="03_estate_market_understanding",
            filename="03_estate_market_understanding.md",
            title="Estate Market Understanding",
            sources=ArticleSources(
                transcripts=["estate_market_site_transcript.md"],
                analyses=["estate_market_site_analysis.md"],
                documents=[],
                screenshots=["estate_market_site"],
            ),
            related=[
                "04_market_statistics",
                "02_company_overview",
                "01_bali_regions_overview",
            ],
            description="Understanding the Bali real estate market and how to navigate it",
        ),
        ArticleConfig(
            id="04_market_statistics",
            filename="04_market_statistics.md",
            title="Market Statistics",
            sources=ArticleSources(
                transcripts=["estate_market_statistics_transcript.md"],
                analyses=["estate_market_statistics_analysis.md"],
                documents=[],
                screenshots=["estate_market_statistics"],
            ),
            related=[
                "03_estate_market_understanding",
                "05_financial_models_taxes",
                "01_bali_regions_overview",
            ],
            description="Bali real estate market statistics, trends, and data analysis",
        ),
        ArticleConfig(
            id="05_financial_models_taxes",
            filename="05_financial_models_taxes.md",
            title="Financial Models & Taxes",
            sources=ArticleSources(
                transcripts=["financial_models_transcript.md"],
                analyses=["financial_models_analysis.md"],
                documents=[],
                screenshots=["financial_models"],
            ),
            related=[
                "06_leasehold_vs_freehold",
                "04_market_statistics",
                "02_company_overview",
            ],
            description="Financial modeling, ROI calculations, and tax considerations for Bali real estate",
        ),
        ArticleConfig(
            id="06_leasehold_vs_freehold",
            filename="06_leasehold_vs_freehold.md",
            title="Leasehold vs Freehold",
            sources=ArticleSources(
                transcripts=["leasehold_freehold_transcript.md"],
                analyses=[],
                documents=[],
                screenshots=[],
            ),
            related=[
                "05_financial_models_taxes",
                "01_bali_regions_overview",
                "03_estate_market_understanding",
            ],
            description="Understanding property ownership types in Bali - leasehold and freehold",
        ),
    ]


class SynthesisResult(BaseModel):
    """Result of the synthesis operation."""

    articles_created: list[str] = Field(default_factory=list)
    articles_skipped: list[str] = Field(default_factory=list)
    index_updated: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    success: bool = True


def read_source_files(sources: ArticleSources, base_path: Path) -> SourceContent:
    """Read all source files for an article."""
    content = SourceContent()

    # Read transcripts
    transcripts_dir = base_path / "transcripts"
    for transcript in sources.transcripts:
        transcript_path = transcripts_dir / transcript
        if transcript_path.exists():
            content.transcript_content[transcript] = transcript_path.read_text(encoding="utf-8")

    # Read analyses
    analyses_dir = base_path / "visual_analysis"
    for analysis in sources.analyses:
        analysis_path = analyses_dir / analysis
        if analysis_path.exists():
            content.analysis_content[analysis] = analysis_path.read_text(encoding="utf-8")

    # Read documents
    documents_dir = base_path / "documents"
    for document in sources.documents:
        document_path = documents_dir / document
        if document_path.exists():
            content.document_content[document] = document_path.read_text(encoding="utf-8")

    # Collect screenshot paths
    screenshots_dir = base_path / "screenshots"
    for screenshot_folder in sources.screenshots:
        folder_path = screenshots_dir / screenshot_folder
        if folder_path.exists() and folder_path.is_dir():
            content.screenshot_paths.extend(sorted(folder_path.glob("*.jpg")))
            content.screenshot_paths.extend(sorted(folder_path.glob("*.png")))

    return content


def extract_key_points_from_content(content: str) -> list[str]:
    """Extract key points from content by looking for bullet points and headers."""
    key_points: list[str] = []
    lines = content.split("\n")

    for line in lines:
        stripped = line.strip()
        # Look for bullet points
        if stripped.startswith(("- ", "* ", "  - ", "  * ")):
            point = stripped.lstrip("-* ").strip()
            if point and len(point) > 10 and len(key_points) < 15:
                key_points.append(point)
        # Look for numbered items
        elif stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            point = stripped.split(". ", 1)[-1].strip()
            if point and len(point) > 10 and len(key_points) < 15:
                key_points.append(point)

    return key_points


def synthesize_article(config: ArticleConfig, base_path: Path) -> Article:
    """Synthesize content from all sources into an article."""
    source_content = read_source_files(config.sources, base_path)

    article = Article(
        filename=config.filename,
        title=config.title,
    )

    # Build summary from available sources
    summary_parts: list[str] = []
    if config.description:
        summary_parts.append(config.description)

    # Aggregate all content for detailed section
    detailed_parts: list[str] = []
    source_materials: list[str] = []
    all_key_points: list[str] = []

    # Process transcripts
    for name, content in source_content.transcript_content.items():
        detailed_parts.append(f"### From Transcript: {name}\n\n{content}")
        source_materials.append(f"Transcript: {name}")
        all_key_points.extend(extract_key_points_from_content(content))

    # Process visual analyses
    for name, content in source_content.analysis_content.items():
        detailed_parts.append(f"### From Visual Analysis: {name}\n\n{content}")
        source_materials.append(f"Visual Analysis: {name}")
        all_key_points.extend(extract_key_points_from_content(content))

    # Process documents
    for name, content in source_content.document_content.items():
        detailed_parts.append(f"### From Document: {name}\n\n{content}")
        source_materials.append(f"Document: {name}")
        all_key_points.extend(extract_key_points_from_content(content))

    # Build visual references
    visual_refs: list[str] = []
    for screenshot_path in source_content.screenshot_paths[:10]:  # Limit to first 10
        rel_path = screenshot_path.relative_to(base_path)
        visual_refs.append(f"![{screenshot_path.stem}](../{rel_path})")

    # Build related articles list
    related_articles: list[str] = []
    for related_id in config.related:
        # Find the config for this related article
        for other_config in SynthesisConfig.articles:
            if other_config.id == related_id:
                related_articles.append(f"[{other_config.title}]({other_config.filename})")
                break

    # Deduplicate and limit key points
    seen_points: set[str] = set()
    unique_key_points: list[str] = []
    for point in all_key_points:
        point_lower = point.lower()
        if point_lower not in seen_points and len(unique_key_points) < 10:
            seen_points.add(point_lower)
            unique_key_points.append(point)

    # Assemble the article
    article.summary = " ".join(summary_parts) if summary_parts else f"This article covers {config.title.lower()}."
    article.key_points = unique_key_points if unique_key_points else [
        "Content synthesis in progress",
        "See source materials for detailed information",
    ]
    article.detailed_content = "\n\n---\n\n".join(detailed_parts) if detailed_parts else "*No source content available yet. Run extraction scripts first.*"
    article.visual_references = visual_refs
    article.related_articles = related_articles
    article.source_materials = source_materials if source_materials else ["*No sources processed yet*"]

    return article


def generate_article_markdown(article: Article) -> str:
    """Generate markdown for an article following the template."""
    lines: list[str] = []

    # Title
    lines.append(f"# {article.title}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(article.summary)
    lines.append("")

    # Key Points
    lines.append("## Key Points")
    lines.append("")
    for point in article.key_points:
        lines.append(f"- {point}")
    lines.append("")

    # Detailed Content
    lines.append("## Detailed Content")
    lines.append("")
    lines.append(article.detailed_content)
    lines.append("")

    # Visual References
    if article.visual_references:
        lines.append("## Visual References")
        lines.append("")
        for ref in article.visual_references:
            lines.append(ref)
            lines.append("")
        lines.append("")

    # Related Articles
    if article.related_articles:
        lines.append("## Related Articles")
        lines.append("")
        for related in article.related_articles:
            lines.append(f"- {related}")
        lines.append("")

    # Source Materials
    lines.append("## Source Materials")
    lines.append("")
    for source in article.source_materials:
        lines.append(f"- {source}")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    return "\n".join(lines)


def update_index(articles: list[Article], base_path: Path) -> None:
    """Update knowledge_base/index.md with all articles and current status."""
    index_path = base_path / "index.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Check which source files exist
    transcripts_dir = base_path / "transcripts"
    visual_dir = base_path / "visual_analysis"
    documents_dir = base_path / "documents"

    def check_file(directory: Path, filename: str) -> str:
        """Check if file exists and return status."""
        if (directory / filename).exists():
            return "[green]Processed[/green]"
        return "[yellow]Pending[/yellow]"

    # Build the index content
    content = f"""# Knowledge Base Index

This knowledge base contains extracted information from training videos and documents related to Bali real estate.

## Quick Navigation

### Knowledge Articles
"""

    # Add article links with processing status
    for config in SynthesisConfig.articles:
        article_path = base_path / "articles" / config.filename
        status = "Ready" if article_path.exists() else "Pending"
        content += f"- [{config.title}](articles/{config.filename}) - *{status}*\n"

    content += """
### Raw Materials

#### Transcripts
"""

    transcript_files = [
        ("bali_regions_transcript.md", "Bali Regions Transcript"),
        ("leasehold_freehold_transcript.md", "Leasehold Freehold Transcript"),
        ("company_presentation_transcript.md", "Company Presentation Transcript"),
        ("estate_market_site_transcript.md", "Estate Market Site Transcript"),
        ("estate_market_statistics_transcript.md", "Estate Market Statistics Transcript"),
        ("financial_models_transcript.md", "Financial Models Transcript"),
    ]

    for filename, title in transcript_files:
        exists = (transcripts_dir / filename).exists()
        status = "Ready" if exists else "Pending"
        content += f"- [{title}](transcripts/{filename}) - *{status}*\n"

    content += """
#### Visual Analysis
"""

    analysis_files = [
        ("company_presentation_analysis.md", "Company Presentation Analysis"),
        ("estate_market_site_analysis.md", "Estate Market Site Analysis"),
        ("estate_market_statistics_analysis.md", "Estate Market Statistics Analysis"),
        ("financial_models_analysis.md", "Financial Models Analysis"),
    ]

    for filename, title in analysis_files:
        exists = (visual_dir / filename).exists()
        status = "Ready" if exists else "Pending"
        content += f"- [{title}](visual_analysis/{filename}) - *{status}*\n"

    content += """
#### Documents
"""

    document_files = [
        ("companypresentationextra.md", "Company Presentation Extra (PDF)"),
        ("company_extra.md", "Company Extra"),
    ]

    for filename, title in document_files:
        exists = (documents_dir / filename).exists()
        status = "Ready" if exists else "Pending"
        content += f"- [{title}](documents/{filename}) - *{status}*\n"

    content += """
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
| CompanyPresentationExtra.pdf | PDF | 112KB | Processed |

---

## Article Cross-Reference Matrix

| Article | Related Topics |
|---------|---------------|
"""

    for config in SynthesisConfig.articles:
        related_titles: list[str] = []
        for related_id in config.related:
            for other in SynthesisConfig.articles:
                if other.id == related_id:
                    related_titles.append(other.title)
                    break
        content += f"| {config.title} | {', '.join(related_titles)} |\n"

    content += f"""
---

*Last updated: {timestamp}*
"""

    index_path.write_text(content, encoding="utf-8")


def display_article_status(base_path: Path) -> None:
    """Display the current status of all articles."""
    table = Table(title="Article Status", expand=True)
    table.add_column("Article", style="cyan", no_wrap=False)
    table.add_column("Sources Available", justify="center")
    table.add_column("Status", justify="center")

    for config in SynthesisConfig.articles:
        article_path = base_path / "articles" / config.filename
        source_content = read_source_files(config.sources, base_path)

        # Count available sources
        sources_available = (
            len(source_content.transcript_content)
            + len(source_content.analysis_content)
            + len(source_content.document_content)
        )
        total_sources = (
            len(config.sources.transcripts)
            + len(config.sources.analyses)
            + len(config.sources.documents)
        )

        if article_path.exists():
            status = "[green]Created[/green]"
        elif sources_available == 0:
            status = "[red]No Sources[/red]"
        else:
            status = "[yellow]Ready to Create[/yellow]"

        source_info = f"{sources_available}/{total_sources}"
        if source_content.screenshot_paths:
            source_info += f" (+{len(source_content.screenshot_paths)} screenshots)"

        table.add_row(config.title, source_info, status)

    console.print(table)


def main() -> int:
    """Main entry point for the synthesis script."""
    # Load environment variables
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Synthesize knowledge articles from extracted source materials"
    )
    parser.add_argument(
        "--article",
        type=str,
        help="Process specific article by ID (e.g., 02_company_overview)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing articles",
    )
    args = parser.parse_args()

    # Display header
    console.print(
        Panel(
            "[bold]Knowledge Synthesis[/bold]\n\n"
            "Synthesizing extracted transcripts, visual analyses, and documents\n"
            "into structured knowledge articles.",
            title="Knowledge Base Synthesis Pipeline",
            expand=True,
        )
    )
    console.print()

    # Initialize result tracking
    result = SynthesisResult()

    # Display current status
    console.print(
        Panel(
            "[bold]Analyzing available source materials...[/bold]",
            title="Source Analysis",
            expand=True,
        )
    )
    console.print()

    display_article_status(KNOWLEDGE_BASE_PATH)
    console.print()

    if args.dry_run:
        console.print(
            Panel(
                "[yellow]Dry run mode - no files will be written[/yellow]",
                title="Dry Run",
                expand=True,
            )
        )
        console.print()
        return 0

    # Determine which articles to process
    articles_to_process: list[ArticleConfig] = []
    if args.article:
        for config in SynthesisConfig.articles:
            if config.id == args.article:
                articles_to_process.append(config)
                break
        if not articles_to_process:
            console.print(
                Panel(
                    f"[red]Article not found: {args.article}[/red]\n\n"
                    "Available articles:\n"
                    + "\n".join(f"  - {c.id}" for c in SynthesisConfig.articles),
                    title="Error",
                    expand=True,
                    border_style="red",
                )
            )
            return 1
    else:
        articles_to_process = SynthesisConfig.articles

    # Create articles directory if it doesn't exist
    articles_dir = KNOWLEDGE_BASE_PATH / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    # Process articles
    console.print(
        Panel(
            f"[bold]Processing {len(articles_to_process)} articles...[/bold]",
            title="Synthesis",
            expand=True,
        )
    )
    console.print()

    created_articles: list[Article] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        for config in articles_to_process:
            task = progress.add_task(f"Processing {config.title}...", total=None)

            article_path = articles_dir / config.filename

            # Check if article already exists
            if article_path.exists() and not args.force:
                result.articles_skipped.append(config.filename)
                progress.update(task, description=f"[dim]Skipped {config.title} (exists)[/dim]")
                progress.remove_task(task)
                continue

            # Check if we have any sources
            source_content = read_source_files(config.sources, KNOWLEDGE_BASE_PATH)
            has_sources = (
                bool(source_content.transcript_content)
                or bool(source_content.analysis_content)
                or bool(source_content.document_content)
            )

            if not has_sources:
                result.warnings.append(f"{config.title}: No source materials available")
                progress.update(task, description=f"[yellow]No sources for {config.title}[/yellow]")

            # Synthesize the article
            try:
                article = synthesize_article(config, KNOWLEDGE_BASE_PATH)
                markdown_content = generate_article_markdown(article)

                # Write the article
                article_path.write_text(markdown_content, encoding="utf-8")
                result.articles_created.append(config.filename)
                created_articles.append(article)

                progress.update(task, description=f"[green]Created {config.title}[/green]")
            except Exception as e:
                result.errors.append(f"{config.title}: {str(e)}")
                result.success = False
                progress.update(task, description=f"[red]Failed {config.title}[/red]")

            progress.remove_task(task)

    console.print()

    # Update index
    console.print(
        Panel(
            "[bold]Updating knowledge base index...[/bold]",
            title="Index Update",
            expand=True,
        )
    )

    try:
        update_index(created_articles, KNOWLEDGE_BASE_PATH)
        result.index_updated = True
        console.print(
            Panel(
                "[green]Index updated successfully[/green]",
                expand=True,
            )
        )
    except Exception as e:
        result.errors.append(f"Index update failed: {str(e)}")
        result.success = False
        console.print(
            Panel(
                f"[red]Index update failed: {str(e)}[/red]",
                expand=True,
                border_style="red",
            )
        )

    console.print()

    # Display summary
    summary_parts: list[str] = []

    if result.articles_created:
        summary_parts.append(f"[green]Created {len(result.articles_created)} articles:[/green]")
        for article in result.articles_created:
            summary_parts.append(f"  - {article}")

    if result.articles_skipped:
        summary_parts.append(f"\n[dim]Skipped {len(result.articles_skipped)} existing articles[/dim]")

    if result.warnings:
        summary_parts.append(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
        for warning in result.warnings:
            summary_parts.append(f"  - {warning}")

    if result.errors:
        summary_parts.append(f"\n[red]Errors ({len(result.errors)}):[/red]")
        for error in result.errors:
            summary_parts.append(f"  - {error}")

    if result.index_updated:
        summary_parts.append("\n[green]Index updated[/green]")

    summary = "\n".join(summary_parts) if summary_parts else "No changes made"

    border_style = "green" if result.success else "red"
    title = "Synthesis Complete" if result.success else "Synthesis Complete with Errors"

    console.print(
        Panel(
            summary,
            title=title,
            expand=True,
            border_style=border_style,
        )
    )

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
