# Fix Time-Setting Communication Module

## Problem Statement

The scheduling system has several issues with how time slots are generated, filtered, and communicated to prospects:

### Issue 1: Unreasonable Hours Offered (4:00 AM)
**Root cause:** `WORKING_HOURS = [10, 11, 14, 15, 16, 17, 18]` in `calendar.py` generates slots at these Bali hours. For Warsaw (UTC+1, 7 hours behind Bali), 10:00 Bali = 03:00 Warsaw, 11:00 Bali = 04:00 Warsaw. The `_filter_slots_by_client_hours()` method exists in `tool.py` (line 457) but is **NEVER CALLED** in `get_available_times()`. The filter is dead code.

### Issue 2: Only :00-:30 Slots (Missing :30-:00 Slots)
**Root cause:** `WORKING_HOURS = [10, 11, 14, 15, 16, 17, 18]` only contains full hours. The `generate_mock_slots()` and `get_available_slots_from_calendar()` in `calendar.py` only create slots at `time(hour=hour, minute=0)` with `end_time=time(hour=hour, minute=30)`. Half-hour slots (e.g., 10:30-11:00, 11:30-12:00) are never generated. This means consecutive ranges can't form (e.g., 10:00-10:30 and 11:00-11:30 aren't consecutive, there's a gap at 10:30-11:00).

### Issue 3: Communication Should Show Ranges, Not Individual Slots
**Partially fixed:** The `_format_time_ranges_natural()` already groups consecutive slots into ranges, but since half-hour slots are missing, the ranges appear as individual 30-min slots (e.g., "с 04:00 до 04:30, с 08:00 до 08:30" instead of "с 08:00 до 10:30").

### Issue 4: Missing Context About Bali Working Hours
**Root cause:** The system never communicates that the agent is based in Bali working 10:00-18:00 and explaining the overlap. The agent system prompt mentions "Я в Бали (UTC+8)" but doesn't explain working hours or why certain times are available.

## Implementation Plan

### File 1: `src/telegram_sales_bot/scheduling/calendar.py`

**Changes:**
1. **Replace `WORKING_HOURS` with continuous time range generation** (lines 16-17)
   - Instead of discrete hours `[10, 11, 14, 15, 16, 17, 18]`, define `WORKING_HOURS_START = 10` and `WORKING_HOURS_END = 19` (10:00-19:00 Bali time)
   - Generate 30-minute slots for EVERY half-hour within the range: 10:00, 10:30, 11:00, 11:30, ..., 18:00, 18:30
   - This means 18 slots per day instead of 7

2. **Update `generate_mock_slots()`** (lines 141-199)
   - Loop from `WORKING_HOURS_START` to `WORKING_HOURS_END` in 30-minute increments
   - Generate slot IDs for both :00 and :30 (e.g., "20260210_1000", "20260210_1030")
   - Keep the 70% availability probability

3. **Update `get_available_slots_from_calendar()`** (lines 274-310)
   - Same change: generate slots for every 30 minutes from 10:00 to 18:30
   - Slot ID format: "YYYYMMDD_HHMM" (e.g., "20260210_1030" for 10:30)

### File 2: `src/telegram_sales_bot/scheduling/tool.py`

**Changes:**
1. **Call `_filter_slots_by_client_hours()` in `get_available_times()`** (around line 637)
   - After fetching slots and filtering past slots, ADD the client hours filter
   - Use `min_hour=8` (no meetings before 8am client time)
   - This is the KEY fix - the method exists but is never called!

2. **Update `_format_time_ranges_natural()` to include Bali working hours context** (lines 509-591)
   - When `client_timezone` is provided, add a brief one-time note: "Я работаю на Бали (UTC+8), рабочее время с 10:00 до 19:00 по Бали. Вот пересечения по вашему времени:"
   - This should be a natural human explanation, not robotic

3. **Improve `_filter_slots_by_client_hours()`** (lines 457-507)
   - Already well-implemented, just needs to be called. Keep `min_hour=8, max_hour=22` defaults.

### File 3: `.claude/skills/telegram/config/agent_system_prompt.md`

**Changes:**
1. **Update "Предложение Времени" section** (lines 110-134)
   - Update the "ХОРОШО" example to show realistic ranges after filtering
   - Add instruction: "При первом показе слотов объясни что ты на Бали и работаешь с 10 до 19 по Бали, поэтому по времени клиента есть такие пересечения"
   - Remove the example showing 02:00-04:00 (those would now be filtered out)
   - Show realistic examples: "с 08:00 до 11:30" for Warsaw

2. **Add explicit instruction about natural time range communication**
   - "Вместо перечисления отдельных слотов, коммуницируй диапазонами: 'с 8 до 10:30 можем созвониться в любое время на полчаса'"

### File 4: `.claude/commands/telegram_conversation_automatic_test.md`

**Changes:**
1. **Update Phase 7 expectations** (lines 141-150)
   - Update PASS criteria: agent should NOT show times before 8:00 in client timezone
   - Agent should explain Bali working hours context
   - Times should appear as ranges (e.g., "с 08:00 до 11:30") not individual 30-min slots
   - Add specific check that no slots before 8:00 Warsaw time are shown

## Files to Modify

| # | File | Type | Key Changes |
|---|------|------|-------------|
| 1 | `src/telegram_sales_bot/scheduling/calendar.py` | Modify | Generate all 30-min slots (10:00-18:30), not just hour-start slots |
| 2 | `src/telegram_sales_bot/scheduling/tool.py` | Modify | Call `_filter_slots_by_client_hours()`, add Bali context to output |
| 3 | `.claude/skills/telegram/config/agent_system_prompt.md` | Modify | Update scheduling examples and instructions |
| 4 | `.claude/commands/telegram_conversation_automatic_test.md` | Modify | Update Phase 7 PASS criteria |

## Acceptance Criteria

1. Slots are generated every 30 minutes from 10:00 to 18:30 Bali time (18 slots/day vs 7)
2. No slots before 8:00 AM in client timezone are shown (4:00 AM Warsaw = gone)
3. Consecutive 30-min slots merge into ranges: "с 08:00 до 11:00" instead of "08:00-08:30, 09:00-09:30"
4. First time showing slots includes brief Bali working hours context
5. Agent system prompt examples reflect realistic filtered ranges
6. Test expectations match new behavior
