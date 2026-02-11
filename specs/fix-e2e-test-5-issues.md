# Fix E2E Test 5 Issues: CLI Timeouts & Cascading Failures

## Context

E2E test run on 2026-02-11 scored **1/9 phases passed**. The dominant failure mode is **CLI agent timeouts** (5 out of ~11 batches escalated with `CLI execution failed: Task timed out after 60 seconds`). This caused cascading phase desynchronization where the agent's responses arrived too late for the test to detect them.

The agent's **reasoning was correct in every case** (visible in Docker logs) - the problem is purely infrastructure: the 60s CLI timeout is too short for Opus.

## Test Results Reference

- Results JSON: `.claude/skills/testing/scripts/e2e_test_results.json`

## Issues to Fix (Priority Order)

### Issue 1: CLI Agent Timeout Too Short (60s)

**Location**: `src/telegram_sales_bot/core/cli_agent.py` (or wherever the CLI subprocess timeout is configured)

**Problem**: The Claude CLI agent has a 60-second timeout. Opus regularly needs more than 60s for complex multi-context responses (BANT tracking + knowledge base + objection handling + conversation history).

**Fix**: Increase the CLI execution timeout to **105 seconds**. The agent uses Opus and complex prompts - 60s is not enough.

**Evidence from logs**:
```
Agent decision: escalate - CLI execution failed: Task timed out after 60 seconds
```
This happened 5 times during the test, on Phases 1, 4, 5, 6b, and 7.

### Issue 2: Add Retry on CLI Timeout Before Escalating

**Location**: `src/telegram_sales_bot/core/cli_agent.py` or `src/telegram_sales_bot/core/daemon.py` (wherever escalation logic lives)

**Problem**: When CLI times out, the agent immediately escalates (gives up). There is no retry attempt.

**Fix**: On CLI timeout, retry **once** with the same prompt before escalating. The retry should use the same full timeout (105s). Only escalate if BOTH attempts fail. Log the retry attempt clearly.

### Issue 3: Duplicate Availability Message

**Location**: `src/telegram_sales_bot/scheduling/tool.py` or the daemon message-sending logic

**Problem**: The check_availability tool was called twice in sequence, sending identical availability slots to the client twice (messages #20 and #21 in the conversation are identical).

**Evidence from logs**:
```
-> Sent availability to Buddah
-> Sent availability to Buddah
Agent decision: check_availability - ... (second call)
```

**Fix**: Add idempotency protection. Track the last `check_availability` result per prospect (e.g., a hash of the slots + timestamp). If the same availability was sent within the last 5 minutes, skip the duplicate send and have the agent respond with a conversational message instead ("Выше отправил слоты - какое время подходит?").

### Issue 4: Wait Behavior - Test Script Acknowledgment Handling

**Location**: `.claude/skills/testing/scripts/run_e2e_auto_test.py` (Phase 2 logic)

**Problem**: When the client says "напишите через 2 минуты", the agent correctly:
1. Sends an immediate acknowledgment ("Конечно, напишу через 2 минуты!")
2. Schedules a follow-up via the scheduler daemon for 2 minutes later

But the test script fails because the acknowledgment arrives during the 100s silence window instead of the initial 30s wait. The test sees the acknowledgment as "Agent broke silence after 11s".

**Fix**: Update Phase 2 test logic:
- After sending the "wait 2 minutes" message, the first `wait_for_response(30s)` should consume the acknowledgment
- If the acknowledgment arrives during the silence window instead, recognize messages containing "через 2 минут" / "напишу через" / "конечно" as acknowledgments (not follow-ups) and continue measuring silence
- The 100s silence window should measure silence AFTER the acknowledgment is consumed
- Only count a NEW substantive message (not an acknowledgment) as breaking silence

### Issue 5: Phase 1 Initial Outreach Timing

**Location**: `src/telegram_sales_bot/core/daemon.py` and/or `src/telegram_sales_bot/core/cli_agent.py`

**Problem**: The initial outreach message generation took >150s. Agent logs show "Generating initial message for Buddah..." but the CLI timed out at 60s, and the message was either not sent or sent too late for the 150s test window.

**Fix**: This is mostly solved by Issue 1 (increasing timeout to 180s). Additionally, consider whether the initial outreach can use a simpler/shorter prompt since it only needs to generate a 1-2 sentence greeting with a light opening question.

## Files to Investigate & Modify

1. `src/telegram_sales_bot/core/cli_agent.py` - CLI timeout configuration, retry logic
2. `src/telegram_sales_bot/core/daemon.py` - Escalation handling, retry before escalate
3. `src/telegram_sales_bot/scheduling/tool.py` - Duplicate availability prevention
4. `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Phase 2 acknowledgment handling

## Constraints

- **ALWAYS use Opus model** - never switch to a faster/smaller model
- **Never auto-book a time slot** - the agent must keep communicating until the client explicitly approves ONE specific time. Do NOT pick a slot on the client's behalf
- Do not change the agent system prompt unless absolutely necessary
- Do not modify test pass/fail criteria (except Phase 2 acknowledgment handling which is a legitimate test bug)

## Validation

After fixes, re-run the E2E test:
```bash
/telegram_conversation_automatic_test
```

Target: **7+/9 phases passed** (Phase 2 timing may still be tight depending on scheduler daemon polling interval)
