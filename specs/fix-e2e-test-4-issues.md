# Fix 4 E2E Test Issues (2026-02-10 Test Run)

## Objective

Fix four issues found during E2E automated conversation test. Test results: `.claude/skills/testing/scripts/e2e_test_results.json`.

## Issue 1: Phase 1 Race Condition (Test Infrastructure)

**Root Cause:** `run_e2e_auto_test.py` line 735 calls `delete_chat_history(player)` AFTER Docker daemon starts. The daemon sends initial outreach immediately, then the test deletes it, then Phase 1 waits 150s for a message that never comes.

**Fix:** Remove `delete_chat_history()` call and the sleep at lines 735-736. The calling workflow already handles cleanup before Docker starts.

**File:** `.claude/skills/testing/scripts/run_e2e_auto_test.py`

## Issue 2: Agent Doesn't Auto-Book First Slot on Confirmation

**Root Cause:** System prompt has no rule for when client says "да/записывайте" after seeing 2-3 slots. LLM re-asks instead of booking.

**Fix:** Add explicit rule to system prompt: when client gives generic confirmation after 2-3 slots shown, auto-book the FIRST slot.

**File:** `.claude/skills/telegram/config/agent_system_prompt.md` (add after line 156)

## Issue 3: Email Not Persisted in prospects.json

**Root Cause:** Email is only persisted in the `schedule` action handler (daemon.py line 578). The `check_availability` handler doesn't persist email, and the system prompt doesn't instruct the agent to include email in `check_availability` scheduling_data.

**Fix:**
1. Update system prompt line 189 to include `email` in `check_availability` scheduling_data
2. Add email persistence in daemon.py's `check_availability` handler (around line 442)

**Files:** `agent_system_prompt.md`, `daemon.py`

## Issue 5: Calendar Event at Wrong Time

**Root Cause:** LLM hallucinates wrong Bali-time slot_id when converting from client timezone. The daemon trusts the slot_id blindly. Example: agent offered 08:00 Warsaw (=15:00 Bali) but LLM produced slot_id `20260211_1800` (=18:00 Bali = 11:00 Warsaw).

**Fix:** Track offered slot IDs and validate before booking:
1. Modify `confirm_time_slot()` and `get_available_times()` to return `tuple[str, list[str]]` (text + slot IDs)
2. Track offered slots in daemon per prospect (`self._offered_slots`)
3. Validate slot_id in `schedule` handler, auto-correct to first offered if mismatch

**Files:** `scheduling/tool.py`, `daemon.py`

## Implementation Batches

**Batch 1 (independent):**
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Issue 1
- `.claude/skills/telegram/config/agent_system_prompt.md` - Issues 2, 3

**Batch 2 (sequential - tool.py must change before daemon.py):**
- `src/telegram_sales_bot/scheduling/tool.py` - Issue 5 (return offered IDs)
- `src/telegram_sales_bot/core/daemon.py` - Issues 3, 5 (email persist + slot validation)

## Acceptance Criteria

1. Phase 1: E2E test receives initial outreach without race condition
2. Phase 8: Agent auto-books first slot on generic confirmation
3. Email persisted in prospects.json after check_availability
4. Calendar events only at times actually offered to client
