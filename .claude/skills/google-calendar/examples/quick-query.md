# Quick Query Examples

## Today's Schedule

```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --all --days 1 --pretty
```

## This Week's Schedule (JSON)

```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --all --days 7 --json
```

## Query Specific Account

```bash
# Work calendar only
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --account work --days 7 --pretty

# Personal calendar only
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --account personal --days 7 --pretty
```

## List Calendars

```bash
uv run python .claude/skills/google-calendar/scripts/fetch_events.py \
  --account work --list-calendars
```

## Programmatic Usage

```python
from calendar_client import CalendarClient, fetch_all_events

# Single account
client = CalendarClient("work")
events = client.get_events(days=7)

# All accounts combined
result = fetch_all_events(days=7)
print(f"Total {result['total']} events")
print(f"Conflicts: {len(result['conflicts'])}")
```
