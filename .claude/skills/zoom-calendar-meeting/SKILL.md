---
name: zoom-calendar-meeting
description: Creates Zoom meetings and adds them to Google Calendar with embedded join links. Use when user wants to schedule a Zoom call, create a video meeting on calendar, or set up a Zoom meeting for a specific time.
---

# Zoom + Google Calendar Meeting

Creates a Zoom meeting and automatically adds it to Google Calendar with the join link embedded.

## Prerequisites

### 1. Zoom Setup
Ensure Zoom credentials are configured. Check status:
```bash
uv run python .claude/skills/zoom/scripts/zoom_meetings.py setup
```

See [zoom skill](../zoom/SKILL.md) for full setup instructions.

### 2. Google Calendar Setup
Ensure Google Calendar has **full access** (not readonly). Check:
```bash
uv run python .claude/skills/google-calendar/scripts/setup_auth.py --list
```

**Important:** The calendar scope must be `https://www.googleapis.com/auth/calendar` (not `calendar.readonly`).

If you get "insufficient permissions" errors when creating events, re-authenticate:
```bash
echo "y" | uv run python .claude/skills/google-calendar/scripts/setup_auth.py --account personal
```

## Workflow

### Step 1: Check Calendar Availability

Query the target calendar to find available slots:

```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
    --account {account} \
    --days 2 \
    --pretty
```

### Step 2: Create Zoom Meeting

Create the meeting with topic, start time, and duration:

```bash
uv run python .claude/skills/zoom/scripts/zoom_meetings.py create "{topic}" \
    --start "{YYYY-MM-DDTHH:MM:SS}" \
    --duration {minutes}
```

**Output contains:**
- Meeting ID
- Join URL (e.g., `https://us05web.zoom.us/j/...`)
- Password

### Step 3: Create Calendar Event with Zoom Link

Add the meeting to Google Calendar with Zoom details embedded:

```bash
uv run python .claude/skills/google-calendar/scripts/manage_events.py create \
    --summary "{topic}" \
    --start "{YYYY-MM-DDTHH:MM:SS}" \
    --end "{YYYY-MM-DDTHH:MM:SS}" \
    --description "Join Zoom: {ZOOM_JOIN_URL}

Password: {ZOOM_PASSWORD}" \
    --location "Zoom" \
    --account {account}
```

### Step 4: Verify

Confirm the event was created:

```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
    --account {account} \
    --days 2 \
    --pretty
```

## Examples

### Example 1: Create a 1-hour Meeting Tomorrow at 7:30 PM

User request:
```
Create a Zoom meeting called "AI discussion" for 1 hour tomorrow at 19:30 on my personal calendar
```

You would:

1. Check availability:
   ```bash
   uv run python .claude/skills/google-calendar/scripts/fetch_events.py --account personal --days 2 --pretty
   ```

2. Create Zoom meeting:
   ```bash
   uv run python .claude/skills/zoom/scripts/zoom_meetings.py create "AI discussion" \
       --start "2026-01-20T19:30:00" \
       --duration 60
   ```

3. Extract from output:
   - Join URL: `https://us05web.zoom.us/j/87179744482?pwd=...`
   - Password: `66uZmp`

4. Create calendar event:
   ```bash
   uv run python .claude/skills/google-calendar/scripts/manage_events.py create \
       --summary "AI discussion" \
       --start "2026-01-20T19:30:00" \
       --end "2026-01-20T20:30:00" \
       --description "Join Zoom: https://us05web.zoom.us/j/87179744482?pwd=...

   Password: 66uZmp" \
       --location "Zoom" \
       --account personal
   ```

5. Verify:
   ```bash
   uv run python .claude/skills/google-calendar/scripts/fetch_events.py --account personal --days 2 --pretty
   ```

### Example 2: Create a 30-minute Work Meeting

User request:
```
Schedule a 30 min Zoom for "Sprint Planning" next Monday at 10am on work calendar
```

You would:

1. Check work calendar availability
2. Create Zoom meeting with `--duration 30`
3. Create calendar event on `--account work`
4. Verify creation

## Troubleshooting

### "Request had insufficient authentication scopes"

The Google Calendar token has readonly permissions. Fix by re-authenticating:

1. Ensure `setup_auth.py` uses `calendar` scope (not `calendar.readonly`)
2. Re-run authentication:
   ```bash
   echo "y" | uv run python .claude/skills/google-calendar/scripts/setup_auth.py --account personal
   ```

### Zoom Meeting Created but Calendar Event Failed

The Zoom meeting was created successfully. You can:
1. Fix calendar permissions and retry just the calendar creation step
2. Manually add the Zoom link to your calendar using the join URL

### Time Zone Issues

Both scripts use local time by default. If times appear wrong:
- Zoom: Add `--timezone "Europe/Kiev"` to the create command
- Calendar: Add `--timezone "Europe/Kiev"` to the create command

## Quick Reference

| Account | Calendar Command | Description |
|---------|------------------|-------------|
| personal | `--account personal` | Personal Google Calendar |
| work | `--account work` | Work Google Calendar |

| Duration | Example |
|----------|---------|
| 30 min | `--duration 30` |
| 1 hour | `--duration 60` |
| 2 hours | `--duration 120` |
