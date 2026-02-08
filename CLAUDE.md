# Engineering Rules for Claude Code Template

## Do Not Mock Tests

- Use real database connections
- Use real Claude Agent SDK agents
- IMPORTANT: The trick with database connection is to make sure your tests are ephemeral, it should start and end the database in the exact same state. Create the test data you need for the test, then clean it up after the test.

## Use .env File When Needed and Expose with python-dotenv

- Use python-dotenv to load environment variables from .env file
- See .env.example for all available configuration options

## IMPORTANT: Actually Read the File

- IMPORTANT: When asked to read a file, read all of it - don't just read the first N lines.
- Read the file in chunks. If that's too large, cut in half and try again, then iterate to the next chunk.
- This is VERY IMPORTANT for understanding the codebase.
- Even if the file is large, read all of it in chunks.
- IMPORTANT: Use `wc -l <filename>` to get line counts if needed. So you can properly divide your Read tool in the right chunks.

## Use Astral UV, Never Raw Python

- We're using Astral UV to manage our python projects.
- Always use uv to run commands, never raw python.

## Python Rich Panels

- Always full width panels with rich.

## Git Commits

- IMPORTANT: Do NOT commit any changes to the git repository unless you are explicitly asked to do so.

## Avoid Dict and Prefer Pydantic Models

- Prefer pydantic models over dicts.
- Use Pydantic models for data validation and serialization.

## Manual Testing - Telegram Accounts

- **Sales Agent Account:** @BetterBohdan - runs the sales agent, sends outreach messages
- **Test Prospect Account:** @bohdanpytaichuk (Telegram ID: 7836623698) - the ONLY test prospect, receives messages from the agent
- Only use ONE test prospect (@bohdanpytaichuk) for testing - do not create multiple test prospects

### Testing Initial Outreach (Telegram Agent)
The main agent reads from `.claude/skills/telegram/config/prospects.json`. To test initial messages:
1. Set @bohdanpytaichuk status to `"new"` in prospects.json
2. Run: `PYTHONPATH=src uv run python -m telegram_sales_bot.core.daemon`
3. @bohdanpytaichuk receives the initial sales message from @BetterBohdan

### Testing Assignment Notifications (Outreach Daemon)
The outreach daemon uses `test_prospects` database table and notifies sales reps about new assignments.

## Package Structure

This project uses a proper Python package structure located at `src/telegram_sales_bot/`:

- **core/** - Main daemon, agent, service, and models
- **prospects/** - Prospect management
- **scheduling/** - Follow-ups, calendar integration, scheduled actions
- **integrations/** - Zoom, Google Calendar, ElevenLabs
- **temporal/** - Message buffering, pause detection, timezone handling
- **humanizer/** - Natural timing and typo injection
- **knowledge/** - Knowledge base loader and content (base/, tone/, methodology/)
- **registry/** - Sales rep registration subsystem
- **database/** - Database initialization and migrations
- **cli/** - Command-line utilities (auth, setup, fetch)
- **config/** - Configuration files (agent_config.json, sales_slots.json)

### Running the Bot

```bash
# Run main sales daemon
PYTHONPATH=src uv run python -m telegram_sales_bot.core.daemon

# Run scheduler daemon (polling-based)
PYTHONPATH=src uv run python -m telegram_sales_bot.scheduling.polling_daemon

# Run registry bot
PYTHONPATH=src uv run python -m telegram_sales_bot.registry.runner

# Run outreach daemon
PYTHONPATH=src uv run python -m telegram_sales_bot.registry.outreach

# Initialize database
PYTHONPATH=src uv run python -m telegram_sales_bot.database.init
```
