# Plan: Improve Time Conversation with Natural Ranges and Accurate Timezone Calculations

## Task Description

Drastically improve the time slot conversation experience by:
1. **Using tone of voice** - keeping communication natural, not robotic
2. **Proposing time ranges** instead of individual 30-minute slots (e.g., "с 10 до 16 по Бали, кроме 13-14 и 15-16")
3. **Showing exact free slots** based on calendar availability
4. **Fixing timezone calculations** - the current system calculates timezone differences incorrectly (+1 and +8 should have 7 hours difference, not 6). Move timezone math to Python scripts instead of LLM reasoning.

### Bad Communication Example (Current State)
```
Доступные слоты для встречи (время по Бали UTC+8):

Сегодня (5 февраля)
- 17:00-17:30

Завтра (6 февраля)
- 11:00-11:30
- 14:00-14:30
- 18:00-18:30

Понедельник (9 февраля)
- 16:00-16:30
- 18:00-18:30
```

### Good Communication Example (Target State)
```
Свободное время на этой неделе по Бали:
- Завтра: с 10 до 12, с 14 до 16 (кроме 15:00-15:30)
- Понедельник: с 16 до 19

По вашему времени (Варшава UTC+1) это:
- Завтра: с 3 до 5 утра, с 7 до 9 утра
- Понедельник: с 9 до 12

Какое время Вам удобнее - утро или вечер?
```

## Objective

When this plan is complete:
1. Time slots will be displayed as merged time ranges with gap exceptions
2. Timezone calculations will use Python's `zoneinfo` library (not LLM arithmetic)
3. The agent will offer 2-3 time options naturally instead of listing every 30-min slot
4. Communication will follow tone-of-voice guidelines with natural phrasing

## Problem Statement

The current scheduling system has three critical issues:

1. **Robotic Slot Display**: Individual 30-minute slots are listed as separate bullet points, creating walls of text that overwhelm prospects and feel machine-generated.

2. **Incorrect Timezone Math**: The LLM is instructed to mentally calculate timezone differences, leading to arithmetic errors (e.g., UTC+1 vs UTC+8 calculated as 6 hours instead of 7).

3. **Unnatural Communication**: The slot display format contradicts tone-of-voice guidelines that recommend offering choices naturally ("в будни или на выходных?") instead of data dumps.

## Solution Approach

1. **Create TimeRange Model**: Add Pydantic model for representing merged time ranges with gaps
2. **Implement Slot Aggregation**: Build algorithm to merge consecutive slots into ranges
3. **Add Timezone Calculation Tool**: Create Python-based timezone converter that the agent calls instead of calculating mentally
4. **Update Display Formatting**: Format merged ranges naturally with tone-of-voice compliance
5. **Enhance Agent Instructions**: Update system prompt to use new tools and natural phrasing

## Relevant Files

### Core Files to Modify

- `.claude/skills/telegram/scripts/scheduling_tool.py` (lines 302-381)
  - Contains `get_available_times()` method that formats individual slots
  - Has `_format_time_slot()` and `_format_time_slot_dual_timezone()` for display
  - Already has timezone conversion helpers using `zoneinfo`

- `.claude/skills/telegram/scripts/models.py` (lines 161-185)
  - Contains `SalesSlot` Pydantic model
  - Needs new `TimeRange` model for merged slots

- `.claude/skills/telegram/scripts/telegram_agent.py` (lines 212-293)
  - Contains scheduling instructions in system prompt
  - Needs update to use timezone calculation tool
  - Needs natural phrasing guidelines for slot offering

- `.claude/skills/telegram/scripts/daemon.py` (lines 435-444)
  - Calls `scheduling_tool.get_available_times()`
  - May need to pass additional context for natural formatting

### Reference Files (Read-Only)

- `.claude/skills/tone-of-voice/SKILL.md` - Communication style guidelines
- `.claude/skills/tone-of-voice/references/фразы.md` (lines 64-80, 160-186)
  - Contains natural time offering phrases: "Можем на 16:00 или 19:00"
  - Contains natural time confirmation patterns
- `.claude/skills/telegram/scripts/timezone_detector.py`
  - Existing timezone detection logic (heuristic-based)

### New Files to Create

- `.claude/skills/telegram/scripts/timezone_calculator.py`
  - Python-based timezone conversion functions
  - Will be called as a tool by the agent

## Implementation Phases

### Phase 1: Foundation - Timezone Calculator

Build reliable Python-based timezone calculations that the agent can invoke as a tool, removing arithmetic from LLM reasoning.

### Phase 2: Core Implementation - Slot Range Aggregation

Create the slot merging algorithm and TimeRange model to transform individual 30-minute slots into human-readable time ranges with gap exceptions.

### Phase 3: Integration & Polish - Natural Formatting

Update the agent's system prompt and formatting methods to use natural language patterns from tone-of-voice guidelines.

## Step by Step Tasks

### 1. Create TimeRange Pydantic Model

- Add `TimeRange` model to `.claude/skills/telegram/scripts/models.py`:
  ```python
  class TimeRange(BaseModel):
      """A contiguous time range with optional gaps."""
      date: date
      start_time: time
      end_time: time
      gaps: list[tuple[time, time]] = []  # Booked slots within the range

      def format_russian(self, include_gaps: bool = True) -> str:
          """Format as 'с 10 до 16' or 'с 10 до 16 (кроме 13:00-14:00)'"""
          ...
  ```
- Add validation that `start_time < end_time`
- Add validation that gaps are within the range

### 2. Create Timezone Calculator Module

- Create new file `.claude/skills/telegram/scripts/timezone_calculator.py`
- Implement core functions:
  ```python
  def get_timezone_offset(timezone: str) -> int:
      """Get UTC offset in hours for a timezone (handles DST)."""

  def calculate_time_difference(tz1: str, tz2: str, at_time: datetime = None) -> int:
      """Calculate hour difference between two timezones."""

  def convert_time(dt: datetime, from_tz: str, to_tz: str) -> datetime:
      """Convert datetime between timezones."""

  def format_dual_timezone_range(
      start: time, end: time,
      date: date,
      client_tz: str,
      bali_tz: str = "Asia/Makassar"
  ) -> str:
      """Format time range in both timezones naturally."""
  ```
- Use `zoneinfo.ZoneInfo` for all timezone operations
- Add comprehensive tests with edge cases (DST, same timezone, large offsets)

### 3. Implement Slot Aggregation Algorithm

- Add `_group_consecutive_slots()` method to `SchedulingTool` class:
  ```python
  def _group_consecutive_slots(
      self,
      slots: list[SalesSlot]
  ) -> list[TimeRange]:
      """
      Group consecutive available slots into time ranges.

      Algorithm:
      1. Sort slots by start_time
      2. Initialize first range with first slot
      3. For each subsequent slot:
         - If consecutive (end_time == next start_time): extend range
         - If gap: save current range, start new one
      4. Return list of TimeRange objects
      """
  ```
- Handle edge cases:
  - Single slot (no merging needed)
  - All slots booked (empty result)
  - Gaps in middle of day (lunch break)

### 4. Add Gap Detection for Booked Slots

- Modify aggregation to track booked slots as gaps within ranges:
  ```python
  def _identify_gaps_in_range(
      self,
      all_slots: list[SalesSlot],  # Both available and booked
      time_range: TimeRange
  ) -> TimeRange:
      """Add booked slots as gaps within the time range."""
  ```
- Update `SalesCalendar.get_available_slots()` to optionally return booked slots too
- This allows showing "с 10 до 16 (кроме 13:00-14:00)" format

### 5. Create Natural Time Range Formatter

- Add `_format_time_ranges_natural()` method:
  ```python
  def _format_time_ranges_natural(
      self,
      ranges: list[TimeRange],
      client_timezone: Optional[str] = None
  ) -> str:
      """
      Format time ranges using natural language.

      Output style:
      - "Завтра: с 10 до 12, с 14 до 16"
      - "По вашему времени: с 3 до 5, с 7 до 9"
      - "Когда Вам удобнее - утро или вечер?"
      """
  ```
- Use timezone calculator for accurate conversions
- Follow tone-of-voice patterns from `фразы.md`

### 6. Update get_available_times() Method

- Modify `.claude/skills/telegram/scripts/scheduling_tool.py` lines 302-381:
  - Add parameter `use_ranges: bool = True` for backward compatibility
  - When `use_ranges=True`:
    1. Retrieve all slots (available + booked)
    2. Group into TimeRange objects per day
    3. Use `_format_time_ranges_natural()` for output
  - Keep individual slot display as fallback option

### 7. Add Timezone Calculation Tool for Agent

- Add new tool definition in `telegram_agent.py`:
  ```python
  CONVERT_TIMEZONE_TOOL = {
      "name": "convert_timezone",
      "description": "Convert time between timezones accurately...",
      "input_schema": {
          "type": "object",
          "properties": {
              "time": {"type": "string", "description": "Time in HH:MM format"},
              "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
              "from_timezone": {"type": "string"},
              "to_timezone": {"type": "string"}
          }
      }
  }
  ```
- Handle tool calls in daemon to invoke Python timezone calculator
- Return both converted time AND hour difference for context

### 8. Update Agent System Prompt

- Modify scheduling instructions in `telegram_agent.py` (lines 212-293):
  - Remove instructions for LLM to calculate timezone differences
  - Add instruction to use `convert_timezone` tool for all conversions
  - Add natural phrasing guidelines:
    ```
    ## Предложение Времени (Естественный Стиль)

    ПЛОХО (список):
    "- 10:00-10:30
     - 11:00-11:30
     - 14:00-14:30"

    ХОРОШО (выбор):
    "Свободно с 10 до 12 и с 14 до 16. Вам удобнее утро или день?"

    ПРАВИЛА:
    1. Не показывай все слоты - предложи 2-3 временных диапазона
    2. Заканчивай вопросом с выбором
    3. Если клиент назвал предпочтение - предложи конкретный слот из диапазона
    ```

### 9. Add Integration Tests

- Create test file `.claude/skills/telegram/scripts/tests/test_time_ranges.py`:
  - Test `TimeRange` model validation
  - Test slot aggregation with various scenarios
  - Test timezone calculator accuracy
  - Test natural formatting output
- Test scenarios:
  - Full day availability (one range: "с 10 до 19")
  - Morning + afternoon blocks ("с 10 до 12, с 14 до 18")
  - Many gaps ("с 10 до 18 кроме 11:00, 13:00-14:00, 16:30")
  - Timezone conversions with different offsets

### 10. Validate End-to-End Flow

- Run the telegram daemon manually with test prospect
- Verify:
  - Slots display as merged ranges, not individual bullets
  - Timezone calculations are accurate (test with known UTC offsets)
  - Agent uses natural phrasing from tone-of-voice
  - Booking still works when user selects a time from range

## Testing Strategy

### Unit Tests
- `TimeRange` model validation (start < end, gaps within range)
- Timezone calculator functions (all common timezone pairs)
- Slot aggregation algorithm (edge cases: single slot, all booked, gaps)

### Integration Tests
- Full flow from `get_available_times()` to formatted output
- Agent tool call handling for timezone conversion
- Daemon integration with new formatting

### Manual Testing
- Send test message to @bohdanpytaichuk asking about meeting times
- Verify output matches "good communication" example format
- Test with different client timezones (Moscow, Warsaw, Dubai)

## Acceptance Criteria

1. **Time Range Display**: Available slots are shown as merged ranges (e.g., "с 10 до 16") instead of individual 30-min slots
2. **Gap Handling**: Booked slots within a range are shown as exceptions (e.g., "кроме 13:00-14:00")
3. **Accurate Timezone Math**: Timezone differences are calculated correctly using Python (UTC+1 vs UTC+8 = 7 hours)
4. **Natural Phrasing**: Agent offers 2-3 time choices with a question, following tone-of-voice guidelines
5. **Backward Compatibility**: Individual slot booking still works (user can pick specific time from range)
6. **No Robotic Patterns**: Messages don't list every slot as separate bullet points

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python -m py_compile .claude/skills/telegram/scripts/timezone_calculator.py` - Verify timezone calculator compiles
- `uv run python -m py_compile .claude/skills/telegram/scripts/scheduling_tool.py` - Verify scheduling tool compiles
- `uv run python -m py_compile .claude/skills/telegram/scripts/models.py` - Verify models compile
- `PYTHONPATH=.claude/skills/telegram/scripts uv run python -c "from timezone_calculator import calculate_time_difference; print(calculate_time_difference('Europe/Warsaw', 'Asia/Makassar'))"` - Should print 7
- `PYTHONPATH=.claude/skills/telegram/scripts uv run pytest .claude/skills/telegram/scripts/tests/test_time_ranges.py -v` - Run unit tests
- Manual test: Run daemon and verify time slot display format with test prospect

## Notes

### Dependencies
- Uses existing `zoneinfo` from Python 3.9+ standard library (no new packages needed)
- Uses existing `pytz` already in project for fallback/edge cases

### Considerations
- The `SalesCalendar` class needs to optionally return booked slots for gap detection
- Agent instructions must be updated to NOT perform mental timezone math
- Consider caching timezone offsets for frequently used pairs (Moscow, Warsaw, Dubai)

### Migration Path
- Add `use_ranges=True` parameter to enable new behavior
- Keep old format available via `use_ranges=False` for debugging
- Once validated, remove the flag and make ranges the default

### Related Skills
- `tone-of-voice` - Provides natural phrasing templates
- `how-to-communicate` - Principle 7: "Propose specific times, not 'when convenient'"
- `humanizer` - Guidelines for removing AI patterns from text
