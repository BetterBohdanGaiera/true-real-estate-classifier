# Fix Meeting Scheduling Flow

## Objective

Fix three critical issues in the meeting scheduling conversation flow:
1. Bot doesn't confirm time when client already mentions it
2. Available slots are not based on real Google Calendar data
3. Booked meetings don't appear in Google Calendar

## Root Cause Analysis

### Problem 1: Time Confirmation Not Working
**Root cause:** The agent system prompt instructs the LLM to use `check_availability` when client expresses interest, but there's no mechanism to **confirm a specific time** the client already mentioned. The flow always goes: check_availability -> show all slots -> ask preference -> schedule. If the client says "tomorrow at 10:00", the bot should confirm that time is available and book it, not dump all slots.

**Fix:** Update `agent_system_prompt.md` to add a "confirm_time" flow where:
- If client already stated a preferred time, check if it's available first
- If available, confirm and proceed to schedule (with email)
- If not available, suggest nearest alternatives
- Add a new action handling in daemon for when agent provides scheduling_data with a specific time to confirm

### Problem 2: Slots Not Based on Real Calendar
**Root cause:** `SalesCalendar.generate_mock_slots()` creates random slots (70% available) without consulting Google Calendar. The existing `CalendarAwareScheduler` in `calendar_aware.py` exists but is **NOT wired into the main flow** - it has a broken import (`from sales_agent.registry.calendar_connector import CalendarConnector` - old module path) and is never used by the daemon or SchedulingTool.

**Fix:**
- Fix the broken import in `calendar_aware.py`
- Integrate `CalendarAwareScheduler` into the `SchedulingTool.get_available_times()` method
- When Google Calendar is connected, use real availability; when not, fall back to mock slots (current behavior)
- The daemon already initializes CalendarConnector and passes it to SchedulingTool, but SchedulingTool doesn't use it for slot fetching

### Problem 3: Meetings Don't Appear in Calendar
**Root cause:** In `SchedulingTool.book_meeting()`, Google Calendar event creation has a gate: `if self.calendar_connector and zoom_url:` - meaning calendar event is ONLY created when BOTH calendar connector AND zoom_url exist. If Zoom fails or isn't configured, no calendar event is created. Additionally, `CalendarConnector.get_events()` uses `SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]` - **read-only scope** that cannot create events.

**Fix:**
- Change Google Calendar OAuth scope to include write access: `calendar.events` or `calendar`
- Remove the `zoom_url` dependency for Google Calendar event creation - create calendar event regardless
- Create calendar event even without Zoom link, adding Zoom link later if available

## Files to Modify

### 1. `src/telegram_sales_bot/integrations/google_calendar.py`
- Change SCOPES from `calendar.readonly` to `https://www.googleapis.com/auth/calendar` (full read/write)
- Ensure `create_event()` method works correctly with proper timezone handling
- Add proper error logging

### 2. `src/telegram_sales_bot/scheduling/calendar_aware.py`
- Fix broken import: change `from sales_agent.registry.calendar_connector import CalendarConnector` to `from telegram_sales_bot.integrations.google_calendar import CalendarConnector`
- This file is already well-implemented, just needs the import fix

### 3. `src/telegram_sales_bot/scheduling/calendar.py`
- Add a new method `get_available_slots_with_calendar()` that accepts an optional `CalendarConnector` and `rep_telegram_id` to filter slots against real Google Calendar
- When calendar is connected: generate working hour slots, then exclude busy periods from Google Calendar
- When not connected: fall back to current mock behavior

### 4. `src/telegram_sales_bot/scheduling/tool.py`
- In `get_available_times()`: use calendar connector to get real availability when available
- In `book_meeting()`: remove the `and zoom_url` condition for Google Calendar event creation
- Create calendar event even without Zoom link - include Zoom link in description only if available
- Add a new method `confirm_time_slot()` that checks if a specific time is available and returns a natural confirmation or alternatives

### 5. `.claude/skills/telegram/config/agent_system_prompt.md`
- Add instructions for when client already mentions a specific time: confirm it rather than dumping all slots
- Update the scheduling flow to handle time confirmation scenarios
- Add guidance on confirming times the client has already stated

### 6. `src/telegram_sales_bot/core/daemon.py`
- Update `_handle_action()` for `check_availability` to pass calendar_connector for real availability
- Update `_handle_action()` for `schedule` to ensure calendar event is created properly
- No structural changes needed - the wiring is mostly in SchedulingTool

## Implementation Steps

### Step 1: Fix Google Calendar Scopes (google_calendar.py)
- Change SCOPES to allow write access
- Existing `create_event()` method signature is already fine

### Step 2: Fix Import in calendar_aware.py
- Update broken import path to use new package structure

### Step 3: Integrate Real Calendar into SalesCalendar (calendar.py)
- Add method that generates all working hour slots for a date range
- Add method that filters slots using Google Calendar busy periods
- Keep mock behavior as fallback

### Step 4: Update SchedulingTool (tool.py)
- Use CalendarConnector in `get_available_times()` when available
- Fix `book_meeting()` to create calendar events without requiring Zoom
- Add `confirm_time_slot()` method for confirming specific client-mentioned times

### Step 5: Update Agent System Prompt (agent_system_prompt.md)
- Add time confirmation flow instructions
- Teach agent to recognize when client has already stated a preference
- Add examples for confirming a specific time vs. showing all slots

### Step 6: Wire Everything in Daemon (daemon.py)
- Ensure calendar connector is properly passed through the chain
- No major changes needed since SchedulingTool already receives it

## Acceptance Criteria

1. When client says "I'm free tomorrow at 10:00", the bot should confirm that time (if available) or suggest alternatives
2. Available time slots should reflect real Google Calendar data when connected
3. When a meeting is booked, it should appear in Google Calendar regardless of Zoom status
4. When Google Calendar is not connected, system falls back to mock slots gracefully
5. All existing functionality (timezone display, email validation, follow-ups) continues to work

## Testing Strategy

- Test with Docker deployment as specified in fix.md
- Manual testing through `telegram_conversation_manual_test`
- Verify calendar events are created
- Verify slots reflect actual calendar availability
