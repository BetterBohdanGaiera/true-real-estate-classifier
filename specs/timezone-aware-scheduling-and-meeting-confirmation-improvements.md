# Plan: Timezone-Aware Scheduling & Meeting Confirmation Improvements

## Task Description
Improve the Telegram sales agent's scheduling communication to handle timezone awareness properly when clients ask "По какому времени?" (which timezone?), present available slots in a more natural conversational manner, correctly validate and confirm email addresses, and ensure Zoom meetings are actually created and invitations sent.

Based on the user feedback:
- When prospects ask "По какому времени?", they're asking about timezone. The agent needs to clarify its own timezone, ask for the client's timezone, and schedule calls based on mutual understanding.
- Available meeting slots should be communicated better - the agent should know its own availability but present options naturally based on what it knows (not the specific slots the user mentioned in their message).
- Email validation needs improvement - the example shows "gmil.com" was accepted initially when it should have been "gmail.com".
- The meeting was confirmed but not actually created in the system - integration is broken.

## Objective
Create a timezone-aware, natural scheduling experience where:
1. The agent proactively clarifies timezones when scheduling (its own: Bali UTC+8, and asks for client's)
2. Available slots are presented based on actual calendar availability, converted to client timezone
3. Email validation catches common typos (gmil.com → gmail.com suggestion)
4. Meetings are actually created in Zoom with calendar invitations sent
5. Confirmation messages accurately reflect what was scheduled

## Problem Statement
The current scheduling system has four critical issues:

1. **Timezone Ambiguity**: When prospects ask about time, the agent doesn't clarify timezones upfront, leading to confusion about which timezone the proposed times are in. The agent operates in Bali time (UTC+8) but doesn't make this explicit or convert times to the client's timezone.

2. **Unnatural Slot Presentation**: The agent is showing slots that don't match its actual availability. Example: User says "могу послезавтра с 10 по 12 и с 15 по 18" (I can day after tomorrow from 10-12 and 15-18), but agent responds with "можем сегодня вечером в 20:00 или завтра утром в 10:00" (we can today at 20:00 or tomorrow at 10:00) - completely different times.

3. **Email Validation Gap**: Basic email validation (`"@" in email and "." in email`) allows typos like "gmil.com" to pass through. The system should detect common domain typos and prompt clarification.

4. **Broken Meeting Creation Promise**: The confirmation message states "Встреча назначена" (meeting scheduled) and "Ссылка на Zoom будет отправлена" (Zoom link will be sent), but:
   - No actual Zoom meeting is created (mock mode)
   - No email is ever sent
   - Only Telegram confirmation happens
   - Prospect is left waiting for an email that never arrives

## Solution Approach
Implement a four-phase enhancement:

**Phase 1 - Timezone Intelligence**: Add timezone detection and conversion logic to the agent's scheduling workflow, updating system prompts to always clarify timezones upfront.

**Phase 2 - Natural Slot Selection**: Improve the agent's understanding of its own availability and teach it to propose times based on what's actually free, respecting both agent and client availability windows.

**Phase 3 - Smart Email Validation**: Implement a typo-detection layer that catches common email domain mistakes and prompts clarification before booking.

**Phase 4 - Real Meeting Integration**: Connect the booking flow to actual Zoom meeting creation and implement scheduled email delivery.

## Relevant Files

### Core Scheduling Logic
- `.claude/skills/telegram/scripts/telegram_agent.py` (lines 212-269) - System prompt defines scheduling flow and timezone handling instructions
- `.claude/skills/telegram/scripts/scheduling_tool.py` (lines 100-222) - Slot presentation and booking confirmation logic
- `.claude/skills/telegram/scripts/daemon.py` (lines 426-501) - Booking orchestration and state transitions

### Timezone & Calendar
- `.claude/skills/telegram/scripts/timezone_detector.py` - Existing timezone estimation logic from message patterns
- `.claude/skills/telegram/scripts/models.py` (lines 98-124) - Prospect model with timezone fields
- `.claude/skills/register-sales/scripts/calendar_connector.py` (lines 302-339) - Google Calendar busy slot detection
- `.claude/skills/scheduling/scripts/calendar_aware_scheduler.py` (lines 98-246) - Availability filtering with calendar integration

### Communication Guidelines
- `.claude/skills/tone-of-voice/SKILL.md` - Communication style principles
- `.claude/skills/how-to-communicate/SKILL.md` - Methodology for scheduling conversations
- `.claude/skills/tone-of-voice/references/фразы.md` (lines 64-90) - Scheduling phrase templates

### Meeting Creation
- `.claude/skills/zoom/scripts/zoom_service.py` (lines 122-250) - Zoom meeting creation (currently not integrated)
- `.claude/skills/google-calendar/scripts/calendar_client.py` (lines 195-253) - Google Calendar event creation with attendees

### Data Models
- `.claude/skills/telegram/scripts/models.py` (lines 160-183) - SalesSlot and SchedulingResult models
- `.claude/skills/telegram/config/prospects.json` - Prospect storage with timezone fields
- `.claude/skills/telegram/config/sales_slots.json` - Sales slot configuration

## New Files

### Email Validation Enhancement
- `.claude/skills/telegram/scripts/email_validator.py` - Smart email validation with typo detection

### Email Delivery Service
- `.claude/skills/email/scripts/email_service.py` - Email sending service for meeting invitations
- `.claude/skills/email/config/email_config.json` - Email provider configuration

## Implementation Phases

### Phase 1: Timezone Intelligence Foundation
Establish consistent timezone handling across all scheduling interactions:
- Update system prompts to clarify agent timezone upfront
- Integrate timezone_detector into scheduling flow
- Store and use client timezone for time conversions
- Display all times in both Bali time and client's local time

### Phase 2: Natural Slot Communication
Improve how the agent presents availability:
- Fix slot filtering logic to use timezone-aware datetime comparisons
- Update agent prompts to propose times from actual availability
- Teach agent to understand client's availability windows and find overlap
- Format slot presentation to feel conversational, not robotic

### Phase 3: Smart Email Validation & Real Meeting Creation
Complete the booking experience:
- Add typo detection for common email domain mistakes
- Integrate real Zoom meeting creation into booking flow
- Connect Google Calendar event creation with attendee invitations
- Implement scheduled email delivery for meeting reminders

### Phase 4: Integration & Polish
Ensure all components work together seamlessly:
- Update confirmation messages to reflect actual system behavior
- Add comprehensive error handling for timezone conversion edge cases
- Test cross-timezone scheduling scenarios
- Validate email delivery and meeting creation end-to-end

## Step by Step Tasks

### 1. Update System Prompt for Timezone Clarity
- Modify `telegram_agent.py` lines 214-269 to include timezone clarification instructions
- Add requirement: "ВСЕГДА уточняй часовой пояс: 'Я в Бали (UTC+8). В каком часовом поясе вы?'"
- Update example flow to show timezone exchange before slot display
- Add instruction to show times in BOTH timezones: "14:00 вашего времени (10:00 Бали)"

### 2. Create Smart Email Validator
- Create new file `.claude/skills/telegram/scripts/email_validator.py`
- Implement `validate_email_with_suggestions(email: str) -> tuple[bool, str, Optional[str]]`
- Add common domain typo mapping: gmil→gmail, yaho→yahoo, hotmial→hotmail, outloo→outlook, etc.
- Return tuple: (is_valid, error_message, suggested_correction)
- Include unit tests for common typo patterns

### 3. Integrate Email Validation into Booking Flow
- Update `scheduling_tool.py` book_meeting() method (lines 173-188)
- Replace basic validation with email_validator.validate_email_with_suggestions()
- When typo detected, return SchedulingResult with suggestion: "Вы имели в виду gmail.com? Подтвердите email."
- Only proceed with booking after confirmation

### 4. Add Timezone Awareness to Scheduling Tool
- Update `scheduling_tool.py` get_available_times() method (lines 100-150)
- Add parameter `client_timezone: Optional[str] = None`
- When client_timezone provided, convert displayed times to client's local time
- Format slots with dual-timezone display: "Понедельник 9 февраля, 14:00 (10:00 Бали UTC+8)"
- Update slot filtering logic (lines 117-123) to use timezone-aware datetime instead of naive `datetime.now()`

### 5. Fix Slot Filtering to Use Bali Timezone
- In `scheduling_tool.py` lines 117-123, replace `datetime.now()` with timezone-aware Bali time
- Add constant `BALI_TZ = ZoneInfo("Asia/Makassar")` at module top
- Use `datetime.now(BALI_TZ)` for "now" comparison
- Update comparison logic: `datetime.combine(slot.date, slot.start_time, tzinfo=BALI_TZ) > datetime.now(BALI_TZ)`
- Ensure past slots are filtered correctly regardless of server timezone

### 6. Update Agent Prompt for Slot Selection Logic
- Modify `telegram_agent.py` lines 220-236 to improve slot presentation instructions
- Add: "Когда клиент говорит свои доступные часы, найди ПЕРЕСЕЧЕНИЕ с твоими свободными слотами"
- Add: "НЕ предлагай случайные времена - ВСЕГДА используй action=check_availability сначала"
- Add: "Если клиент сказал 'с 10 по 12', проверь слоты 10:00, 10:30, 11:00, 11:30 в его таймзоне"
- Remove misleading example that shows arbitrary times

### 7. Integrate Timezone Detector into Scheduling Flow
- Update `daemon.py` scheduling action handler (lines 426-501)
- Before calling scheduling_tool.get_available_times(), check if prospect.estimated_timezone exists
- If not, estimate timezone using TimezoneDetector from conversation history
- Pass client_timezone to get_available_times() for dual-timezone display
- Store detected timezone in prospect record for future interactions

### 8. Create Real Zoom Meeting Integration
- Update `scheduling_tool.py` book_meeting() method (lines 190-222)
- Add ZoomBookingService initialization (from zoom/scripts/zoom_service.py)
- After slot booking succeeds, call zoom_service.create_meeting() with meeting details
- Store returned zoom_url in SchedulingResult
- Update confirmation message to include actual Zoom link when available

### 9. Implement Google Calendar Event Creation
- In `scheduling_tool.py` after Zoom meeting creation
- Initialize CalendarClient from google-calendar skill
- Call create_event() with:
  - summary: "Консультация: {prospect.name}"
  - start/end: Meeting time in ISO 8601 format
  - attendees: [client_email]
  - location: zoom_url
  - timezone: "Asia/Makassar"
- Google Calendar will automatically send email invitation to attendee
- Handle calendar creation failure gracefully (meeting still booked, but no calendar invite)

### 10. Update Confirmation Message Logic
- Modify `scheduling_tool.py` lines 211-215 to show different messages based on what was actually created
- If zoom_url exists: "Ссылка на Zoom: {zoom_url}\n\nПриглашение отправлено на {email}."
- If zoom_url is None but email sent: "Ссылка на Zoom будет отправлена на {email}."
- If neither: "Наш эксперт свяжется с вами в Telegram."
- Always be truthful about what the system actually did

### 11. Add Timezone Conversion Utilities
- Create helper methods in `scheduling_tool.py`:
  - `_convert_to_client_timezone(dt: datetime, client_tz: str) -> datetime`
  - `_format_dual_timezone(dt: datetime, client_tz: str) -> str` returns "14:00 вашего времени (10:00 Бали)"
- Use these methods in slot formatting logic
- Handle timezone conversion errors gracefully (fallback to Bali time only)

### 12. Update Prospect Model Timezone Usage
- Ensure `models.py` Prospect model (lines 114-117) timezone fields are utilized
- When prospect.estimated_timezone exists, pass it to scheduling functions
- Update ProspectManager to save timezone when detected
- Add timezone_confidence threshold (only use if confidence > 0.7)

### 13. Add Comprehensive Error Handling
- Wrap Zoom meeting creation in try-except with specific error messages
- Wrap Google Calendar event creation in try-except
- Wrap timezone conversion in try-except with fallback
- Log all errors using rich.console for debugging
- Ensure booking succeeds even if Zoom/Calendar integrations fail (graceful degradation)

### 14. Update Configuration Files
- Add `zoom_enabled: true` to `.claude/skills/telegram/config/agent_config.json`
- Add `calendar_integration_enabled: true` to agent config
- Ensure ZoomBookingService credentials are configured (check ~/.zoom_credentials/)
- Verify Google Calendar OAuth tokens are available for calendar creation

### 15. Test Timezone Conversion Edge Cases
- Test with prospect in Moscow timezone (UTC+3) - 5 hour difference from Bali
- Test with prospect in New York (UTC-5) - 13 hour difference, crosses day boundary
- Test with prospect in same timezone as Bali (UTC+8) - no conversion needed
- Test when client timezone unknown - should still work with Bali time only
- Test DST transitions (though Bali doesn't observe DST, client might)

### 16. Validation Testing
- Create manual test scenario:
  1. Prospect asks "когда созвонимся?" (when shall we call?)
  2. Agent asks timezone: "Я в Бали (UTC+8). В каком вы часовом поясе?"
  3. Prospect responds "Я в Варшаве" (I'm in Warsaw, UTC+1)
  4. Agent shows slots converted to Warsaw time
  5. Prospect chooses time
  6. Agent validates email (catching typos)
  7. Zoom meeting created
  8. Google Calendar invitation sent
  9. Confirmation message with Zoom link delivered
- Verify all steps complete successfully
- Confirm email arrives in inbox with correct meeting details

## Testing Strategy

### Unit Tests
- `test_email_validator.py`: Test all common domain typos and edge cases
- `test_timezone_conversion.py`: Test conversion between various timezones
- `test_slot_filtering.py`: Test that past slots are correctly filtered using Bali timezone
- `test_dual_timezone_formatting.py`: Test time display in multiple timezones

### Integration Tests
- `test_scheduling_flow_with_timezone.py`: End-to-end test of timezone-aware scheduling
- `test_zoom_meeting_creation.py`: Test Zoom API integration (requires credentials)
- `test_calendar_event_creation.py`: Test Google Calendar integration (requires OAuth)
- `test_email_validation_in_booking.py`: Test typo detection blocks booking until confirmed

### Manual Testing Scenarios
1. **Typo Detection**: Try booking with "gmil.com", "yaho.com", verify suggestions appear
2. **Timezone Clarification**: Start scheduling conversation, verify agent asks about timezone
3. **Cross-Timezone Booking**: Book from Moscow timezone, verify times displayed correctly
4. **Meeting Creation**: Complete booking, verify Zoom meeting exists and email received
5. **Graceful Degradation**: Disable Zoom credentials, verify booking still works with fallback message

## Acceptance Criteria

- [ ] When scheduling is initiated, agent ALWAYS clarifies "Я в Бали (UTC+8). В каком вы часовом поясе?"
- [ ] Client timezone is detected and stored in prospect.estimated_timezone field
- [ ] Available slots are displayed in BOTH Bali time and client's local time
- [ ] Email validation catches common domain typos (gmil→gmail) and prompts confirmation
- [ ] Booking with typo email is blocked until user confirms or corrects
- [ ] When booking succeeds, a real Zoom meeting is created via Zoom API
- [ ] Google Calendar event is created with client email as attendee
- [ ] Client receives automatic email invitation from Google Calendar with Zoom link
- [ ] Confirmation message shows actual Zoom URL (not promise of future email)
- [ ] If Zoom/Calendar integration fails, booking still succeeds with appropriate fallback message
- [ ] Slot filtering uses timezone-aware datetime comparison (fixes past slot display bug)
- [ ] System works correctly for clients in different timezones (Moscow UTC+3, NYC UTC-5, Bangkok UTC+7)
- [ ] Agent proposes times based on actual availability, not random suggestions

## Validation Commands

Execute these commands to validate the implementation:

- `wc -l .claude/skills/telegram/scripts/email_validator.py` - Verify email validator file created
- `grep -n "timezone" .claude/skills/telegram/scripts/telegram_agent.py` - Check timezone instructions added to system prompt
- `grep -n "BALI_TZ" .claude/skills/telegram/scripts/scheduling_tool.py` - Verify timezone-aware filtering implemented
- `grep -n "zoom_service" .claude/skills/telegram/scripts/scheduling_tool.py` - Confirm Zoom integration added
- `uv run python -c "from .claude.skills.telegram.scripts.email_validator import validate_email_with_suggestions; print(validate_email_with_suggestions('test@gmil.com'))"` - Test email validation
- `PYTHONPATH=.claude/skills uv run python -m pytest tests/test_email_validator.py -v` - Run email validator tests
- `PYTHONPATH=.claude/skills uv run python -m pytest tests/test_timezone_conversion.py -v` - Run timezone conversion tests
- `uv run python .claude/skills/telegram/scripts/manual_test.py` - Run manual test with timezone scenario

## Notes

### Timezone Implementation Details
- Use `zoneinfo.ZoneInfo` (Python 3.9+) for timezone handling instead of deprecated pytz where possible
- Bali timezone: `Asia/Makassar` (UTC+8, no DST)
- Store all datetimes in UTC internally, convert to local timezone only for display
- Prospect.estimated_timezone uses IANA timezone names (e.g., "Europe/Moscow", "America/New_York")

### Email Validator Domain Mapping
Common typos to catch:
- gmil.com → gmail.com
- gmai.com → gmail.com
- gmal.com → gmail.com
- yaho.com → yahoo.com
- yahooo.com → yahoo.com
- hotmial.com → hotmail.com
- outloo.com → outlook.com
- outlok.com → outlook.com

### Zoom Integration Requirements
- Credentials must be configured in `~/.zoom_credentials/credentials.json`
- Use Server-to-Server OAuth (account-level access)
- Meeting settings: waiting_room=True, host_video=True, duration=30min
- Topic format: "Консультация: {prospect.name}"

### Google Calendar Integration Requirements
- OAuth tokens in `~/.google_calendar_credentials/` per sales rep
- Use CalendarClient from google-calendar skill
- Set sendUpdates="all" to trigger email invitations
- Include Zoom URL in event description and location fields

### Graceful Degradation Strategy
If integrations fail, system should still function:
- No Zoom credentials → Mock mode, promise future email (current behavior)
- No Calendar access → Zoom meeting created but no calendar invite
- No email validator → Fall back to basic validation
- Unknown client timezone → Display in Bali time only with "(UTC+8)" suffix

### Dependencies to Install
```bash
uv add email-validator  # For robust email validation
# zoneinfo is built into Python 3.9+, no install needed
```

### Migration Notes
- Existing prospects in prospects.json may not have timezone fields populated
- On first scheduling interaction with existing prospect, system should detect and store timezone
- Existing booked slots in sales_slots.json remain in naive time (assume Bali time)
- New bookings after this change will store timezone-aware information

### Future Enhancements (Out of Scope)
- Automated pre-meeting reminder emails 24 hours before (requires scheduled job system)
- Client timezone preference stored explicitly (vs. estimated from messages)
- Multi-language email templates (currently Russian only)
- SMS notifications as backup to email
- Rescheduling/cancellation flow with calendar updates
