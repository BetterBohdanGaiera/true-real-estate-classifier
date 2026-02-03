---
name: fetching-library-docs
description: Fetches up-to-date library and framework documentation as local markdown files. CLI replacement for Context7. Use when user says "use context7", "fetch docs for", "get documentation for", needs current API docs, or when working with a library that may have outdated training data. Supports 80+ libraries including React, Next.js, Pydantic, FastAPI, Tailwind, Anthropic SDK, and more.
---

# Purpose

Replace Context7 MCP server with a CLI-based tool. Fetches current, version-specific documentation for libraries and frameworks, saves as local markdown files that Claude can read directly.

## When to Use

- User explicitly says "use context7" or "fetch docs"
- Working with a library and you need current API/usage docs
- User asks about a library's latest features or API
- Code generation needs up-to-date documentation to avoid hallucinated APIs
- User specifies a library version that may differ from training data

## Instructions

### Prerequisites
- Project must use Astral UV (`uv`) for running Python scripts
- Script handles its own dependencies via PEP 723 inline metadata

### Workflow

1. **Identify the library** the user needs docs for. Determine if a specific topic or version is needed.

2. **Run the fetch script**:
   ```bash
   uv run --script .claude/skills/fetching-library-docs/scripts/fetch_docs.py <library> [topic] [--version VERSION] [--max-pages N] [--refresh]
   ```

   Examples:
   ```bash
   # Fetch general Pydantic docs
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py pydantic

   # Fetch React hooks documentation specifically
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py react hooks

   # Fetch specific version
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py nextjs --version 14

   # Force refresh cached docs
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py fastapi --refresh

   # Fetch more pages for comprehensive coverage
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py anthropic --max-pages 15

   # List all cached documentation
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py --list
   ```

3. **Read the fetched docs** from `ai_docs/<library>/` directory. The script saves markdown files there.

4. **Use the documentation** to provide accurate, up-to-date code examples and API usage.

### Supported Libraries

The script includes a registry of 80+ popular libraries with curated documentation URLs. Run with `--list` to see cached docs. If a library isn't in the registry, the script will attempt to discover its documentation automatically.

**Key ecosystems covered:**
- **Python**: pydantic, fastapi, django, flask, sqlalchemy, anthropic, openai, langchain, pytest, httpx, pandas, numpy, polars, pytorch, scikit-learn, streamlit, dspy
- **JavaScript/TypeScript**: react, nextjs, vue, svelte, angular, express, nestjs, tailwindcss, typescript, zod, prisma, drizzle, trpc, astro, hono, bun, deno, vite, playwright, tanstack-query, shadcn-ui
- **Rust**: tokio, axum, serde, actix-web
- **Go**: gin, echo
- **Infrastructure**: docker, kubernetes, terraform, cloudflare-workers, vercel, supabase, firebase
- **AI/ML**: huggingface-transformers, llama-index, crew-ai

### Caching

- Docs are cached in `ai_docs/<library>/` for 7 days
- Use `--refresh` flag to force re-fetch
- Cache includes metadata in `.meta.json`

### Adding New Libraries

Edit `registry.json` in the skill directory to add new libraries:
```json
{
  "my-library": {
    "name": "My Library",
    "url": "https://docs.my-library.com/",
    "aliases": ["mylib"],
    "pages": [
      {"path": "getting-started/", "title": "Getting Started"},
      {"path": "api/", "title": "API Reference"}
    ]
  }
}
```

## Examples

### Example 1: User needs current Pydantic v2 API

User request: "Create a Pydantic model with field validators"

You would:
1. Fetch Pydantic docs focused on validators:
   ```bash
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py pydantic validators
   ```
2. Read the fetched files from `ai_docs/pydantic/`
3. Use the current API to write accurate code with `@field_validator` (not the deprecated `@validator`)

### Example 2: User says "use context7" with Next.js

User request: "use context7 - help me set up Next.js App Router"

You would:
1. Fetch Next.js docs on routing:
   ```bash
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py nextjs routing --version 14
   ```
2. Read `ai_docs/nextjs/` files
3. Provide accurate App Router setup using current Next.js 14 patterns

### Example 3: Working with a less common library

User request: "Help me use Hono framework for an API"

You would:
1. Fetch Hono docs:
   ```bash
   uv run .claude/skills/fetching-library-docs/scripts/fetch_docs.py hono
   ```
2. Read the fetched documentation
3. Use current Hono API patterns for the implementation
