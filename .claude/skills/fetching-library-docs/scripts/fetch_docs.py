#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "beautifulsoup4", "markdownify", "rich"]
# ///
"""
Fetch up-to-date library documentation and save as clean Markdown files.

Replaces Context7 MCP server with a standalone CLI tool. Fetches documentation
from known URLs (via registry.json) or auto-discovers docs sites. Converts
HTML to clean Markdown, caches results with a 7-day TTL.

Usage:
    uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py pydantic
    uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py fastapi "dependency injection"
    uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py react hooks --max-pages 20
    uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py pydantic --refresh
    uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py --list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY_PATH: Path = Path(__file__).resolve().parent.parent / "registry.json"
CACHE_TTL_SECONDS: int = 7 * 24 * 60 * 60  # 7 days
HTTP_TIMEOUT: int = 20  # seconds
USER_AGENT: str = "Mozilla/5.0 (compatible; DocFetcher/1.0)"
MIN_CONTENT_LENGTH: int = 100  # skip pages with less content than this
JINA_READER_PREFIX: str = "https://r.jina.ai/"  # free JS-rendering service

# Patterns that indicate a JS-rendered page with no real content
JS_RENDERED_INDICATORS: list[str] = [
    "loading...",
    "please enable javascript",
    "you need to enable javascript",
    "noscript",
    "react-root",
    "__next",
]

# CSS selectors for elements to remove before extracting content
REMOVE_SELECTORS: list[str] = [
    "nav",
    "header",
    "footer",
    "aside",
    "sidebar",
    ".sidebar",
    ".nav",
    ".navigation",
    ".menu",
    ".toc",
    ".table-of-contents",
    ".header",
    ".footer",
    ".breadcrumb",
    ".breadcrumbs",
    ".pagination",
    ".pager",
    "#sidebar",
    "#nav",
    "#navigation",
    "#header",
    "#footer",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".edit-page",
    ".page-nav",
    ".prev-next",
    ".docsearch",
    ".search-bar",
    ".algolia",
    "script",
    "style",
    "noscript",
    "iframe",
]

# CSS selectors to find the main content area (tried in order)
CONTENT_SELECTORS: list[str] = [
    "main",
    "article",
    "#content",
    ".content",
    "#main-content",
    ".main-content",
    ".markdown-body",
    ".document",
    ".doc-content",
    ".documentation",
    ".rst-content",
    "[role='main']",
    ".prose",
    "#docs-content",
    ".page-content",
    "body",
]

# URL patterns to skip when extracting links
SKIP_LINK_PATTERNS: list[str] = [
    r"/blog",
    r"/changelog",
    r"/community",
    r"github\.com",
    r"twitter\.com",
    r"x\.com",
    r"discord\.gg",
    r"discord\.com",
    r"/search",
    r"/login",
    r"/signup",
    r"/sign-up",
    r"/sign-in",
    r"/register",
    r"\.pdf$",
    r"\.zip$",
    r"\.tar",
    r"\.gz$",
    r"\.exe$",
    r"\.dmg$",
    r"\.whl$",
    r"/releases",
    r"/discussions",
    r"/issues",
    r"/pull/",
    r"/edit/",
    r"/raw/",
    r"stackoverflow\.com",
    r"reddit\.com",
    r"youtube\.com",
    r"mailto:",
    r"javascript:",
]

# Common documentation URL patterns for auto-discovery
DISCOVERY_URL_TEMPLATES: list[str] = [
    "https://docs.{lib}.dev/",
    "https://{lib}.readthedocs.io/en/latest/",
    "https://{lib}.readthedocs.io/en/stable/",
    "https://www.{lib}.dev/docs/",
    "https://{lib}.dev/",
    "https://{lib}.org/docs/",
    "https://{lib}.js.org/",
    "https://docs.{lib}.com/",
]

console = Console()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def load_registry() -> dict[str, Any]:
    """Load the library registry from registry.json.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[yellow]Warning: could not load registry: {exc}[/yellow]")
        return {}


def resolve_library(
    name: str,
    registry: dict[str, Any],
    version: Optional[str] = None,
) -> tuple[str, str, Optional[list[dict[str, str]]]]:
    """Resolve a library name to (canonical_name, base_url, pages).

    Looks up the registry first (including aliases). Falls back to
    auto-discovery of documentation URLs.

    Returns:
        (canonical_name, base_url, optional_pages_list)

    Raises:
        SystemExit if the docs URL cannot be resolved.
    """
    # Normalise lookup key
    lookup = name.lower().strip()

    # Direct match
    if lookup in registry:
        entry = registry[lookup]
        base_url = _versioned_url(entry, version) or entry["url"]
        return entry.get("name", name), base_url, entry.get("pages")

    # Alias match
    for key, entry in registry.items():
        aliases: list[str] = entry.get("aliases", [])
        if lookup in [a.lower() for a in aliases]:
            base_url = _versioned_url(entry, version) or entry["url"]
            return entry.get("name", key), base_url, entry.get("pages")

    # Auto-discovery
    console.print(
        f"[yellow]Library '{name}' not in registry. Attempting auto-discovery...[/yellow]"
    )
    discovered_url = _discover_docs_url(lookup)
    if discovered_url:
        return name, discovered_url, None

    console.print(
        Panel(
            f"[red]Could not find documentation for '{name}'.[/red]\n\n"
            "Suggestions:\n"
            "  - Check the library name spelling\n"
            "  - Add the library to registry.json\n"
            "  - Pass a direct URL via the registry",
            width=console.width,
        )
    )
    sys.exit(1)


def _versioned_url(entry: dict[str, Any], version: Optional[str]) -> Optional[str]:
    """Build a versioned URL if a version was requested and the entry supports it."""
    if version and "versioned_url" in entry:
        return entry["versioned_url"].replace("{version}", version)
    return None


def _discover_docs_url(lib: str) -> Optional[str]:
    """Try common URL patterns to find a live documentation site."""
    client = httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        for template in DISCOVERY_URL_TEMPLATES:
            url = template.format(lib=lib)
            try:
                resp = client.get(url)
                if resp.status_code == 200 and len(resp.text) > 500:
                    console.print(f"[green]Discovered docs at: {url}[/green]")
                    return url
            except httpx.HTTPError:
                continue
    finally:
        client.close()

    return None


# ---------------------------------------------------------------------------
# HTTP fetching
# ---------------------------------------------------------------------------


def fetch_page(url: str, client: httpx.Client) -> Optional[str]:
    """Fetch a single page. Returns HTML string or None on failure."""
    try:
        resp = client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None
        return resp.text
    except httpx.HTTPStatusError as exc:
        console.print(
            f"[dim red]  HTTP {exc.response.status_code} for {url}[/dim red]"
        )
        return None
    except httpx.HTTPError as exc:
        console.print(f"[dim red]  Error fetching {url}: {exc}[/dim red]")
        return None


# ---------------------------------------------------------------------------
# HTML -> Markdown conversion
# ---------------------------------------------------------------------------


def html_to_markdown(html: str, source_url: str) -> str:
    """Convert an HTML page to clean Markdown.

    Strips navigation, sidebars, and other non-content elements. Finds the
    main content area and converts it with markdownify.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for selector in REMOVE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    # Find main content container
    content: Optional[Tag] = None
    for selector in CONTENT_SELECTORS:
        found = soup.select_one(selector)
        if found and len(found.get_text(strip=True)) > MIN_CONTENT_LENGTH:
            content = found
            break

    if content is None:
        # Last resort: use the full body
        content = soup.body or soup

    # Remove images before conversion (since strip and convert are mutually exclusive)
    for img in content.find_all("img"):
        img.decompose()

    # Convert to markdown using ATX-style headings
    markdown_text: str = md(
        str(content),
        heading_style="ATX",
    )

    # Clean up excessive blank lines (3+ newlines -> 2)
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text)
    # Strip leading/trailing whitespace
    markdown_text = markdown_text.strip()

    # Prepend source URL as an HTML comment
    header = f"<!-- Source: {source_url} -->\n\n"
    return header + markdown_text


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------


def extract_links(
    html: str,
    base_url: str,
    topic: Optional[str] = None,
) -> list[str]:
    """Extract same-domain documentation links from an HTML page.

    Filters out blog, changelog, external, and other non-doc links.
    Optionally filters by topic relevance.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    seen: set[str] = set()
    results: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"]

        # Skip fragment-only and query-only links
        if href.startswith("#") or href.startswith("?"):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Strip fragment and trailing query
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # Ensure trailing slash consistency for dedup
        if not clean_url.endswith("/") and "." not in parsed.path.split("/")[-1]:
            clean_url += "/"

        # Skip if already seen
        if clean_url in seen:
            continue
        seen.add(clean_url)

        # Must be same domain
        if parsed.netloc != base_domain:
            continue

        # Skip unwanted patterns
        if _should_skip_link(full_url):
            continue

        # Topic filtering
        if topic and not _link_matches_topic(anchor, full_url, topic):
            continue

        results.append(clean_url)

    return results


def _should_skip_link(url: str) -> bool:
    """Check whether a URL matches any of the skip patterns."""
    url_lower = url.lower()
    for pattern in SKIP_LINK_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False


def _link_matches_topic(anchor: Tag, url: str, topic: str) -> bool:
    """Check whether a link is relevant to the given topic."""
    topic_lower = topic.lower()
    topic_words = topic_lower.split()

    # Check link text
    link_text = anchor.get_text(strip=True).lower()
    if topic_lower in link_text:
        return True
    if any(word in link_text for word in topic_words):
        return True

    # Check URL path
    url_lower = url.lower()
    if topic_lower.replace(" ", "-") in url_lower:
        return True
    if topic_lower.replace(" ", "_") in url_lower:
        return True
    if any(word in url_lower for word in topic_words):
        return True

    return False


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def get_output_dir(library: str) -> Path:
    """Return the output directory for a library's docs (relative to CWD)."""
    return Path.cwd() / "ai_docs" / _sanitize_name(library)


def _sanitize_name(name: str) -> str:
    """Sanitize a library name for use as a directory name."""
    return re.sub(r"[^\w\-.]", "_", name.lower())


def load_cache_meta(output_dir: Path) -> Optional[dict[str, Any]]:
    """Load the cache metadata file if it exists."""
    meta_path = output_dir / ".meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def is_cache_fresh(meta: dict[str, Any]) -> bool:
    """Check whether cached docs are within the TTL window."""
    fetched_at = meta.get("fetched_at")
    if not fetched_at:
        return False
    try:
        fetched_ts = datetime.fromisoformat(fetched_at).timestamp()
    except (ValueError, TypeError):
        return False
    return (time.time() - fetched_ts) < CACHE_TTL_SECONDS


def save_cache_meta(
    output_dir: Path,
    library: str,
    base_url: str,
    version: Optional[str],
    topic: Optional[str],
    files: list[str],
) -> None:
    """Write cache metadata to .meta.json."""
    meta = {
        "library": library,
        "base_url": base_url,
        "version": version,
        "topic": topic,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    meta_path = output_dir / ".meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Core fetch workflow
# ---------------------------------------------------------------------------


def fetch_library_docs(
    library: str,
    topic: Optional[str] = None,
    version: Optional[str] = None,
    refresh: bool = False,
    max_pages: int = 10,
) -> list[Path]:
    """Fetch documentation for a library and save as Markdown files.

    Returns a list of paths to the saved Markdown files.
    """
    registry = load_registry()
    canonical_name, base_url, registry_pages = resolve_library(library, registry, version)

    output_dir = get_output_dir(canonical_name)

    # ---- Check cache (unless --refresh) ----
    if not refresh:
        meta = load_cache_meta(output_dir)
        if meta and is_cache_fresh(meta):
            cached_files = [output_dir / f for f in meta.get("files", []) if (output_dir / f).exists()]
            if cached_files:
                console.print(
                    Panel(
                        f"[green]Using cached docs for [bold]{canonical_name}[/bold] "
                        f"(fetched {meta.get('fetched_at', 'unknown')})[/green]\n\n"
                        f"Files: {len(cached_files)} | Directory: {output_dir}",
                        width=console.width,
                    )
                )
                return cached_files

    # ---- Prepare output directory ----
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold]Fetching docs for [cyan]{canonical_name}[/cyan][/bold]\n"
            f"URL: {base_url}"
            + (f"\nTopic: {topic}" if topic else "")
            + (f"\nVersion: {version}" if version else ""),
            width=console.width,
        )
    )

    client = httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )

    saved_files: list[Path] = []

    try:
        # ---- Fetch main page ----
        console.print("[bold]Fetching main page...[/bold]")
        main_html = fetch_page(base_url, client)
        if not main_html:
            console.print("[red]Failed to fetch main documentation page.[/red]")
            return []

        # Save main page
        main_md = html_to_markdown(main_html, base_url)
        if len(main_md) >= MIN_CONTENT_LENGTH:
            main_file = output_dir / "index.md"
            main_file.write_text(main_md, encoding="utf-8")
            saved_files.append(main_file)
            console.print(f"  [green]Saved:[/green] index.md ({len(main_md):,} chars)")

        # ---- Determine pages to fetch ----
        urls_to_fetch: list[str] = []

        if registry_pages:
            # Use registry-defined pages
            for page_entry in registry_pages:
                page_path = page_entry.get("path", "")
                page_url = urljoin(base_url, page_path)
                urls_to_fetch.append(page_url)
            console.print(
                f"[dim]Using {len(urls_to_fetch)} pages from registry[/dim]"
            )
        else:
            # Discover links from the main page
            discovered = extract_links(main_html, base_url, topic)
            urls_to_fetch = discovered
            console.print(
                f"[dim]Discovered {len(discovered)} links"
                + (f" (filtered by topic: '{topic}')" if topic else "")
                + "[/dim]"
            )

        # Cap to max_pages
        urls_to_fetch = urls_to_fetch[:max_pages]

        # ---- Fetch sub-pages ----
        for i, page_url in enumerate(urls_to_fetch, start=1):
            # Skip if it is the same as the main page
            if page_url.rstrip("/") == base_url.rstrip("/"):
                continue

            console.print(
                f"  [{i}/{len(urls_to_fetch)}] Fetching: {page_url}"
            )

            page_html = fetch_page(page_url, client)
            if not page_html:
                continue

            page_md = html_to_markdown(page_html, page_url)
            if len(page_md) < MIN_CONTENT_LENGTH:
                console.print(f"    [dim]Skipped (too little content: {len(page_md)} chars)[/dim]")
                continue

            # Derive filename from URL path
            filename = _url_to_filename(page_url, base_url)
            file_path = output_dir / filename
            # Ensure parent directories exist for nested paths
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(page_md, encoding="utf-8")
            saved_files.append(file_path)
            console.print(
                f"    [green]Saved:[/green] {filename} ({len(page_md):,} chars)"
            )

    finally:
        client.close()

    # ---- Save cache metadata ----
    if saved_files:
        relative_names = [str(f.relative_to(output_dir)) for f in saved_files]
        save_cache_meta(output_dir, canonical_name, base_url, version, topic, relative_names)

    return saved_files


def _url_to_filename(url: str, base_url: str) -> str:
    """Convert a URL to a safe markdown filename relative to the base URL."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Get the path relative to the base URL
    path = parsed.path
    base_path = base_parsed.path
    if path.startswith(base_path):
        path = path[len(base_path):]

    # Clean up the path
    path = path.strip("/")
    if not path:
        path = "page"

    # Replace path separators with double-dashes for flat structure
    path = re.sub(r"[/\\]+", "--", path)
    # Remove file extensions
    path = re.sub(r"\.\w+$", "", path)
    # Sanitize
    path = re.sub(r"[^\w\-.]", "_", path)
    # Limit length
    if len(path) > 120:
        path = path[:120]

    return f"{path}.md"


# ---------------------------------------------------------------------------
# --list command
# ---------------------------------------------------------------------------


def list_cached_docs() -> None:
    """List all cached documentation sets in ai_docs/."""
    ai_docs_dir = Path.cwd() / "ai_docs"
    if not ai_docs_dir.exists():
        console.print("[yellow]No cached documentation found (ai_docs/ does not exist).[/yellow]")
        return

    table = Table(title="Cached Documentation", width=console.width)
    table.add_column("Library", style="cyan bold")
    table.add_column("Files", justify="right", style="green")
    table.add_column("Fetched", style="yellow")
    table.add_column("Path", style="dim")

    found_any = False
    for subdir in sorted(ai_docs_dir.iterdir()):
        if not subdir.is_dir():
            continue

        meta = load_cache_meta(subdir)
        if meta:
            file_count = len(meta.get("files", []))
            fetched_at = meta.get("fetched_at", "unknown")
            # Format the date nicely
            try:
                dt = datetime.fromisoformat(fetched_at)
                fetched_display = dt.strftime("%Y-%m-%d %H:%M")
                # Indicate if cache is stale
                if not is_cache_fresh(meta):
                    fetched_display += " [red](stale)[/red]"
            except (ValueError, TypeError):
                fetched_display = fetched_at
            lib_name = meta.get("library", subdir.name)
        else:
            # Count .md files manually
            md_files = list(subdir.glob("*.md"))
            file_count = len(md_files)
            fetched_display = "[dim]unknown[/dim]"
            lib_name = subdir.name

        table.add_row(lib_name, str(file_count), fetched_display, str(subdir))
        found_any = True

    if found_any:
        console.print(table)
    else:
        console.print("[yellow]No cached documentation found.[/yellow]")


# ---------------------------------------------------------------------------
# Summary display
# ---------------------------------------------------------------------------


def show_summary(files: list[Path], output_dir: Path) -> None:
    """Display a summary table of fetched documentation files."""
    table = Table(title="Fetched Documentation", width=console.width)
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right", style="green")

    total_size = 0
    for fpath in files:
        size = fpath.stat().st_size
        total_size += size
        relative = str(fpath.relative_to(output_dir))
        table.add_row(relative, _format_size(size))

    console.print(table)
    console.print(
        Panel(
            f"[bold green]Successfully fetched {len(files)} file(s)[/bold green] "
            f"({_format_size(total_size)} total)\n"
            f"Output directory: {output_dir}",
            width=console.width,
        )
    )


def _format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Fetch library documentation and save as clean Markdown.",
        epilog=(
            "Examples:\n"
            "  %(prog)s pydantic\n"
            "  %(prog)s fastapi 'dependency injection'\n"
            "  %(prog)s react hooks --max-pages 20\n"
            "  %(prog)s pydantic -v 2.0 --refresh\n"
            "  %(prog)s --list\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "library",
        nargs="?",
        help="Library name to fetch documentation for",
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Topic to focus on within the library (filters links by relevance)",
    )
    parser.add_argument(
        "--version",
        "-v",
        default=None,
        help="Specific version of the library",
    )
    parser.add_argument(
        "--refresh",
        "-r",
        action="store_true",
        help="Force refresh cached documentation",
    )
    parser.add_argument(
        "--max-pages",
        "-m",
        type=int,
        default=10,
        help="Maximum number of sub-pages to fetch (default: 10)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all cached documentation",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # --list mode
    if args.list:
        list_cached_docs()
        return

    # library is required when not using --list
    if not args.library:
        parser.print_help()
        console.print("\n[red]Error: library name is required (unless using --list).[/red]")
        sys.exit(1)

    # Fetch docs
    files = fetch_library_docs(
        library=args.library,
        topic=args.topic,
        version=args.version,
        refresh=args.refresh,
        max_pages=args.max_pages,
    )

    if not files:
        console.print(
            Panel(
                "[red bold]No documentation could be fetched.[/red bold]\n\n"
                "Possible reasons:\n"
                "  - The library name may be misspelled\n"
                "  - The docs site may be down\n"
                "  - The URL pattern is not recognized\n\n"
                "Try adding the library to registry.json with the correct URL.",
                width=console.width,
            )
        )
        sys.exit(1)

    # Show summary
    output_dir = get_output_dir(args.library)
    show_summary(files, output_dir)


if __name__ == "__main__":
    main()
