# Meeting Scheduling Fix - Code Review Report

**Reviewer:** Claude Opus 4.6 (automated review)
**Date:** 2026-02-09
**Spec:** `specs/fix-meeting-scheduling-flow.md`
**Trigger:** `fix.md` (three meeting scheduling issues)

---

## Summary

The implementation addresses all three stated issues:
1. Time confirmation when client already mentions a time
2. Real Google Calendar data for slot generation
3. Calendar event creation on meeting booking

Additionally, significant refactoring occurred (migration from `TelegramAgent` to `CLITelegramAgent`, session persistence). This review focuses on the meeting scheduling changes but flags collateral changes where they introduce risk.

---

## Verdict: CONDITIONAL PASS (1 Blocker must be fixed)

---

## BLOCKERS (Must fix before deployment)

### B-1. `CalendarConnector.create_event()` does not exist

**File:** `src/telegram_sales_bot/scheduling/tool.py` line 836
**Severity:** Runtime crash (AttributeError) on every meeting booking when calendar is connected

The `book_meeting()` method calls:
```python
self.calendar_connector.create_event(
    summary=f"Консультация: {prospect.name}",
    start=start_iso,
    end=end_iso,
    description=description,
    location=zoom_url or "",
    attendees=[client_email],
    timezone="Asia/Makassar"
)
```

However, `CalendarConnector` in `/src/telegram_sales_bot/integrations/google_calendar.py` only has these methods:
- `is_connected()`
- `get_auth_url()`
- `complete_auth()`
- `get_events()`
- `get_busy_slots()`
- `disconnect()`

**There is no `create_event()` method.** This will raise `AttributeError` at runtime every time a meeting is booked with Google Calendar connected. The spec explicitly said "Ensure `create_event()` method works correctly" but the method was never implemented.

**Impact:** This is the primary goal of Issue #3 ("booked meetings don't appear in Google Calendar"). The fix doesn't work.

**Action required:** Implement `create_event()` on `CalendarConnector` using the Google Calendar API `events().insert()` endpoint. The method signature is already defined by the call site:
```python
def create_event(
    self,
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] = None,
    timezone: str = "Asia/Makassar",
) -> dict:
```

**Note:** The exception handler around the call (line 846) will catch `AttributeError`, so the bot won't crash, but it will silently fail to create calendar events, defeating the purpose of the fix.

---

## HIGH RISK

### H-1. N+1 API calls in `get_available_slots_from_calendar()`

**File:** `src/telegram_sales_bot/scheduling/calendar.py` lines 318-346

`get_busy_slots()` is called **once per slot** (7 slots/day * 5 days = 35 API calls for a 7-day window). Each `get_busy_slots()` call internally calls `get_events()` which makes a full Google Calendar API request.

For a typical 7-day query:
- 5 weekdays * 7 working hours = **35 Google Calendar API calls**
- Each call has network latency (~200-500ms) = **7-17 seconds** total latency
- Google Calendar API rate limit is 500 requests per 100 seconds, so this won't hit rate limits, but the latency is unacceptable for a chat bot.

**Compare with:** The existing `CalendarAwareScheduler` in `calendar_aware.py` (lines 136-164) correctly groups API calls by day (1 call per day = 5 calls for 7 days). The new code duplicates this logic but with the N+1 pattern.

**Recommendation:** Cache `get_busy_slots()` results by date. Call it once per day, then check all slots for that day against the cached result:
```python
busy_cache = {}  # date -> list of busy slots
for slot in all_working_slots:
    slot_date = slot.date
    if slot_date not in busy_cache:
        busy_cache[slot_date] = calendar_connector.get_busy_slots(...)
    busy_slots = busy_cache[slot_date]
    # ... check overlap
```

### H-2. `get_slot_by_time()` always uses mock data, even with real calendar

**File:** `src/telegram_sales_bot/scheduling/tool.py` lines 891-911

`get_slot_by_time()` calls `self.calendar.get_available_slots()` (the mock version) and never uses `get_available_slots_from_calendar()`. This means `confirm_time_slot()` (which calls `get_slot_by_time()`) will check availability against **mock data**, not real Google Calendar data.

**Impact:** When a client says "Let's do tomorrow at 10:00", the system may confirm a time that's actually blocked in Google Calendar, or reject a time that's actually free.

**Recommendation:** Update `get_slot_by_time()` to use calendar-aware data:
```python
if self.calendar_connector and self.rep_telegram_id:
    available_slots = self.calendar.get_available_slots_from_calendar(...)
else:
    available_slots = self.calendar.get_available_slots(...)
```

### H-3. `confirm_time_slot()` double-fetches slots and wastes the first fetch

**File:** `src/telegram_sales_bot/scheduling/tool.py` lines 948-961

When the requested slot is not available, the code first fetches mock slots (line 949-952), then **immediately overwrites** with calendar-aware slots (lines 955-961) if the calendar connector is available. The first fetch is always wasted when the calendar connector is present.

```python
# Slot not available - find alternatives on the same day
available_slots = self.calendar.get_available_slots(   # <-- always fetched
    from_date=target_date, days=1
)

# Use calendar-aware if possible
if self.calendar_connector and self.rep_telegram_id:
    available_slots = self.calendar.get_available_slots_from_calendar(  # <-- overwrites above
        ...
    )
```

**Impact:** Unnecessary computation and (if combined with H-1) unnecessary API calls. Logically correct but wasteful.

**Recommendation:** Use an `if/else`:
```python
if self.calendar_connector and self.rep_telegram_id:
    available_slots = self.calendar.get_available_slots_from_calendar(...)
else:
    available_slots = self.calendar.get_available_slots(...)
```

---

## MEDIUM RISK

### M-1. `confirm_time_slot()` is dead code (never called)

**File:** `src/telegram_sales_bot/scheduling/tool.py` lines 913-1001

`confirm_time_slot()` is defined but never called from anywhere in the codebase. The agent system prompt describes a flow where the agent uses `check_availability` when a client mentions a specific time, but the daemon's `_handle_action()` for `check_availability` (daemon.py line 396) calls `self.scheduling_tool.get_available_times()`, not `confirm_time_slot()`.

**Impact:** The time confirmation logic exists in the prompt instructions (telling the LLM what to do) but the specialized method is unused. The LLM will use `check_availability` which shows all slots via `get_available_times()` rather than confirming a specific time. The prompt instructs the LLM to handle this contextually, so this may work acceptably through prompt engineering alone, but the purpose-built method goes unused.

**Recommendation:** Either wire `confirm_time_slot()` into `_handle_action()` as a separate action type, or remove it to avoid confusion.

### M-2. `get_busy_slots()` ignores the `timezone` parameter

**File:** `src/telegram_sales_bot/integrations/google_calendar.py` lines 300-337

The `timezone` parameter is accepted but never used inside the method. The `get_events()` call uses UTC-based `timeMin`/`timeMax`, and the date filtering on line 332 (`start.date() == date.date()`) uses whatever timezone the events come back in (which may differ from the passed timezone).

**Impact:** When the caller passes `timezone="Asia/Makassar"` (UTC+8), the `get_events()` call fetches based on UTC `now`, and the date comparison may miss events near midnight boundaries. An event at 11:55 PM Bali time = 3:55 PM UTC, which would have a different `.date()` in UTC vs Bali.

**Pre-existing:** This issue existed before the current changes, but the new code in `calendar.py` relies on this method more heavily.

### M-3. Naive vs. timezone-aware datetime comparison in `get_available_slots_from_calendar()`

**File:** `src/telegram_sales_bot/scheduling/calendar.py` lines 325-337

```python
slot_start_dt = datetime.combine(slot.date, slot.start_time)    # naive
slot_end_dt = datetime.combine(slot.date, slot.end_time)        # naive
# ...
for busy_start, busy_end in busy_slots:                         # timezone-aware (from API)
    if slot_start_dt < busy_end and slot_end_dt > busy_start:   # comparing naive vs aware
```

The slot datetimes are naive (no timezone info), but `get_busy_slots()` returns timezone-aware datetimes (parsed from ISO strings with timezone offsets). In Python, comparing a naive datetime with an aware datetime raises `TypeError`.

**However:** The `get_busy_slots()` method uses `datetime.fromisoformat(event["start"].replace("Z", "+00:00"))`, which creates UTC-aware datetimes. Comparing naive Bali-time datetimes against UTC-aware datetimes would fail.

**Mitigating factor:** The `except Exception` block on line 343 catches this and falls through to "fail-open" (includes the slot anyway). This means the Google Calendar filtering would silently fail for all slots, falling back to including everything, which defeats the purpose.

**Recommendation:** Make slot datetimes timezone-aware:
```python
from zoneinfo import ZoneInfo
bali_tz = ZoneInfo("Asia/Makassar")
slot_start_dt = datetime.combine(slot.date, slot.start_time, tzinfo=bali_tz)
slot_end_dt = datetime.combine(slot.date, slot.end_time, tzinfo=bali_tz)
```

### M-4. Unused `end_date` variable in `get_available_slots_from_calendar()`

**File:** `src/telegram_sales_bot/scheduling/calendar.py` line 278

```python
end_date = from_date + timedelta(days=days)
```

This variable is computed but never referenced in the method body. The loop uses `range(days)` instead. Harmless but indicates incomplete implementation.

### M-5. `CalendarConnector` initialized without `rep_telegram_id` in non-per-rep mode

**File:** `src/telegram_sales_bot/core/daemon.py` lines 187-197

In the non-per-rep `else` branch:
```python
calendar_connector = CalendarConnector()
```

The connector is created, but `self.rep_telegram_id` remains `None`. Later, `SchedulingTool` receives `rep_telegram_id=None` (line 216). This means `get_available_slots_from_calendar()` always falls back to mock data in non-per-rep mode because the guard check `self.calendar_connector and self.rep_telegram_id` fails.

**Impact:** The fix for Issue #2 (real calendar data) only works in per-rep mode, not in the default non-per-rep mode. This may be intentional (per-rep means the calendar is tied to a specific person), but it silently bypasses real calendar integration for the common deployment scenario.

---

## LOW RISK

### L-1. `CalendarAwareScheduler` (calendar_aware.py) is now redundant

The import fix in `calendar_aware.py` is correct, but the entire `CalendarAwareScheduler` class is now superseded by the new `get_available_slots_from_calendar()` method in `calendar.py`. Both implement the same logic (generate working hour slots, filter by Google Calendar busy periods). Having two implementations increases maintenance burden.

**Recommendation:** Deprecate or remove `calendar_aware.py` in a follow-up.

### L-2. Agent prompt assumes `confirm_time_slot` behavior that doesn't exist in code flow

The agent system prompt (lines 101-123) instructs the LLM to use `check_availability` when client names a time, and the LLM should confirm it. However, `check_availability` in `_handle_action()` just calls `get_available_times()` which dumps all available slots. The LLM must then interpret the full slot list and respond appropriately, rather than getting a targeted confirmation.

**Impact:** The LLM can still handle this via its reasoning, but it's less reliable than a dedicated code path.

### L-3. Duplicate `timezone` import in google_calendar.py

**File:** `src/telegram_sales_bot/integrations/google_calendar.py` line 41

```python
from datetime import datetime, timezone, timezone, timedelta
```

`timezone` is imported twice. This is a pre-existing issue (also present in `calendar_aware.py` line 27 and `calendar.py` line 9). Harmless but sloppy.

### L-4. Description formatting inconsistency in `book_meeting()`

**File:** `src/telegram_sales_bot/scheduling/tool.py` lines 827-834

```python
description_parts = [
    f"Консультация по недвижимости на Бали\n",  # has trailing \n
    f"Клиент: {prospect.name}",                  # no trailing \n
    f"Email: {client_email}",                     # no trailing \n
]
if zoom_url:
    description_parts.append(f"\nZoom: {zoom_url}")  # has leading \n
description = "\n".join(description_parts)
```

The first element has a trailing `\n` and then `"\n".join()` adds another, creating a double blank line. Minor cosmetic issue in the Google Calendar event description.

### L-5. Session persistence and CLITelegramAgent migration

**File:** `src/telegram_sales_bot/core/daemon.py`

The migration from `TelegramAgent` to `CLITelegramAgent` and session persistence logic (`_persist_session`, session restoration) is well-structured. The `sessions` dict exists on `CLITelegramAgent` (confirmed). However, `update_prospect_field` is used to persist `session_id` - this was confirmed to exist in `ProspectManager`.

No issues found with the migration itself.

---

## Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| Syntactically correct | PASS | All Python syntax is valid |
| No broken existing functionality | PASS with caveats | Mock fallback paths preserved; see M-5 for non-per-rep mode |
| New code integrates with codebase | PARTIAL | `create_event()` missing (B-1), `confirm_time_slot()` unwired (M-1) |
| No security issues | PASS | OAuth scope upgrade is intentional and necessary |
| Error handling | PASS | All new code has try/except with fail-open semantics |
| Edge cases covered | PARTIAL | Naive/aware datetime mismatch (M-3), N+1 latency (H-1) |
| Calendar fallback to mock | PASS | All paths fall back gracefully when calendar unavailable |

---

## Specific Answers to Review Questions

**Q: Does `get_available_slots_from_calendar()` properly handle missing calendar_connector?**
A: Yes. The guard check (lines 263-268) correctly falls back to `get_available_slots()` when connector is None, rep_telegram_id is None, or the rep's calendar is not connected.

**Q: Does `book_meeting()` now create calendar events even without Zoom URL?**
A: Yes, the condition was changed from `if self.calendar_connector and zoom_url` to `if self.calendar_connector`. However, the `create_event()` method it calls does not exist (B-1), so it will fail at runtime.

**Q: Is the `confirm_time_slot()` method correct?**
A: The logic is correct but has two issues: (1) it uses `get_slot_by_time()` which checks mock data instead of real calendar (H-2), and (2) it double-fetches when finding alternatives (H-3). Also, it's never called from anywhere (M-1).

**Q: Are there any NameError risks with `calendar_connector` variable scoping in daemon.py?**
A: No. The variable is initialized to `None` at line 174, then conditionally assigned in both the `if self.rep_telegram_id` branch and the `else` branch. All paths lead to a defined variable when used on line 215.

**Q: Does the new method in calendar.py call `get_busy_slots()` efficiently?**
A: No. It calls `get_busy_slots()` once per slot (N+1 pattern), resulting in up to 35 API calls for a 7-day window (H-1). Should be grouped by date.

**Q: Are all fallbacks to mock behavior working?**
A: Yes for slot generation. The mock fallback is properly triggered when: (1) calendar_connector is None, (2) rep_telegram_id is None, (3) rep's calendar is not connected, or (4) any API call fails. However, the naive/aware datetime comparison (M-3) may cause ALL real calendar checks to silently fail, effectively always using fail-open behavior.

---

## Recommended Fix Priority

1. **B-1** (Blocker): Implement `create_event()` on `CalendarConnector` - without this, Issue #3 is completely unresolved
2. **M-3** (Medium, acts as Blocker): Fix naive/aware datetime comparison - without this, Issue #2 silently degrades to mock data
3. **H-1** (High): Add per-day caching for `get_busy_slots()` - 35 API calls per availability check is unacceptable latency
4. **H-2** (High): Make `get_slot_by_time()` calendar-aware - confirm_time_slot checks wrong data source
5. **H-3** (High): Fix double-fetch in `confirm_time_slot()` - easy cleanup
6. Everything else can be addressed in follow-up PRs
