---
name: telegram
description: Core sales agent system for Telegram. Use for running the sales daemon, fetching/sending messages, prospect outreach, and automated conversations. Queries like "run sales agent", "start telegram daemon", "show Telegram messages", "send message to prospect".
---

# Telegram Sales Agent Skill

The core sales agent system that handles prospect outreach and automated conversations via Telegram. This skill orchestrates communication with prospects, integrates with scheduling for Zoom meetings, and uses AI-powered responses following tone-of-voice guidelines.

## Running the Telegram Agent Daemon

The main entry point is the `daemon.py` script:

```bash
# Run daemon with default account (@BetterBohdan using user.session)
PYTHONPATH=.claude/skills/telegram/scripts:.claude/skills/scheduling/scripts:.claude/skills/database/scripts:.claude/skills/eleven-labs/scripts:.claude/skills/humanizer/scripts:.claude/skills/zoom/scripts:.claude/skills/register-sales/scripts uv run python .claude/skills/telegram/scripts/daemon.py

# Run daemon as a specific registered rep
PYTHONPATH=.claude/skills/telegram/scripts:.claude/skills/scheduling/scripts:.claude/skills/database/scripts:.claude/skills/eleven-labs/scripts:.claude/skills/humanizer/scripts:.claude/skills/zoom/scripts:.claude/skills/register-sales/scripts uv run python .claude/skills/telegram/scripts/daemon.py --rep-telegram-id <TELEGRAM_ID>

# Run daemon with verbose logging
PYTHONPATH=.claude/skills/telegram/scripts:.claude/skills/scheduling/scripts:.claude/skills/database/scripts:.claude/skills/eleven-labs/scripts:.claude/skills/humanizer/scripts:.claude/skills/zoom/scripts:.claude/skills/register-sales/scripts uv run python .claude/skills/telegram/scripts/daemon.py --verbose
```

## Architecture

The telegram skill is the core sales agent system that orchestrates:

- **Communication Skills**: Loads tone-of-voice and how-to-communicate skills for message generation
- **Scheduling**: Integrates with scheduling skill for follow-up management
- **Database**: Uses database skill for persistence
- **Media**: Uses eleven-labs skill for voice transcription
- **Humanization**: Uses humanizer skill for natural timing
- **Calendar**: Uses google-calendar skill via register-sales for availability
- **Meetings**: Uses zoom skill for booking calls

## Main Components

| Component | File | Purpose |
|-----------|------|---------|
| Daemon | `daemon.py` | Main entry point, event loop, message handling |
| Agent | `telegram_agent.py` | Claude AI agent with tool calling |
| Knowledge Loader | `knowledge_loader.py` | Loads tone-of-voice and how-to-communicate skills |
| Telegram Service | `telegram_service.py` | Telethon client wrapper with natural timing |
| Telegram Fetch | `telegram_fetch.py` | Message fetching utilities |
| Bot Send | `bot_send.py` | Bot API for sending messages |
| Prospect Manager | `prospect_manager.py` | Prospect state management (JSON) |
| Models | `models.py` | Pydantic models for all data structures |
| Message Buffer | `message_buffer.py` | Message batching and debounce |
| Pause Detector | `pause_detector.py` | Conversation gap detection |
| Timezone Detector | `timezone_detector.py` | Client timezone estimation |
| Phrase Tracker | `phrase_tracker.py` | Opening phrase variety |
| Fact Extractor | `fact_extractor.py` | BANT fact extraction |
| Context Summarizer | `context_summarizer.py` | Conversation summarization |
| Sales Calendar | `sales_calendar.py` | Calendar slot management |
| Scheduling Tool | `scheduling_tool.py` | Meeting booking interface |
| Scheduler Service | `scheduler_service.py` | APScheduler integration |
| Scheduled Action Manager | `scheduled_action_manager.py` | Database-backed action scheduling |

## Configuration

Config files are located at `.claude/skills/telegram/config/`:

- `prospects.json` - Prospect state and conversation history
- `agent_config.json` - Agent configuration (model, temperature, batching)
- `sales_slots.json` - Available meeting slots
- `sales_slots_data.json` - Meeting slot data

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` - Claude API key
- `DATABASE_URL` - PostgreSQL database URL
- `TELETHON_API_ID` / `TELETHON_API_HASH` - Telegram API credentials

Optional:
- `ELEVENLABS_API_KEY` - For voice message transcription
- `ZOOM_ACCOUNT_ID` / `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET` - For Zoom integration

## Integration with Other Skills

The telegram daemon loads content from:
- `tone-of-voice/` skill - Communication style guide
- `how-to-communicate/` skill - Methodology (BANT, Zmeyeka)
- `scheduling/` skill - Follow-up management
- `database/` skill - Persistence
- `eleven-labs/` skill - Voice transcription
- `humanizer/` skill - Natural timing
- `zoom/` skill - Meeting booking
- `register-sales/` skill - Calendar integration, multi-account support

## Testing

```bash
# Run conversation simulator
PYTHONPATH=.claude/skills/telegram/scripts uv run python .claude/skills/telegram/scripts/conversation_simulator.py

# Run conversation tests
PYTHONPATH=.claude/skills/telegram/scripts uv run python .claude/skills/telegram/scripts/run_conversation_tests.py
```

---

# Telegram Fetch Utility

Fetch, search, download, and send Telegram messages with flexible filtering and output options.

## Prerequisites

Authentication must be configured in `~/.telegram_dl/`. Run `setup` command to check status or get instructions:

```bash
python3 scripts/telegram_fetch.py setup
```

If not configured, follow these steps:
1. Get API credentials from https://my.telegram.org/auth
2. Clone telegram_dl: https://github.com/glebis/telegram_dl
3. Run `python telegram_dl.py` and follow interactive prompts
4. Verify with `python3 scripts/telegram_fetch.py setup`

## Quick Start

Run the script at `scripts/telegram_fetch.py` with appropriate commands:

```bash
# List available chats
python3 scripts/telegram_fetch.py list

# Get recent messages
python3 scripts/telegram_fetch.py recent --limit 20

# Search messages
python3 scripts/telegram_fetch.py search "meeting"

# Get unread messages
python3 scripts/telegram_fetch.py unread
```

## Commands

### List Chats

To see available Telegram chats:

```bash
python3 scripts/telegram_fetch.py list
python3 scripts/telegram_fetch.py list --limit 50
python3 scripts/telegram_fetch.py list --search "AI"
```

Returns JSON with chat IDs, names, types, and unread counts.

### Fetch Recent Messages

To get recent messages:

```bash
# From all chats (last 50 messages across top 10 chats)
python3 scripts/telegram_fetch.py recent

# From specific chat
python3 scripts/telegram_fetch.py recent --chat "Tool Building Ape"
python3 scripts/telegram_fetch.py recent --chat-id 123456789

# With limits
python3 scripts/telegram_fetch.py recent --limit 100
python3 scripts/telegram_fetch.py recent --days 7
```

### Search Messages

To search message content:

```bash
# Global search across all chats
python3 scripts/telegram_fetch.py search "project deadline"

# Search in specific chat
python3 scripts/telegram_fetch.py search "meeting" --chat-id 123456789

# Limit results
python3 scripts/telegram_fetch.py search "important" --limit 20
```

### Fetch Unread Messages

To get only unread messages:

```bash
python3 scripts/telegram_fetch.py unread
python3 scripts/telegram_fetch.py unread --chat-id 123456789
```

### Send Messages

To send a message to a chat:

```bash
# Send to existing chat by name
python3 scripts/telegram_fetch.py send --chat "John Doe" --text "Hello!"

# Send to username (works even without prior conversation)
python3 scripts/telegram_fetch.py send --chat "@username" --text "Hello!"

# Reply to a specific message (use message ID from recent/search output)
python3 scripts/telegram_fetch.py send --chat "Tool Building Ape" --text "Thanks!" --reply-to 12345

# Send to a forum topic (for groups with topics enabled)
python3 scripts/telegram_fetch.py send --chat "Group Name" --text "Hello topic!" --topic 12
```

### Send Files

To send images, documents, or videos:

```bash
# Send an image
python3 scripts/telegram_fetch.py send --chat "John Doe" --file "/path/to/image.jpg"

# Send document with caption
python3 scripts/telegram_fetch.py send --chat "@username" --file "report.pdf" --text "Here's the report"

# Reply with media
python3 scripts/telegram_fetch.py send --chat "Group" --file "screenshot.png" --reply-to 12345
```

**Chat resolution order:**
1. `@username` - Resolves Telegram username directly
2. Numeric ID - Resolves chat by Telegram ID
3. Name match - Fuzzy search in existing dialogs

Returns JSON with send status, resolved chat name, message ID, and file info (for media).

### Edit Messages

To edit an existing message:

```bash
# Edit a message by ID
python3 scripts/telegram_fetch.py edit --chat "@mentalhealthtech" --message-id 76 --text "Updated text"

# Edit in a group/channel
python3 scripts/telegram_fetch.py edit --chat "Mental health tech" --message-id 123 --text "Corrected content"
```

**Note:** You can only edit your own messages. Telegram formatting (**bold**, etc.) is preserved.

Returns JSON with edit status and message ID.

### Download Attachments

To download media files from a chat:

```bash
# Download last 5 attachments from a chat (default)
python3 scripts/telegram_fetch.py download --chat "Tool Building Ape"

# Download last 10 attachments
python3 scripts/telegram_fetch.py download --chat "Project Group" --limit 10

# Download to custom directory
python3 scripts/telegram_fetch.py download --chat "@username" --output "/path/to/folder"

# Download from specific message
python3 scripts/telegram_fetch.py download --chat "John Doe" --message-id 12345
```

**Default output:** `~/Downloads/telegram_attachments/`

Returns JSON with download results (file names, paths, sizes).

### Fetch Forum Thread Messages

To get messages from a specific forum thread (topics in groups):

```bash
# Fetch from thread 174 in Claude Code Lab
python3 scripts/telegram_fetch.py thread --chat-id -1003237581133 --thread-id 174

# Fetch with custom limit
python3 scripts/telegram_fetch.py thread --chat-id -1003237581133 --thread-id 174 --limit 50

# Save to file
python3 scripts/telegram_fetch.py thread --chat-id -1003237581133 --thread-id 174 -o ~/thread.md

# Append to daily note
python3 scripts/telegram_fetch.py thread --chat-id -1003237581133 --thread-id 174 --to-daily

# JSON output
python3 scripts/telegram_fetch.py thread --chat-id -1003237581133 --thread-id 174 --json
```

**Messages are sorted newest first** (reverse chronological order).

**How to find thread ID:**
- Forum topic IDs appear in the thread URL: `https://t.me/c/CHAT_ID/THREAD_ID`
- Use `recent` command on the chat to see message IDs in threads

Returns markdown or JSON with all messages from the specified thread.

## Output Options

### Default (Markdown to stdout)

By default, outputs formatted markdown suitable for Claude to read and summarize.

### JSON Format

Add `--json` flag for structured data:

```bash
python3 scripts/telegram_fetch.py recent --json
```

### Append to Obsidian Daily Note

Add messages to today's daily note in the vault:

```bash
python3 scripts/telegram_fetch.py recent --to-daily
python3 scripts/telegram_fetch.py search "project" --to-daily
```

Appends to `~/Brains/brain/Daily/YYYYMMDD.md`

### Append to Person's Note

Add messages to a specific person's note:

```bash
python3 scripts/telegram_fetch.py recent --chat "John Doe" --to-person "John Doe"
```

Creates or appends to `~/Brains/brain/{PersonName}.md`

### Save to File (Token-Efficient)

Save messages directly to file without consuming context tokens:

```bash
# Save 100 messages to markdown file
python3 scripts/telegram_fetch.py recent --chat "AGENCY: Community" --limit 100 -o ~/chat_archive.md

# Save with media files downloaded to same folder
python3 scripts/telegram_fetch.py recent --chat "Project Group" --limit 50 -o ~/project/archive.md --with-media

# Save search results to file
python3 scripts/telegram_fetch.py search "meeting" -o ~/meetings.md
```

Returns JSON with save status (file path, message count, media download results) - minimal token usage.

## Example User Requests

When user asks:

- "Show my recent Telegram messages" -> `recent --limit 20`
- "What Telegram messages did I get today?" -> `recent --days 1`
- "Search Telegram for messages about the project" -> `search "project"`
- "Get unread messages from Tool Building Ape" -> `unread` + filter output
- "Add my Telegram messages to daily note" -> `recent --to-daily`
- "What chats do I have on Telegram?" -> `list`
- "Send hello to John on Telegram" -> `send --chat "John" --text "Hello!"`
- "Message @username on Telegram" -> `send --chat "@username" --text "..."`
- "Reply to that message with thanks" -> `send --chat "..." --text "Thanks!" --reply-to <id>`
- "Send this image to John" -> `send --chat "John" --file "/path/to/image.jpg"`
- "Send report.pdf with caption" -> `send --chat "..." --file "report.pdf" --text "Here's the report"`
- "Send to topic 12 in Group" -> `send --chat "Group" --text "..." --topic 12`
- "Download attachments from Tool Building Ape" -> `download --chat "Tool Building Ape"`
- "Download last 10 files from Project Group" -> `download --chat "Project Group" --limit 10`
- "Save last 100 messages from AGENCY to file" -> `recent --chat "AGENCY: Community" --limit 100 -o ~/agency.md`
- "Archive chat with media" -> `recent --chat "Group" -o ~/archive.md --with-media`
- "Edit that message" -> `edit --chat "..." --message-id <id> --text "new text"`
- "Fix the typo in message 123" -> `edit --chat "..." --message-id 123 --text "corrected text"`
- "Is Telegram configured?" -> `setup`
- "How do I set up Telegram?" -> `setup` (returns instructions if not configured)

## Rate Limiting

The script includes built-in rate limiting (0.1s between messages) and handles Telegram's FloodWaitError automatically with backoff.

## Dependencies

Requires `telethon` Python package. Install with: `pip install telethon`
