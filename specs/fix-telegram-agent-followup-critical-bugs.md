# Plan: Fix Telegram Agent Follow-up Critical Bugs

## Task Description

Fix two critical bugs discovered during manual testing of the Telegram agent:

1. **Bug 1 - Bot-like Internal Reasoning Leak**: When a client requested a follow-up ("напишите мне через 5 минут"), the agent sent internal reasoning text to the user instead of a natural confirmation: "Клиент просит написать ему через 5 минут. Это запрос на follow-up через короткое время."

2. **Bug 2 - Scheduled Follow-up Never Sent**: When the scheduled follow-up time arrived, the agent decided NOT to send the follow-up, incorrectly claiming "прошло всего 1-2 минуты" when 5+ minutes had actually passed.

## Objective

1. Ensure the agent sends ONLY natural, user-facing confirmation messages (e.g., "Хорошо, напишу через 5 минут!") when scheduling follow-ups
2. Ensure scheduled follow-ups are ALWAYS executed at the correct time without incorrect time calculations or decision-making that skips them

## Problem Statement

### Bug 1: Internal Reasoning Leaking to Users

The Claude agent returns multiple content blocks when using the `schedule_followup` tool:
- **Text Block 1 (first)**: Internal analysis/reasoning (e.g., "Клиент просит написать ему через 5 минут...")
- **Tool Use Block**: The actual `schedule_followup` tool call with time/intent
- **Text Block 2 (last)**: User-facing confirmation (e.g., "Хорошо, напишу через 5 минут!")

The current code in `telegram_agent.py` at lines 531-537 correctly uses `reversed()` to get the LAST text block. However, the bug still occurred, which indicates one of two possibilities:
1. The agent sometimes returns ONLY ONE text block containing reasoning (no separate confirmation)
2. The LAST text block itself contained reasoning instead of a user-facing message

**Evidence from prospects.json (lines 37-42):**
```json
{
  "id": 683107,
  "sender": "agent",
  "text": "Клиент просит написать ему через 5 минут. Это запрос на follow-up через короткое время.",
  "timestamp": "2026-01-20T15:56:35.871293"
}
```

### Bug 2: Scheduled Follow-up Skipped Incorrectly

When `execute_scheduled_action()` (daemon.py lines 533-612) runs, it calls `generate_follow_up()` which can return `action="wait"` if the agent decides not to follow up. This is problematic for CLIENT-REQUESTED follow-ups because:

1. The client EXPLICITLY asked to be contacted at a specific time
2. The agent's system prompt (telegram_agent.py lines 490-493) says "4+ сообщение: возможно, стоит остановиться (верни action='wait')"
3. When `action="wait"` is returned (daemon.py lines 588-590), the function returns early WITHOUT:
   - Marking the action as executed
   - Reschedule attempts
   - Any user notification

Additionally, the agent may have calculated time incorrectly, believing "прошло всего 1-2 минуты" when 5+ minutes had passed.

## Solution Approach

### Fix 1: Ensure Clean User-Facing Confirmations

1. **Strengthen system prompt instructions** to make Claude NEVER output reasoning text when using the `schedule_followup` tool
2. **Add fallback detection** in `_parse_response()` to detect reasoning text patterns and use fallback confirmation instead
3. **Improve fallback confirmation generation** in daemon.py to always provide natural responses

### Fix 2: Ensure Scheduled Follow-ups Execute

1. **Distinguish scheduled vs auto follow-ups**: Client-requested follow-ups should NEVER be vetoed by `action="wait"`
2. **Update system prompt for scheduled follow-ups**: Tell the agent this is a client-requested action that MUST be sent
3. **Handle "wait" response properly**: Mark action as completed with reason instead of leaving it pending
4. **Add time validation**: Log actual elapsed time for debugging

## Relevant Files

### Core Files to Modify

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/agent/telegram_agent.py`
  - Lines 30-64: `SCHEDULE_FOLLOWUP_TOOL` definition - needs stronger instructions
  - Lines 213-245: System prompt scheduling instructions - needs explicit "no reasoning" rule
  - Lines 464-472: `intent_guidance` in `generate_follow_up()` - needs "MUST send" for scheduled actions
  - Lines 531-544: `_parse_response()` - needs reasoning detection and fallback

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/daemon.py`
  - Lines 339-393: Confirmation message handling - improve fallback robustness
  - Lines 533-612: `execute_scheduled_action()` - handle "wait" response properly

### Files for Reference (Read-Only)

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/crm/models.py`
  - `AgentAction` model definition
  - `ScheduledAction` model

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/scheduling/scheduled_action_manager.py`
  - `mark_executed()` function to properly complete actions

## Implementation Phases

### Phase 1: Fix Internal Reasoning Leak (Bug 1)

Focus on preventing reasoning text from ever reaching the user by:
1. Updating Claude's system prompt to be explicit about confirmation format
2. Adding detection for reasoning patterns in `_parse_response()`
3. Ensuring fallback confirmation is always natural

### Phase 2: Fix Scheduled Follow-up Execution (Bug 2)

Focus on ensuring client-requested follow-ups always execute by:
1. Modifying `generate_follow_up()` prompt to indicate scheduled vs auto follow-ups
2. Updating `execute_scheduled_action()` to properly handle all outcomes
3. Adding logging for debugging time calculations

### Phase 3: Testing and Validation

1. Manual test with "напишите через X минут" requests
2. Verify confirmation messages are natural
3. Verify follow-ups arrive at scheduled time

## Step by Step Tasks

### 1. Update SCHEDULE_FOLLOWUP_TOOL Description (telegram_agent.py)

- Add explicit instruction to NEVER include analysis/reasoning in the response text
- Specify the exact format expected: tool call + short confirmation
- Example text: "Your text response MUST be a SHORT, NATURAL confirmation like 'Хорошо, через 5 минут напишу!' - NOT analysis or reasoning"

**Location:** `telegram_agent.py` lines 30-45

### 2. Update System Prompt Scheduling Instructions (telegram_agent.py)

- Add explicit rule in the scheduling section (lines 213-245):
  - "ЗАПРЕЩЕНО: писать анализ или рассуждения в текстовом ответе"
  - "ТОЛЬКО короткое подтверждение клиенту"
- Add examples of what NOT to write

**Location:** `telegram_agent.py` lines 223-245

### 3. Add Reasoning Detection to _parse_response() (telegram_agent.py)

- After extracting `text_message` at line 537, add pattern detection
- If text contains reasoning patterns (starts with "Клиент", contains "Это запрос", etc.), set `text_message = None`
- This triggers the daemon's fallback confirmation generator

**Reasoning patterns to detect:**
- Starts with "Клиент " (Russian for "The client")
- Contains "Это запрос на" (Russian for "This is a request for")
- Contains "follow-up" in a reasoning context
- More than 100 characters (natural confirmations are short)

**Location:** `telegram_agent.py` lines 537-544

### 4. Update generate_follow_up() for Scheduled Actions (telegram_agent.py)

- Modify `intent_guidance` (lines 464-472) to differentiate client-requested vs auto follow-ups
- When `follow_up_intent` is provided, add: "ВАЖНО: Это follow-up был ЯВНО ЗАПРОШЕН клиентом. Ты ДОЛЖНА отправить сообщение."
- Remove the option to return `action="wait"` for scheduled actions

**Location:** `telegram_agent.py` lines 464-498

### 5. Handle "wait" Response Properly in execute_scheduled_action() (daemon.py)

- When agent returns `action="wait"` (lines 588-590), don't just return
- Import `mark_executed` from scheduled_action_manager
- Mark the action as executed with a note explaining why it wasn't sent
- Add logging with actual elapsed time since scheduling

**Location:** `daemon.py` lines 586-593

### 6. Add Time Validation Logging (daemon.py)

- Before calling `generate_follow_up()`, log:
  - Current time
  - Original scheduled time from action
  - Actual elapsed time
- This helps debug time-related issues

**Location:** `daemon.py` around line 579

### 7. Improve Fallback Confirmation Robustness (daemon.py)

- The fallback confirmation at lines 341-379 is good
- Add a safety check: if `action.message` exists but looks like reasoning, ignore it and use fallback
- Apply same pattern detection as in step 3

**Location:** `daemon.py` lines 339-379

## Testing Strategy

### Unit Tests

1. **Test reasoning detection**:
   - Input: "Клиент просит написать ему через 5 минут. Это запрос на follow-up."
   - Expected: Returns `None`, triggering fallback

2. **Test natural confirmation passthrough**:
   - Input: "Хорошо, напишу через 5 минут!"
   - Expected: Returns the message unchanged

### Integration Tests

1. **Test schedule_followup flow**:
   - Send: "напишите мне через 2 минуты"
   - Verify: Confirmation message is natural (no reasoning)
   - Verify: After 2 minutes, follow-up message is sent

2. **Test scheduled action execution**:
   - Create a scheduled action in database
   - Call `execute_scheduled_action()` directly
   - Verify: Message is sent (not skipped)

### Manual Testing

1. Start daemon
2. Send "А напишите мне через 3 минуты" from test account
3. Verify confirmation is natural: "Хорошо, напишу через 3 минуты!" or similar
4. Wait 3 minutes
5. Verify follow-up message arrives

## Acceptance Criteria

1. **No internal reasoning in user messages**: All confirmation messages must be short, natural responses in Russian without analysis text
2. **Client-requested follow-ups always execute**: When a client asks to be contacted at a specific time, the message MUST be sent at that time
3. **Proper action status tracking**: All scheduled actions must be marked as executed (or cancelled with reason) after processing
4. **Fallback works reliably**: If agent provides bad confirmation text, the daemon generates a natural fallback

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python -c "from sales_agent.agent.telegram_agent import TelegramAgent; print('Agent imports OK')"` - Verify agent module loads
- `uv run python -c "from sales_agent.daemon import TelegramDaemon; print('Daemon imports OK')"` - Verify daemon module loads
- `uv run python -m py_compile src/sales_agent/agent/telegram_agent.py src/sales_agent/daemon.py` - Verify no syntax errors
- Manual test: Send "напишите через 1 минуту" and verify:
  1. Confirmation is natural (not reasoning)
  2. Follow-up arrives in ~1 minute

## Notes

### Pattern Detection Heuristics

Russian reasoning patterns to detect and reject:
- `^Клиент ` (Starts with "The client")
- `Это запрос` (Contains "This is a request")
- `follow-up` when not in a natural sentence
- `^Понял` (Starts with "I understand" - internal acknowledgment)
- Length > 100 chars (natural confirmations are brief)

### Backward Compatibility

- The changes are backward compatible with existing scheduled actions in the database
- Existing `follow_up_intent` values will continue to work
- No database migration needed

### Related Specs

- `specs/natural-followup-behavior-improvements.md` - Previous work on natural time expressions
- `specs/scheduled-follow-ups-and-smart-reminders.md` - Original scheduling implementation
