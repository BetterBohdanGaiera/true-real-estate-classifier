# E2E Google Calendar Integration Testing - Implementation Plan

## Executive Summary

This plan adds end-to-end testing for Google Calendar integration to verify:
1. Real calendar event creation via Google Calendar API
2. Time slot proposal and selection flows
3. Timezone conversion accuracy between client and Bali (UTC+8)
4. Zoom meeting link integration in calendar events
5. Conflict detection and slot availability checking

The implementation extends the existing `StressTestRunner` and `ConversationSimulator` classes to include calendar operation triggers and validations, adding new metrics and scenarios specifically for scheduling workflows.

---

## Files to Create

| File | Purpose |
|------|---------|
| `.claude/skills/testing/scripts/calendar_test_client.py` | Test client for Google Calendar API with [TEST] event handling |
| `.claude/skills/testing/scripts/calendar_test_scenarios.py` | Calendar-specific test scenarios with timezone variations |
| `.claude/skills/testing/scripts/calendar_validation.py` | Post-test validation functions for calendar events |
| `.claude/skills/testing/scripts/run_calendar_tests.py` | CLI runner for calendar integration tests |
| `.claude/skills/database/migrations/007_calendar_test_results.sql` | Migration for calendar-specific test metrics |

## Files to Modify

| File | Change |
|------|--------|
| `.claude/skills/testing/scripts/conversation_simulator.py` | Add CalendarTestMetrics model |
| `.claude/skills/testing/scripts/stress_scenarios.py` | Add ConversationOutcome enum if missing |

---

## Technical Architecture

```
                    +-----------------------+
                    |   CLI Runner          |
                    | run_calendar_tests.py |
                    +-----------+-----------+
                                |
              +-----------------+------------------+
              |                                    |
   +----------v----------+           +-------------v-------------+
   | StressTestRunner    |           | ConversationSimulator     |
   | (E2E with Telegram) |           | (Mock mode)               |
   +----------+----------+           +-------------+-------------+
              |                                    |
              +-----------------+------------------+
                                |
                    +-----------v-----------+
                    | CalendarTestClient    |
                    | - create_test_event() |
                    | - cleanup_test_events()|
                    | - validate_event()    |
                    +-----------+-----------+
                                |
              +-----------------+------------------+
              |                                    |
   +----------v----------+           +-------------v-------------+
   | Google Calendar API |           | CalendarValidation       |
   | (via CalendarClient)|           | - verify_timezone()      |
   +---------------------+           | - verify_attendees()     |
                                     | - verify_zoom_link()     |
                                     +---------------------------+
```

---

## Implementation Batches

### Batch 1: Foundation (No Dependencies - Can Build in Parallel)

1. **calendar_test_client.py** - Core test client wrapping Google Calendar API
2. **calendar_validation.py** - Validation logic for calendar events
3. **007_calendar_test_results.sql** - Database migration for metrics

### Batch 2: Scenarios (Depends on Batch 1)

4. **calendar_test_scenarios.py** - Test scenarios with timezone variations

### Batch 3: Integration (Depends on Batch 1 & 2)

5. **run_calendar_tests.py** - CLI runner integrating all components
6. **conversation_simulator.py** - Add CalendarTestMetrics model

---

## Test Scenarios

### 1. Zoom Scheduler Happy Path
- Client provides email immediately
- Selects first proposed slot
- Meeting created successfully
- Timezone: Moscow (UTC+3)

### 2. Timezone Mismatch - Kyiv
- Client in Kyiv (UTC+2/+3 with DST)
- Verify time displayed in client's timezone
- Event created in Bali time (UTC+8)

### 3. Timezone Mismatch - EST
- Client in New York (UTC-5)
- 13-hour difference from Bali
- Tests day-change scenarios

### 4. Slot Conflict
- Pre-create blocking event
- Client selects conflicting slot
- Agent proposes alternatives

### 5. Email Collection Before Slots
- Verify agent asks for email BEFORE showing slots
- Client initially resistant
- Eventually provides email

### 6. DST Edge Case - Ukraine
- Tests handling of daylight saving time transitions
- Verifies correct conversion during DST change period

---

## Acceptance Criteria

| Component | Criteria |
|-----------|----------|
| CalendarTestClient | Creates events with [TEST] prefix, tracks and cleans up events |
| CalendarValidator | Validates timezone, attendees, Zoom link, time accuracy |
| Calendar Scenarios | 6 scenarios covering happy path, timezones, conflicts |
| run_calendar_tests.py | CLI runs scenarios, displays results, supports cleanup |
| Database Migration | Adds calendar metrics columns to test_results |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Google Calendar API rate limits | Medium | High | Add exponential backoff, limit concurrent tests |
| Timezone conversion edge cases | Medium | Medium | Test DST transitions explicitly, use pytz |
| Orphaned [TEST] events | High | Low | Always run cleanup, implement cleanup on test failure |
| Zoom API availability | Low | Medium | Mock Zoom link if API unavailable |
| Test isolation failures | Medium | Medium | Unique email per test run, cleanup between scenarios |

---

## Dependencies

| Dependency | Required For | Status |
|------------|--------------|--------|
| google-api-python-client | Calendar API calls | Already installed |
| pytz | Timezone conversions | Already installed |
| asyncpg | Database operations | Already installed |
| rich | CLI output | Already installed |
