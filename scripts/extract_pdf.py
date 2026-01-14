# /// script
# requires-python = ">=3.10"
# dependencies = ["pdfplumber", "python-dotenv", "rich", "pydantic"]
# ///
"""
PDF Text and Table Extraction Script

Extracts text and tables from PDF documents and saves them as structured markdown files.
Uses pdfplumber for accurate text and table extraction with layout preservation.
"""

import argparse
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment variables
load_dotenv()

console = Console(width=120)


class ExtractedTable(BaseModel):
    """Represents a table extracted from a PDF page."""

    page_number: int
    table_index: int
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ExtractedPage(BaseModel):
    """Represents extracted content from a single PDF page."""

    page_number: int
    text: str = ""
    tables: list[ExtractedTable] = Field(default_factory=list)


class ExtractedDocument(BaseModel):
    """Represents the complete extracted PDF document."""

    source_file: str
    total_pages: int
    pages: list[ExtractedPage] = Field(default_factory=list)


def sanitize_cell(cell: str | None) -> str:
    """Sanitize a table cell value for markdown output."""
    if cell is None:
        return ""
    # Replace newlines and pipes that would break markdown tables
    return str(cell).replace("\n", " ").replace("|", "\\|").strip()


def format_table_as_markdown(table: ExtractedTable) -> str:
    """Convert an extracted table to markdown format."""
    if not table.headers and not table.rows:
        return ""

    lines: list[str] = []

    # Use headers if available, otherwise use first row as headers
    if table.headers:
        headers = table.headers
        data_rows = table.rows
    elif table.rows:
        headers = table.rows[0]
        data_rows = table.rows[1:]
    else:
        return ""

    # Sanitize headers
    sanitized_headers = [sanitize_cell(h) for h in headers]

    # Create header row
    header_line = "| " + " | ".join(sanitized_headers) + " |"
    lines.append(header_line)

    # Create separator row
    separator = "| " + " | ".join(["---"] * len(sanitized_headers)) + " |"
    lines.append(separator)

    # Create data rows
    for row in data_rows:
        # Ensure row has same number of columns as headers
        sanitized_row = [sanitize_cell(cell) for cell in row]
        while len(sanitized_row) < len(sanitized_headers):
            sanitized_row.append("")
        sanitized_row = sanitized_row[: len(sanitized_headers)]  # Trim excess columns

        row_line = "| " + " | ".join(sanitized_row) + " |"
        lines.append(row_line)

    return "\n".join(lines)


def extract_page_content(page: pdfplumber.page.Page, page_number: int) -> ExtractedPage:
    """Extract text and tables from a single PDF page."""
    extracted_page = ExtractedPage(page_number=page_number)

    # Extract text
    text = page.extract_text()
    if text:
        extracted_page.text = text.strip()

    # Extract tables
    tables = page.extract_tables()
    for idx, table_data in enumerate(tables):
        if table_data and len(table_data) > 0:
            extracted_table = ExtractedTable(
                page_number=page_number,
                table_index=idx + 1,
            )

            # First row as headers, rest as data
            if len(table_data) > 0:
                extracted_table.headers = [str(cell) if cell else "" for cell in table_data[0]]
            if len(table_data) > 1:
                extracted_table.rows = [
                    [str(cell) if cell else "" for cell in row] for row in table_data[1:]
                ]

            extracted_page.tables.append(extracted_table)

    return extracted_page


def extract_pdf(pdf_path: Path) -> ExtractedDocument:
    """Extract all content from a PDF file."""
    document = ExtractedDocument(
        source_file=str(pdf_path),
        total_pages=0,
    )

    with pdfplumber.open(pdf_path) as pdf:
        document.total_pages = len(pdf.pages)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Extracting {document.total_pages} pages...[/cyan]",
                total=document.total_pages,
            )

            for page_num, page in enumerate(pdf.pages, start=1):
                extracted_page = extract_page_content(page, page_num)
                document.pages.append(extracted_page)
                progress.update(task, advance=1)

    return document


def format_document_as_markdown(document: ExtractedDocument) -> str:
    """Convert extracted document to markdown format."""
    lines: list[str] = []

    # Document title from filename
    source_path = Path(document.source_file)
    title = source_path.stem.replace("_", " ").replace("-", " ").title()
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> Extracted from: `{source_path.name}`")
    lines.append(f"> Total pages: {document.total_pages}")
    lines.append("")

    # Process each page
    for page in document.pages:
        lines.append(f"## Page {page.page_number}")
        lines.append("")

        # Add text content
        if page.text:
            lines.append(page.text)
            lines.append("")

        # Add tables
        for table in page.tables:
            lines.append(f"### Table {table.table_index}")
            lines.append("")
            markdown_table = format_table_as_markdown(table)
            if markdown_table:
                lines.append(markdown_table)
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_default_output_path(input_path: Path) -> Path:
    """Generate default output path based on input filename."""
    # Convert filename to snake_case
    stem = input_path.stem.lower()
    # Replace spaces and hyphens with underscores
    stem = stem.replace(" ", "_").replace("-", "_")
    # Remove consecutive underscores
    while "__" in stem:
        stem = stem.replace("__", "_")

    output_dir = Path(__file__).parent.parent / "knowledge_base" / "documents"
    return output_dir / f"{stem}.md"


def main() -> None:
    """Main entry point for PDF extraction."""
    parser = argparse.ArgumentParser(
        description="Extract text and tables from PDF documents to markdown format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run scripts/extract_pdf.py data/CompanyPresentationExtra.pdf
  uv run scripts/extract_pdf.py data/document.pdf --output output.md
  uv run scripts/extract_pdf.py data/document.pdf -o knowledge_base/docs/custom.md
        """,
    )
    parser.add_argument(
        "pdf_file",
        type=Path,
        help="Path to the PDF file to extract",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output markdown file path (default: knowledge_base/documents/<filename>.md)",
    )

    args = parser.parse_args()

    # Validate input file
    pdf_path = Path(args.pdf_file)
    if not pdf_path.exists():
        console.print(
            Panel(
                f"[red]Error:[/red] PDF file not found: {pdf_path}",
                title="File Error",
                expand=True,
            )
        )
        sys.exit(1)

    if not pdf_path.suffix.lower() == ".pdf":
        console.print(
            Panel(
                f"[red]Error:[/red] File does not appear to be a PDF: {pdf_path}",
                title="File Error",
                expand=True,
            )
        )
        sys.exit(1)

    # Determine output path
    output_path = args.output if args.output else generate_default_output_path(pdf_path)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold cyan]Input:[/bold cyan] {pdf_path}\n"
            f"[bold cyan]Output:[/bold cyan] {output_path}",
            title="PDF Extraction",
            expand=True,
        )
    )

    try:
        # Extract content from PDF
        document = extract_pdf(pdf_path)

        # Format as markdown
        markdown_content = format_document_as_markdown(document)

        # Write output file
        output_path.write_text(markdown_content, encoding="utf-8")

        # Calculate statistics
        total_tables = sum(len(page.tables) for page in document.pages)
        pages_with_text = sum(1 for page in document.pages if page.text)
        pages_with_tables = sum(1 for page in document.pages if page.tables)

        console.print(
            Panel(
                f"[green]Successfully extracted PDF content![/green]\n\n"
                f"[bold]Statistics:[/bold]\n"
                f"  - Total pages: {document.total_pages}\n"
                f"  - Pages with text: {pages_with_text}\n"
                f"  - Pages with tables: {pages_with_tables}\n"
                f"  - Total tables extracted: {total_tables}\n\n"
                f"[bold]Output saved to:[/bold] {output_path}",
                title="Extraction Complete",
                expand=True,
            )
        )

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
        console.print(
            Panel(
                f"[red]Error:[/red] Invalid or corrupted PDF file\n\n"
                f"Details: {e}",
                title="PDF Parse Error",
                expand=True,
            )
        )
        sys.exit(1)
    except PermissionError as e:
        console.print(
            Panel(
                f"[red]Error:[/red] Permission denied\n\n"
                f"Details: {e}",
                title="Permission Error",
                expand=True,
            )
        )
        sys.exit(1)
    except Exception as e:
        console.print(
            Panel(
                f"[red]Error:[/red] Failed to extract PDF\n\n"
                f"Exception type: {type(e).__name__}\n"
                f"Details: {e}",
                title="Extraction Error",
                expand=True,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
