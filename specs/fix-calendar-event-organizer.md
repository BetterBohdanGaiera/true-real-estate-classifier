# Fix: Google Calendar events not appearing for organizer (bohdan.p@trueagency.online)

## Problem

When the bot creates a Google Calendar event via API:
- Invite IS sent to the attendee (bohdan.pytaichuk@gmail.com) - works
- But the event doesn't appear on the organizer's calendar (bohdan.p@trueagency.online) when running in Docker
- When the attendee accepts, the event can't be properly accepted because the organizer's calendar doesn't have it

## Root Cause (diagnosed)

The Google Calendar OAuth token is stored at `~/.sales_registry/calendar_tokens/203144303.json` and belongs to `bohdan.p@trueagency.online`. Verified:
- `CalendarConnector.create_event(telegram_id=203144303)` works perfectly - event created, organizer=bohdan.p@trueagency.online, attendee invite sent.

BUT in the daemon, there are two problems:

### Problem 1: Wrong telegram_id used for calendar operations
In `daemon.py`, the `SchedulingTool` is initialized with `rep_telegram_id`. In default mode (no `--rep-telegram-id` flag), this was `None`. A recent fix changed it to use `bot_user_id` (the Telegram ID of @BetterBohdan) as fallback. But @BetterBohdan's Telegram ID may NOT be `203144303` - the ID that has the calendar token. So `create_event(telegram_id=bot_user_id)` fails because there's no token file for that ID.

### Problem 2: Docker needs REP_TELEGRAM_ID env var
The docker-compose.yml has `REP_TELEGRAM_ID: ${REP_TELEGRAM_ID:-}` which defaults to empty. Without it, the daemon runs in default mode and doesn't know which rep's calendar to use.

## Diagnostic Evidence

```
Calendar token file: ~/.sales_registry/calendar_tokens/203144303.json
Calendar owner: bohdan.p@trueagency.online
Calendar ID: bohdan.p@trueagency.online (primary)
Access role: owner

Test event creation with telegram_id=203144303:
  Status: confirmed
  Organizer: {'email': 'bohdan.p@trueagency.online', 'self': True}
  Creator: {'email': 'bohdan.p@trueagency.online', 'self': True}
  Attendee: bohdan.pytaichuk@gmail.com - response: needsAction
```

## Fix Required

### 1. Fix daemon.py - Find available calendar token when rep_telegram_id is None

In `src/telegram_sales_bot/core/daemon.py`, in the `initialize()` method, when NOT in per-rep mode and a `calendar_connector` is enabled, discover the first available calendar token and use that telegram_id for scheduling operations.

Location: around line 188-217 in `initialize()`, where `calendar_connector` is initialized in the `else` branch (default mode).

After this block:
```python
else:
    try:
        calendar_connector = CalendarConnector()
        if calendar_connector.enabled:
            ...
```

Add logic to find the first connected calendar account:
```python
# Find the first available calendar token to use as rep_telegram_id
from pathlib import Path
tokens_dir = Path.home() / ".sales_registry" / "calendar_tokens"
if tokens_dir.exists():
    token_files = list(tokens_dir.glob("*.json"))
    if token_files:
        discovered_rep_id = int(token_files[0].stem)
        if calendar_connector.is_connected(discovered_rep_id):
            self.rep_telegram_id = discovered_rep_id  # Use for calendar ops
```

### 2. Fix the effective_rep_id calculation

The current code (recently modified) at ~line 212:
```python
effective_rep_id = self.rep_telegram_id or self.bot_user_id
```

This should work correctly after fix #1 sets `self.rep_telegram_id` to the discovered calendar token ID.

### 3. Update .env.example and document REP_TELEGRAM_ID

Add to `.env.example` or the docker-compose.yml docs:
```
# Set to the Telegram ID of the sales rep whose calendar should be used
# Find it from: ls ~/.sales_registry/calendar_tokens/
# Example: REP_TELEGRAM_ID=203144303
REP_TELEGRAM_ID=203144303
```

### 4. Add calendar token discovery to book_meeting error path

In `src/telegram_sales_bot/scheduling/tool.py`, the `book_meeting()` method has good warning messages now. Add one more fallback: if `rep_telegram_id` is set but not connected, try to discover a connected account:

```python
if not self.calendar_connector.is_connected(self.rep_telegram_id):
    # Try to find any connected calendar token
    tokens_dir = Path.home() / ".sales_registry" / "calendar_tokens"
    if tokens_dir.exists():
        for tf in tokens_dir.glob("*.json"):
            alt_id = int(tf.stem)
            if self.calendar_connector.is_connected(alt_id):
                print(f"WARNING: rep {self.rep_telegram_id} not connected, using discovered {alt_id}")
                self.rep_telegram_id = alt_id
                break
```

### 5. Write test to verify the fix

Add a test to `test_meeting_scheduling.py` that:
1. Checks if calendar token exists for `203144303`
2. Creates event with that ID
3. Verifies organizer is `bohdan.p@trueagency.online`
4. Verifies attendee receives invite
5. Verifies event is fetchable from organizer's calendar (with retry for eventual consistency)

### 6. Verify end-to-end in Docker

After fixing, test with:
```bash
# Option A: Set REP_TELEGRAM_ID in .env
echo "REP_TELEGRAM_ID=203144303" >> .env
docker-compose -f deployment/docker/docker-compose.yml up -d telegram-agent

# Option B: Auto-discovery should work without setting it
docker-compose -f deployment/docker/docker-compose.yml up -d telegram-agent
# Check logs for: "Scheduling tool ready (calendar rep_id=203144303)"
docker-compose -f deployment/docker/docker-compose.yml logs telegram-agent | grep "calendar rep_id"
```

## Files to Modify

1. `src/telegram_sales_bot/core/daemon.py` - Calendar token auto-discovery in default mode
2. `src/telegram_sales_bot/scheduling/tool.py` - Fallback discovery in book_meeting
3. `.claude/skills/testing/scripts/test_meeting_scheduling.py` - Add organizer verification test
4. `.env` - Add `REP_TELEGRAM_ID=203144303`

## Key Facts
- Calendar token: `~/.sales_registry/calendar_tokens/203144303.json`
- Calendar owner: `bohdan.p@trueagency.online`
- Bot account: `@BetterBohdan`
- Test attendee: `bohdan.pytaichuk@gmail.com`
- Docker volume mount: `${HOME}/.sales_registry:/home/agent/.sales_registry:rw` (already configured)
