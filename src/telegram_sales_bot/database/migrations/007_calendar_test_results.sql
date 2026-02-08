-- Migration: 007_calendar_test_results
-- Description: Add calendar-specific metrics to test results for E2E calendar integration testing
-- Created: 2026-02-03
--
-- This migration adds columns to track calendar integration test outcomes:
-- - Whether a calendar event was created
-- - Timezone conversion accuracy
-- - Zoom link embedding verification
-- - Attendee management
--
-- These metrics enable comprehensive validation of the scheduling flow
-- in the sales conversation agent.
--
-- Usage: psql $DATABASE_URL -f migrations/007_calendar_test_results.sql

-- =============================================================================
-- ADD CALENDAR METRICS COLUMNS TO TEST_RESULTS
-- =============================================================================

-- Calendar event creation status
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS calendar_created BOOLEAN DEFAULT FALSE;

-- Timezone validation
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS correct_timezone BOOLEAN DEFAULT FALSE;

-- Time slot matching
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS slot_match BOOLEAN DEFAULT FALSE;

-- Zoom link embedding
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS zoom_link_embedded BOOLEAN DEFAULT FALSE;

-- Attendee addition
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS attendee_added BOOLEAN DEFAULT FALSE;

-- Client timezone for conversion testing (e.g., "Europe/Kyiv", "America/New_York")
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS client_timezone VARCHAR(50);

-- Google Calendar event ID for reference and cleanup
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS calendar_event_id VARCHAR(255);

-- Conflict detection result (NULL if not tested)
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS conflict_detected BOOLEAN;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Partial index for filtering calendar integration test results
-- Only indexes rows where calendar_created is TRUE (reduces index size)
CREATE INDEX IF NOT EXISTS idx_test_results_calendar
    ON test_results(calendar_created)
    WHERE calendar_created = TRUE;

-- Index for finding tests by client timezone
CREATE INDEX IF NOT EXISTS idx_test_results_client_timezone
    ON test_results(client_timezone)
    WHERE client_timezone IS NOT NULL;

-- =============================================================================
-- COLUMN COMMENTS
-- =============================================================================

COMMENT ON COLUMN test_results.calendar_created IS 'Whether a Google Calendar event was created during this test';
COMMENT ON COLUMN test_results.correct_timezone IS 'Whether the event timezone was correctly set to Bali (UTC+8/Asia/Makassar)';
COMMENT ON COLUMN test_results.slot_match IS 'Whether the event time matched the proposed slot shown to client';
COMMENT ON COLUMN test_results.zoom_link_embedded IS 'Whether the Zoom meeting link was embedded in the event description';
COMMENT ON COLUMN test_results.attendee_added IS 'Whether the client email was added as an event attendee';
COMMENT ON COLUMN test_results.client_timezone IS 'Client timezone used for timezone conversion testing (e.g., Europe/Kyiv)';
COMMENT ON COLUMN test_results.calendar_event_id IS 'Google Calendar event ID for reference and cleanup verification';
COMMENT ON COLUMN test_results.conflict_detected IS 'Whether a slot conflict was correctly detected (NULL if not tested)';

-- =============================================================================
-- VERIFICATION QUERY (for manual testing)
-- =============================================================================
-- Run this after migration to verify columns were added:
--
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'test_results'
--   AND column_name IN (
--     'calendar_created', 'correct_timezone', 'slot_match',
--     'zoom_link_embedded', 'attendee_added', 'client_timezone',
--     'calendar_event_id', 'conflict_detected'
--   );
