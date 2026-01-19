# Parallel Fetch Example

## Parallel Subagent Execution

To query calendars from multiple accounts simultaneously, call the Task tool in parallel:

```
# Multiple Task calls in single message (parallel execution)

Task(
    subagent_type="general-purpose",
    prompt="Execute the following command and return result as JSON:
    uv run python .claude/skills/google-calendar/scripts/fetch_events.py --account work --days 7 --json",
    model="haiku"
)

Task(
    subagent_type="general-purpose",
    prompt="Execute the following command and return result as JSON:
    uv run python .claude/skills/google-calendar/scripts/fetch_events.py --account personal --days 7 --json",
    model="haiku"
)
```

## Result Integration

Parse and integrate JSON returned by each subagent:

```python
import json
from datetime import datetime

# Subagent results
work_events = json.loads(work_result)
personal_events = json.loads(personal_result)

# Integrate and sort by time
all_events = work_events + personal_events
all_events.sort(key=lambda x: x["start"])

# Group by date
events_by_date = {}
for event in all_events:
    date = event["start"].split("T")[0]
    events_by_date.setdefault(date, []).append(event)
```

## Conflict Detection

```python
def detect_conflicts(events):
    """Events at same time from different accounts = conflict"""
    conflicts = []
    for i, e1 in enumerate(events):
        for e2 in events[i+1:]:
            if e1["account"] == e2["account"]:
                continue
            # Check time overlap
            if is_overlapping(e1, e2):
                conflicts.append((e1, e2))
    return conflicts
```

## Output Example

```
📅 2026-01-06 (Mon)

[09:00-10:00] 🔵 Team Standup (work)
[14:00-15:00] 🔵 Customer Meeting (work)
              ⚠️ Conflict: Overlaps with personal event
[14:00-14:30] 🟢 Bank Visit (personal)

📊 Total 3 events | 1 conflict
```
