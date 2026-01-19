---
name: google-calendar
description: Google Calendar event query/create/update/delete. Use for requests like "today's schedule", "this week's events", "add a meeting". Supports unified view across multiple accounts (work, personal).
---

# Google Calendar Sync

## Overview

Query calendars from multiple Google accounts (work, personal, etc.) at once and provide a unified schedule view.
- Uses pre-authenticated refresh tokens (no login required each time)
- Fast retrieval via parallel subagent execution
- Detects scheduling conflicts across accounts

## Trigger Conditions

### Query
- "today's schedule", "show me this week's events"
- "check calendar", "what's my schedule"
- "next meeting", "what do I have tomorrow"
- "check for scheduling conflicts"

### Create
- "create a new event", "add a meeting"
- "schedule a meeting tomorrow at 3pm"
- "create a team meeting next Monday"

### Update
- "change the event time", "reschedule the meeting"
- "move sync meeting to 2:21pm"
- "update the meeting title"

### Delete
- "delete the event", "cancel the meeting"
- "remove the event"

## Prerequisites

### 1. Google Cloud Project Setup

1. Create a project at [Google Cloud Console](https://console.cloud.google.com)
2. Enable Calendar API
3. Create OAuth 2.0 Client ID (Desktop type)
4. Download `credentials.json` → save to `references/credentials.json`

### 2. Account Authentication (one-time setup)

```bash
# Work account
uv run python .claude/skills/google-calendar/scripts/setup_auth.py --account work

# Personal account
uv run python .claude/skills/google-calendar/scripts/setup_auth.py --account personal
```

Browser opens for Google login → refresh token saved to `accounts/{name}.json`

## Workflow

### 1. Check Registered Accounts

```bash
ls .claude/skills/google-calendar/accounts/
# → work.json, personal.json
```

### 2. Parallel Subagent Execution

Call Task tool **in parallel** for each account:

```python
# Parallel execution - multiple Task calls in single message
Task(subagent_type="general-purpose", prompt="fetch calendar for work account")
Task(subagent_type="general-purpose", prompt="fetch calendar for personal account")
```

Each subagent executes:
```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --account {account_name} \
  --days 7
```

### 3. Result Integration

- Sort all account events by time
- Mark same-time events as conflicts
- Distinguish accounts by color/icon

## Output Format

```
📅 2026-01-06 (Mon) Schedule

[09:00-10:00] 🔵 Team Standup (work)
[10:00-11:30] 🟢 Dentist Appointment (personal)
[14:00-15:00] 🔵 Customer Meeting - Samyang (work)
              ⚠️ Conflict: Overlaps with personal event
[14:00-14:30] 🟢 Bank Visit (personal)

📊 Today: 4 total events (work: 2, personal: 2)
   ⚠️ 1 conflict
```

## Execution Example

User: "Show me this week's schedule"

```
1. Check accounts/ folder
   └── Registered accounts: work, personal

2. Parallel Subagent Execution
   ├── Task: Fetch work account events
   └── Task: Fetch personal account events

3. Collect Results (wait for each subagent)
   ├── work: 8 events
   └── personal: 3 events

4. Integrate and Sort
   └── 11 events, 2 conflicts detected

5. Output
   └── Display grouped by day
```

## Error Handling

| Situation | Action |
|-----------|--------|
| accounts/ folder empty | Show initial setup guide (how to run setup_auth.py) |
| Specific account token expired | Prompt re-authentication for that account, continue with other accounts |
| API quota exceeded | Advise retry later |
| Network error | Request connection check |

## Scripts

| File | Purpose |
|------|---------|
| `scripts/setup_auth.py` | Per-account OAuth authentication and token storage |
| `scripts/fetch_events.py` | Fetch events for specific account (CLI) |
| `scripts/manage_events.py` | Create/update/delete events (CLI) |
| `scripts/calendar_client.py` | Google Calendar API client library |

## Event Management (Create/Update/Delete)

### Create Event

```bash
uv run python .claude/skills/google-calendar/scripts/manage_events.py create \
    --summary "Team Meeting" \
    --start "2026-01-06T14:00:00" \
    --end "2026-01-06T15:00:00" \
    --account work
```

### Create All-Day Event

```bash
uv run python .claude/skills/google-calendar/scripts/manage_events.py create \
    --summary "Day Off" \
    --start "2026-01-10" \
    --end "2026-01-11" \
    --account personal
```

### Update Event

```bash
uv run python .claude/skills/google-calendar/scripts/manage_events.py update \
    --event-id "abc123" \
    --summary "Team Meeting (Updated)" \
    --start "2026-01-06T14:21:00" \
    --account work
```

### Delete Event

```bash
uv run python .claude/skills/google-calendar/scripts/manage_events.py delete \
    --event-id "abc123" \
    --account work
```

### Options

| Option | Description |
|--------|-------------|
| `--summary` | Event title |
| `--start` | Start time (ISO format: 2026-01-06T14:00:00 or 2026-01-06) |
| `--end` | End time |
| `--description` | Event description |
| `--location` | Location |
| `--attendees` | Attendee emails (comma-separated) |
| `--account` | Account (work, personal, etc.) |
| `--adc` | Use gcloud ADC |
| `--timezone` | Timezone (default: Asia/Seoul) |
| `--json` | JSON format output |

## References

| Document | Content |
|----------|---------|
| `references/setup.md` | Detailed setup guide |
| `references/credentials.json` | Google OAuth Client ID (gitignore) |

## File Structure

```
.claude/skills/google-calendar/
├── SKILL.md                    # This file
├── scripts/
│   ├── calendar_client.py      # API client
│   ├── setup_auth.py           # Authentication setup
│   ├── fetch_events.py         # Event fetch CLI
│   └── manage_events.py        # Event create/update/delete CLI
├── references/
│   ├── setup.md                # Setup guide
│   └── credentials.json        # OAuth Client ID (gitignore)
└── accounts/                   # Per-account tokens (gitignore)
    ├── work.json
    └── personal.json
```

## Security Notes

- `accounts/*.json`: Contains refresh tokens, never commit
- `references/credentials.json`: Contains Client Secret, do not commit
- Must be added to `.gitignore`
