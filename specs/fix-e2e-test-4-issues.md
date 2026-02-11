# Fix 4 E2E Test Issues (2026-02-10 Test Run #2)

## Objective

Fix four issues found during the latest E2E automated conversation test (8/9 passed).
Test results: `.claude/skills/testing/scripts/e2e_test_results.json`.

## Issue 1: Auto-booking without explicit client confirmation (CRITICAL)

**Problem:** When client's requested time (10:00 Warsaw) was unavailable, agent offered 3 alternative slots (08:30, 09:00, 10:30). Client replied "Да, записывайте!" and the system auto-booked 08:30 (first slot) WITHOUT client choosing a specific one.

**Root Causes:**
1. **System prompt (agent_system_prompt.md:158-168):** Auto-booking rule says "Бронируй ПЕРВЫЙ предложенный слот" when client confirms after 2-3 slots. Wrong when alternatives were offered because requested time was busy.
2. **Daemon (daemon.py:541-546):** Auto-corrects invalid slot_id to `offered[0]` silently.

**Fix:**
1. `agent_system_prompt.md`: Change auto-booking rule to distinguish between confirmed-available slot (auto-book OK) vs alternatives (must clarify which one)
2. `daemon.py`: When auto-correcting, send alternatives back instead of silently booking first

## Issue 2: Timezone stored as Europe/Kaliningrad instead of Europe/Warsaw

**Problem:** Client said "я сейчас в Варшаве" but system stored Europe/Kaliningrad.

**Root Cause:** In daemon.py check_availability handler (lines 399-443), heuristic `estimate_timezone()` runs and stores its guess BEFORE agent-provided `client_timezone` override. The heuristic picks Kaliningrad (UTC+2) from message patterns, persists it, then agent's "Europe/Warsaw" overrides the runtime variable but NOT the stored value.

**Fix:** Move agent-provided timezone check BEFORE heuristic estimation in both `check_availability` and `schedule` handlers. If agent provides timezone, store with confidence=1.0 and skip heuristics.

**Files:** `src/telegram_sales_bot/core/daemon.py`

## Issue 3: MessageBuffer duplicate firing on multi-message burst

**Problem:** Agent sent TWO responses to a 4-message burst. First correct, second near-duplicate 4s later.

**Root Cause:** Race condition in `message_buffer.py`. When `add_message()` calls `cancel()` on existing timer, the timer task may have already woken from `asyncio.sleep()` and started `_flush_buffer()`. Cancel doesn't affect a task already past its sleep. Both old timer's flush and new timer's flush execute.

**Fix:** Add generation counter. Each `add_message` increments generation. Timer task checks if its generation matches current before flushing.

**Files:** `src/telegram_sales_bot/temporal/message_buffer.py`

## Issue 4: Phase 1 race condition in test script

**Problem:** Test script takes ~150s to connect via Telethon, Docker daemon sends outreach in ~30s, message is missed.

**Root Cause:** Test script structure: connect to Telegram THEN wait for outreach. But Docker is already running.

**Fix:** Add a "ready" signal mechanism. Test script outputs `E2E_READY` marker after Telethon connects. The calling workflow starts Docker containers only after seeing this marker. Also restructure `main()` to clearly separate connection from test phases.

**Files:** `.claude/skills/testing/scripts/run_e2e_auto_test.py`

## Implementation Batches

**Batch 1 (all independent, parallel):**
- `agent_system_prompt.md` - Issue 1 prompt fix
- `message_buffer.py` - Issue 3 duplicate fix
- `run_e2e_auto_test.py` - Issue 4 test script fix

**Batch 2 (after Batch 1):**
- `daemon.py` - Issues 1 + 2 (auto-booking safety + timezone priority)

## Acceptance Criteria

1. When client says generic "да" after MULTIPLE alternatives → agent asks which slot specifically
2. When client says generic "да" after ONE confirmed slot → auto-book that slot
3. Client-stated city overrides heuristic timezone detection
4. Multi-message burst produces exactly ONE batched response
5. Test script connects to Telegram before Docker starts
